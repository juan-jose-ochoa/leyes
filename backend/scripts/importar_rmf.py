#!/usr/bin/env python3
"""
Importador de RMF - Resolución Miscelánea Fiscal

Lee el archivo DOCX de RMF, parsea con estructura jerárquica y carga a PostgreSQL.
Las reglas se guardan en la tabla articulos con tipo='regla'.
"""

import json
import os
import sys
from pathlib import Path

# Agregar directorio de scripts al path para importar parser
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from parsear_rmf import extraer_texto_docx, parsear_rmf, RMF_DIR

try:
    import psycopg2
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


def find_rmf_docx():
    """Encuentra el archivo DOCX de RMF"""
    if not RMF_DIR.exists():
        return None

    # Preferir el archivo convertido completo
    preferred = RMF_DIR / "rmf_2025_full_converted.docx"
    if preferred.exists():
        return preferred

    docx_files = list(RMF_DIR.glob("*.docx"))
    if docx_files:
        return docx_files[0]

    # Si no hay DOCX, intentar convertir PDF
    pdf_files = list(RMF_DIR.glob("*.pdf"))
    if pdf_files:
        try:
            from pdf2docx import Converter

            pdf_path = pdf_files[0]
            docx_path = pdf_path.with_suffix('.docx')

            print(f"   Convirtiendo PDF a DOCX...")
            cv = Converter(str(pdf_path))
            cv.convert(str(docx_path))
            cv.close()

            return docx_path
        except ImportError:
            print("ERROR: pdf2docx no instalado. Ejecuta: pip install pdf2docx")
            return None
        except Exception as e:
            print(f"ERROR convirtiendo PDF: {e}")
            return None

    return None


def insertar_ley_rmf(cursor, rmf_info):
    """Inserta la RMF como ley y retorna su ID"""
    cursor.execute("""
        INSERT INTO leyes (codigo, nombre, nombre_corto, tipo, url_fuente, fecha_descarga)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        rmf_info["codigo"],
        rmf_info["nombre"],
        rmf_info["codigo"],
        'resolucion',  # Tipo especial para RMF
        rmf_info.get("url"),
        rmf_info.get("fecha_descarga")
    ))
    return cursor.fetchone()[0]


def insertar_divisiones_rmf(cursor, ley_id, divisiones):
    """
    Inserta divisiones RMF y construye la jerarquía.
    Retorna un diccionario path_texto -> division_id
    """
    division_map = {}

    for div in divisiones:
        padre_id = None
        path_texto = div.get("path_texto", "")

        # Buscar padre basándonos en path_texto
        if " > " in path_texto:
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

    # Actualizar path_ids y nivel
    for path_texto, division_id in division_map.items():
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


def insertar_reglas(cursor, ley_id, reglas, division_map):
    """Inserta reglas RMF como artículos con tipo='regla' o 'inexistente'"""
    for regla in reglas:
        # Encontrar la división correspondiente
        division_id = None
        division_path = regla.get("division_path", "")
        if division_path and division_path in division_map:
            division_id = division_map[division_path]

        # Usar tipo de la regla si existe, sino default 'regla'
        tipo = regla.get("tipo", "regla")

        cursor.execute("""
            INSERT INTO articulos (
                ley_id, division_id, numero_raw, numero_base, sufijo, ordinal,
                contenido, es_transitorio, tipo, referencias, orden_global
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            ley_id,
            division_id,
            regla["numero"],
            None,  # numero_base no aplica para reglas RMF
            None,  # sufijo no aplica
            None,  # ordinal no aplica
            regla["contenido"],
            False,  # es_transitorio
            tipo,  # 'regla' o 'inexistente'
            regla.get("referencias"),  # referencias legales al final
            regla.get("orden_global")
        ))


def procesar_rmf(cursor, docx_path):
    """Procesa el documento RMF: parsea DOCX e inserta en PostgreSQL"""
    print(f"   Leyendo {docx_path.name}...")

    # Extraer y parsear
    paragraphs = extraer_texto_docx(docx_path)
    print(f"   {len(paragraphs)} párrafos extraídos")

    nombre_doc = "Resolución Miscelánea Fiscal 2025"
    resultado = parsear_rmf(paragraphs, nombre_doc)
    print(f"   {resultado['total_divisiones']} divisiones, {resultado['total_reglas']} reglas")

    if resultado['total_reglas'] == 0:
        return {"status": "sin_reglas", "reglas": 0, "divisiones": 0}

    # Preparar info para insertar
    rmf_info = {
        "codigo": "RMF2025",
        "nombre": nombre_doc,
        "url": "https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/normatividad_rmf_rgce2025.html",
        "fecha_descarga": None
    }

    # Insertar en PostgreSQL
    ley_id = insertar_ley_rmf(cursor, rmf_info)

    division_map = {}
    if resultado['divisiones']:
        division_map = insertar_divisiones_rmf(cursor, ley_id, resultado['divisiones'])

    insertar_reglas(cursor, ley_id, resultado['reglas'], division_map)

    return {
        "status": "ok",
        "reglas": resultado['total_reglas'],
        "divisiones": resultado['total_divisiones']
    }


def main():
    print("=" * 60)
    print("IMPORTADOR DE RMF")
    print("Resolución Miscelánea Fiscal")
    print("=" * 60)

    # Buscar DOCX
    print("\nBuscando archivo DOCX de RMF...")
    docx_path = find_rmf_docx()

    if not docx_path:
        print("ERROR: No se encontró archivo RMF")
        print("Ejecuta primero: python scripts/descargar_rmf.py")
        return 1

    print(f"Encontrado: {docx_path}")

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

    # Eliminar RMF existente si existe
    print("\nEliminando RMF existente si existe...")
    cursor.execute("""
        DELETE FROM leyes WHERE codigo = 'RMF2025'
    """)

    # Procesar RMF
    print("\nProcesando RMF...")
    try:
        resultado = procesar_rmf(cursor, docx_path)

        if resultado["status"] == "sin_reglas":
            print("Sin reglas encontradas")
            conn.rollback()
            return 1
        else:
            print(f"\nOK: {resultado['reglas']} reglas, {resultado['divisiones']} divisiones")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return 1

    # Commit
    conn.commit()

    # Refrescar vista materializada
    print("\nRefrescando vista materializada...")
    cursor.execute("REFRESH MATERIALIZED VIEW jerarquia_completa")
    conn.commit()

    # Verificar
    print("\n" + "=" * 60)
    print("VERIFICACION")
    print("=" * 60)

    cursor.execute("""
        SELECT COUNT(*) FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
        WHERE l.codigo = 'RMF2025' AND a.tipo = 'regla'
    """)
    total_reglas = cursor.fetchone()[0]
    print(f"Total reglas RMF: {total_reglas}")

    # Test búsqueda
    cursor.execute("""
        SELECT COUNT(*) FROM articulos
        WHERE tipo = 'regla'
        AND search_vector @@ websearch_to_tsquery('spanish_unaccent', 'factura')
    """)
    factura_count = cursor.fetchone()[0]
    print(f"Test busqueda 'factura' en reglas: {factura_count} resultados")

    conn.close()
    print("\nImportacion completada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
