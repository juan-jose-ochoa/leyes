#!/usr/bin/env python3
"""
Extractor de contenido de leyes para esquema leyesmx.

Extrae artículos y párrafos de PDFs oficiales usando coordenadas X/Y.
La estructura (títulos/capítulos) viene de estructura_esperada.json (ver extraer_mapa.py).

Uso:
    python backend/etl/extraer.py CFF
"""

import re
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

try:
    import pdfplumber
except ImportError:
    print("Error: pdfplumber no instalado. Ejecuta: pip install pdfplumber")
    sys.exit(1)

from config import get_config, listar_leyes

# Constantes para detección de jerarquía por coordenadas X
X_FRACCION = 85
X_INCISO = 114
X_NUMERAL = 142
X_TOLERANCE = 10
Y_PARAGRAPH_GAP = 12

BASE_DIR = Path(__file__).parent.parent.parent


@dataclass
class Parrafo:
    """Un párrafo dentro de un artículo."""
    numero: int                     # Orden secuencial: 1, 2, 3...
    tipo: str                       # 'texto', 'fraccion', 'inciso', 'numeral'
    identificador: Optional[str]    # 'I', 'a)', '1.', None para texto
    contenido: str
    padre_numero: Optional[int] = None  # Número del párrafo padre
    x_id: Optional[int] = None      # X del identificador (o inicio de línea)
    x_texto: Optional[int] = None   # X donde empieza el contenido de texto

    def to_dict(self) -> dict:
        d = {
            "numero": self.numero,
            "tipo": self.tipo,
            "identificador": self.identificador,
            "contenido": self.contenido,
            "padre_numero": self.padre_numero,
        }
        if self.x_id is not None:
            d["x_id"] = self.x_id
        if self.x_texto is not None:
            d["x_texto"] = self.x_texto
        return d


@dataclass
class Articulo:
    """Un artículo o regla."""
    numero: str                     # "1o", "17-H BIS", "2.1.1.1"
    tipo: str                       # "articulo", "regla", "transitorio"
    parrafos: list[Parrafo] = field(default_factory=list)
    orden: int = 0
    pagina: int = 0

    def to_dict(self) -> dict:
        return {
            "numero": self.numero,
            "tipo": self.tipo,
            "orden": self.orden,
            "pagina": self.pagina,
            "parrafos": [p.to_dict() for p in self.parrafos],
        }


@dataclass
class Division:
    """Una división estructural (título, capítulo, etc.)."""
    tipo: str                       # 'titulo', 'capitulo', 'seccion', 'libro'
    numero: str                     # 'PRIMERO', 'I', '2.1'
    nombre: Optional[str]           # 'Disposiciones Generales'
    orden: int
    padre_orden: Optional[int] = None  # Orden de la división padre

    def to_dict(self) -> dict:
        return {
            "tipo": self.tipo,
            "numero": self.numero,
            "nombre": self.nombre,
            "orden": self.orden,
            "padre_orden": self.padre_orden,
        }


