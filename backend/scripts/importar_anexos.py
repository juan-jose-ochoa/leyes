#!/usr/bin/env python3
"""
Importador de Anexos de la RMF

Lee los archivos JSON parseados de los anexos y carga a PostgreSQL.
- Anexo 1-A: Fichas de trámite (tipo='ficha')
- Anexo 3: Criterios no vinculativos (tipo='criterio')
"""

import json
import os
import sys
from pathlib import Path

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 no instalado. Ejecuta: pip install psycopg2-binary")
    sys.exit(1)

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).parent.parent.parent
RMF_DIR = BASE_DIR / "doc" / "rmf"

# Cargar .env si existe
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

# Configuración de PostgreSQL
PG_CONFIG = {
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": int(os.environ.get("PG_PORT", "5432")),
    "database": os.environ.get("PG_DB", "leyesmx"),
    "user": os.environ.get("PG_USER", "leyesmx"),
    "password": os.environ.get("PG_PASS", "leyesmx")
}


def obtener_ley_padre(cursor, codigo_padre: str) -> int:
    """Obtiene el ID de la ley padre (RMF2025)."""
    cursor.execute(
        "SELECT id FROM leyes WHERE codigo = %s",
        (codigo_padre,)
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Ley padre '{codigo_padre}' no encontrada. Importa primero la RMF.")
    return row[0]


def insertar_anexo(cursor, codigo: str, nombre: str, ley_padre_id: int) -> int:
    """Inserta un anexo como ley con tipo='anexo' y retorna su ID."""
    cursor.execute("""
        INSERT INTO leyes (codigo, nombre, nombre_corto, tipo, ley_padre_id)
        VALUES (%s, %s, %s, 'anexo', %s)
        RETURNING id
    """, (codigo, nombre, codigo, ley_padre_id))
    return cursor.fetchone()[0]


def importar_anexo_1a(cursor, ley_padre_id: int):
    """Importa las fichas de trámite del Anexo 1-A."""
    json_path = RMF_DIR / "anexo_1a_fichas.json"

    if not json_path.exists():
        print(f"   ERROR: No existe {json_path.name}")
        print("   Ejecuta primero: python scripts/parsear_anexo_1a.py")
        return 0

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # Crear el anexo
    ley_id = insertar_anexo(
        cursor,
        "RMF2025-A1A",
        "Anexo 1-A RMF 2025 - Trámites Fiscales",
        ley_padre_id
    )

    # Insertar fichas como artículos
    for i, ficha in enumerate(data["fichas"], 1):
        # Construir contenido estructurado
        contenido_partes = [ficha["contenido"]]

        if ficha.get("descripcion"):
            contenido_partes.insert(0, f"DESCRIPCIÓN: {ficha['descripcion']}")
        if ficha.get("requisitos"):
            contenido_partes.append(f"\nREQUISITOS: {ficha['requisitos']}")
        if ficha.get("condiciones"):
            contenido_partes.append(f"\nCONDICIONES: {ficha['condiciones']}")
        if ficha.get("fundamento_juridico"):
            contenido_partes.append(f"\nFUNDAMENTO JURÍDICO: {ficha['fundamento_juridico']}")

        contenido = "\n".join(contenido_partes)

        cursor.execute("""
            INSERT INTO articulos (
                ley_id, numero_raw, contenido, tipo, orden_global, referencias
            )
            VALUES (%s, %s, %s, 'ficha', %s, %s)
        """, (
            ley_id,
            ficha["numero_raw"],
            contenido,
            i,
            ficha.get("fundamento_juridico")
        ))

    print(f"   Fichas importadas: {len(data['fichas'])}")
    return len(data["fichas"])


def importar_anexo_3(cursor, ley_padre_id: int):
    """Importa los criterios no vinculativos del Anexo 3."""
    json_path = RMF_DIR / "anexo_3_criterios.json"

    if not json_path.exists():
        print(f"   ERROR: No existe {json_path.name}")
        print("   Ejecuta primero: python scripts/parsear_anexo_3.py")
        return 0

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # Crear el anexo
    ley_id = insertar_anexo(
        cursor,
        "RMF2025-A3",
        "Anexo 3 RMF 2025 - Criterios No Vinculativos",
        ley_padre_id
    )

    # Insertar criterios como artículos
    for i, criterio in enumerate(data["criterios"], 1):
        contenido = criterio["contenido"]

        cursor.execute("""
            INSERT INTO articulos (
                ley_id, numero_raw, contenido, tipo, orden_global
            )
            VALUES (%s, %s, %s, 'criterio', %s)
        """, (
            ley_id,
            criterio["numero_raw"],
            contenido,
            i
        ))

    print(f"   Criterios importados: {len(data['criterios'])}")
    return len(data["criterios"])


def main():
    print("=" * 60)
    print("IMPORTADOR DE ANEXOS RMF")
    print("=" * 60)

    # Conectar a PostgreSQL
    print(f"\nConectando a PostgreSQL ({PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']})...")
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        conn.autocommit = False
        cursor = conn.cursor()
        print("Conectado")
    except psycopg2.Error as e:
        print(f"Error de conexion: {e}")
        return 1

    try:
        # Obtener ley padre (RMF2025)
        print("\nBuscando RMF2025 como ley padre...")
        ley_padre_id = obtener_ley_padre(cursor, "RMF2025")
        print(f"   Encontrada (ID: {ley_padre_id})")

        # Eliminar anexos existentes
        print("\nEliminando anexos existentes...")
        cursor.execute("""
            DELETE FROM leyes WHERE codigo IN ('RMF2025-A1A', 'RMF2025-A3')
        """)

        # Importar Anexo 1-A
        print("\nImportando Anexo 1-A (Fichas de trámite)...")
        fichas = importar_anexo_1a(cursor, ley_padre_id)

        # Importar Anexo 3
        print("\nImportando Anexo 3 (Criterios No Vinculativos)...")
        criterios = importar_anexo_3(cursor, ley_padre_id)

        if fichas == 0 and criterios == 0:
            print("\nNo se importaron anexos")
            conn.rollback()
            return 1

        # Commit
        conn.commit()

        # Refrescar vista materializada
        print("\nRefrescando vista materializada...")
        cursor.execute("REFRESH MATERIALIZED VIEW jerarquia_completa")
        conn.commit()

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return 1

    # Verificación
    print("\n" + "=" * 60)
    print("VERIFICACION")
    print("=" * 60)

    cursor.execute("""
        SELECT l.codigo, l.nombre, COUNT(a.id) as total
        FROM leyes l
        LEFT JOIN articulos a ON a.ley_id = l.id
        WHERE l.tipo = 'anexo'
        GROUP BY l.codigo, l.nombre
        ORDER BY l.codigo
    """)
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[2]} registros - {row[1]}")

    # Test búsqueda
    cursor.execute("""
        SELECT COUNT(*) FROM articulos
        WHERE tipo = 'ficha'
        AND search_vector @@ websearch_to_tsquery('spanish_unaccent', 'RFC')
    """)
    rfc_count = cursor.fetchone()[0]
    print(f"\nTest búsqueda 'RFC' en fichas: {rfc_count} resultados")

    cursor.execute("""
        SELECT COUNT(*) FROM articulos
        WHERE tipo = 'criterio'
        AND search_vector @@ websearch_to_tsquery('spanish_unaccent', 'indebida')
    """)
    indebida_count = cursor.fetchone()[0]
    print(f"Test búsqueda 'indebida' en criterios: {indebida_count} resultados")

    conn.close()
    print("\nImportación completada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
