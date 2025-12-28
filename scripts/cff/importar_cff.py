#!/usr/bin/env python3
"""
Importador de CFF desde JSON extraído.

Lee el JSON generado por extractor_cff.py y carga a PostgreSQL.
El JSON ya tiene fracciones parseadas y validadas.

Uso:
    python scripts/cff/importar_cff.py [--limpiar]

Opciones:
    --limpiar   Elimina datos existentes de CFF antes de importar
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import Json
except ImportError:
    print("Error: psycopg2 no instalado. Ejecuta: pip install psycopg2-binary")
    sys.exit(1)

# Directorios
BASE_DIR = Path(__file__).parent.parent.parent
JSON_PATH = BASE_DIR / "doc/leyes/cff/cff_extraido.json"

# Cargar .env
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

# Configuración PostgreSQL
PG_CONFIG = {
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": int(os.environ.get("PG_PORT", "5432")),
    "database": os.environ.get("PG_DB", "leyesmx"),
    "user": os.environ.get("PG_USER", "leyesmx"),
    "password": os.environ.get("PG_PASS", "leyesmx")
}

# Información del CFF
CFF_INFO = {
    "codigo": "CFF",
    "nombre": "Código Fiscal de la Federación",
    "tipo": "ley"
}


def cargar_json():
    """Carga el JSON extraído del PDF."""
    if not JSON_PATH.exists():
        print(f"ERROR: No existe {JSON_PATH}")
        print("Ejecuta primero: python scripts/cff/extractor_cff.py")
        sys.exit(1)

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def limpiar_cff_existente(cursor, codigo):
    """Elimina datos existentes del CFF."""
    print(f"   Limpiando datos existentes de {codigo}...")

    cursor.execute("SELECT id FROM leyes WHERE codigo = %s", (codigo,))
    row = cursor.fetchone()

    if row:
        ley_id = row[0]
        cursor.execute("DELETE FROM fracciones WHERE articulo_id IN (SELECT id FROM articulos WHERE ley_id = %s)", (ley_id,))
        cursor.execute("DELETE FROM articulos WHERE ley_id = %s", (ley_id,))
        cursor.execute("DELETE FROM divisiones WHERE ley_id = %s", (ley_id,))
        cursor.execute("DELETE FROM leyes WHERE id = %s", (ley_id,))
        print(f"   Datos eliminados.")
    else:
        print(f"   No existían datos previos.")


def insertar_ley(cursor):
    """Inserta el CFF como ley y retorna su ID."""
    cursor.execute("""
        INSERT INTO leyes (codigo, nombre, nombre_corto, tipo, fecha_descarga)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (codigo) DO UPDATE SET
            nombre = EXCLUDED.nombre,
            fecha_descarga = EXCLUDED.fecha_descarga
        RETURNING id
    """, (
        CFF_INFO["codigo"],
        CFF_INFO["nombre"],
        CFF_INFO["codigo"],
        CFF_INFO["tipo"],
        datetime.now()
    ))
    return cursor.fetchone()[0]


def insertar_estructura(cursor, ley_id, estructura):
    """Inserta la estructura de títulos y capítulos."""
    print("   Insertando estructura...")

    divisiones_ids = {}
    orden = 0

    # Insertar títulos
    for titulo in estructura.get('titulos', []):
        orden += 1
        cursor.execute("""
            INSERT INTO divisiones (ley_id, tipo, numero, nombre, orden_global)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (ley_id, 'titulo', titulo['numero'], titulo['nombre'], orden))
        div_id = cursor.fetchone()[0]
        divisiones_ids[f"titulo-{titulo['numero']}"] = div_id

    print(f"      {len(estructura.get('titulos', []))} títulos")

    # Insertar capítulos
    for cap in estructura.get('capitulos', []):
        orden += 1
        cursor.execute("""
            INSERT INTO divisiones (ley_id, tipo, numero, nombre, orden_global)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (ley_id, 'capitulo', cap['numero'], cap['nombre'], orden))
        div_id = cursor.fetchone()[0]
        divisiones_ids[f"capitulo-{cap['numero']}"] = div_id

    print(f"      {len(estructura.get('capitulos', []))} capítulos")

    return divisiones_ids


def insertar_articulos(cursor, ley_id, articulos):
    """Inserta artículos y sus fracciones."""
    print("   Insertando artículos...")

    articulos_insertados = 0
    fracciones_insertadas = 0

    for i, art in enumerate(articulos):
        # Insertar artículo
        cursor.execute("""
            INSERT INTO articulos (
                ley_id, numero_raw, numero_base, sufijo, ordinal,
                contenido, es_transitorio, referencias, orden_global
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            ley_id,
            art['numero_raw'],
            art['numero_base'],
            art.get('sufijo'),
            art.get('ordinal'),
            art.get('contenido', ''),
            art.get('es_transitorio', False),
            art.get('referencias'),
            i + 1
        ))
        art_id = cursor.fetchone()[0]
        articulos_insertados += 1

        # Insertar fracciones
        padre_map = {}  # numero -> id para vincular incisos con fracciones

        for frac in art.get('fracciones', []):
            padre_id = None
            if frac.get('padre') and frac['padre'] in padre_map:
                padre_id = padre_map[frac['padre']]

            cursor.execute("""
                INSERT INTO fracciones (
                    articulo_id, padre_id, tipo, numero, numero_orden, contenido, orden
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                art_id,
                padre_id,
                frac['tipo'],
                frac.get('numero'),
                frac.get('orden', 0),
                frac.get('contenido', ''),
                frac.get('orden', 0)
            ))
            frac_id = cursor.fetchone()[0]
            fracciones_insertadas += 1

            # Guardar mapping para incisos
            if frac.get('numero') and frac['tipo'] == 'fraccion':
                padre_map[frac['numero']] = frac_id

        if (i + 1) % 100 == 0:
            print(f"      {i + 1}/{len(articulos)} artículos...")

    print(f"      {articulos_insertados} artículos insertados")
    print(f"      {fracciones_insertadas} fracciones insertadas")

    return articulos_insertados, fracciones_insertadas


def main():
    """Ejecuta la importación completa."""
    limpiar = '--limpiar' in sys.argv

    print("=" * 60)
    print("IMPORTADOR CFF (desde JSON)")
    print("=" * 60)

    # Cargar JSON
    print("\n1. Cargando JSON...")
    data = cargar_json()
    estructura = data.get('estructura', {})
    articulos = data.get('articulos', [])
    stats = data.get('estadisticas', {})

    print(f"   Artículos: {len(articulos)}")
    print(f"   Fracciones: {stats.get('total_fracciones', 0)}")

    # Conectar a PostgreSQL
    print("\n2. Conectando a PostgreSQL...")
    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()

    try:
        # Limpiar si se solicitó
        if limpiar:
            print("\n3. Limpiando datos existentes...")
            limpiar_cff_existente(cursor, CFF_INFO['codigo'])
        else:
            cursor.execute("SELECT id FROM leyes WHERE codigo = %s", (CFF_INFO['codigo'],))
            if cursor.fetchone():
                print(f"\n   ADVERTENCIA: Ya existe {CFF_INFO['codigo']}.")
                print("   Usa --limpiar para reemplazar los datos existentes.")
                return

        # Insertar ley
        print("\n4. Insertando ley...")
        ley_id = insertar_ley(cursor)
        print(f"   Ley ID: {ley_id}")

        # Insertar estructura
        print("\n5. Insertando estructura...")
        divisiones_ids = insertar_estructura(cursor, ley_id, estructura)

        # Insertar artículos
        print("\n6. Insertando artículos...")
        total_arts, total_fracs = insertar_articulos(cursor, ley_id, articulos)

        # Commit
        conn.commit()

        print("\n" + "=" * 60)
        print("IMPORTACIÓN COMPLETADA")
        print("=" * 60)
        print(f"   Artículos: {total_arts}")
        print(f"   Fracciones: {total_fracs}")
        print(f"   Divisiones: {len(divisiones_ids)}")

        # Verificación
        print("\n   Verificación de artículo 17-H BIS:")
        cursor.execute("""
            SELECT
                a.numero_raw,
                LENGTH(a.contenido) as contenido_len,
                (SELECT COUNT(*) FROM fracciones f WHERE f.articulo_id = a.id) as num_fracciones
            FROM articulos a
            WHERE a.ley_id = %s AND UPPER(a.numero_raw) = '17-H BIS'
        """, (ley_id,))
        row = cursor.fetchone()
        if row:
            print(f"      {row[0]}: contenido={row[1]} chars, fracciones={row[2]}")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
