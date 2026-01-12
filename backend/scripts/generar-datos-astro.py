#!/usr/bin/env python3
"""
Genera JSON optimizado para Astro SSG.

Lee los datos de ETL (contenido.json, mapa_estructura.json) y genera:
- frontend-astro/src/data/catalogo.json - Lista de leyes con metadatos
- frontend-astro/src/data/{ley}/articulos.json - Artículos por ley
- frontend-astro/src/data/{ley}/estructura.json - Divisiones por ley

Uso:
    python backend/scripts/generar-datos-astro.py
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Agregar backend/etl al path para importar config
sys.path.insert(0, str(Path(__file__).parent.parent / "etl"))
from config import LEYES

# Rutas
PROJECT_ROOT = Path(__file__).parent.parent.parent
ETL_DATA = PROJECT_ROOT / "backend" / "etl" / "data"
ASTRO_DATA = PROJECT_ROOT / "frontend-astro" / "src" / "data"


def cargar_contenido(ley_codigo: str) -> dict | None:
    """Carga contenido.json de una ley."""
    path = ETL_DATA / ley_codigo.lower() / "contenido.json"
    if not path.exists():
        print(f"  ⚠ No existe: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cargar_estructura(ley_codigo: str) -> dict | None:
    """Carga mapa_estructura.json de una ley."""
    path = ETL_DATA / ley_codigo.lower() / "mapa_estructura.json"
    if not path.exists():
        print(f"  ⚠ No existe estructura: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generar_articulos_json(contenido: dict, ley_config: dict) -> list:
    """
    Transforma contenido.json a formato optimizado para Astro.

    Estructura de salida por artículo:
    {
        "numero": "1o",
        "tipo": "articulo",
        "orden": 1,
        "pagina": 1,
        "y": 434,  # Coordenada Y del primer párrafo
        "contenido": "Texto completo...",
        "parrafos": [...]  # Opcional, para vista detallada
    }
    """
    articulos = []

    for art in contenido.get("articulos", []):
        # Concatenar contenido de todos los párrafos
        contenido_texto = "\n\n".join(
            p.get("contenido", "") for p in art.get("parrafos", [])
        )

        # Obtener coordenadas del primer párrafo
        primer_parrafo = art.get("parrafos", [{}])[0] if art.get("parrafos") else {}

        articulo_astro = {
            "numero": art.get("numero"),
            "tipo": art.get("tipo", "articulo"),
            "orden": art.get("orden"),
            "pagina": art.get("pagina") or primer_parrafo.get("pagina", 1),
            "y": primer_parrafo.get("y", 0),
            "contenido": contenido_texto,
            "parrafos": art.get("parrafos", []),
            "referencias": art.get("referencias"),
        }

        articulos.append(articulo_astro)

    return articulos


def generar_estructura_json(mapa: dict) -> dict:
    """
    Transforma mapa_estructura.json a formato optimizado para Astro.

    Mantiene la jerarquía pero simplifica para navegación.
    """
    if not mapa:
        return {}

    estructura = {
        "ley": mapa.get("ley"),
        "estadisticas": mapa.get("estadisticas", {}),
        "divisiones": []
    }

    # Procesar títulos -> capítulos -> secciones
    for titulo_num, titulo_data in mapa.get("titulos", {}).items():
        titulo = {
            "tipo": "titulo",
            "numero": titulo_num,
            "nombre": titulo_data.get("nombre"),
            "pagina": titulo_data.get("pagina"),
            "hijos": []
        }

        for cap_num, cap_data in titulo_data.get("capitulos", {}).items():
            capitulo = {
                "tipo": "capitulo",
                "numero": cap_num,
                "nombre": cap_data.get("nombre"),
                "pagina": cap_data.get("pagina"),
                "articulos": cap_data.get("articulos", []),
                "hijos": []
            }

            # Secciones si existen
            for sec_num, sec_data in cap_data.get("secciones", {}).items():
                seccion = {
                    "tipo": "seccion",
                    "numero": sec_num,
                    "nombre": sec_data.get("nombre"),
                    "pagina": sec_data.get("pagina"),
                    "articulos": sec_data.get("articulos", []),
                }
                capitulo["hijos"].append(seccion)

            titulo["hijos"].append(capitulo)

        estructura["divisiones"].append(titulo)

    # Procesar libros si existen (para algunas leyes como LSS)
    for libro_num, libro_data in mapa.get("libros", {}).items():
        libro = {
            "tipo": "libro",
            "numero": libro_num,
            "nombre": libro_data.get("nombre"),
            "pagina": libro_data.get("pagina"),
            "hijos": []
        }

        for titulo_num, titulo_data in libro_data.get("titulos", {}).items():
            titulo = {
                "tipo": "titulo",
                "numero": titulo_num,
                "nombre": titulo_data.get("nombre"),
                "pagina": titulo_data.get("pagina"),
                "articulos": titulo_data.get("articulos", []),
                "hijos": []
            }
            libro["hijos"].append(titulo)

        estructura["divisiones"].append(libro)

    return estructura


def generar_catalogo() -> dict:
    """
    Genera catálogo de todas las leyes con metadatos.
    """
    catalogo = {
        "_generado": datetime.now().isoformat(),
        "_version": "1.1",
        "leyes": []
    }

    for codigo, config in LEYES.items():
        # Cargar estadísticas si existen
        estructura = cargar_estructura(codigo)
        stats = estructura.get("estadisticas", {}) if estructura else {}

        # Cargar contenido para ultima_reforma_dof
        contenido = cargar_contenido(codigo)
        ultima_reforma = contenido.get("ultima_reforma_dof") if contenido else None

        ley = {
            "codigo": codigo,
            "nombre": config.get("nombre"),
            "nombre_corto": config.get("nombre_corto"),
            "tipo": config.get("tipo"),
            "categoria": config.get("categoria"),
            "reglamentos": config.get("reglamentos"),
            "reglamento_de": config.get("reglamento_de"),
            "url_fuente": config.get("url_fuente"),
            "tipo_contenido": config.get("tipo_contenido", "articulo"),
            "total_articulos": stats.get("total", 0) or stats.get("articulos_vigentes", 0),
            "divisiones_permitidas": config.get("divisiones_permitidas", []),
            "ultima_reforma_dof": ultima_reforma,
        }

        # Eliminar campos None
        ley = {k: v for k, v in ley.items() if v is not None}

        catalogo["leyes"].append(ley)

    # Orden de leyes por frecuencia de consulta (UX priority)
    ORDEN_LEYES = [
        'CFF', 'LISR', 'LIVA', 'RMF', 'LIF', 'LIEPS', 'LA', 'LFDC',
        'LFT', 'LSS', 'LINFONAVIT', 'LISSSTE',
        'CPEUM',
        # Reglamentos al final, ordenados por ley base
        'RCFF', 'RLISR', 'RLIVA', 'RLIEPS', 'RLFT', 'RACERF', 'RLSS',
    ]

    def orden_key(ley):
        try:
            return ORDEN_LEYES.index(ley["codigo"])
        except ValueError:
            return 999  # Al final si no está en la lista

    catalogo["leyes"].sort(key=orden_key)

    return catalogo


def guardar_json(data: dict | list, path: Path):
    """Guarda JSON con formato legible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ {path.relative_to(PROJECT_ROOT)}")


