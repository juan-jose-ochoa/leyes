#!/usr/bin/env python3
"""
Extractor de párrafos usando coordenadas X del PDF.

Determina la jerarquía correcta basándose en la indentación:
- X~85:  Fracción (I., II., etc.) o párrafo de artículo
- X~114: Inciso (a), b), etc.) o párrafo de fracción
- X~142: Numeral (1., 2., etc.) o continuación de inciso

Uso:
    python scripts/leyesmx/extraer_parrafos_x.py CFF 66-A
"""

import re
import json
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("Error: pdfplumber no instalado. Ejecuta: pip install pdfplumber")
    sys.exit(1)


# Umbrales de X para cada nivel (ajustables por PDF)
X_FRACCION = 85
X_INCISO = 114
X_NUMERAL = 142
X_TOLERANCE = 10  # Tolerancia para matching

# Umbral de Y para detectar salto de párrafo
# En el CFF: gap=10 es línea continua, gap=15 es párrafo nuevo
Y_PARAGRAPH_GAP = 12  # Umbral conservador


@dataclass
class Parrafo:
    numero: int
    tipo: str  # texto, fraccion, inciso, numeral
    identificador: Optional[str]
    contenido: str
    x_pos: int
    padre_numero: Optional[int] = None
    hijos: list = field(default_factory=list)


def detectar_tipo_identificador(texto: str) -> tuple[str, Optional[str], str]:
    """
    Detecta el tipo de elemento y extrae el identificador.
    Retorna: (tipo, identificador, contenido_sin_identificador)
    """
    texto = texto.strip()

    # Fracción romana: I., II., III., IV., V., VI., VII., VIII., IX., X., etc.
    match = re.match(r'^([IVXLC]+)\.\s*(.*)$', texto)
    if match:
        return ('fraccion', match.group(1), match.group(2))

    # Inciso: a), b), c), etc.
    match = re.match(r'^([a-z])\)\s*(.*)$', texto)
    if match:
        return ('inciso', match.group(1) + ')', match.group(2))

    # Numeral: 1., 2., 3., etc.
    match = re.match(r'^(\d+)\.\s*(.*)$', texto)
    if match:
        return ('numeral', match.group(1) + '.', match.group(2))

    return ('texto', None, texto)


def determinar_nivel_x(x: int) -> int:
    """
    Determina el nivel jerárquico basado en X.
    0 = artículo, 1 = fracción, 2 = inciso, 3 = numeral
    """
    if x < X_FRACCION + X_TOLERANCE:
        return 0  # Nivel artículo
    elif x < X_INCISO + X_TOLERANCE:
        return 1  # Nivel fracción
    elif x < X_NUMERAL + X_TOLERANCE:
        return 2  # Nivel inciso
    else:
        return 3  # Nivel numeral o continuación


def extraer_lineas_pagina(page) -> list[dict]:
    """Extrae líneas de una página con coordenadas X."""
    words = page.extract_words(keep_blank_chars=True, x_tolerance=3, y_tolerance=3)

    # Agrupar por línea (mismo Y aproximado)
    lines = {}
    for w in words:
        y_key = round(w['top'] / 5) * 5
        if y_key not in lines:
            lines[y_key] = []
        lines[y_key].append(w)

    result = []
    for y_key in sorted(lines.keys()):
        line_words = sorted(lines[y_key], key=lambda w: w['x0'])
        x0 = round(line_words[0]['x0'])
        text = ' '.join(w['text'] for w in line_words).strip()

        if text and x0 >= 70:  # Ignorar headers/footers
            result.append({'x': x0, 'y': y_key, 'text': text})

    return result


