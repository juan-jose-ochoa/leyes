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


@dataclass
class ArticuloRef:
    """Referencia a un artículo."""
    numero: str
    pagina: int
    derogado: bool = False
    transitorio: bool = False


@dataclass
class SeccionRef:
    """Referencia a una sección dentro de capítulo."""
    numero: str
    nombre: Optional[str]
    pagina: int
    articulos: list[ArticuloRef] = field(default_factory=list)


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


def extraer_articulos_outline(doc) -> tuple[list[ArticuloRef], list[ArticuloRef]]:
    """
    Extrae artículos del outline del PDF.

    Returns:
        Tupla de (articulos_regulares, transitorios)
    """
    toc = doc.get_toc()
    articulos = []
    transitorios = []
    en_transitorios = False

    for level, title, page in toc:
        # Detectar sección de transitorios
        if title == "TRANSITORIOS":
            en_transitorios = True
            continue
        if title == "TRANSITORIOS_DE_DECRETOS_DE_REFORMA":
            # Ignorar transitorios de decretos de reforma por ahora
            break

        # Solo procesar artículos
        if not title.startswith("Artículo_"):
            continue

        numero = normalizar_numero(title)

        articulo = ArticuloRef(
            numero=numero,
            pagina=page,
            transitorio=en_transitorios
        )

        if en_transitorios:
            transitorios.append(articulo)
        else:
            articulos.append(articulo)

    return articulos, transitorios


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


