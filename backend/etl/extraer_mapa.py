#!/usr/bin/env python3
"""
Extractor de mapa estructural del PDF.

Usa el outline (TOC) del PDF como fuente primaria para artículos.
Extrae estructura jerárquica (Títulos/Capítulos) del texto.

Uso:
    python backend/etl/extraer_mapa.py CFF
"""

import re
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

try:
    import fitz
except ImportError:
    print("Error: PyMuPDF no instalado. Ejecuta: pip install pymupdf")
    sys.exit(1)

from config import get_config

BASE_DIR = Path(__file__).parent.parent.parent

# Variantes de números para búsqueda en PDF (romano ↔ ordinal)
VARIANTES_NUMERO = {
    'I': ['I', 'PRIMERA', 'PRIMERO'],
    'PRIMERA': ['I', 'PRIMERA', 'PRIMERO'],
    'PRIMERO': ['I', 'PRIMERA', 'PRIMERO'],
    'II': ['II', 'SEGUNDA', 'SEGUNDO'],
    'SEGUNDA': ['II', 'SEGUNDA', 'SEGUNDO'],
    'SEGUNDO': ['II', 'SEGUNDA', 'SEGUNDO'],
    'III': ['III', 'TERCERA', 'TERCERO'],
    'TERCERA': ['III', 'TERCERA', 'TERCERO'],
    'TERCERO': ['III', 'TERCERA', 'TERCERO'],
    'IV': ['IV', 'CUARTA', 'CUARTO'],
    'CUARTA': ['IV', 'CUARTA', 'CUARTO'],
    'CUARTO': ['IV', 'CUARTA', 'CUARTO'],
    'V': ['V', 'QUINTA', 'QUINTO'],
    'QUINTA': ['V', 'QUINTA', 'QUINTO'],
    'QUINTO': ['V', 'QUINTA', 'QUINTO'],
    'VI': ['VI', 'SEXTA', 'SEXTO'],
    'SEXTA': ['VI', 'SEXTA', 'SEXTO'],
    'SEXTO': ['VI', 'SEXTA', 'SEXTO'],
    'VII': ['VII', 'SEPTIMA', 'SÉPTIMA', 'SEPTIMO', 'SÉPTIMO'],
    'SEPTIMA': ['VII', 'SEPTIMA', 'SÉPTIMA', 'SEPTIMO', 'SÉPTIMO'],
    'SÉPTIMA': ['VII', 'SEPTIMA', 'SÉPTIMA', 'SEPTIMO', 'SÉPTIMO'],
    'VIII': ['VIII', 'OCTAVA', 'OCTAVO'],
    'OCTAVA': ['VIII', 'OCTAVA', 'OCTAVO'],
    'OCTAVO': ['VIII', 'OCTAVA', 'OCTAVO'],
    'IX': ['IX', 'NOVENA', 'NOVENO'],
    'NOVENA': ['IX', 'NOVENA', 'NOVENO'],
    'NOVENO': ['IX', 'NOVENA', 'NOVENO'],
    'X': ['X', 'DECIMA', 'DÉCIMA', 'DECIMO', 'DÉCIMO'],
    'DECIMA': ['X', 'DECIMA', 'DÉCIMA', 'DECIMO', 'DÉCIMO'],
    'DÉCIMA': ['X', 'DECIMA', 'DÉCIMA', 'DECIMO', 'DÉCIMO'],
}

def obtener_variantes_numero(numero: str) -> list[str]:
    """Devuelve todas las variantes posibles de un número (romano + ordinales)."""
    numero_upper = numero.upper().strip()
    return VARIANTES_NUMERO.get(numero_upper, [numero_upper])


def normalizar_romano_subseccion(texto: str) -> Optional[str]:
    """
    Normaliza texto a número romano para subsecciones.
    Maneja el caso de 'll' (dos eles) que a veces aparece en PDFs en lugar de 'II'.

    Returns:
        Número romano normalizado o None si no es válido.
    """
    texto = texto.strip()

    # Mapeo de caracteres confusos
    # 'l' minúscula → 'I' (común en PDFs mal codificados)
    normalizado = texto.replace('l', 'I').replace('L', 'I').upper()

    # Verificar que sea un romano válido (I-X para subsecciones)
    romanos_validos = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']
    if normalizado in romanos_validos:
        return normalizado

    return None


def obtener_coordenada_y(page, patron: str) -> float:
    """
    Obtiene la coordenada Y de un texto en la página usando el patrón regex.
    Retorna la coordenada Y del bbox (posición vertical) o 99999 si no encuentra.
    """
    blocks = page.get_text("dict")["blocks"]

    for block in blocks:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            texto_linea = "".join([span["text"] for span in line["spans"]])
            if re.search(patron, texto_linea, re.IGNORECASE):
                return line["bbox"][1]  # coordenada Y superior

    return 99999.0  # No encontrado, poner al final