class Extractor:
    """Extractor genérico de leyes usando coordenadas X/Y."""

    def __init__(self, codigo: str):
        self.codigo = codigo.upper()
        self.config = get_config(self.codigo)
        self.pdf_path = BASE_DIR / self.config["pdf_path"]
        self.pdf = None

    def abrir_pdf(self):
        """Abre el PDF."""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {self.pdf_path}")
        self.pdf = pdfplumber.open(str(self.pdf_path))
        print(f"   PDF: {self.pdf_path.name} ({len(self.pdf.pages)} páginas)")

    def cerrar_pdf(self):
        """Cierra el PDF."""
        if self.pdf:
            self.pdf.close()

    def _extraer_lineas_pagina(self, page) -> list[dict]:
        """Extrae líneas de una página con coordenadas X/Y."""
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
            x1 = round(line_words[-1]['x1'])  # x_end para detectar justificación
            text = ' '.join(w['text'] for w in line_words).strip()

            if text and x0 >= 70:  # Ignorar headers/footers
                result.append({'x': x0, 'x_end': x1, 'y': y_key, 'text': text})

        return result

    def _detectar_tipo_identificador(self, texto: str) -> tuple:
        """Detecta tipo de elemento y extrae identificador."""
        texto = texto.strip()

        # Fracción romana
        match = re.match(r'^([IVXLC]+)\.\s*(.*)$', texto)
        if match:
            return ('fraccion', match.group(1), match.group(2))

        # Inciso
        match = re.match(r'^([a-z])\)\s*(.*)$', texto)
        if match:
            return ('inciso', match.group(1) + ')', match.group(2))

        # Numeral
        match = re.match(r'^(\d+)\.\s*(.*)$', texto)
        if match:
            return ('numeral', match.group(1) + '.', match.group(2))

        return ('texto', None, texto)

    def _consolidar_lineas(self, lineas: list[dict]) -> list[dict]:
        """Consolida líneas físicas en párrafos lógicos usando 5 reglas.

        Reglas para detectar nuevo párrafo:
        1. Sangría (X mayor que líneas normales)
        2. Y-gap mayor que espaciado normal entre líneas
        3. Línea anterior NO justificada a la derecha (x_end < margen)
        4. Empieza con mayúscula
        5. Línea anterior termina con "."

        Si 4+ reglas se cumplen → nuevo párrafo
        """
        if not lineas:
            return []

        # Constantes para detección
        X_NORMAL = 71       # X de líneas de texto normal (sin sangría)
        X_SANGRIA = 80      # X mínimo para considerar sangría
        X_MARGEN_DERECHO = 530  # Margen derecho (líneas justificadas llegan a ~543)
        Y_GAP_NORMAL = 15   # Espaciado normal entre líneas

        lineas_consolidadas = []
        buffer_texto = ""
        buffer_x = None
        buffer_y = None
        buffer_x_end = None

        for linea in lineas:
            x = linea['x']
            x_end = linea.get('x_end', 544)
            y = linea['y']
            text = linea['text']

            # Si tiene identificador (I., a), 1.) → siempre nuevo párrafo
            _, identificador, _ = self._detectar_tipo_identificador(text)
            if identificador:
                if buffer_texto:
                    lineas_consolidadas.append({'x': buffer_x, 'text': buffer_texto})
                buffer_texto = text
                buffer_x = x
                buffer_y = y
                buffer_x_end = x_end
                continue

            if not buffer_texto:
                # Primera línea
                buffer_texto = text
                buffer_x = x
                buffer_y = y
                buffer_x_end = x_end
                continue

            # Calcular puntuación de las 5 reglas
            puntos = 0
            y_gap = y - buffer_y

            # Regla 1: Sangría (línea actual tiene X > normal)
            tiene_sangria = x >= X_SANGRIA
            if tiene_sangria:
                puntos += 1

            # Regla 2: Y-gap mayor que normal
            y_gap_grande = y_gap > Y_GAP_NORMAL
            if y_gap_grande:
                puntos += 1

            # Regla 3: Línea anterior NO justificada a la derecha
            anterior_no_justificada = buffer_x_end < X_MARGEN_DERECHO
            if anterior_no_justificada:
                puntos += 1

            # Regla 4: Empieza con mayúscula
            primer_char = text.strip()[0] if text.strip() else ''
            empieza_mayuscula = primer_char.isupper()
            if empieza_mayuscula:
                puntos += 1

            # Regla 5: Línea anterior termina con "."
            anterior_termina_punto = buffer_texto.rstrip().endswith('.')
            if anterior_termina_punto:
                puntos += 1

            # Decisión: 4+ reglas = nuevo párrafo
            if puntos >= 4:
                lineas_consolidadas.append({'x': buffer_x, 'text': buffer_texto})
                buffer_texto = text
                buffer_x = x
                buffer_y = y
                buffer_x_end = x_end
            else:
                # Continuación del párrafo actual
                buffer_texto += " " + text
                buffer_y = y
                buffer_x_end = x_end

        if buffer_texto:
            lineas_consolidadas.append({'x': buffer_x, 'text': buffer_texto})

        return lineas_consolidadas

    def _construir_parrafos(self, lineas_consolidadas: list[dict]) -> list[Parrafo]:
        """Construye párrafos con jerarquía desde líneas consolidadas."""
        parrafos = []
        numero = 0
        ultimo_por_x = {}

        def encontrar_padre_por_x(x_actual: int) -> Optional[int]:
            candidatos = [(x_key, num) for x_key, num in ultimo_por_x.items()
                          if x_key < x_actual - X_TOLERANCE]
            if not candidatos:
                return None
            candidatos.sort(key=lambda t: t[0], reverse=True)
            return candidatos[0][1]

        for linea in lineas_consolidadas:
            x, text = linea['x'], linea['text']
            if not text.strip():
                continue

            tipo, identificador, contenido = self._detectar_tipo_identificador(text)

            # Normalizar espacios múltiples
            contenido_limpio = ' '.join((contenido if identificador else text).split())

            # Determinar padre
            if tipo == 'fraccion':
                padre = None
            elif tipo in ('inciso', 'numeral'):
                padre = encontrar_padre_por_x(x)
            elif tipo == 'texto':
                if x < X_FRACCION + X_TOLERANCE:
                    padre = None
                else:
                    padre = encontrar_padre_por_x(x)
            else:
                padre = None

            numero += 1
            # x_id = X del identificador o inicio de línea
            x_id = round(x)
            # x_texto = X donde empieza el contenido (después del identificador)
            # Aproximación: identificador + espacio ocupa ~22 unidades
            if identificador:
                x_texto = x_id + 22
            else:
                x_texto = x_id
            parrafos.append(Parrafo(numero, tipo, identificador, contenido_limpio, padre, x_id, x_texto))

            # Actualizar tracking
            x_key = round(x / 10) * 10
            ultimo_por_x[x_key] = numero
            ultimo_por_x = {k: v for k, v in ultimo_por_x.items() if k <= x_key}

        return parrafos

    def _extraer_parrafos_articulo(self, pag_inicio: int, pag_fin: int,
                                    patron_art: re.Pattern, patron_siguiente: re.Pattern) -> list[Parrafo]:
        """Extrae párrafos de un artículo usando coordenadas X/Y."""
        todas_lineas = []
        en_articulo = False
        basura = self.config.get("basura_lineas", [
            'CÓDIGO FISCAL', 'CÁMARA DE DIPUTADOS', 'Secretaría General',
            'Servicios Parlamentarios', 'DOF', 'de 375', 'Última Reforma'
        ])

        for pag_num in range(pag_inicio, pag_fin + 1):
            lineas = self._extraer_lineas_pagina(self.pdf.pages[pag_num])

            for linea in lineas:
                text = linea['text']

                # Filtrar basura
                if any(skip in text for skip in basura):
                    continue

                # Detectar inicio
                match_inicio = patron_art.search(text)
                if match_inicio and not en_articulo:
                    en_articulo = True
                    text = text[match_inicio.end():].strip()
                    # Limpiar "- " residual del formato "Artículo Xo.-"
                    text = text.lstrip('- ').strip()
                    if text:
                        linea['text'] = text
                        todas_lineas.append(linea)
                    continue

                # Detectar fin (siguiente artículo)
                if en_articulo:
                    match = patron_siguiente.match(text)  # match() = inicio de línea
                    if match and linea['x'] >= 80:  # X de encabezado de artículo
                        en_articulo = False
                        break
                    todas_lineas.append(linea)

            if not en_articulo and pag_num > pag_inicio:
                break

        lineas_consolidadas = self._consolidar_lineas(todas_lineas)
        return self._construir_parrafos(lineas_consolidadas)

    def _encontrar_pagina_articulo(self, numero: str) -> tuple:
        """Encuentra página inicial y final de un artículo."""
        patron = re.compile(rf'Artículo\s+{re.escape(numero)}\.', re.IGNORECASE)
        patron_sig = re.compile(r'Artículo\s+\d+[o]?(?:\.-[A-Z])?(?:-[A-Z])?(?:\s+[A-Z][a-z]+)?\.', re.IGNORECASE)

        pag_inicio = None
        for i, page in enumerate(self.pdf.pages):
            text = page.extract_text() or ""
            if patron.search(text):
                pag_inicio = i
                break

        if pag_inicio is None:
            return None, None

        pag_fin = pag_inicio
        for i in range(pag_inicio + 1, min(pag_inicio + 10, len(self.pdf.pages))):
            text = self.pdf.pages[i].extract_text() or ""
            text_sin_actual = patron.sub('', text)
            if patron_sig.search(text_sin_actual):
                pag_fin = i
                break
            pag_fin = i

        return pag_inicio, pag_fin

    def extraer_contenido(self) -> list[Articulo]:
        """Extrae artículos/reglas con sus párrafos usando coordenadas X/Y."""
        articulos = []
        tipo_contenido = self.config["tipo_contenido"]

        # Primero, encontrar todos los artículos escaneando el PDF
        patron_art = re.compile(self.config["patrones"]["articulo"], re.IGNORECASE | re.MULTILINE)
        patron_siguiente = re.compile(r'Artículo\s+\d+[o]?(?:\.-[A-Z])?(?:-[A-Z])?(?:\s+[A-Z][a-z]+)?\.[\-\s]', re.IGNORECASE)

        # Escanear todas las páginas para encontrar artículos
        articulos_encontrados = []
        for i, page in enumerate(self.pdf.pages):
            text = page.extract_text() or ""
            for match in patron_art.finditer(text):
                grupos = match.groups()
                numero_base = grupos[0]
                ordinal = grupos[1] if len(grupos) > 1 else None
                letra = grupos[2] if len(grupos) > 2 else None
                sufijo = grupos[3] if len(grupos) > 3 else None

                numero = numero_base
                if ordinal:
                    numero += ordinal.lower()
                if letra:
                    numero += f"-{letra.upper()}"
                if sufijo:
                    numero += f" {sufijo.upper()}"

                articulos_encontrados.append((numero, i))

        # Eliminar duplicados manteniendo primera aparición
        numeros_vistos = set()
        articulos_unicos = []
        for numero, pagina in articulos_encontrados:
            if numero not in numeros_vistos:
                numeros_vistos.add(numero)
                articulos_unicos.append((numero, pagina))

        print(f"   Encontrados {len(articulos_unicos)} {tipo_contenido}s")

        # Extraer cada artículo
        for idx, (numero, pag_inicio) in enumerate(articulos_unicos):
            # Determinar página fin
            if idx + 1 < len(articulos_unicos):
                pag_fin = articulos_unicos[idx + 1][1]
            else:
                pag_fin = min(pag_inicio + 5, len(self.pdf.pages) - 1)

            # Patrón específico para este artículo
            # Convertir "4o-A" a patrón que coincida con "4o.-A.-" del PDF
            numero_patron = re.escape(numero).replace(r'\-', r'\.?-')
            patron_este = re.compile(rf'Artículo\s+{numero_patron}\.', re.IGNORECASE)

            # Extraer párrafos
            parrafos = self._extraer_parrafos_articulo(pag_inicio, pag_fin, patron_este, patron_siguiente)

            articulo = Articulo(
                numero=numero,
                tipo=tipo_contenido,
                parrafos=parrafos,
                orden=len(articulos) + 1,
                pagina=pag_inicio + 1
            )
            articulos.append(articulo)

        return articulos


