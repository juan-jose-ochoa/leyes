#!/usr/bin/env python3
"""
Verificador de regresiones para el ETL de LeyesMX.

USO:
====
    python backend/etl/verificar_regresion.py

    # Excluir ley nueva que aún no tiene baseline:
    python backend/etl/verificar_regresion.py --excluir LSS

FUNCIONAMIENTO:
===============
1. Re-ejecuta extraer.py para cada ley (regenera contenido.json)
2. Usa git diff para detectar cambios
3. Muestra reporte con último artículo de cada ley modificada
4. El análisis es MANUAL: comparar git diff vs PDF

SALIDA:
=======
- Exit code 0: Sin cambios detectados
- Exit code 1: Hay cambios (revisar manualmente si son regresiones o correcciones)
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import listar_leyes, get_config

BASE_DIR = Path(__file__).parent.parent.parent


def extraer_ley(codigo: str) -> bool:
    """Ejecuta extraer.py para una ley. Retorna True si exitoso."""
    result = subprocess.run(
        [sys.executable, "backend/etl/extraer.py", codigo],
        cwd=BASE_DIR,
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def git_diff_stat(codigo: str) -> tuple[str | None, int, int]:
    """Retorna (diff_stat, insertions, deletions) para contenido.json."""
    config = get_config(codigo)
    if not config.get("pdf_path"):
        return None, 0, 0

    contenido_path = Path(config["pdf_path"]).parent / "contenido.json"

    # Get stat
    result = subprocess.run(
        ["git", "diff", "--stat", str(contenido_path)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True
    )
    stat = result.stdout.strip()

    # Get numstat for insertions/deletions
    result = subprocess.run(
        ["git", "diff", "--numstat", str(contenido_path)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True
    )
    nums = result.stdout.strip()
    insertions, deletions = 0, 0
    if nums:
        parts = nums.split()
        if len(parts) >= 2:
            insertions = int(parts[0]) if parts[0] != '-' else 0
            deletions = int(parts[1]) if parts[1] != '-' else 0

    return (stat if stat else None), insertions, deletions


def get_ultimo_articulo(codigo: str) -> dict | None:
    """Lee último artículo del contenido.json actual."""
    config = get_config(codigo)
    if not config.get("pdf_path"):
        return None

    contenido_path = BASE_DIR / Path(config["pdf_path"]).parent / "contenido.json"
    if not contenido_path.exists():
        return None

    with open(contenido_path, encoding='utf-8') as f:
        data = json.load(f)

    if not data.get("articulos"):
        return None

    ultimo = data["articulos"][-1]
    return {
        "numero": ultimo["numero"],
        "parrafos": len(ultimo.get("parrafos", [])),
        "ultimo_parrafo": ultimo["parrafos"][-1]["contenido"][:80] if ultimo.get("parrafos") else "N/A"
    }


def main():
    excluir = set()
    if "--excluir" in sys.argv:
        idx = sys.argv.index("--excluir")
        if idx + 1 < len(sys.argv):
            excluir.add(sys.argv[idx + 1].upper())

    print("=" * 70)
    print("VERIFICADOR DE REGRESIONES - LeyesMX ETL")
    print("=" * 70)

    leyes = [l for l in listar_leyes() if l not in excluir]

    if excluir:
        print(f"\nExcluyendo: {', '.join(excluir)}")

    print(f"\nVerificando {len(leyes)} leyes: {', '.join(leyes)}")

    # Paso 1: Extraer todas las leyes
    print("\n" + "-" * 70)
    print("PASO 1: Extrayendo contenido (regenerando contenido.json)")
    print("-" * 70)

    for codigo in leyes:
        config = get_config(codigo)
        if not config.get("pdf_path"):
            print(f"  {codigo}: SKIP (sin PDF)")
            continue

        if extraer_ley(codigo):
            print(f"  {codigo}: OK")
        else:
            print(f"  {codigo}: ERROR")

    # Paso 2: Verificar cambios con git diff
    print("\n" + "-" * 70)
    print("PASO 2: Detectando cambios (git diff)")
    print("-" * 70)

    cambios = []
    for codigo in leyes:
        config = get_config(codigo)
        if not config.get("pdf_path"):
            continue

        diff, ins, dels = git_diff_stat(codigo)
        if diff:
            cambios.append((codigo, ins, dels))
            print(f"  {codigo}: +{ins}/-{dels} líneas")
        else:
            print(f"  {codigo}: Sin cambios")

    # Paso 3: Reporte de último artículo para leyes con cambios
    if cambios:
        print("\n" + "-" * 70)
        print("PASO 3: Último artículo de leyes modificadas (para revisión manual)")
        print("-" * 70)

        for codigo, ins, dels in cambios:
            ultimo = get_ultimo_articulo(codigo)
            if ultimo:
                print(f"\n  {codigo} Art {ultimo['numero']}: {ultimo['parrafos']} párrafos")
                print(f"    Último: \"{ultimo['ultimo_parrafo']}...\"")

    # Resumen
    print("\n" + "=" * 70)

    if cambios:
        total_ins = sum(c[1] for c in cambios)
        total_dels = sum(c[2] for c in cambios)
        print(f"RESULTADO: {len(cambios)} leyes con cambios (+{total_ins}/-{total_dels} líneas)")
        print("\nPara revisar:")
        print("  git diff backend/etl/data/*/contenido.json")
        print("\nAnaliza manualmente comparando git diff vs PDF.")
        print("Si son correcciones, haz commit. Si son regresiones, investiga.")
        sys.exit(1)
    else:
        print("RESULTADO: Sin cambios - No hay regresiones")
        sys.exit(0)


if __name__ == "__main__":
    main()