@dataclass
class ArticuloRef:
    """Referencia a un artículo."""
    numero: str
    pagina: int
    derogado: bool = False


@dataclass
class SubseccionRef:
    """Referencia a una subsección dentro de sección (ej: LA usa I, II, III sin palabra SUBSECCION)."""
    numero: str
    nombre: Optional[str]
    pagina: int
    articulos: list[ArticuloRef] = field(default_factory=list)


@dataclass
class SeccionRef:
    """Referencia a una sección dentro de capítulo."""
    numero: str
    nombre: Optional[str]
    pagina: int
    articulos: list[ArticuloRef] = field(default_factory=list)
    subsecciones: list[SubseccionRef] = field(default_factory=list)


@dataclass
class CapituloRef:
    """Referencia a un capítulo."""
    numero: str
    nombre: Optional[str]
    pagina: int
    articulos: list[ArticuloRef] = field(default_factory=list)
    secciones: list[SeccionRef] = field(default_factory=list)


@dataclass
class TituloRef:
    """Referencia a un título."""
    numero: str
    nombre: Optional[str]
    pagina: int
    capitulos: list[CapituloRef] = field(default_factory=list)


def normalizar_numero(titulo_outline: str) -> str:
    """
    Normaliza número de artículo del outline.
    Artículo_4o_A → 4o-A
    Artículo_29_B → 29-B
    Artículo_29_Bis → 29 Bis
    Artículo_32_B_Ter → 32-B Ter
    """
    # Quitar prefijo "Artículo_"
    numero = titulo_outline.replace("Artículo_", "")

    # Sufijos especiales que van con espacio
    sufijos = ['Bis', 'Ter', 'Quáter', 'Quintus', 'Quinquies', 'Sexies']

    # Procesar partes separadas por _
    partes = numero.split('_')
    resultado = []

    for i, parte in enumerate(partes):
        # ¿Es sufijo especial?
        if parte in sufijos:
            resultado.append(' ' + parte)
        # ¿Es letra sola (A, B, C...)?
        elif len(parte) == 1 and parte.isalpha() and parte.isupper():
            resultado.append('-' + parte)
        else:
            if resultado:
                resultado.append('-' + parte)
            else:
                resultado.append(parte)

    return ''.join(resultado)


def extraer_articulos_outline(doc, transitorios_marcador: str = "TRANSITORIOS") -> list[ArticuloRef]:
    """
    Extrae artículos del outline del PDF.

    Args:
        doc: Documento PDF abierto con fitz
        transitorios_marcador: Texto del outline que marca fin de artículos

    Returns:
        Lista de artículos
    """
    toc = doc.get_toc()
    articulos = []

    for level, title, page in toc:
        # Detectar fin de artículos (sección de transitorios)
        if title == transitorios_marcador or title == "TRANSITORIOS_DE_DECRETOS_DE_REFORMA":
            break

        # Solo procesar artículos
        if not title.startswith("Artículo_"):
            continue

        numero = normalizar_numero(title)
        articulos.append(ArticuloRef(numero=numero, pagina=page))

    return articulos


def marcar_derogados(doc, articulos: list[ArticuloRef]) -> None:
    """
    Detecta y marca artículos derogados leyendo el texto del PDF.
    Modifica los artículos in-place, marcando art.derogado = True.
    """
    for art in articulos:
        # Leer texto de la página del artículo
        page_idx = art.pagina - 1
        if page_idx < 0 or page_idx >= len(doc):
            continue

        texto = doc[page_idx].get_text()

        # Buscar línea del artículo
        lineas = texto.split('\n')

        for i, linea in enumerate(lineas):
            # Normalizar número para comparación
            num_buscar = art.numero.replace('-', '').replace(' ', '')
            linea_norm = linea.replace('-', '').replace(' ', '').replace('.', '')

            if f'Artículo{num_buscar}' in linea_norm or f'Artículo{num_buscar}' in linea_norm.replace('_', ''):
                # Revisar esta línea y las siguientes
                texto_cercano = ' '.join(lineas[i:i+3]).lower()
                if 'se deroga' in texto_cercano or '(derogado)' in texto_cercano:
                    art.derogado = True
                    break


