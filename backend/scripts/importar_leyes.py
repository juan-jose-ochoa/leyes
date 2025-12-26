#!/usr/bin/env python3
"""
Importador de Leyes v2 - Migración directa a PostgreSQL

Lee los archivos DOCX, parsea con estructura jerárquica y carga a PostgreSQL.
Usa el nuevo schema normalizado con divisiones y artículos.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Agregar directorio de scripts al path para importar parser
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from parsear_ley import extraer_texto_docx, parsear_ley

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("Error: psycopg2 no instalado. Ejecuta: pip install psycopg2-binary")
    sys.exit(1)

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).parent.parent.parent

# Cargar .env si existe
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

# Configuración de PostgreSQL (desde variables de entorno)
PG_CONFIG = {
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": int(os.environ.get("PG_PORT", "5432")),
    "database": os.environ.get("PG_DB", "leyesmx"),
    "user": os.environ.get("PG_USER", "leyesmx"),
    "password": os.environ.get("PG_PASS", "leyesmx")
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


def find_docx(doc_info):
    """Encuentra el archivo DOCX correspondiente a un documento"""
    archivo_local = doc_info["archivo_local"]
    pdf_path = BASE_DIR / "doc" / archivo_local
    docx_path = pdf_path.with_suffix('.docx')

    if docx_path.exists():
        return docx_path
    return None


def insertar_ley(cursor, doc_info):
    """Inserta una ley y retorna su ID"""
    cursor.execute("""
        INSERT INTO leyes (codigo, nombre, nombre_corto, tipo, url_fuente, sha256, fecha_descarga)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        doc_info["nombre_corto"],
        doc_info["nombre"],
        doc_info["nombre_corto"],
        doc_info["tipo"],
        doc_info.get("url"),
        doc_info.get("sha256"),
        doc_info.get("fecha_descarga")
    ))
    return cursor.fetchone()[0]


def insertar_divisiones(cursor, ley_id, divisiones):
    """
    Inserta divisiones y construye la jerarquía.
    Retorna un diccionario path_texto -> division_id para vincular artículos.
    """
    division_map = {}  # path_texto -> id

    for div in divisiones:
        # Determinar padre
        padre_id = None
        path_ids = []
        nivel = 0

        # Buscar padre basándonos en path_texto
        path_texto = div.get("path_texto", "")
        if " > " in path_texto:
            # El padre es el path sin el último elemento
            partes = path_texto.split(" > ")
            path_padre = " > ".join(partes[:-1])
            if path_padre in division_map:
                padre_id = division_map[path_padre]

        cursor.execute("""
            INSERT INTO divisiones (ley_id, padre_id, tipo, numero, numero_orden, nombre, path_texto, orden_global)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            ley_id,
            padre_id,
            div["tipo"],
            div["numero"],
            div.get("numero_orden"),
            div.get("nombre"),
            path_texto,
            div.get("orden_global")
        ))

        division_id = cursor.fetchone()[0]
        division_map[path_texto] = division_id

    # Actualizar path_ids y nivel para cada división
    for path_texto, division_id in division_map.items():
        # Construir path_ids recorriendo ancestros
        path_ids = []
        current_path = path_texto
        while current_path:
            if current_path in division_map:
                path_ids.insert(0, division_map[current_path])
            partes = current_path.split(" > ")
            if len(partes) > 1:
                current_path = " > ".join(partes[:-1])
            else:
                break

        nivel = len(path_ids) - 1 if path_ids else 0

        cursor.execute("""
            UPDATE divisiones
            SET path_ids = %s, nivel = %s
            WHERE id = %s
        """, (path_ids, nivel, division_id))

    return division_map


def insertar_articulos(cursor, ley_id, articulos, division_map):
    """Inserta artículos vinculados a sus divisiones"""
    for art in articulos:
        # Encontrar la división correspondiente
        division_id = None
        division_path = art.get("division_path", "")
        if division_path and division_path in division_map:
            division_id = division_map[division_path]

        cursor.execute("""
            INSERT INTO articulos (
                ley_id, division_id, numero_raw, numero_base, sufijo, ordinal,
                contenido, es_transitorio, decreto_dof, reformas, orden_global
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            ley_id,
            division_id,
            art["numero_raw"],
            art.get("numero_base"),
            art.get("sufijo"),
            art.get("ordinal"),
            art["contenido"],
            art.get("es_transitorio", False),
            art.get("decreto_dof"),
            art.get("reformas"),
            art.get("orden_global")
        ))


def procesar_documento(cursor, doc_info):
    """Procesa un documento completo: parsea DOCX e inserta en PostgreSQL"""
    nombre = doc_info["nombre"]
    codigo = doc_info["nombre_corto"]

    # Buscar DOCX
    docx_path = find_docx(doc_info)
    if not docx_path:
        return {"status": "sin_docx", "articulos": 0, "divisiones": 0}

    print(f"   Leyendo {docx_path.name}...")

    # Extraer y parsear
    paragraphs = extraer_texto_docx(docx_path)
    print(f"   {len(paragraphs)} párrafos")

    resultado = parsear_ley(paragraphs, nombre)
    print(f"   {resultado['total_divisiones']} divisiones, {resultado['total_articulos']} artículos")

    if resultado['total_articulos'] == 0:
        return {"status": "sin_articulos", "articulos": 0, "divisiones": 0}

    # Insertar en PostgreSQL
    ley_id = insertar_ley(cursor, doc_info)

    division_map = {}
    if resultado['divisiones']:
        division_map = insertar_divisiones(cursor, ley_id, resultado['divisiones'])

    insertar_articulos(cursor, ley_id, resultado['articulos'], division_map)

    return {
        "status": "ok",
        "articulos": resultado['total_articulos'],
        "divisiones": resultado['total_divisiones'],
        "transitorios": sum(1 for a in resultado['articulos'] if a.get('es_transitorio'))
    }


