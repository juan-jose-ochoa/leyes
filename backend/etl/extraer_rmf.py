#!/usr/bin/env python3
"""
Extractor de estructura y contenido para RMF (Resolución Miscelánea Fiscal).

A diferencia de las leyes, RMF:
- No tiene outline en el PDF
- Usa numeración decimal jerárquica (2.1.1, 3.10.5)
- La estructura se deriva de la numeración
- Las referencias legales van al final de cada regla

Uso:
    python backend/etl/extraer_rmf.py RMF2026
    python backend/etl/extraer_rmf.py RMF2026 --solo-estructura
    python backend/etl/extraer_rmf.py RMF2026 --solo-contenido
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
    "RMF2026": {
        "nombre": "Resolución Miscelánea Fiscal para 2026",
        "nombre_corto": "RMF 2026",
        "tipo": "resolucion",
        "url_fuente": "https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/normatividad_rmf_rgce2026.html",
        "pdf_path": "backend/etl/data/rmf2026/rmf_2026_original.pdf",
    },
    "RMF2025": {
        "nombre": "Resolución Miscelánea Fiscal para 2025",
        "nombre_corto": "RMF 2025",
        "tipo": "resolucion",
        "url_fuente": "https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/normatividad_rmf_rgce2025.html",
        "pdf_path": "backend/etl/data/rmf2025/rmf_2025_compilada.pdf",
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
PATRON_REFERENCIAS = re.compile(r'^(CFF|LISR|LIVA|LIEPS|LIF|RCFF|RMF|RISR|Ley|CPEUM)\s')


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

                    # Verificar si es número de regla
                    match = PATRON_REGLA.match(texto)
                    if match and es_bold(span["flags"]):
                        numero = match.group(1)

                        # Evitar duplicados (misma regla en varias páginas)
                        if numero not in reglas_vistas:
                            reglas_vistas.add(numero)
                            reglas.append(ReglaRef(
                                numero=numero,
                                pagina=page_num + 1
                            ))

    return reglas


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
        print("     python backend/etl/extraer_rmf.py RMF2026 --solo-estructura")
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

    # 5. Mostrar estructura
    print("\n5. Estructura extraída:")
    imprimir_estructura(titulos)

    # 6. Guardar JSON
    output_dir = pdf_path.parent

    if not solo_contenido:
        mapa_path = output_dir / "mapa_estructura.json"
        print(f"\n6. Guardando {mapa_path.name}...")

        mapa_json = generar_json_estructura(titulos)
        mapa_json["ley"] = codigo
        mapa_json["fuente"] = config.get("url_fuente", "")
        mapa_json["metodo"] = "texto"
        mapa_json["notas"] = "Extraído del texto del PDF (sin outline)."

        with open(mapa_path, 'w', encoding='utf-8') as f:
            json.dump(mapa_json, f, ensure_ascii=False, indent=2)
        print("   Guardado")

    doc.close()

    print("\n" + "=" * 60)
    print("EXTRACCIÓN COMPLETADA")
    if not integridad["ok"]:
        print("ADVERTENCIA: Hay problemas de integridad - revisar")
    print("=" * 60)

    return 0 if integridad["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