def _calcular_centrado_bold(line: dict, page_width: float) -> tuple[bool, bool, str]:
    """
    Calcula si una línea está centrada y es bold.

    Args:
        line: Diccionario de línea de PyMuPDF (de get_text('dict'))
        page_width: Ancho de la página

    Returns:
        (centrado, all_bold, texto)
    """
    TOLERANCIA_CENTRADO = 5.0
    THRESHOLD_BOLD = 0.8

    bbox = line['bbox']
    x_min, x_max = bbox[0], bbox[2]
    text_width = x_max - x_min

    # Centrado
    if text_width <= 0:
        centrado = False
    else:
        expected_x = (page_width - text_width) / 2
        centrado = abs(x_min - expected_x) <= TOLERANCIA_CENTRADO

    # Bold y texto
    total_chars = 0
    bold_chars = 0
    text_parts = []

    for span in line.get('spans', []):
        t = span.get('text', '').strip()
        if t:
            total_chars += len(t)
            if span.get('flags', 0) & 16:  # bit 4 = bold
                bold_chars += len(t)
            text_parts.append(t)

    all_bold = total_chars > 0 and (bold_chars / total_chars) >= THRESHOLD_BOLD
    texto = ' '.join(text_parts)

    return centrado, all_bold, texto


def extraer_estructura(doc, config: dict, pagina_fin: int = None) -> list[TituloRef]:
    """
    Extrae estructura jerárquica (Títulos/Capítulos/Secciones) del texto del PDF.

    Usa información de layout (centrado + bold) para detectar nombres de división
    que ocupan múltiples líneas, incluso cruzando páginas.

    Args:
        doc: Documento PyMuPDF
        config: Configuración de la ley (contiene patrones)
        pagina_fin: Página donde termina el contenido (opcional, 1-indexed)
    """
    titulos = []
    titulo_actual = None
    capitulo_actual = None

    # Patrones desde config, con defaults
    patrones = config.get("patrones", {})
    patron_titulo = patrones.get("titulo", r'^T[IÍ]TULO\s+(PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[EÉ]PTIMO|OCTAVO|NOVENO|D[EÉ]CIMO|[IVX]+)\s*$')
    patron_capitulo = patrones.get("capitulo", r'^CAP[IÍ]TULO\s+([IVX]+(?:\s+BIS)?|[UÚ]NICO)\s*$')
    patron_seccion = patrones.get("seccion", r'^SECCI[OÓ]N\s+([IVX]+|PRIMERA|SEGUNDA|TERCERA|CUARTA|QUINTA|SEXTA|S[EÉ]PTIMA|OCTAVA|NOVENA|D[EÉ]CIMA|[UÚ]NICA)\s*$')

    # Patrón de subsección (solo para leyes como LA que usan romanos sueltos)
    # Si está habilitado, detecta líneas que son solo números romanos (I, II, III, etc.)
    detectar_subsecciones = config.get("detectar_subsecciones", False)

    # Configuración de layout
    requiere_centrado = config.get("requiere_centrado", True)

    # PASO 1: Construir lista de líneas de TODAS las páginas
    # Esto permite capturar nombres que cruzan páginas
    # Filtramos header/footer usando filtro_y de config
    filtro_y = config.get("filtro_y", {})
    header_max = filtro_y.get("header_max", 0)
    footer_min = filtro_y.get("footer_min", 999)

    lineas_layout = []
    for page_num, page in enumerate(doc):
        if pagina_fin and (page_num + 1) > pagina_fin:
            break

        page_width = page.rect.width
        blocks = page.get_text('dict')['blocks']

        for block in blocks:
            if 'lines' not in block:
                continue
            for line in block['lines']:
                y = line['bbox'][1]
                # Filtrar header/footer
                if y < header_max or y > footer_min:
                    continue
                centrado, all_bold, texto = _calcular_centrado_bold(line, page_width)
                # Filtrar líneas vacías
                if not texto.strip():
                    continue
                lineas_layout.append({
                    'texto': texto,
                    'centrado': centrado,
                    'all_bold': all_bold,
                    'y': y,
                    'pagina': page_num + 1
                })

    # PASO 2: Procesar todas las líneas para extraer estructura
    i = 0
    while i < len(lineas_layout):
        linea = lineas_layout[i]
        texto = linea['texto'].strip()

        if not texto:
            i += 1
            continue

        # ¿Es título?
        match = re.match(patron_titulo, texto, re.IGNORECASE)
        if match and (not requiere_centrado or linea['centrado']) and linea['all_bold']:
            # Capturar nombre: líneas siguientes que sean centrado+bold
            nombre_partes = []
            j = i + 1
            while j < len(lineas_layout):
                sig = lineas_layout[j]
                if (not requiere_centrado or sig['centrado']) and sig['all_bold'] and sig['texto'].strip():
                    # Verificar que no sea otro marcador
                    if (re.match(patron_titulo, sig['texto'], re.IGNORECASE) or
                        re.match(patron_capitulo, sig['texto'], re.IGNORECASE) or
                        re.match(patron_seccion, sig['texto'], re.IGNORECASE)):
                        break
                    nombre_partes.append(sig['texto'].strip())
                    j += 1
                else:
                    break

            nombre = ' '.join(nombre_partes) if nombre_partes else None

            titulo_actual = TituloRef(
                numero=match.group(1).upper(),
                nombre=nombre,
                pagina=linea['pagina']
            )
            titulos.append(titulo_actual)
            capitulo_actual = None
            i = j  # Saltar las líneas del nombre
            continue

        # ¿Es capítulo?
        match = re.match(patron_capitulo, texto, re.IGNORECASE)
        if match and (not requiere_centrado or linea['centrado']) and linea['all_bold']:
            if titulo_actual is None:
                titulo_actual = TituloRef(numero="PRELIMINAR", nombre=None, pagina=1)
                titulos.insert(0, titulo_actual)

            # Capturar nombre: líneas siguientes que sean centrado+bold
            nombre_partes = []
            j = i + 1
            while j < len(lineas_layout):
                sig = lineas_layout[j]
                if (not requiere_centrado or sig['centrado']) and sig['all_bold'] and sig['texto'].strip():
                    # Verificar que no sea otro marcador
                    if (re.match(patron_titulo, sig['texto'], re.IGNORECASE) or
                        re.match(patron_capitulo, sig['texto'], re.IGNORECASE) or
                        re.match(patron_seccion, sig['texto'], re.IGNORECASE)):
                        break
                    nombre_partes.append(sig['texto'].strip())
                    j += 1
                else:
                    break

            nombre = ' '.join(nombre_partes) if nombre_partes else None

            capitulo_actual = CapituloRef(
                numero=match.group(1).upper(),
                nombre=nombre,
                pagina=linea['pagina']
            )
            titulo_actual.capitulos.append(capitulo_actual)
            i = j  # Saltar las líneas del nombre
            continue

        # ¿Es sección?
        match = re.match(patron_seccion, texto, re.IGNORECASE)
        if match and (not requiere_centrado or linea['centrado']) and linea['all_bold']:
            if capitulo_actual is None:
                i += 1
                continue  # Ignorar secciones sin capítulo

            # Capturar nombre: líneas siguientes que sean centrado+bold
            nombre_partes = []
            j = i + 1
            while j < len(lineas_layout):
                sig = lineas_layout[j]
                if (not requiere_centrado or sig['centrado']) and sig['all_bold'] and sig['texto'].strip():
                    # Verificar que no sea otro marcador
                    if (re.match(patron_titulo, sig['texto'], re.IGNORECASE) or
                        re.match(patron_capitulo, sig['texto'], re.IGNORECASE) or
                        re.match(patron_seccion, sig['texto'], re.IGNORECASE)):
                        break
                    # Verificar que no sea una subsección (romano solo)
                    if detectar_subsecciones and normalizar_romano_subseccion(sig['texto'].strip()):
                        break
                    nombre_partes.append(sig['texto'].strip())
                    j += 1
                else:
                    break

            nombre = ' '.join(nombre_partes) if nombre_partes else None

            seccion = SeccionRef(
                numero=match.group(1).upper(),
                nombre=nombre,
                pagina=linea['pagina']
            )
            capitulo_actual.secciones.append(seccion)
            i = j  # Saltar las líneas del nombre
            continue

        # ¿Es subsección? (solo si está habilitado - ej: LA)
        # Las subsecciones son líneas que son solo un número romano (I, II, III, etc.)
        # seguido de una línea con el nombre
        if detectar_subsecciones:
            romano = normalizar_romano_subseccion(texto)
            if romano and linea['centrado'] and linea['all_bold']:
                # Verificar que haya una sección actual donde añadir la subsección
                seccion_actual = None
                if capitulo_actual and capitulo_actual.secciones:
                    seccion_actual = capitulo_actual.secciones[-1]

                if seccion_actual:
                    # Capturar nombre: líneas siguientes que sean centrado+bold
                    nombre_partes = []
                    j = i + 1
                    while j < len(lineas_layout):
                        sig = lineas_layout[j]
                        if (sig['centrado'] and sig['all_bold'] and sig['texto'].strip()):
                            # Verificar que no sea otro marcador
                            if (re.match(patron_titulo, sig['texto'], re.IGNORECASE) or
                                re.match(patron_capitulo, sig['texto'], re.IGNORECASE) or
                                re.match(patron_seccion, sig['texto'], re.IGNORECASE)):
                                break
                            # Verificar que no sea otra subsección (romano solo)
                            if normalizar_romano_subseccion(sig['texto'].strip()):
                                break
                            nombre_partes.append(sig['texto'].strip())
                            j += 1
                        else:
                            break

                    nombre = ' '.join(nombre_partes) if nombre_partes else None

                    subseccion = SubseccionRef(
                        numero=romano,
                        nombre=nombre,
                        pagina=linea['pagina']
                    )
                    seccion_actual.subsecciones.append(subseccion)
                    i = j  # Saltar las líneas del nombre
                    continue

        i += 1

    return titulos