def encontrar_articulo(pdf, numero_articulo: str) -> tuple[int, int]:
    """
    Encuentra la página inicial y final de un artículo.
    Retorna: (página_inicio, página_fin)
    """
    # Soporta formatos: "Artículo 2o." y "Artículo 2o.-" con espacios variables
    patron_inicio = re.compile(rf'Artículo\s+{re.escape(numero_articulo)}\.[\-\s]')
    patron_siguiente = re.compile(r'Artículo\s+\d+[o]?(?:-[A-Z])?\.[\-\s]')

    pagina_inicio = None
    pagina_fin = None

    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""

        if pagina_inicio is None and patron_inicio.search(text):
            pagina_inicio = i
        elif pagina_inicio is not None:
            # Buscar siguiente artículo
            text_sin_actual = patron_inicio.sub('', text)
            if patron_siguiente.search(text_sin_actual):
                pagina_fin = i
                break

    if pagina_inicio is not None and pagina_fin is None:
        pagina_fin = min(pagina_inicio + 5, len(pdf.pages) - 1)

    return pagina_inicio, pagina_fin


def extraer_articulo(pdf_path: str, numero_articulo: str, quiet: bool = False, pdf=None) -> list[Parrafo]:
    """
    Extrae un artículo completo con jerarquía correcta.

    Args:
        pdf_path: Ruta al archivo PDF (ignorado si se pasa pdf)
        numero_articulo: Número del artículo (ej: "66-A", "2o")
        quiet: Si True, no imprime mensajes de progreso
        pdf: Objeto pdfplumber.PDF ya abierto (opcional, para optimizar)
    """
    if pdf is None:
        with pdfplumber.open(pdf_path) as pdf_opened:
            return _extraer_articulo_interno(pdf_opened, numero_articulo, quiet)
    else:
        return _extraer_articulo_interno(pdf, numero_articulo, quiet)


def _extraer_articulo_interno(pdf, numero_articulo: str, quiet: bool) -> list[Parrafo]:
    """Implementación interna de extracción."""
    pag_inicio, pag_fin = encontrar_articulo(pdf, numero_articulo)

    if pag_inicio is None:
        raise ValueError(f"Artículo {numero_articulo} no encontrado")

    if not quiet:
        print(f"Artículo {numero_articulo} encontrado en páginas {pag_inicio + 1}-{pag_fin + 1}")

    # Extraer todas las líneas del artículo
    todas_lineas = []
    # Soporta formatos: "Artículo 2o." y "Artículo 2o.-" con espacios variables
    patron_art = re.compile(rf'Artículo\s+{re.escape(numero_articulo)}\.[\-\s]?')
    # Patrón para detectar siguiente artículo (más robusto)
    patron_siguiente = re.compile(r'Artículo\s+\d+[o]?(?:-[A-Z])?(?:\s+[A-Z][a-z]+)?\.[\-\s]', re.IGNORECASE)
    en_articulo = False

    for pag_num in range(pag_inicio, pag_fin + 1):
        lineas = extraer_lineas_pagina(pdf.pages[pag_num])

        for linea in lineas:
            text = linea['text']

            # Filtrar líneas de header/footer primero
            if any(skip in text for skip in ['CÓDIGO FISCAL', 'CÁMARA DE DIPUTADOS',
                                               'Secretaría General', 'Servicios Parlamentarios',
                                               'DOF', 'de 375', 'Última Reforma']):
                continue

            # Detectar inicio del artículo
            match_inicio = patron_art.search(text)
            if match_inicio and not en_articulo:
                en_articulo = True
                # Extraer solo la parte desde el identificador
                text = text[match_inicio.start():]
                linea['text'] = text
                todas_lineas.append(linea)
                continue

            # Detectar fin (siguiente artículo)
            if en_articulo:
                match = patron_siguiente.search(text)
                if match and not patron_art.search(text):
                    # Verificar que es realmente otro artículo (no "artículo anterior" o similar)
                    antes = text[:match.start()].lower()
                    if not any(p in antes for p in ['del ', 'al ', 'el ', 'este ', 'dicho ', 'presente ', 'referido ']):
                        en_articulo = False
                        break

                todas_lineas.append(linea)

        if not en_articulo and pag_num > pag_inicio:
            break

    return construir_jerarquia(todas_lineas, numero_articulo)


