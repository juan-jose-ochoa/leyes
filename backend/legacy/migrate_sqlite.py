#!/usr/bin/env python3
"""
Migración de datos de SQLite a PostgreSQL
Lee los archivos .db generados por convertir_ley.py e inserta en PostgreSQL
"""

import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("Error: psycopg2 no instalado. Ejecuta: pip install psycopg2-binary")
    sys.exit(1)

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).parent.parent.parent

# Configuración de PostgreSQL (modificar según tu entorno)
PG_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "leyesmx",
    "user": "leyesmx",
    "password": "leyesmx"
}


def load_manifest():
    """Carga el manifest.json con metadatos de documentos"""
    manifest_path = BASE_DIR / "doc" / "manifest.json"
    if not manifest_path.exists():
        print(f"Error: No se encontró {manifest_path}")
        print("Ejecuta primero: python scripts/descargar_leyes_mx.py")
        sys.exit(1)

    with open(manifest_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_sqlite_db(doc_info):
    """Encuentra el archivo .db correspondiente a un documento"""
    archivo_local = doc_info["archivo_local"]
    # Ruta del PDF: leyes/cff/cff_codigo_fiscal_de_la_federacion.pdf
    pdf_path = BASE_DIR / "doc" / archivo_local
    db_path = pdf_path.with_suffix('.db')

    if db_path.exists():
        return db_path
    return None


def read_sqlite_articles(db_path):
    """Lee todos los artículos de una base de datos SQLite"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT titulo, articulo, contenido, referencia
        FROM articulos
        ORDER BY id
    """)

    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return articles


def migrate_to_postgres(pg_conn, manifest):
    """Migra todos los documentos a PostgreSQL"""
    cursor = pg_conn.cursor()

    # Limpiar tablas existentes (en orden por foreign keys)
    print("\n🗑️  Limpiando tablas existentes...")
    cursor.execute("TRUNCATE referencias_cruzadas, articulos, leyes RESTART IDENTITY CASCADE")
    pg_conn.commit()

    total_articulos = 0
    documentos_migrados = 0
    documentos_sin_db = []

    for doc in manifest["documentos"]:
        nombre = doc["nombre"]
        codigo = doc["nombre_corto"]
        tipo = doc["tipo"]

        print(f"\n📂 {codigo}: {nombre}")

        # Buscar archivo .db
        db_path = find_sqlite_db(doc)
        if not db_path:
            print(f"   ⚠️  Sin archivo .db - saltando")
            documentos_sin_db.append(codigo)
            continue

        # Leer artículos de SQLite
        articles = read_sqlite_articles(db_path)
        if not articles:
            print(f"   ⚠️  Sin artículos - saltando")
            documentos_sin_db.append(codigo)
            continue

        print(f"   📄 {len(articles)} artículos encontrados")

        # Insertar ley en PostgreSQL
        cursor.execute("""
            INSERT INTO leyes (codigo, nombre, tipo, url_fuente, sha256, fecha_descarga)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            codigo,
            nombre,
            tipo,
            doc.get("url"),
            doc.get("sha256"),
            doc.get("fecha_descarga")
        ))
        ley_id = cursor.fetchone()[0]

        # Insertar artículos (constraint único incluye titulo, así que permite duplicados por sección)
        for art in articles:
            cursor.execute("""
                INSERT INTO articulos (ley_id, titulo, articulo, contenido, referencia)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (ley_id, titulo, articulo) DO NOTHING
            """, (ley_id, art["titulo"], art["articulo"], art["contenido"], art.get("referencia", "")))

        total_articulos += len(articles)
        documentos_migrados += 1
        print(f"   ✅ Migrado")

    pg_conn.commit()

    return {
        "documentos_migrados": documentos_migrados,
        "total_articulos": total_articulos,
        "documentos_sin_db": documentos_sin_db
    }


def verify_migration(pg_conn):
    """Verifica la migración con algunas consultas"""
    cursor = pg_conn.cursor()

    print("\n" + "=" * 60)
    print("VERIFICACIÓN DE MIGRACIÓN")
    print("=" * 60)

    # Contar leyes
    cursor.execute("SELECT tipo, COUNT(*) FROM leyes GROUP BY tipo ORDER BY tipo")
    print("\n📊 Documentos por tipo:")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]}")

    # Contar artículos por ley
    cursor.execute("""
        SELECT l.codigo, l.nombre, COUNT(a.id) as articulos
        FROM leyes l
        LEFT JOIN articulos a ON l.id = a.ley_id
        GROUP BY l.id, l.codigo, l.nombre
        ORDER BY l.tipo, l.codigo
    """)
    print("\n📄 Artículos por documento:")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[2]} artículos")

    # Probar búsqueda full-text
    cursor.execute("""
        SELECT COUNT(*)
        FROM articulos
        WHERE search_vector @@ websearch_to_tsquery('spanish_unaccent', 'factura')
    """)
    factura_count = cursor.fetchone()[0]
    print(f"\n🔍 Test búsqueda 'factura': {factura_count} resultados")

    cursor.execute("""
        SELECT COUNT(*)
        FROM articulos
        WHERE search_vector @@ websearch_to_tsquery('spanish_unaccent', 'impuesto renta')
    """)
    isr_count = cursor.fetchone()[0]
    print(f"🔍 Test búsqueda 'impuesto renta': {isr_count} resultados")


def main():
    print("=" * 60)
    print("MIGRACIÓN SQLite → PostgreSQL")
    print("=" * 60)

    # Cargar manifest
    print("\n📋 Cargando manifest.json...")
    manifest = load_manifest()
    print(f"   {manifest['total_documentos']} documentos en manifest")

    # Conectar a PostgreSQL
    print(f"\n🔌 Conectando a PostgreSQL ({PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']})...")
    try:
        pg_conn = psycopg2.connect(**PG_CONFIG)
        print("   ✅ Conectado")
    except psycopg2.Error as e:
        print(f"   ❌ Error de conexión: {e}")
        print("\n💡 Asegúrate de:")
        print("   1. PostgreSQL está corriendo")
        print("   2. La base de datos 'leyesmx' existe")
        print("   3. Las credenciales son correctas")
        print("   4. Has ejecutado los scripts SQL de schema")
        print("\nPara crear la base de datos:")
        print("   createdb leyesmx")
        print("   psql leyesmx < backend/sql/001_schema.sql")
        print("   psql leyesmx < backend/sql/002_functions.sql")
        print("   psql leyesmx < backend/sql/003_api_views.sql")
        sys.exit(1)

    # Ejecutar migración
    try:
        result = migrate_to_postgres(pg_conn, manifest)

        print("\n" + "=" * 60)
        print("RESUMEN DE MIGRACIÓN")
        print("=" * 60)
        print(f"✅ Documentos migrados: {result['documentos_migrados']}")
        print(f"📄 Total artículos: {result['total_articulos']}")

        if result['documentos_sin_db']:
            print(f"\n⚠️  Documentos sin .db (ejecuta convertir_ley.py):")
            for codigo in result['documentos_sin_db']:
                print(f"   - {codigo}")

        # Verificar
        verify_migration(pg_conn)

    except Exception as e:
        pg_conn.rollback()
        print(f"\n❌ Error durante migración: {e}")
        raise
    finally:
        pg_conn.close()

    print("\n✅ Migración completada exitosamente")


if __name__ == "__main__":
    main()