def extraer_estructura(doc, config: dict, pagina_fin: int = None) -> list[TituloRef]:
    """
    Extrae estructura jerárquica (Títulos/Capítulos/Secciones) del texto del PDF.

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
    patron_seccion = patrones.get("seccion", r'^SECCI[OÓ]N\s+([IVX]+)\s*$')
    # Ruido: encabezados, pies de página, números de página (SALTAR)
    patron_ruido = r'^(LEY\s|CÁMARA|Secretaría|Últim|CÓDIGO|CONSTITUCIÓN|\d+\s+de\s+\d+|\[)'
    # No es nombre de división: artículos, capítulos, títulos, secciones, fracciones
    patron_no_nombre = r'^(ART|CAP|TITULO|TÍTULO|SECC|[IVX]+\.\s|[a-z]\)\s)'

    def es_ruido(linea):
        """Línea de encabezado/pie que debe saltarse."""
        return not linea or len(linea) <= 3 or re.match(patron_ruido, linea, re.IGNORECASE)

    def es_nombre_division(linea):
        """Línea que puede ser nombre de una división."""
        return not re.match(patron_no_nombre, linea, re.IGNORECASE)

    def buscar_nombre(lineas, idx, doc, page_num):
        """Busca el primer renglón significativo y evalúa si es nombre."""
        # Buscar en la misma página
        for i in range(idx + 1, len(lineas)):
            linea = lineas[i].strip()
            if es_ruido(linea):
                continue
            # Primer renglón significativo encontrado
            return linea if es_nombre_division(linea) else None

        # Si no encontró en la misma página, buscar en la siguiente
        if page_num + 1 < len(doc):
            texto_sig = doc[page_num + 1].get_text()
            for linea in texto_sig.split('\n'):
                linea = linea.strip()
                if es_ruido(linea):
                    continue
                # Primer renglón significativo encontrado
                return linea if es_nombre_division(linea) else None

        return None

    for page_num, page in enumerate(doc):
        # Si hay límite de página, detenerse
        if pagina_fin and (page_num + 1) > pagina_fin:
            break
        texto = page.get_text()
        lineas = texto.split('\n')

        for i, linea in enumerate(lineas):
            linea_limpia = linea.strip()

            # ¿Es título?
            match = re.match(patron_titulo, linea_limpia, re.IGNORECASE)
            if match:
                nombre = buscar_nombre(lineas, i, doc, page_num)

                titulo_actual = TituloRef(
                    numero=match.group(1).upper(),
                    nombre=nombre,
                    pagina=page_num + 1
                )
                titulos.append(titulo_actual)
                capitulo_actual = None
                continue

            # ¿Es capítulo?
            match = re.match(patron_capitulo, linea_limpia, re.IGNORECASE)
            if match:
                if titulo_actual is None:
                    titulo_actual = TituloRef(numero="PRELIMINAR", nombre=None, pagina=1)
                    titulos.insert(0, titulo_actual)

                nombre = buscar_nombre(lineas, i, doc, page_num)

                capitulo_actual = CapituloRef(
                    numero=match.group(1).upper(),
                    nombre=nombre,
                    pagina=page_num + 1
                )
                titulo_actual.capitulos.append(capitulo_actual)
                continue

            # ¿Es sección?
            match = re.match(patron_seccion, linea_limpia, re.IGNORECASE)
            if match:
                if capitulo_actual is None:
                    continue  # Ignorar secciones sin capítulo

                nombre = buscar_nombre(lineas, i, doc, page_num)

                seccion = SeccionRef(
                    numero=match.group(1).upper(),
                    nombre=nombre,
                    pagina=page_num + 1
                )
                capitulo_actual.secciones.append(seccion)

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

    # Crear lista de puntos de corte con posición en texto
    # Incluye tanto capítulos como secciones
    puntos_corte = []  # (pagina, pos, objeto, tipo)

    for titulo in titulos:
        for cap in titulo.capitulos:
            # Buscar posición exacta del capítulo en la página
            page_idx = cap.pagina - 1
            if page_idx >= 0 and page_idx < len(doc):
                texto = doc[page_idx].get_text()
                # Para capítulos virtuales (UNICO), buscar posición del TÍTULO
                if cap.numero == "UNICO" and cap.pagina == titulo.pagina:
                    patron = rf'T[IÍ]TULO\s+{re.escape(titulo.numero)}'
                else:
                    patron = rf'CAP[IÍ]TULO\s+{re.escape(cap.numero)}'
                match = re.search(patron, texto, re.IGNORECASE)
                pos_en_pagina = match.start() if match else 0
            else:
                pos_en_pagina = 0

            # Si el capítulo tiene secciones, agregar las secciones como puntos de corte
            if cap.secciones:
                for sec in cap.secciones:
                    page_idx = sec.pagina - 1
                    if page_idx >= 0 and page_idx < len(doc):
                        texto = doc[page_idx].get_text()
                        patron = rf'SECCI[OÓ]N\s+{re.escape(sec.numero)}'
                        match = re.search(patron, texto, re.IGNORECASE)
                        pos_sec = match.start() if match else 0
                    else:
                        pos_sec = 0
                    puntos_corte.append((sec.pagina, pos_sec, sec, 'seccion'))
            else:
                # Sin secciones, el capítulo es el punto de corte
                puntos_corte.append((cap.pagina, pos_en_pagina, cap, 'capitulo'))

    puntos_corte.sort(key=lambda x: (x[0], x[1]))

    # Crear índice de posición de artículos en página
    articulos_con_pos = []
    for art in articulos:
        page_idx = art.pagina - 1
        if page_idx >= 0 and page_idx < len(doc):
            texto = doc[page_idx].get_text()
            # Buscar posición del artículo en el texto
            num_escapado = art.numero.replace('-', '[-–]?').replace(' ', r'[\s_]*')
            patron = rf'Artículo[\s_]+{num_escapado}'
            match = re.search(patron, texto, re.IGNORECASE)
            pos_en_pagina = match.start() if match else 0
        else:
            pos_en_pagina = 0
        articulos_con_pos.append((art, pos_en_pagina))

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


def extraer_mapa(codigo: str) -> tuple[list[TituloRef], list[ArticuloRef]]:
    """
    Extrae el mapa estructural completo del PDF.

    Usa el outline del PDF como fuente autoritativa para artículos.

    Returns:
        Tupla de (titulos, transitorios)
    """
    config = get_config(codigo)
    pdf_path = BASE_DIR / config["pdf_path"]

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    print(f"   PDF: {pdf_path.name} ({len(doc)} páginas)")

    # 1. Extraer artículos del outline (fuente autoritativa)
    print("   Extrayendo artículos del outline...")
    articulos, transitorios = extraer_articulos_outline(doc)
    print(f"   Encontrados: {len(articulos)} artículos, {len(transitorios)} transitorios")

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
                    derogado=False,
                    transitorio=art.get("tipo") == "transitorio"
                ))
            # Separar transitorios
            transitorios = [a for a in articulos if a.transitorio]
            articulos = [a for a in articulos if not a.transitorio]
            print(f"   Cargados: {len(articulos)} artículos, {len(transitorios)} transitorios")

    # 2. Marcar derogados (in-place)
    print("   Detectando artículos derogados...")
    marcar_derogados(doc, articulos)
    derogados_count = sum(1 for a in articulos if a.derogado)
    print(f"   Vigentes: {len(articulos) - derogados_count}, Derogados: {derogados_count}")

    # 3. Extraer estructura (Títulos/Capítulos)
    print("   Extrayendo estructura jerárquica...")
    pagina_fin = config.get("pagina_fin_contenido")
    titulos = extraer_estructura(doc, config, pagina_fin)
    print(f"   Encontrados: {len(titulos)} títulos, {sum(len(t.capitulos) for t in titulos)} capítulos")

    # 4. Asignar TODOS los artículos a capítulos (incluyendo derogados)
    print("   Asignando artículos a capítulos...")
    asignar_articulos_a_capitulos(titulos, articulos, doc)

    doc.close()

    return titulos, transitorios


def imprimir_mapa(titulos: list[TituloRef], transitorios: list[ArticuloRef]):
    """Imprime el mapa en formato legible."""
    total_articulos = 0
    total_derogados = 0
    total_secciones = 0

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
                    arts = [a.numero for a in sec.articulos]
                    derogados_sec = sum(1 for a in sec.articulos if a.derogado)
                    total_articulos += len(arts)
                    total_derogados += derogados_sec
                    if arts:
                        rango = f"{arts[0]} ... {arts[-1]}" if len(arts) > 2 else ", ".join(arts)
                        print(f"    SECCION {sec.numero}{nombre_sec}")
                        derog_info = f", {derogados_sec} derogados" if derogados_sec else ""
                        print(f"      Artículos: {rango} ({len(arts)} arts{derog_info})")
                    else:
                        print(f"    SECCION {sec.numero}{nombre_sec}")
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

    if transitorios:
        print(f"\nTRANSITORIOS ({len(transitorios)} artículos)")

    print(f"\n{'='*60}")
    print(f"RESUMEN:")
    print(f"  Títulos:     {len(titulos)}")
    print(f"  Capítulos:   {sum(len(t.capitulos) for t in titulos)}")
    if total_secciones > 0:
        print(f"  Secciones:   {total_secciones}")
    print(f"  Artículos:   {total_articulos} ({total_articulos - total_derogados} vigentes, {total_derogados} derogados)")
    print(f"  Transitorios:{len(transitorios)}")


def generar_json(titulos: list[TituloRef], transitorios: list[ArticuloRef]) -> dict:
    """Genera estructura JSON para guardar."""
    resultado = {
        "titulos": {}
    }

    total_secciones = 0
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
                        "articulos": [a.numero for a in sec.articulos]
                    }
                    total_articulos += len(sec.articulos)
                    total_derogados += sum(1 for a in sec.articulos if a.derogado)
                    cap_data["secciones"][sec.numero] = sec_data
            else:
                cap_data["articulos"] = [a.numero for a in cap.articulos]
                total_articulos += len(cap.articulos)
                total_derogados += sum(1 for a in cap.articulos if a.derogado)

            titulo_data["capitulos"][cap.numero] = cap_data

        resultado["titulos"][titulo.numero] = titulo_data

    # Transitorios
    resultado["transitorios"] = [a.numero for a in transitorios]

    # Estadísticas
    resultado["estadisticas"] = {
        "titulos": len(titulos),
        "capitulos": sum(len(t.capitulos) for t in titulos),
        "secciones": total_secciones,
        "articulos_vigentes": total_articulos - total_derogados,
        "articulos_derogados": total_derogados,
        "articulos_transitorios": len(transitorios),
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
        titulos, transitorios = extraer_mapa(codigo)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print("\n2. Mapa estructural:")
    imprimir_mapa(titulos, transitorios)

    # Guardar JSON
    config = get_config(codigo)
    output_dir = BASE_DIR / Path(config["pdf_path"]).parent
    mapa_path = output_dir / "mapa_estructura.json"

    print(f"\n3. Guardando {mapa_path.name}...")
    mapa_json = generar_json(titulos, transitorios)
    mapa_json["ley"] = codigo
    mapa_json["fuente"] = config.get("url_fuente", "")
    mapa_json["metodo"] = "outline"
    mapa_json["notas"] = "Extraído del outline del PDF. Fuente autoritativa."

    with open(mapa_path, 'w', encoding='utf-8') as f:
        json.dump(mapa_json, f, ensure_ascii=False, indent=2)

    print("   Guardado")
    print("\n" + "=" * 60)
    print("EXTRACCIÓN DE MAPA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()