def construir_jerarquia(lineas: list[dict], numero_articulo: str) -> list[Parrafo]:
    """
    Construye la jerarquía de párrafos basándose en coordenadas X.
    """
    parrafos = []
    numero = 0

    # Stack para tracking de elementos por X aproximado
    # Clave = X redondeado a decenas, Valor = número de párrafo
    ultimo_por_x = {}

    # También mantener tracking por tipo para casos simples
    ultimo_por_nivel = {0: None, 1: None, 2: None, 3: None}

    # Juntar líneas que son continuación física
    # REGLAS:
    # 1. Si hay Y-gap significativo = nuevo párrafo (aunque X sea igual)
    # 2. Si X aumenta significativamente = continuación indentada
    # 3. Si X igual y sin identificador y sin Y-gap = continuación del mismo nivel
    # 4. Si X menor pero la línea empieza con minúscula = wrap de línea (continuación)
    # 5. Si X menor y empieza con mayúscula/identificador = nuevo elemento
    lineas_consolidadas = []
    buffer_texto = ""
    buffer_x = None
    buffer_y = None  # Track Y for gap detection
    buffer_tiene_id = False

    def es_continuacion_wrap(texto: str) -> bool:
        """Detecta si una línea es continuación por wrap (empieza con minúscula o puntuación)."""
        if not texto:
            return False
        primer_char = texto.strip()[0] if texto.strip() else ''
        # Continuación si empieza con minúscula, número (sin punto después), o ciertos caracteres
        return primer_char.islower() or primer_char in ',:;.()' or \
               (primer_char.isdigit() and not re.match(r'^\d+\.', texto.strip()))

    for linea in lineas:
        x, y, text = linea['x'], linea['y'], linea['text']
        tipo, identificador, contenido = detectar_tipo_identificador(text)

        # Calcular Y-gap respecto a línea anterior
        y_gap = (y - buffer_y) if buffer_y is not None else 0

        if not buffer_texto:
            # Primera línea
            buffer_texto = text
            buffer_x = x
            buffer_y = y
            buffer_tiene_id = identificador is not None
        elif identificador:
            # Nueva línea con identificador = nuevo elemento
            lineas_consolidadas.append({'x': buffer_x, 'text': buffer_texto})
            buffer_texto = text
            buffer_x = x
            buffer_y = y
            buffer_tiene_id = True
        elif y_gap >= Y_PARAGRAPH_GAP and not es_continuacion_wrap(text):
            # Y-gap significativo = nuevo párrafo (aunque X sea igual)
            lineas_consolidadas.append({'x': buffer_x, 'text': buffer_texto})
            buffer_texto = text
            buffer_x = x
            buffer_y = y
            buffer_tiene_id = False
        elif x > buffer_x + X_TOLERANCE:
            # X mayor = continuación indentada del elemento anterior
            buffer_texto += " " + text
            buffer_y = y  # Actualizar Y
        elif x < buffer_x - X_TOLERANCE:
            # X menor - podría ser wrap o nuevo elemento
            if es_continuacion_wrap(text):
                # Es wrap de línea (continuación)
                buffer_texto += " " + text
                buffer_y = y
            else:
                # Nuevo elemento en nivel superior
                lineas_consolidadas.append({'x': buffer_x, 'text': buffer_texto})
                buffer_texto = text
                buffer_x = x
                buffer_y = y
                buffer_tiene_id = False
        else:
            # X igual (dentro de tolerancia) y sin Y-gap significativo
            if buffer_tiene_id:
                # El buffer tiene identificador, esta línea no
                # = nuevo elemento al mismo nivel (hermano, no continuación)
                lineas_consolidadas.append({'x': buffer_x, 'text': buffer_texto})
                buffer_texto = text
                buffer_x = x
                buffer_y = y
                buffer_tiene_id = False
            else:
                # Ambos sin identificador al mismo X = continuación
                buffer_texto += " " + text
                buffer_y = y

    if buffer_texto:
        lineas_consolidadas.append({'x': buffer_x, 'text': buffer_texto})

    # Procesar líneas consolidadas
    for linea in lineas_consolidadas:
        x, text = linea['x'], linea['text']

        if not text.strip():
            continue

        tipo, identificador, contenido = detectar_tipo_identificador(text)
        nivel_x = determinar_nivel_x(x)

        # Determinar padre basado en X
        # Buscar el elemento más cercano con X menor (padre)
        def encontrar_padre_por_x(x_actual: int) -> Optional[int]:
            """Encuentra el padre buscando el elemento con X menor más cercano."""
            candidatos = [(x_key, num) for x_key, num in ultimo_por_x.items()
                          if x_key < x_actual - X_TOLERANCE]
            if not candidatos:
                return None
            # El padre es el de X más grande que sea menor que x_actual
            candidatos.sort(key=lambda t: t[0], reverse=True)
            return candidatos[0][1]

        if tipo == 'fraccion':
            padre = None  # Las fracciones son hijos directos del artículo
            nivel_x = 1
        elif tipo in ('inciso', 'numeral'):
            # Usar X para encontrar el padre correcto
            padre = encontrar_padre_por_x(x)
            nivel_x = 2 if tipo == 'inciso' else 3
        elif tipo == 'texto':
            # Texto sin identificador: el X determina el padre
            if nivel_x == 0:
                # X de artículo: párrafo a nivel artículo (intro o final)
                padre = None
            else:
                # Buscar padre por X
                padre = encontrar_padre_por_x(x)

        numero += 1
        parrafo = Parrafo(
            numero=numero,
            tipo=tipo,
            identificador=identificador,
            contenido=contenido if identificador else text,
            x_pos=x,
            padre_numero=padre
        )
        parrafos.append(parrafo)

        # Actualizar tracking por X
        x_key = round(x / 10) * 10  # Redondear a decenas
        ultimo_por_x[x_key] = numero
        # Limpiar X mayores (ya no son válidos como padres de nuevos elementos)
        ultimo_por_x = {k: v for k, v in ultimo_por_x.items() if k <= x_key}

        # También actualizar por nivel/tipo
        if tipo in ('fraccion', 'inciso', 'numeral'):
            ultimo_por_nivel[nivel_x] = numero
            # Limpiar niveles inferiores
            for n in range(nivel_x + 1, 4):
                ultimo_por_nivel[n] = None

    return parrafos