def asignar_articulos_a_capitulos(titulos: list[TituloRef], articulos: list[ArticuloRef], doc):
    """
    Asigna artículos a capítulos/secciones basándose en páginas y posición en texto.

    Si un título no tiene capítulos, crea un capítulo "UNICO" virtual.
    Si un capítulo tiene secciones, los artículos se asignan a las secciones.
    """
    # Crear capítulos virtuales para títulos sin capítulos
    for titulo in titulos:
        if not titulo.capitulos:
            cap_virtual = CapituloRef(
                numero="UNICO",
                nombre=None,
                pagina=titulo.pagina
            )
            titulo.capitulos.append(cap_virtual)

    # Crear lista de puntos de corte con coordenada Y
    # Incluye tanto capítulos como secciones
    puntos_corte = []  # (pagina, coordenada_y, objeto, tipo)

    for titulo in titulos:
        for cap in titulo.capitulos:
            # Obtener coordenada Y del capítulo en la página
            page_idx = cap.pagina - 1
            if page_idx >= 0 and page_idx < len(doc):
                page = doc[page_idx]
                # Para capítulos virtuales (UNICO), buscar posición del TÍTULO
                if cap.numero == "UNICO" and cap.pagina == titulo.pagina:
                    patron = rf'T[IÍ]TULO\s+{re.escape(titulo.numero)}\b'
                else:
                    patron = rf'CAP[IÍ]TULO\s+{re.escape(cap.numero)}\b'
                coord_y = obtener_coordenada_y(page, patron)
            else:
                coord_y = 0

            # Si el capítulo tiene secciones, agregar las secciones como puntos de corte
            if cap.secciones:
                for sec in cap.secciones:
                    # Si la sección tiene subsecciones, agregar subsecciones como puntos de corte
                    if sec.subsecciones:
                        for subsec in sec.subsecciones:
                            page_idx = subsec.pagina - 1
                            if page_idx >= 0 and page_idx < len(doc):
                                page = doc[page_idx]
                                # Buscar el número romano solo (I, II, III, etc.)
                                # Incluir variantes por si el PDF tiene 'll' en lugar de 'II'
                                variantes = [subsec.numero]
                                if subsec.numero == 'II':
                                    variantes.extend(['ll', 'lI', 'Il'])  # Posibles confusiones de caracteres
                                patron = rf'^({"|".join(variantes)})\s*$'
                                coord_y_subsec = obtener_coordenada_y(page, patron)
                            else:
                                coord_y_subsec = 0
                            puntos_corte.append((subsec.pagina, coord_y_subsec, subsec, 'subseccion'))
                    else:
                        # Sin subsecciones, la sección es el punto de corte
                        page_idx = sec.pagina - 1
                        if page_idx >= 0 and page_idx < len(doc):
                            page = doc[page_idx]
                            # Buscar con todas las variantes del número (romano y ordinales)
                            variantes = obtener_variantes_numero(sec.numero)
                            patron = rf'SECCI[OÓ]N\s+({"|".join(variantes)})\b'
                            coord_y_sec = obtener_coordenada_y(page, patron)
                        else:
                            coord_y_sec = 0
                        puntos_corte.append((sec.pagina, coord_y_sec, sec, 'seccion'))
            else:
                # Sin secciones, el capítulo es el punto de corte
                puntos_corte.append((cap.pagina, coord_y, cap, 'capitulo'))

    puntos_corte.sort(key=lambda x: (x[0], x[1]))

    # Crear índice de coordenada Y de artículos en página
    articulos_con_pos = []
    for art in articulos:
        page_idx = art.pagina - 1
        if page_idx >= 0 and page_idx < len(doc):
            page = doc[page_idx]
            # Buscar coordenada Y del artículo
            num_escapado = art.numero.replace('-', r'\.?[-–]').replace(' ', r'[\s_]*')
            patron = rf'Art[íi]culo[\s_]+{num_escapado}'
            coord_y = obtener_coordenada_y(page, patron)
        else:
            coord_y = 0
        articulos_con_pos.append((art, coord_y))

    # Asignar cada artículo al punto de corte correspondiente (capítulo o sección)
    for art, pos_art in articulos_con_pos:
        punto_asignado = None

        for pagina, pos, obj, tipo in puntos_corte:
            # El artículo pertenece a este punto si:
            # - Está en una página posterior, O
            # - Está en la misma página pero después del encabezado
            if art.pagina > pagina:
                punto_asignado = obj
            elif art.pagina == pagina and pos_art >= pos:
                punto_asignado = obj

        if punto_asignado:
            punto_asignado.articulos.append(art)
        elif puntos_corte:
            # Si el artículo está antes del primer punto, asignar al primero
            puntos_corte[0][2].articulos.append(art)