def verificar_importacion(cursor):
    """Verifica la importación con consultas de diagnóstico"""
    print("\n" + "=" * 60)
    print("VERIFICACION DE IMPORTACION")
    print("=" * 60)

    # Resumen por ley
    cursor.execute("""
        SELECT l.codigo, l.tipo,
               COUNT(DISTINCT d.id) as divisiones,
               COUNT(DISTINCT a.id) as articulos
        FROM leyes l
        LEFT JOIN divisiones d ON l.id = d.ley_id
        LEFT JOIN articulos a ON l.id = a.ley_id
        GROUP BY l.id, l.codigo, l.tipo
        ORDER BY l.tipo, l.codigo
    """)

    print("\nDocumentos importados:")
    print(f"{'Codigo':<10} {'Tipo':<12} {'Divisiones':>10} {'Articulos':>10}")
    print("-" * 45)
    for row in cursor.fetchall():
        print(f"{row[0]:<10} {row[1]:<12} {row[2]:>10} {row[3]:>10}")

    # Total artículos
    cursor.execute("SELECT COUNT(*) FROM articulos")
    total = cursor.fetchone()[0]
    print(f"\nTotal artículos: {total}")

    # Artículos transitorios
    cursor.execute("SELECT COUNT(*) FROM articulos WHERE es_transitorio = true")
    transitorios = cursor.fetchone()[0]
    print(f"Artículos transitorios: {transitorios}")

    # Test búsqueda full-text
    cursor.execute("""
        SELECT COUNT(*) FROM articulos
        WHERE search_vector @@ websearch_to_tsquery('spanish_unaccent', 'impuesto')
    """)
    impuesto_count = cursor.fetchone()[0]
    print(f"\nTest busqueda 'impuesto': {impuesto_count} resultados")

    cursor.execute("""
        SELECT COUNT(*) FROM articulos
        WHERE search_vector @@ websearch_to_tsquery('spanish_unaccent', 'trabajador')
    """)
    trabajador_count = cursor.fetchone()[0]
    print(f"Test busqueda 'trabajador': {trabajador_count} resultados")


def main():
    print("=" * 60)
    print("IMPORTADOR DE LEYES v2")
    print("Estructura Jerarquica Normalizada")
    print("=" * 60)

    # Cargar manifest
    print("\nCargando manifest.json...")
    manifest = load_manifest()
    print(f"{manifest['total_documentos']} documentos en manifest")

    # Conectar a PostgreSQL
    print(f"\nConectando a PostgreSQL ({PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']})...")
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        conn.autocommit = False
        cursor = conn.cursor()
        print("Conectado")
    except psycopg2.Error as e:
        print(f"Error de conexion: {e}")
        print("\nAsegurate de:")
        print("  1. PostgreSQL esta corriendo")
        print("  2. La base de datos 'leyesmx' existe")
        print("  3. Has ejecutado: psql leyesmx < backend/sql/001_schema.sql")
        sys.exit(1)

    # Limpiar tablas existentes
    print("\nLimpiando tablas existentes...")
    cursor.execute("""
        TRUNCATE referencias_cruzadas, fracciones, articulos, divisiones, leyes
        RESTART IDENTITY CASCADE
    """)

    # Procesar cada documento
    stats = {
        "importados": 0,
        "sin_docx": [],
        "sin_articulos": [],
        "total_articulos": 0,
        "total_divisiones": 0
    }

    for doc in manifest["documentos"]:
        codigo = doc["nombre_corto"]
        nombre = doc["nombre"]

        print(f"\n{'='*60}")
        print(f"{codigo}: {nombre}")

        try:
            resultado = procesar_documento(cursor, doc)

            if resultado["status"] == "sin_docx":
                print("   Sin archivo DOCX - saltando")
                stats["sin_docx"].append(codigo)
            elif resultado["status"] == "sin_articulos":
                print("   Sin articulos encontrados - saltando")
                stats["sin_articulos"].append(codigo)
            else:
                stats["importados"] += 1
                stats["total_articulos"] += resultado["articulos"]
                stats["total_divisiones"] += resultado["divisiones"]
                trans = resultado.get("transitorios", 0)
                print(f"   OK: {resultado['articulos']} articulos ({trans} transitorios)")

        except Exception as e:
            print(f"   ERROR: {e}")
            conn.rollback()
            raise

    # Commit final
    conn.commit()

    # Refrescar vista materializada
    print("\nRefrescando vista materializada...")
    cursor.execute("REFRESH MATERIALIZED VIEW jerarquia_completa")
    conn.commit()

    # Verificar
    verificar_importacion(cursor)

    # Resumen final
    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    print(f"Documentos importados: {stats['importados']}")
    print(f"Total divisiones: {stats['total_divisiones']}")
    print(f"Total articulos: {stats['total_articulos']}")

    if stats["sin_docx"]:
        print(f"\nSin DOCX (ejecuta convertir_ley.py primero):")
        for c in stats["sin_docx"]:
            print(f"  - {c}")

    if stats["sin_articulos"]:
        print(f"\nSin articulos encontrados:")
        for c in stats["sin_articulos"]:
            print(f"  - {c}")

    conn.close()
    print("\nImportacion completada")


if __name__ == "__main__":
    main()
