#!/usr/bin/env python3
"""
Verificador de regresiones para el ETL de LeyesMX.

CUÁNDO USAR ESTE SCRIPT:
========================
1. ANTES de hacer commit de cambios en extraer.py, config.py o cualquier
   archivo del ETL que pueda afectar la extracción de contenido.

2. Después de modificar patrones regex en config.py (patrones de artículo,
   título, capítulo, sección).

3. Al agregar una nueva ley, para verificar que las leyes existentes
   no fueron afectadas.

USO:
====
    python backend/etl/verificar_regresion.py

    # Excluir ley nueva que aún no tiene baseline:
    python backend/etl/verificar_regresion.py --excluir LA

SALIDA:
=======
- Exit code 0: Sin regresiones detectadas
- Exit code 1: Regresión detectada (diferencia en artículos o párrafos)

FUNCIONAMIENTO:
===============
Para cada ley configurada en config.py:
1. Lee el contenido.json existente (baseline)
2. Re-ejecuta la extracción
3. Compara número de artículos y párrafos
4. Reporta diferencias
"""

import sys
from pathlib import Path

# Agregar directorio padre al path para imports
sys.path.insert(0, str(Path(__file__).parent))

import json
from config import listar_leyes, get_config

BASE_DIR = Path(__file__).parent.parent.parent


def cargar_baseline(codigo: str) -> dict | None:
    """Carga estadísticas del contenido.json existente."""
    config = get_config(codigo)

    # Saltar leyes sin PDF configurado (ej: RMF2025)
    if not config.get("pdf_path"):
        return None

    contenido_path = BASE_DIR / Path(config["pdf_path"]).parent / "contenido.json"

    if not contenido_path.exists():
        return None

    with open(contenido_path, encoding='utf-8') as f:
        data = json.load(f)

    articulos = data.get("articulos", [])
    total_parrafos = sum(len(a.get("parrafos", [])) for a in articulos)

    return {
        "articulos": len(articulos),
        "parrafos": total_parrafos
    }


def extraer_y_comparar(codigo: str, baseline: dict) -> tuple[bool, str]:
    """Re-extrae y compara contra baseline. Retorna (ok, mensaje)."""
    from extraer import Extractor

    try:
        extractor = Extractor(codigo)
        extractor.abrir_pdf()
        articulos = extractor.extraer_contenido()
        extractor.cerrar_pdf()
    except Exception as e:
        return False, f"Error extrayendo: {e}"

    nuevo = {
        "articulos": len(articulos),
        "parrafos": sum(len(a.parrafos) for a in articulos)
    }

    if nuevo["articulos"] != baseline["articulos"]:
        return False, f"Artículos: {baseline['articulos']} -> {nuevo['articulos']}"

    if nuevo["parrafos"] != baseline["parrafos"]:
        return False, f"Párrafos: {baseline['parrafos']} -> {nuevo['parrafos']}"

    return True, f"{nuevo['articulos']} arts, {nuevo['parrafos']} párrs"


def main():
    excluir = set()
    if "--excluir" in sys.argv:
        idx = sys.argv.index("--excluir")
        if idx + 1 < len(sys.argv):
            excluir.add(sys.argv[idx + 1].upper())

    print("=" * 60)
    print("VERIFICADOR DE REGRESIONES - LeyesMX ETL")
    print("=" * 60)

    leyes = [l for l in listar_leyes() if l not in excluir]

    if excluir:
        print(f"\nExcluyendo: {', '.join(excluir)}")

    print(f"\nVerificando {len(leyes)} leyes: {', '.join(leyes)}\n")

    resultados = []
    hay_regresion = False

    for codigo in leyes:
        baseline = cargar_baseline(codigo)

        if baseline is None:
            print(f"  {codigo}: SKIP (sin baseline)")
            continue

        ok, mensaje = extraer_y_comparar(codigo, baseline)

        if ok:
            print(f"  {codigo}: OK ({mensaje})")
        else:
            print(f"  {codigo}: REGRESIÓN - {mensaje}")
            hay_regresion = True

        resultados.append((codigo, ok, mensaje))

    print("\n" + "=" * 60)

    if hay_regresion:
        print("RESULTADO: REGRESIÓN DETECTADA")
        print("\nNo hacer commit hasta resolver las diferencias.")
        sys.exit(1)
    else:
        print("RESULTADO: Sin regresiones")
        sys.exit(0)


if __name__ == "__main__":
    main()