def extraer_mapa_rmf(codigo: str, config: dict) -> list[TituloRef]:
    """
    Extrae el mapa estructural para RMF usando ExtractorRMF.

    RMF tiene estructura diferente:
    - Títulos: "Título 1.", "Título 2."
    - Capítulos: "Capítulo 2.1.", "Capítulo 2.2."
    - Reglas: "2.1.1.", "2.1.2." (se asignan por prefijo numérico)
    """
    from extractor.rmf import ExtractorRMF

    pdf_path = BASE_DIR / config["pdf_path"]
    print(f"   PDF: {pdf_path.name} (usando ExtractorRMF)")

    # 1. Cargar artículos desde contenido.json (RMF no tiene outline)
    contenido_path = pdf_path.parent / "contenido.json"
    articulos = []
    if contenido_path.exists():
        print("   Cargando reglas desde contenido.json...")
        with open(contenido_path) as f:
            contenido = json.load(f)
        for art in contenido.get("articulos", []):
            articulos.append(ArticuloRef(
                numero=art["numero"],
                pagina=art.get("pagina", 1),
                derogado=False
            ))
        print(f"   Cargadas: {len(articulos)} reglas")
    else:
        raise FileNotFoundError(f"contenido.json no existe. Ejecuta primero: python extraer.py {codigo}")

    # 2. Extraer estructura usando ExtractorRMF
    print("   Extrayendo estructura con ExtractorRMF...")
    extractor = ExtractorRMF(codigo, config)
    extractor.abrir_pdf()
    divisiones = extractor.extraer_estructura()
    extractor.cerrar_pdf()

    # 3. Convertir Division -> TituloRef
    titulos = []
    titulo_actual = None

    for div in divisiones:
        if div.tipo == "titulo":
            titulo_actual = TituloRef(
                numero=div.numero,
                nombre=div.nombre,
                pagina=div.pagina
            )
            titulos.append(titulo_actual)
        elif div.tipo == "capitulo" and titulo_actual:
            capitulo = CapituloRef(
                numero=div.numero,
                nombre=div.nombre,
                pagina=div.pagina
            )
            titulo_actual.capitulos.append(capitulo)

    print(f"   Encontrados: {len(titulos)} títulos, {sum(len(t.capitulos) for t in titulos)} capítulos")

    # 4. Asignar reglas a capítulos por prefijo numérico (2.1.x → capítulo 2.1)
    print("   Asignando reglas a capítulos por prefijo...")
    capitulos_idx = {}
    for titulo in titulos:
        for cap in titulo.capitulos:
            capitulos_idx[cap.numero] = cap

    for art in articulos:
        # Extraer prefijo del capítulo (2.1.3 → 2.1)
        partes = art.numero.split('.')
        if len(partes) >= 2:
            cap_num = f"{partes[0]}.{partes[1]}"
            if cap_num in capitulos_idx:
                capitulos_idx[cap_num].articulos.append(art)

    return titulos


