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
    python backend/etl/verificar_regresion.py --excluir LSS

SALIDA:
=======
- Exit code 0: Sin regresiones detectadas (git diff vacío)
- Exit code 1: Regresión detectada (hay cambios en contenido.json)

FUNCIONAMIENTO:
===============
1. Re-ejecuta extraer.py para cada ley configurada
2. Usa git diff para detectar cambios en contenido.json
3. Reporta diferencias
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import listar_leyes, get_config

BASE_DIR = Path(__file__).parent.parent.parent


def extraer_ley(codigo: str) -> bool:
    """Ejecuta extraer.py para una ley. Retorna True si exitoso."""
    config = get_config(codigo)
    if not config.get("pdf_path"):
        return False

    result = subprocess.run(
        [sys.executable, "backend/etl/extraer.py", codigo],
        cwd=BASE_DIR,
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def git_diff_stat(codigo: str) -> str | None:
    """Retorna git diff --stat para contenido.json de una ley, o None si no hay cambios."""
    config = get_config(codigo)
    if not config.get("pdf_path"):
        return None

    contenido_path = Path(config["pdf_path"]).parent / "contenido.json"

    result = subprocess.run(
        ["git", "diff", "--stat", str(contenido_path)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True
    )

    output = result.stdout.strip()
    return output if output else None


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

    print(f"\nVerificando {len(leyes)} leyes: {', '.join(leyes)}")
    print("\n1. Extrayendo contenido...")

    for codigo in leyes:
        config = get_config(codigo)
        if not config.get("pdf_path"):
            print(f"   {codigo}: SKIP (sin PDF)")
            continue

        if extraer_ley(codigo):
            print(f"   {codigo}: OK")
        else:
            print(f"   {codigo}: ERROR")

    print("\n2. Verificando cambios con git diff...")

    hay_regresion = False
    for codigo in leyes:
        diff = git_diff_stat(codigo)
        if diff:
            print(f"   {codigo}: CAMBIOS DETECTADOS")
            print(f"      {diff}")
            hay_regresion = True
        else:
            config = get_config(codigo)
            if config.get("pdf_path"):
                print(f"   {codigo}: Sin cambios")

    print("\n" + "=" * 60)

    if hay_regresion:
        print("RESULTADO: CAMBIOS DETECTADOS")
        print("\nRevisa los cambios con: git diff backend/etl/data/*/contenido.json")
        print("Si son correctos, haz commit. Si no, investiga.")
        sys.exit(1)
    else:
        print("RESULTADO: Sin regresiones")
        sys.exit(0)


if __name__ == "__main__":
    main()