def imprimir_arbol(parrafos: list[Parrafo]):
    """Imprime los párrafos en formato de árbol."""
    # Crear índice por número
    por_numero = {p.numero: p for p in parrafos}

    def get_nivel(p: Parrafo) -> int:
        nivel = 0
        actual = p
        while actual.padre_numero:
            nivel += 1
            actual = por_numero[actual.padre_numero]
        return nivel

    print("\n" + "="*70)
    print("ESTRUCTURA JERÁRQUICA")
    print("="*70)

    for p in parrafos:
        nivel = get_nivel(p)
        indent = "  " * nivel

        if p.identificador:
            label = f"{p.tipo} {p.identificador}"
        else:
            label = f"{p.tipo}"

        contenido = p.contenido[:50] + "..." if len(p.contenido) > 50 else p.contenido
        padre_info = f"(padre={p.padre_numero})" if p.padre_numero else "(raíz)"

        print(f"{indent}[{p.numero:2}] {label:15} X={p.x_pos:3} {padre_info}")
        print(f"{indent}     {contenido}")


def main():
    if len(sys.argv) < 3:
        print("Uso: python extraer_parrafos_x.py <LEY> <ARTICULO>")
        print("Ejemplo: python extraer_parrafos_x.py CFF 66-A")
        sys.exit(1)

    ley = sys.argv[1].upper()
    articulo = sys.argv[2]

    # Buscar PDF
    base_dir = Path(__file__).parent.parent.parent
    pdf_dir = base_dir / "doc" / "leyes" / ley.lower()

    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"Error: No se encontró PDF en {pdf_dir}")
        sys.exit(1)

    pdf_path = pdf_files[0]
    print(f"Usando PDF: {pdf_path}")

    try:
        parrafos = extraer_articulo(str(pdf_path), articulo)
        imprimir_arbol(parrafos)

        # También guardar como JSON
        output = {
            'articulo': articulo,
            'total_parrafos': len(parrafos),
            'parrafos': [asdict(p) for p in parrafos]
        }

        # Remover campo 'hijos' vacío
        for p in output['parrafos']:
            del p['hijos']

        print("\n" + "="*70)
        print("JSON")
        print("="*70)
        print(json.dumps(output, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