def extraer_mapa(codigo: str) -> list[TituloRef]:
    """
    Extrae el mapa estructural completo del PDF.

    Usa el outline del PDF como fuente autoritativa para artículos.
    Para RMF, delega a ExtractorRMF que usa patrones específicos.

    Returns:
        Lista de títulos con su estructura jerárquica
    """
    config = get_config(codigo)

    # RMF usa extractor especializado
    if config.get("tipo_extractor") == "rmf":
        return extraer_mapa_rmf(codigo, config)

    pdf_path = BASE_DIR / config["pdf_path"]

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    print(f"   PDF: {pdf_path.name} ({len(doc)} páginas)")

    # 1. Extraer artículos del outline (fuente autoritativa)
    print("   Extrayendo artículos del outline...")
    transitorios_marcador = config.get("transitorios_marcador", "TRANSITORIOS")
    articulos = extraer_articulos_outline(doc, transitorios_marcador)
    print(f"   Encontrados: {len(articulos)} artículos")

    # 1b. Fallback: si outline vacío, usar contenido.json (generado por extraer.py)
    if not articulos:
        contenido_path = pdf_path.parent / "contenido.json"
        if contenido_path.exists():
            print("   Fallback: cargando artículos desde contenido.json...")
            with open(contenido_path) as f:
                contenido = json.load(f)
            for art in contenido.get("articulos", []):
                articulos.append(ArticuloRef(
                    numero=art["numero"],
                    pagina=art.get("pagina", 1),
                    derogado=False
                ))
            print(f"   Cargados: {len(articulos)} artículos")

    # 2. Marcar derogados (in-place)
    print("   Detectando artículos derogados...")
    marcar_derogados(doc, articulos)
    derogados_count = sum(1 for a in articulos if a.derogado)
    print(f"   Vigentes: {len(articulos) - derogados_count}, Derogados: {derogados_count}")

    # 3. Extraer estructura (Títulos/Capítulos)
    print("   Extrayendo estructura jerárquica...")
    pagina_fin = config.get("pagina_fin_contenido")

    # Si no hay pagina_fin configurada, detectar desde outline (TRANSITORIOS)
    if not pagina_fin:
        toc = doc.get_toc()
        for level, title, page in toc:
            if title == transitorios_marcador or title == "TRANSITORIOS_DE_DECRETOS_DE_REFORMA":
                pagina_fin = page
                break

    titulos = extraer_estructura(doc, config, pagina_fin)

    # Si no hay estructura pero sí artículos, crear título/capítulo virtual
    if not titulos and articulos:
        print("   Sin estructura jerárquica, creando contenedor virtual...")
        titulo_virtual = TituloRef(numero="UNICO", nombre=None, pagina=1)
        cap_virtual = CapituloRef(numero="UNICO", nombre=None, pagina=1)
        titulo_virtual.capitulos.append(cap_virtual)
        titulos.append(titulo_virtual)

    print(f"   Encontrados: {len(titulos)} títulos, {sum(len(t.capitulos) for t in titulos)} capítulos")

    # 4. Asignar TODOS los artículos a capítulos (incluyendo derogados)
    print("   Asignando artículos a capítulos...")
    asignar_articulos_a_capitulos(titulos, articulos, doc)

    doc.close()

    return titulos


