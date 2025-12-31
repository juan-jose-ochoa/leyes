#!/usr/bin/env python3
"""
Extractor de estructura y contenido para RMF (Resolución Miscelánea Fiscal).

A diferencia de las leyes, RMF:
- No tiene outline en el PDF
- Usa numeración decimal jerárquica (2.1.1, 3.10.5)
- La estructura se deriva de la numeración
- Las referencias legales van al final de cada regla

Uso:
    python backend/etl/extraer_rmf.py RMF
    python backend/etl/extraer_rmf.py RMF --solo-estructura
    python backend/etl/extraer_rmf.py RMF --solo-contenido
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

BASE_DIR = Path(__file__).parent.parent.parent

# Configuración de RMF
RMF_CONFIG = {
    "RMF": {
        "nombre": "Resolución Miscelánea Fiscal",
        "nombre_corto": "Miscelánea Fiscal",
        "tipo": "resolucion",
        "url_fuente": "https://www.sat.gob.mx/normatividad/tax-resolution",
        "pdf_path": "backend/etl/data/rmf/rmf_2026_original.pdf",
    },
}

# Constantes de detección visual
PAGINA_WIDTH = 612  # Ancho estándar carta
CENTRO_PAGINA = PAGINA_WIDTH / 2
TOLERANCIA_CENTRADO = 50  # Píxeles de tolerancia para considerar centrado
MARGEN_IZQUIERDO = 99  # X donde empiezan las reglas

# Patrones
PATRON_TITULO = re.compile(r'^Título\s+(\d+)\.\s+(.+)$')
PATRON_CAPITULO = re.compile(r'^Capítulo\s+(\d+\.\d+)\.\s+(.+)$')
PATRON_REGLA = re.compile(r'^(\d+\.\d+\.\d+(?:\.\d+)?)\.\s*$')
PATRON_REGLA_INICIO = re.compile(r'^(\d+\.\d+\.\d+(?:\.\d+)?)\.\s*')
# Detección de itálico para referencias
def linea_es_italica(spans: list) -> bool:
    """Detecta si >50% del texto de una línea es itálico."""
    texto_italic = 0
    texto_total = 0
    for span in spans:
        texto = span["text"].strip()
        if texto:
            texto_total += len(texto)
            if span["flags"] & 2:  # 2^1 = italic flag
                texto_italic += len(texto)
    return texto_total > 0 and (texto_italic / texto_total) > 0.5

# Patrón para detectar si texto es referencia legal (empieza con abreviatura de ley/reglamento)
PATRON_REFERENCIAS = re.compile(r'^(CFF|LISR|LIVA|LIEPS|LIF|RCFF|RMF|RISR|RLISR|Ley|CPEUM|LCF|LSS|Convención)\s')
PATRON_FRACCION = re.compile(r'^([IVX]+)\.\s*')
PATRON_INCISO = re.compile(r'^([a-z])\)\s*')
PATRON_NUMERAL = re.compile(r'^(\d+)\.\s*')

# Coordenadas X para clasificación de párrafos
X_REGLA = 99       # Número de regla (x0)
X_TEXTO = 156      # Texto normal y fracciones (x1)
X_INCISO = 198     # Incisos a), b), c) (x2)
X_NUMERAL = 241    # Numerales 1., 2., 3. (x3)
X_CONTENIDO_NUM = 269  # Contenido de numerales (x4)
X_TOLERANCIA = 10  # Tolerancia para comparación


@dataclass
class Parrafo:
    """Párrafo de contenido."""
    tipo: str  # texto, fraccion, inciso
    contenido: str
    numero: Optional[str] = None  # I, II, III para fracciones; a, b, c para incisos


@dataclass
class ReglaContenido:
    """Contenido completo de una regla."""
    numero: str
    nombre: Optional[str]  # Título/nombre de la regla (texto en bold después del número)
    parrafos: list[Parrafo] = field(default_factory=list)
    referencias: Optional[str] = None  # "CFF 28, 31, LISR 5"


@dataclass
class ReglaRef:
    """Referencia a una regla."""
    numero: str
    pagina: int
    nombre: Optional[str] = None


@dataclass
class CapituloRef:
    """Referencia a un capítulo."""
    numero: str
    nombre: Optional[str]
    pagina: int
    reglas: list[ReglaRef] = field(default_factory=list)


@dataclass
class TituloRef:
    """Referencia a un título."""
    numero: str
    nombre: Optional[str]
    pagina: int
    capitulos: list[CapituloRef] = field(default_factory=list)


def es_centrado(x_min: float, x_max: float) -> bool:
    """Determina si un elemento está centrado en la página."""
    centro_texto = (x_min + x_max) / 2
    return abs(centro_texto - CENTRO_PAGINA) < TOLERANCIA_CENTRADO


def es_bold(flags: int) -> bool:
    """Determina si el texto es bold."""
    return bool(flags & 2 ** 4)


def linea_es_bold(spans: list) -> bool:
    """
    Determina si una línea es bold.

    Considera bold si la mayoría del texto (no espacios) es bold.
    """
    texto_bold = 0
    texto_total = 0

    for span in spans:
        texto = span["text"]
        longitud = len(texto.strip())
        if longitud > 0:
            texto_total += longitud
            if es_bold(span["flags"]):
                texto_bold += longitud

    # Considerar bold si >80% del texto es bold
    return texto_total > 0 and (texto_bold / texto_total) > 0.8


def extraer_estructura(doc) -> list[TituloRef]:
    """
    Extrae la estructura jerárquica (Títulos/Capítulos) del PDF.

    Detecta:
    - Títulos: "Título X. Nombre" - centrado y bold
    - Capítulos: "Capítulo X.Y. Nombre" - centrado y bold
    """
    titulos = []
    titulo_actual = None

    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue

            for line in block["lines"]:
                # Reconstruir línea completa
                texto_linea = ""
                x_min = float('inf')
                x_max = 0

                for span in line["spans"]:
                    texto_linea += span["text"]
                    bbox = span["bbox"]
                    x_min = min(x_min, bbox[0])
                    x_max = max(x_max, bbox[2])

                texto_linea = texto_linea.strip()
                if not texto_linea:
                    continue

                # Solo procesar si está centrado y bold
                if not (es_centrado(x_min, x_max) and linea_es_bold(line["spans"])):
                    continue

                # ¿Es título?
                match = PATRON_TITULO.match(texto_linea)
                if match:
                    titulo_actual = TituloRef(
                        numero=match.group(1),
                        nombre=match.group(2).strip(),
                        pagina=page_num + 1
                    )
                    titulos.append(titulo_actual)
                    continue

                # ¿Es capítulo?
                match = PATRON_CAPITULO.match(texto_linea)
                if match:
                    if titulo_actual is None:
                        # Capítulo sin título - crear título implícito
                        titulo_actual = TituloRef(numero="0", nombre="Preliminar", pagina=1)
                        titulos.append(titulo_actual)

                    capitulo = CapituloRef(
                        numero=match.group(1),
                        nombre=match.group(2).strip(),
                        pagina=page_num + 1
                    )
                    titulo_actual.capitulos.append(capitulo)

    return titulos


def extraer_reglas(doc) -> list[ReglaRef]:
    """
    Extrae todas las reglas del PDF.

    Las reglas se identifican por:
    - Patrón X.Y.Z. o X.Y.Z.W. al inicio de línea
    - Bold
    - Posición X cerca del margen izquierdo
    """
    reglas = []
    reglas_vistas = set()

    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue

            for line in block["lines"]:
                for span in line["spans"]:
                    texto = span["text"].strip()
                    x = span["bbox"][0]

                    # Verificar si es número de regla (bold y en posición X~99)
                    match = PATRON_REGLA.match(texto)
                    if match and es_bold(span["flags"]) and abs(x - X_REGLA) < X_TOLERANCIA:
                        numero = match.group(1)

                        # Evitar duplicados (misma regla en varias páginas)
                        if numero not in reglas_vistas:
                            reglas_vistas.add(numero)
                            reglas.append(ReglaRef(
                                numero=numero,
                                pagina=page_num + 1
                            ))

    return reglas


def extraer_contenido(doc, reglas: list[ReglaRef]) -> dict[str, ReglaContenido]:
    """
    Extrae el contenido de cada regla del PDF.

    Args:
        doc: Documento PyMuPDF
        reglas: Lista de reglas con sus páginas

    Returns:
        Diccionario {numero_regla: ReglaContenido}
    """
    contenido = {}

    # Crear índice de reglas por página para saber cuándo termina cada una
    reglas_por_pagina = {}
    for regla in reglas:
        if regla.pagina not in reglas_por_pagina:
            reglas_por_pagina[regla.pagina] = []
        reglas_por_pagina[regla.pagina].append(regla.numero)

    # Ordenar reglas para saber la siguiente
    reglas_ordenadas = sorted([r.numero for r in reglas], key=lambda x: [int(p) for p in x.split('.')])
    siguiente_regla = {reglas_ordenadas[i]: reglas_ordenadas[i+1] for i in range(len(reglas_ordenadas)-1)}

    regla_actual = None
    parrafos_actuales = []
    nombre_regla = None
    texto_acumulado = ""
    tipo_parrafo = "texto"
    numero_parrafo = None
    y_anterior = None  # Para detectar saltos de párrafo
    titulo_pendiente = None  # Título bold que aparece antes del número de regla
    referencias_encontradas = False  # True después de encontrar referencias (fin de contenido)

    # Umbral para detectar nuevo párrafo (salto de línea mayor a lo normal)
    SALTO_PARRAFO = 12.5  # Líneas normales ~11, párrafos nuevos ~14

    def guardar_parrafo():
        nonlocal texto_acumulado, tipo_parrafo, numero_parrafo
        if texto_acumulado.strip():
            parrafos_actuales.append(Parrafo(
                tipo=tipo_parrafo,
                contenido=texto_acumulado.strip(),
                numero=numero_parrafo
            ))
        texto_acumulado = ""
        tipo_parrafo = "texto"
        numero_parrafo = None

    def guardar_regla():
        nonlocal regla_actual, parrafos_actuales, nombre_regla, y_anterior, referencias_encontradas
        if regla_actual:
            guardar_parrafo()

            # Filtrar párrafos de referencias y extraerlos
            parrafos_finales = []
            referencias_lista = []
            for p in parrafos_actuales:
                if p.tipo == "referencias":
                    referencias_lista.append(p.contenido)
                else:
                    parrafos_finales.append(p)

            referencias = " ".join(referencias_lista) if referencias_lista else None

            contenido[regla_actual] = ReglaContenido(
                numero=regla_actual,
                nombre=nombre_regla,
                parrafos=parrafos_finales,
                referencias=referencias
            )
        regla_actual = None
        parrafos_actuales = []
        nombre_regla = None
        y_anterior = None
        referencias_encontradas = False

    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue

            for line in block["lines"]:
                # Reconstruir línea y obtener coordenadas
                texto_linea = ""
                x_min = float('inf')
                y_actual = line["bbox"][1]

                for span in line["spans"]:
                    texto_linea += span["text"]
                    x_min = min(x_min, span["bbox"][0])

                texto_linea = texto_linea.strip()
                if not texto_linea:
                    continue

                # Detectar si la línea es bold
                es_bold = linea_es_bold(line["spans"])

                # ¿Es inicio de nueva regla?
                match_regla = PATRON_REGLA_INICIO.match(texto_linea)
                if match_regla and abs(x_min - X_REGLA) < X_TOLERANCIA:
                    numero = match_regla.group(1)
                    if numero in [r.numero for r in reglas]:
                        guardar_regla()
                        regla_actual = numero
                        y_anterior = None  # Reset para nueva regla

                        # Usar título pendiente si existe
                        if titulo_pendiente:
                            nombre_regla = titulo_pendiente
                            titulo_pendiente = None

                        # O extraer nombre si está en la misma línea
                        if not nombre_regla:
                            resto = texto_linea[match_regla.end():].strip()
                            if resto:
                                nombre_regla = resto
                        continue

                # Detectar Título/Capítulo (limpia titulo_pendiente porque es nueva sección)
                if PATRON_TITULO.match(texto_linea) or PATRON_CAPITULO.match(texto_linea):
                    titulo_pendiente = None
                    continue

                # Bold en X_TEXTO que NO es fracción → título de siguiente regla
                if es_bold and abs(x_min - X_TEXTO) < X_TOLERANCIA:
                    if not PATRON_FRACCION.match(texto_linea):
                        # Es título de la siguiente regla
                        if titulo_pendiente:
                            titulo_pendiente += " " + texto_linea
                        else:
                            titulo_pendiente = texto_linea
                        continue

                # Si no estamos en una regla, saltar
                if not regla_actual:
                    continue

                # NO bold en X_TEXTO → posible referencia
                # Detectar si la línea es itálica
                es_italica = linea_es_italica(line["spans"])

                if not es_bold and abs(x_min - X_TEXTO) < X_TOLERANCIA:
                    # Referencia si: empieza con código de ley O es itálica
                    if PATRON_REFERENCIAS.match(texto_linea) or es_italica:
                        guardar_parrafo()
                        parrafos_actuales.append(Parrafo(
                            tipo="referencias",
                            contenido=texto_linea
                        ))
                        continue

                # Clasificar por posición X y contenido
                if abs(x_min - X_CONTENIDO_NUM) < X_TOLERANCIA:
                    # Contenido de numeral (x4)
                    if texto_acumulado:
                        texto_acumulado += " " + texto_linea
                    else:
                        texto_acumulado = texto_linea
                elif abs(x_min - X_NUMERAL) < X_TOLERANCIA:
                    # Numeral 1., 2., 3. (x3)
                    match_numeral = PATRON_NUMERAL.match(texto_linea)
                    if match_numeral:
                        guardar_parrafo()
                        tipo_parrafo = "numeral"
                        numero_parrafo = match_numeral.group(1)
                        texto_acumulado = texto_linea[match_numeral.end():].strip()
                    else:
                        # Continuación de numeral
                        texto_acumulado += " " + texto_linea
                elif abs(x_min - X_INCISO) < X_TOLERANCIA:
                    # Inciso a), b), c)
                    match_inciso = PATRON_INCISO.match(texto_linea)
                    if match_inciso:
                        guardar_parrafo()
                        tipo_parrafo = "inciso"
                        numero_parrafo = match_inciso.group(1)
                        texto_acumulado = texto_linea[match_inciso.end():].strip()
                    else:
                        # Continuación de inciso
                        texto_acumulado += " " + texto_linea
                elif abs(x_min - X_TEXTO) < X_TOLERANCIA:
                    # Texto normal o fracción
                    match_fraccion = PATRON_FRACCION.match(texto_linea)
                    if match_fraccion:
                        guardar_parrafo()
                        tipo_parrafo = "fraccion"
                        numero_parrafo = match_fraccion.group(1)
                        # El contenido viene en líneas siguientes
                    else:
                        # Detectar si es nuevo párrafo por salto de Y
                        es_nuevo_parrafo = (
                            y_anterior is not None and
                            (y_actual - y_anterior) > SALTO_PARRAFO and
                            texto_acumulado  # Solo si hay texto previo
                        )

                        if es_nuevo_parrafo:
                            guardar_parrafo()
                            texto_acumulado = texto_linea
                        elif texto_acumulado:
                            texto_acumulado += " " + texto_linea
                        else:
                            texto_acumulado = texto_linea
                else:
                    # Otra posición - probablemente continuación
                    if texto_acumulado:
                        texto_acumulado += " " + texto_linea

                # Actualizar Y anterior
                y_anterior = y_actual

    # Guardar última regla
    guardar_regla()

    return contenido


def asignar_reglas_a_capitulos(titulos: list[TituloRef], reglas: list[ReglaRef]):
    """
    Asigna reglas a capítulos basándose en la numeración.

    La regla 2.1.5 pertenece al capítulo 2.1.
    La regla 3.10.2 pertenece al capítulo 3.10.
    """
    # Crear índice de capítulos por número
    capitulos_idx = {}
    for titulo in titulos:
        for cap in titulo.capitulos:
            capitulos_idx[cap.numero] = cap

    # Asignar cada regla
    for regla in reglas:
        # Extraer número de capítulo de la regla (primeros dos segmentos)
        partes = regla.numero.split('.')
        if len(partes) >= 2:
            cap_num = f"{partes[0]}.{partes[1]}"
            if cap_num in capitulos_idx:
                capitulos_idx[cap_num].reglas.append(regla)


def verificar_integridad(titulos: list[TituloRef], reglas: list[ReglaRef]) -> dict:
    """
    Verifica la integridad de la extracción.

    Returns:
        dict con estadísticas y errores encontrados
    """
    resultado = {
        "ok": True,
        "titulos": len(titulos),
        "capitulos": sum(len(t.capitulos) for t in titulos),
        "reglas_total": len(reglas),
        "reglas_asignadas": 0,
        "reglas_huerfanas": [],
        "capitulos_vacios": [],
        "errores": []
    }

    # Contar reglas asignadas
    for titulo in titulos:
        for cap in titulo.capitulos:
            resultado["reglas_asignadas"] += len(cap.reglas)
            if not cap.reglas:
                resultado["capitulos_vacios"].append(cap.numero)

    # Verificar que todas las reglas fueron asignadas
    reglas_asignadas_set = set()
    for titulo in titulos:
        for cap in titulo.capitulos:
            for regla in cap.reglas:
                reglas_asignadas_set.add(regla.numero)

    for regla in reglas:
        if regla.numero not in reglas_asignadas_set:
            resultado["reglas_huerfanas"].append(regla.numero)

    # Determinar si hay errores
    if resultado["reglas_huerfanas"]:
        resultado["ok"] = False
        resultado["errores"].append(f"{len(resultado['reglas_huerfanas'])} reglas sin capítulo asignado")

    if resultado["reglas_asignadas"] != resultado["reglas_total"]:
        resultado["ok"] = False
        resultado["errores"].append(
            f"Discrepancia: {resultado['reglas_asignadas']} asignadas vs {resultado['reglas_total']} totales"
        )

    return resultado


def generar_json_contenido(titulos: list[TituloRef], contenido: dict[str, ReglaContenido]) -> dict:
    """Genera JSON de contenido (equivalente a contenido.json)."""
    resultado = {"articulos": []}

    orden = 0
    for titulo in titulos:
        for cap in titulo.capitulos:
            for regla_ref in cap.reglas:
                orden += 1
                regla = contenido.get(regla_ref.numero)

                if regla:
                    articulo = {
                        "numero": regla.numero,
                        "orden": orden,
                        "tipo": "regla",
                        "division": f"Título {titulo.numero} > Capítulo {cap.numero}",
                        "nombre": regla.nombre,
                        "parrafos": [],
                        "referencias": regla.referencias
                    }

                    for idx, p in enumerate(regla.parrafos, start=1):
                        parrafo = {
                            "tipo": p.tipo,
                            "contenido": p.contenido,
                            "numero": idx,  # Orden secuencial (SMALLINT)
                            "identificador": p.numero  # Identificador original ('I', 'a)', etc.)
                        }
                        articulo["parrafos"].append(parrafo)

                    resultado["articulos"].append(articulo)
                else:
                    # Regla sin contenido extraído
                    resultado["articulos"].append({
                        "numero": regla_ref.numero,
                        "orden": orden,
                        "tipo": "regla",
                        "division": f"Título {titulo.numero} > Capítulo {cap.numero}",
                        "nombre": None,
                        "parrafos": [],
                        "referencias": None
                    })

    return resultado


def generar_json_estructura(titulos: list[TituloRef]) -> dict:
    """Genera JSON de estructura (equivalente a mapa_estructura.json)."""
    resultado = {"titulos": {}}

    total_capitulos = 0
    total_reglas = 0

    for titulo in titulos:
        titulo_data = {
            "nombre": titulo.nombre,
            "pagina": titulo.pagina,
            "capitulos": {}
        }

        for cap in titulo.capitulos:
            total_capitulos += 1
            cap_data = {
                "nombre": cap.nombre,
                "pagina": cap.pagina,
                "articulos": [r.numero for r in cap.reglas]  # Usamos "articulos" para compatibilidad
            }
            total_reglas += len(cap.reglas)
            titulo_data["capitulos"][cap.numero] = cap_data

        resultado["titulos"][titulo.numero] = titulo_data

    resultado["estadisticas"] = {
        "titulos": len(titulos),
        "capitulos": total_capitulos,
        "secciones": 0,
        "articulos_vigentes": total_reglas,
        "articulos_derogados": 0,
        "articulos_transitorios": 0,
        "total": total_reglas
    }

    return resultado


def imprimir_estructura(titulos: list[TituloRef]):
    """Imprime la estructura en formato legible."""
    total_reglas = 0

    for titulo in titulos:
        print(f"\nTítulo {titulo.numero}: {titulo.nombre} (pág. {titulo.pagina})")

        for cap in titulo.capitulos:
            n_reglas = len(cap.reglas)
            total_reglas += n_reglas

            if cap.reglas:
                primera = cap.reglas[0].numero
                ultima = cap.reglas[-1].numero
                rango = f"{primera} ... {ultima}" if n_reglas > 2 else ", ".join(r.numero for r in cap.reglas)
            else:
                rango = "(sin reglas)"

            print(f"  Capítulo {cap.numero}: {cap.nombre}")
            print(f"    Reglas: {rango} ({n_reglas})")

    print(f"\n{'='*60}")
    print(f"RESUMEN:")
    print(f"  Títulos:   {len(titulos)}")
    print(f"  Capítulos: {sum(len(t.capitulos) for t in titulos)}")
    print(f"  Reglas:    {total_reglas}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python backend/etl/extraer_rmf.py <CODIGO>")
        print("     python backend/etl/extraer_rmf.py RMF --solo-estructura")
        sys.exit(1)

    codigo = sys.argv[1].upper()
    solo_estructura = "--solo-estructura" in sys.argv
    solo_contenido = "--solo-contenido" in sys.argv

    if codigo not in RMF_CONFIG:
        print(f"Error: '{codigo}' no configurado. Disponibles: {list(RMF_CONFIG.keys())}")
        sys.exit(1)

    config = RMF_CONFIG[codigo]
    pdf_path = BASE_DIR / config["pdf_path"]

    if not pdf_path.exists():
        print(f"Error: PDF no encontrado: {pdf_path}")
        sys.exit(1)

    print("=" * 60)
    print(f"EXTRACTOR RMF: {codigo}")
    print("=" * 60)

    doc = fitz.open(str(pdf_path))
    print(f"\nPDF: {pdf_path.name} ({len(doc)} páginas)")

    # 1. Extraer estructura
    print("\n1. Extrayendo estructura (Títulos/Capítulos)...")
    titulos = extraer_estructura(doc)
    print(f"   Encontrados: {len(titulos)} títulos, {sum(len(t.capitulos) for t in titulos)} capítulos")

    # 2. Extraer reglas
    print("\n2. Extrayendo reglas...")
    reglas = extraer_reglas(doc)
    print(f"   Encontradas: {len(reglas)} reglas")

    # 3. Asignar reglas a capítulos
    print("\n3. Asignando reglas a capítulos...")
    asignar_reglas_a_capitulos(titulos, reglas)

    # 4. Verificar integridad
    print("\n4. Verificando integridad...")
    integridad = verificar_integridad(titulos, reglas)

    if integridad["ok"]:
        print("   OK: Integridad verificada")
    else:
        print("   ADVERTENCIAS:")
        for err in integridad["errores"]:
            print(f"     - {err}")
        if integridad["reglas_huerfanas"]:
            print(f"     Reglas huérfanas (primeras 10): {integridad['reglas_huerfanas'][:10]}")

    # 5. Extraer contenido (si no es solo-estructura)
    contenido = {}
    if not solo_estructura:
        print("\n5. Extrayendo contenido de reglas...")
        contenido = extraer_contenido(doc, reglas)
        reglas_con_contenido = sum(1 for r in contenido.values() if r.parrafos)
        reglas_con_refs = sum(1 for r in contenido.values() if r.referencias)
        print(f"   Reglas con contenido: {reglas_con_contenido}")
        print(f"   Reglas con referencias: {reglas_con_refs}")

    # 6. Mostrar estructura
    print("\n6. Estructura extraída:")
    imprimir_estructura(titulos)

    # 7. Guardar JSON
    output_dir = pdf_path.parent

    if not solo_contenido:
        mapa_path = output_dir / "mapa_estructura.json"
        print(f"\n7a. Guardando {mapa_path.name}...")

        mapa_json = generar_json_estructura(titulos)
        mapa_json["ley"] = codigo
        mapa_json["fuente"] = config.get("url_fuente", "")
        mapa_json["metodo"] = "texto"
        mapa_json["notas"] = "Extraído del texto del PDF (sin outline)."

        with open(mapa_path, 'w', encoding='utf-8') as f:
            json.dump(mapa_json, f, ensure_ascii=False, indent=2)
        print("   Guardado")

    if not solo_estructura and contenido:
        contenido_path = output_dir / "contenido.json"
        print(f"\n7b. Guardando {contenido_path.name}...")

        contenido_json = generar_json_contenido(titulos, contenido)
        contenido_json["ley"] = codigo
        contenido_json["fuente"] = config.get("url_fuente", "")

        with open(contenido_path, 'w', encoding='utf-8') as f:
            json.dump(contenido_json, f, ensure_ascii=False, indent=2)
        print(f"   Guardado ({len(contenido_json['articulos'])} reglas)")

    doc.close()

    print("\n" + "=" * 60)
    print("EXTRACCIÓN COMPLETADA")
    if not integridad["ok"]:
        print("ADVERTENCIA: Hay problemas de integridad - revisar")
    print("=" * 60)

    return 0 if integridad["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