def main():
    print("=" * 60)
    print("Generando datos para Astro SSG")
    print("=" * 60)

    # Crear directorio base
    ASTRO_DATA.mkdir(parents=True, exist_ok=True)

    # 1. Generar catálogo
    print("\n[1/3] Generando catálogo de leyes...")
    catalogo = generar_catalogo()
    guardar_json(catalogo, ASTRO_DATA / "catalogo.json")

    # 2. Generar datos por ley
    print("\n[2/3] Generando artículos por ley...")
    leyes_procesadas = 0
    articulos_total = 0

    for codigo in LEYES.keys():
        print(f"\n  Procesando {codigo}...")

        contenido = cargar_contenido(codigo)
        if not contenido:
            continue

        articulos = generar_articulos_json(contenido, LEYES[codigo])
        if articulos:
            ley_dir = ASTRO_DATA / codigo.lower()
            guardar_json(articulos, ley_dir / "articulos.json")
            leyes_procesadas += 1
            articulos_total += len(articulos)

    # 3. Generar estructura por ley
    print("\n[3/3] Generando estructura por ley...")

    for codigo in LEYES.keys():
        mapa = cargar_estructura(codigo)
        if not mapa:
            continue

        estructura = generar_estructura_json(mapa)
        if estructura:
            ley_dir = ASTRO_DATA / codigo.lower()
            guardar_json(estructura, ley_dir / "estructura.json")

    # Resumen
    print("\n" + "=" * 60)
    print("Resumen:")
    print(f"  - Leyes procesadas: {leyes_procesadas}")
    print(f"  - Artículos totales: {articulos_total}")
    print(f"  - Destino: {ASTRO_DATA.relative_to(PROJECT_ROOT)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