def imprimir_mapa(titulos: list[TituloRef]):
    """Imprime el mapa en formato legible."""
    total_articulos = 0
    total_derogados = 0
    total_secciones = 0
    total_subsecciones = 0

    for titulo in titulos:
        nombre = f" - {titulo.nombre}" if titulo.nombre else ""
        print(f"\nTITULO {titulo.numero}{nombre} (pág. {titulo.pagina})")

        for cap in titulo.capitulos:
            nombre_cap = f" - {cap.nombre}" if cap.nombre else ""
            print(f"  CAPITULO {cap.numero}{nombre_cap}")

            # Si tiene secciones, mostrar artículos por sección
            if cap.secciones:
                total_secciones += len(cap.secciones)
                for sec in cap.secciones:
                    nombre_sec = f" - {sec.nombre}" if sec.nombre else ""
                    print(f"    SECCION {sec.numero}{nombre_sec}")

                    # Si tiene subsecciones, mostrar artículos por subsección
                    if sec.subsecciones:
                        total_subsecciones += len(sec.subsecciones)
                        for subsec in sec.subsecciones:
                            nombre_subsec = f" - {subsec.nombre}" if subsec.nombre else ""
                            arts = [a.numero for a in subsec.articulos]
                            derogados_subsec = sum(1 for a in subsec.articulos if a.derogado)
                            total_articulos += len(arts)
                            total_derogados += derogados_subsec
                            if arts:
                                rango = f"{arts[0]} ... {arts[-1]}" if len(arts) > 2 else ", ".join(arts)
                                derog_info = f", {derogados_subsec} derogados" if derogados_subsec else ""
                                print(f"      SUBSEC {subsec.numero}{nombre_subsec}")
                                print(f"        Artículos: {rango} ({len(arts)} arts{derog_info})")
                            else:
                                print(f"      SUBSEC {subsec.numero}{nombre_subsec}")
                                print(f"        (sin artículos)")
                    else:
                        # Sin subsecciones, mostrar artículos de la sección
                        arts = [a.numero for a in sec.articulos]
                        derogados_sec = sum(1 for a in sec.articulos if a.derogado)
                        total_articulos += len(arts)
                        total_derogados += derogados_sec
                        if arts:
                            rango = f"{arts[0]} ... {arts[-1]}" if len(arts) > 2 else ", ".join(arts)
                            derog_info = f", {derogados_sec} derogados" if derogados_sec else ""
                            print(f"      Artículos: {rango} ({len(arts)} arts{derog_info})")
                        else:
                            print(f"      (sin artículos)")
            else:
                # Sin secciones, mostrar artículos del capítulo
                arts = [a.numero for a in cap.articulos]
                derogados_cap = sum(1 for a in cap.articulos if a.derogado)
                total_articulos += len(arts)
                total_derogados += derogados_cap
                if arts:
                    rango = f"{arts[0]} ... {arts[-1]}" if len(arts) > 2 else ", ".join(arts)
                    derog_info = f", {derogados_cap} derogados" if derogados_cap else ""
                    print(f"    Artículos: {rango} ({len(arts)} arts{derog_info})")
                else:
                    print(f"    (sin artículos detectados)")

    print(f"\n{'='*60}")
    print(f"RESUMEN:")
    print(f"  Títulos:     {len(titulos)}")
    print(f"  Capítulos:   {sum(len(t.capitulos) for t in titulos)}")
    if total_secciones > 0:
        print(f"  Secciones:   {total_secciones}")
    if total_subsecciones > 0:
        print(f"  Subsecciones: {total_subsecciones}")
    print(f"  Artículos:   {total_articulos} ({total_articulos - total_derogados} vigentes, {total_derogados} derogados)")