def main():
    if len(sys.argv) < 2:
        print("Uso: python backend/etl/extraer.py <CODIGO>")
        print(f"Leyes disponibles: {', '.join(listar_leyes())}")
        sys.exit(1)

    codigo = sys.argv[1].upper()

    print("=" * 60)
    print(f"EXTRACTOR LEYESMX: {codigo}")
    print("=" * 60)

    try:
        extractor = Extractor(codigo)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Abrir PDF
    print("\n1. Abriendo PDF...")
    try:
        extractor.abrir_pdf()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    config = extractor.config
    output_dir = BASE_DIR / Path(config["pdf_path"]).parent

    # Extraer contenido (la estructura viene de estructura_esperada.json)
    print("\n2. Extrayendo contenido...")
    articulos = extractor.extraer_contenido()

    # Estadísticas
    total_parrafos = sum(len(a.parrafos) for a in articulos)
    tipos_parrafo = {}
    for a in articulos:
        for p in a.parrafos:
            tipos_parrafo[p.tipo] = tipos_parrafo.get(p.tipo, 0) + 1

    print(f"   {len(articulos)} artículos, {total_parrafos} párrafos")
    for tipo, count in sorted(tipos_parrafo.items(), key=lambda x: -x[1]):
        print(f"      {tipo}: {count}")

    # Guardar
    contenido_path = output_dir / "contenido.json"
    with open(contenido_path, 'w', encoding='utf-8') as f:
        json.dump({
            "ley": codigo,
            "tipo_contenido": config["tipo_contenido"],
            "articulos": [a.to_dict() for a in articulos]
        }, f, ensure_ascii=False, indent=2)
    print(f"   Guardado: {contenido_path.name}")

    extractor.cerrar_pdf()

    print("\n" + "=" * 60)
    print("EXTRACCIÓN COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()
