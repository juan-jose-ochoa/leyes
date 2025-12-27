#!/usr/bin/env python3
"""
Importa el índice oficial del PDF a PostgreSQL.

Uso:
    python scripts/importar_indice.py [--ley RMF2025]
"""

import json
import os
import sys
import argparse
from pathlib import Path

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 no instalado. Ejecuta: pip install psycopg2-binary")
    sys.exit(1)

BASE_DIR = Path(__file__).parent.parent

# Cargar .env
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

PG_CONFIG = {
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": int(os.environ.get("PG_PORT", "5432")),
    "database": os.environ.get("PG_DB", "leyesmx"),
    "user": os.environ.get("PG_USER", "leyesmx"),
    "password": os.environ.get("PG_PASS", "leyesmx")
}


def importar_indice(ley_codigo: str, indice_path: Path):
    """Importa el índice JSON a PostgreSQL."""

    # Cargar JSON
    with open(indice_path, 'r', encoding='utf-8') as f:
        indice = json.load(f)

    # Conectar
    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()

    # Eliminar índice existente para esta ley
    cursor.execute("DELETE FROM indice_oficial WHERE ley_codigo = %s", (ley_codigo,))
    print(f"Eliminado índice anterior de {ley_codigo}")

    # Insertar títulos
    for item in indice.get('titulos', []):
        cursor.execute("""
            INSERT INTO indice_oficial (ley_codigo, tipo, numero, nombre, pagina)
            VALUES (%s, %s, %s, %s, %s)
        """, (ley_codigo, 'titulo', item['numero'], item['nombre'], item.get('pagina')))

    # Insertar capítulos
    for item in indice.get('capitulos', []):
        cursor.execute("""
            INSERT INTO indice_oficial (ley_codigo, tipo, numero, nombre, pagina)
            VALUES (%s, %s, %s, %s, %s)
        """, (ley_codigo, 'capitulo', item['numero'], item['nombre'], item.get('pagina')))

    # Insertar secciones
    for item in indice.get('secciones', []):
        cursor.execute("""
            INSERT INTO indice_oficial (ley_codigo, tipo, numero, nombre, pagina)
            VALUES (%s, %s, %s, %s, %s)
        """, (ley_codigo, 'seccion', item['numero'], item['nombre'], item.get('pagina')))

    # Insertar subsecciones
    for item in indice.get('subsecciones', []):
        cursor.execute("""
            INSERT INTO indice_oficial (ley_codigo, tipo, numero, nombre, pagina)
            VALUES (%s, %s, %s, %s, %s)
        """, (ley_codigo, 'subseccion', item['numero'], item['nombre'], item.get('pagina')))

    # Insertar reglas
    for item in indice.get('reglas', []):
        cursor.execute("""
            INSERT INTO indice_oficial (ley_codigo, tipo, numero, nombre, pagina)
            VALUES (%s, %s, %s, %s, %s)
        """, (ley_codigo, 'regla', item['numero'], item.get('titulo'), item.get('pagina')))

    conn.commit()

    # Mostrar resumen
    cursor.execute("""
        SELECT tipo, COUNT(*) as total
        FROM indice_oficial
        WHERE ley_codigo = %s
        GROUP BY tipo
        ORDER BY tipo
    """, (ley_codigo,))

    print(f"\n=== Índice importado para {ley_codigo} ===")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description='Importar índice oficial a PostgreSQL')
    parser.add_argument('--ley', default='RMF2025', help='Código de la ley (default: RMF2025)')
    args = parser.parse_args()

    # Buscar archivo de índice
    indice_path = BASE_DIR / "doc/rmf/indice_rmf_2025.json"

    if not indice_path.exists():
        print(f"Error: No se encontró {indice_path}")
        print("Ejecuta primero: python scripts/rmf/pdf_extractor.py")
        sys.exit(1)

    print(f"Importando índice desde: {indice_path}")
    importar_indice(args.ley, indice_path)

    print("\nVerificando contra datos importados...")
    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM verificar_indice(%s)", (args.ley,))
    print(f"\n{'Categoría':<12} {'Oficial':>8} {'Importado':>10} {'Faltantes':>10} {'Extras':>8} {'%':>6}")
    print("-" * 60)
    for row in cursor.fetchall():
        print(f"{row[0]:<12} {row[1]:>8} {row[2]:>10} {row[3]:>10} {row[4]:>8} {row[5]:>6}")

    conn.close()


if __name__ == "__main__":
    main()