def generar_json(titulos: list[TituloRef]) -> dict:
    """Genera estructura JSON para guardar."""
    resultado = {
        "titulos": {}
    }

    total_secciones = 0
    total_subsecciones = 0
    total_articulos = 0
    total_derogados = 0

    for titulo in titulos:
        titulo_data = {
            "nombre": titulo.nombre,
            "pagina": titulo.pagina,
            "capitulos": {}
        }

        for cap in titulo.capitulos:
            cap_data = {
                "nombre": cap.nombre,
                "pagina": cap.pagina,
            }

            # Si tiene secciones, incluirlas
            if cap.secciones:
                total_secciones += len(cap.secciones)
                cap_data["secciones"] = {}
                for sec in cap.secciones:
                    sec_data = {
                        "nombre": sec.nombre,
                        "pagina": sec.pagina,
                    }

                    # Si tiene subsecciones, incluirlas
                    if sec.subsecciones:
                        total_subsecciones += len(sec.subsecciones)
                        sec_data["subsecciones"] = {}
                        for subsec in sec.subsecciones:
                            subsec_data = {
                                "nombre": subsec.nombre,
                                "pagina": subsec.pagina,
                                "articulos": [a.numero for a in subsec.articulos]
                            }
                            total_articulos += len(subsec.articulos)
                            total_derogados += sum(1 for a in subsec.articulos if a.derogado)
                            sec_data["subsecciones"][subsec.numero] = subsec_data
                    else:
                        sec_data["articulos"] = [a.numero for a in sec.articulos]
                        total_articulos += len(sec.articulos)
                        total_derogados += sum(1 for a in sec.articulos if a.derogado)

                    cap_data["secciones"][sec.numero] = sec_data
            else:
                cap_data["articulos"] = [a.numero for a in cap.articulos]
                total_articulos += len(cap.articulos)
                total_derogados += sum(1 for a in cap.articulos if a.derogado)

            titulo_data["capitulos"][cap.numero] = cap_data

        resultado["titulos"][titulo.numero] = titulo_data

    # Estadísticas
    resultado["estadisticas"] = {
        "titulos": len(titulos),
        "capitulos": sum(len(t.capitulos) for t in titulos),
        "secciones": total_secciones,
        "subsecciones": total_subsecciones,
        "articulos_vigentes": total_articulos - total_derogados,
        "articulos_derogados": total_derogados,
        "total": total_articulos
    }

    return resultado


def main():
    if len(sys.argv) < 2:
        print("Uso: python backend/etl/extraer_mapa.py <CODIGO>")
        sys.exit(1)

    codigo = sys.argv[1].upper()

    print("=" * 60)
    print(f"EXTRACTOR DE MAPA: {codigo}")
    print("=" * 60)
    print("\nFuente: Outline del PDF (estructura oficial)")

    print("\n1. Procesando PDF...")
    try:
        titulos = extraer_mapa(codigo)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print("\n2. Mapa estructural:")
    imprimir_mapa(titulos)

    # Guardar JSON
    config = get_config(codigo)
    output_dir = BASE_DIR / Path(config["pdf_path"]).parent
    mapa_path = output_dir / "mapa_estructura.json"

    print(f"\n3. Guardando {mapa_path.name}...")
    mapa_json = generar_json(titulos)

    # Advertencia sagrada - este archivo es fuente única de verdad
    mapa_json_final = {
        "_advertencia": [
            "╔══════════════════════════════════════════════════════════════════╗",
            "║  ⚠️  ARCHIVO SAGRADO - FUENTE ÚNICA DE VERDAD  ⚠️                 ║",
            "║                                                                  ║",
            "║  NO MODIFICAR MANUALMENTE                                        ║",
            "║                                                                  ║",
            "║  Este archivo es la ÚNICA fuente de verdad para la estructura.  ║",
            "║  La base de datos se regenera desde aquí.                       ║",
            "║                                                                  ║",
            "║  Si el contenido es incorrecto:                                 ║",
            "║    → CORRIGE EL SCRIPT, no este archivo                         ║",
            "║                                                                  ║",
            "║  Modificarlo manualmente es SABOTAJE al sistema.                ║",
            "╚══════════════════════════════════════════════════════════════════╝"
        ],
        "_generado_por": "extraer_mapa.py",
        **mapa_json
    }
    mapa_json_final["ley"] = codigo
    mapa_json_final["fuente"] = config.get("url_fuente", "")
    mapa_json_final["metodo"] = "outline"
    mapa_json_final["notas"] = "Extraído del outline del PDF. Fuente autoritativa."

    with open(mapa_path, 'w', encoding='utf-8') as f:
        json.dump(mapa_json_final, f, ensure_ascii=False, indent=2)

    print("   Guardado")
    print("\n" + "=" * 60)
    print("EXTRACCIÓN DE MAPA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()
