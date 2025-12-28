#!/usr/bin/env python3
"""
Importador de RMF desde PDF (fuente única).

Lee el JSON extraído por pdf_extractor_v2.py y carga a PostgreSQL.
No depende del DOCX - todo viene directamente del PDF oficial.

Uso:
    python importar_rmf_pdf.py [--limpiar]

Opciones:
    --limpiar   Elimina datos existentes de RMF2025 antes de importar
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
RMF_DIR = BASE_DIR / "doc" / "rmf"
JSON_PATH = RMF_DIR / "rmf_extraido_v2.json"

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

# Configuración RMF
RMF_INFO = {
    "codigo": "RMF2025",
    "nombre": "Resolución Miscelánea Fiscal para 2025",
    "url": "https://www.sat.gob.mx/normatividad/22202/resolucion-miscelanea-fiscal-(rmf)-",
    "fecha_publicacion": "2024-12-30"
}


def cargar_json():
    """Carga el JSON extraído del PDF."""
    if not JSON_PATH.exists():
        print(f"ERROR: No existe {JSON_PATH}")
        print("Ejecuta primero: python scripts/rmf/pdf_extractor_v2.py")
        sys.exit(1)

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def limpiar_rmf_existente(cursor, codigo):
    """Elimina datos existentes de la RMF."""
    print(f"   Limpiando datos existentes de {codigo}...")

    # Obtener ID de la ley
    cursor.execute("SELECT id FROM leyes WHERE codigo = %s", (codigo,))
    row = cursor.fetchone()

    if row:
        ley_id = row[0]

        # Eliminar en orden correcto por foreign keys
        cursor.execute("DELETE FROM fracciones WHERE articulo_id IN (SELECT id FROM articulos WHERE ley_id = %s)", (ley_id,))
        cursor.execute("DELETE FROM articulos WHERE ley_id = %s", (ley_id,))
        cursor.execute("DELETE FROM divisiones WHERE ley_id = %s", (ley_id,))
        cursor.execute("DELETE FROM leyes WHERE id = %s", (ley_id,))
        cursor.execute("DELETE FROM indice_oficial WHERE ley_codigo = %s", (codigo,))

        print(f"   Datos eliminados.")
    else:
        print(f"   No existían datos previos.")


def insertar_ley(cursor):
    """Inserta la RMF como ley y retorna su ID."""
    cursor.execute("""
        INSERT INTO leyes (codigo, nombre, nombre_corto, tipo, url_fuente, fecha_descarga)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (codigo) DO UPDATE SET
            nombre = EXCLUDED.nombre,
            url_fuente = EXCLUDED.url_fuente,
            fecha_descarga = EXCLUDED.fecha_descarga
        RETURNING id
    """, (
        RMF_INFO["codigo"],
        RMF_INFO["nombre"],
        RMF_INFO["codigo"],
        'resolucion',
        RMF_INFO["url"],
        datetime.now()
    ))
    return cursor.fetchone()[0]


def insertar_estructura(cursor, ley_id, estructura):
    """Inserta la estructura (títulos, capítulos, secciones, subsecciones).

    El trigger trg_divisiones_paths calcula automáticamente:
    - path_ids: array de IDs desde raíz
    - path_texto: texto legible (Título X > Capítulo Y > ...)
    - nivel: profundidad en jerarquía
    """
    print("   Insertando estructura...")

    # Mapeo de números a IDs de divisiones
    divisiones_ids = {}
    orden = 0

    # Insertar títulos (padre_id = NULL porque son raíz)
    for titulo in estructura.get('titulos', []):
        orden += 1
        cursor.execute("""
            INSERT INTO divisiones (ley_id, tipo, numero, numero_orden, nombre, orden_global)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            ley_id, 'titulo', titulo['numero'],
            int(titulo['numero']), titulo['nombre'], orden
        ))
        div_id = cursor.fetchone()[0]
        divisiones_ids[f"titulo-{titulo['numero']}"] = {'id': div_id}

    print(f"      {len(estructura.get('titulos', []))} títulos")

    # Insertar capítulos (padre_id = título correspondiente)
    for cap in estructura.get('capitulos', []):
        orden += 1
        titulo_num = cap['numero'].split('.')[0]
        titulo_info = divisiones_ids.get(f"titulo-{titulo_num}")
        padre_id = titulo_info['id'] if titulo_info else None

        cursor.execute("""
            INSERT INTO divisiones (ley_id, padre_id, tipo, numero, numero_orden, nombre, orden_global)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            ley_id, padre_id, 'capitulo', cap['numero'],
            float(cap['numero']), cap['nombre'], orden
        ))
        div_id = cursor.fetchone()[0]
        divisiones_ids[f"capitulo-{cap['numero']}"] = {'id': div_id}

    print(f"      {len(estructura.get('capitulos', []))} capítulos")

    # Insertar secciones (padre_id = capítulo correspondiente)
    for sec in estructura.get('secciones', []):
        orden += 1
        parts = sec['numero'].split('.')
        cap_num = f"{parts[0]}.{parts[1]}"
        cap_info = divisiones_ids.get(f"capitulo-{cap_num}")
        padre_id = cap_info['id'] if cap_info else None

        # Calcular numero_orden como flotante compuesto
        numero_orden = int(parts[0]) + int(parts[1]) * 0.01 + int(parts[2]) * 0.0001

        cursor.execute("""
            INSERT INTO divisiones (ley_id, padre_id, tipo, numero, numero_orden, nombre, orden_global)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            ley_id, padre_id, 'seccion', sec['numero'],
            numero_orden, sec['nombre'], orden
        ))
        div_id = cursor.fetchone()[0]
        divisiones_ids[f"seccion-{sec['numero']}"] = {'id': div_id}

    print(f"      {len(estructura.get('secciones', []))} secciones")

    # Insertar subsecciones (padre_id = sección correspondiente)
    for subsec in estructura.get('subsecciones', []):
        orden += 1
        parts = subsec['numero'].split('.')
        sec_num = f"{parts[0]}.{parts[1]}.{parts[2]}"
        sec_info = divisiones_ids.get(f"seccion-{sec_num}")
        padre_id = sec_info['id'] if sec_info else None

        numero_orden = (int(parts[0]) +
                       int(parts[1]) * 0.01 +
                       int(parts[2]) * 0.0001 +
                       int(parts[3]) * 0.000001)

        cursor.execute("""
            INSERT INTO divisiones (ley_id, padre_id, tipo, numero, numero_orden, nombre, orden_global)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            ley_id, padre_id, 'subseccion', subsec['numero'],
            numero_orden, subsec['nombre'], orden
        ))
        div_id = cursor.fetchone()[0]
        divisiones_ids[f"subseccion-{subsec['numero']}"] = {'id': div_id}

    print(f"      {len(estructura.get('subsecciones', []))} subsecciones")

    return divisiones_ids


def crear_divisiones_virtuales(cursor, ley_id, reglas, divisiones_ids):
    """
    Crea capítulos virtuales para reglas de dos niveles (X.Y).

    Títulos que usan reglas de dos niveles: 1, 6, 7, 8, 9, 10
    Estructura: Título X > Capítulo X.Y [nombre regla] > Regla X.Y

    El trigger trg_divisiones_paths calcula path_texto automáticamente.
    """
    print("   Creando capítulos virtuales para reglas de 2 niveles...")

    titulos_dos_niveles = {'1', '6', '7', '8', '9', '10'}
    orden = max(d['id'] for d in divisiones_ids.values()) + 1000
    virtuales_creados = 0

    for regla in reglas:
        numero = regla['numero']
        parts = numero.split('.')

        # Solo para reglas de dos niveles en títulos específicos
        if len(parts) == 2 and parts[0] in titulos_dos_niveles:
            titulo_num = parts[0]
            cap_key = f"capitulo-{numero}"

            # Si ya existe el capítulo virtual, saltarlo
            if cap_key in divisiones_ids:
                continue

            # Buscar el título padre
            titulo_info = divisiones_ids.get(f"titulo-{titulo_num}")
            if not titulo_info:
                # Crear el título si no existe
                cursor.execute("""
                    INSERT INTO divisiones (ley_id, tipo, numero, numero_orden, nombre, orden_global)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """, (
                    ley_id, 'titulo', titulo_num,
                    int(titulo_num), f"Título {titulo_num}", orden
                ))
                result = cursor.fetchone()
                if result:
                    orden += 1
                    titulo_info = {'id': result[0]}
                    divisiones_ids[f"titulo-{titulo_num}"] = titulo_info
                else:
                    continue

            # Crear capítulo virtual con padre_id
            nombre_cap = regla.get('titulo') or f"Regla {numero}"
            padre_id = titulo_info['id']

            cursor.execute("""
                INSERT INTO divisiones (ley_id, padre_id, tipo, numero, numero_orden, nombre, orden_global)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id
            """, (
                ley_id, padre_id, 'capitulo', numero,
                float(numero), nombre_cap, orden
            ))
            result = cursor.fetchone()
            if result:
                orden += 1
                divisiones_ids[cap_key] = {'id': result[0]}
                virtuales_creados += 1

    print(f"      {virtuales_creados} capítulos virtuales creados")
    return divisiones_ids


def determinar_division(numero, divisiones_ids):
    """Determina la división padre de una regla según su número."""
    parts = numero.split('.')

    if len(parts) == 2:
        # Regla de dos niveles: X.Y -> Capítulo X.Y (virtual)
        return divisiones_ids.get(f"capitulo-{numero}")
    elif len(parts) == 3:
        # Regla de tres niveles: X.Y.Z
        # Buscar en orden: subsección, sección, capítulo
        cap_num = f"{parts[0]}.{parts[1]}"

        # Verificar si hay subsecciones para este capítulo
        # (buscar subsección X.Y.Z.*)
        # Por ahora, asignar al capítulo
        return divisiones_ids.get(f"capitulo-{cap_num}")

    return None


def insertar_reglas(cursor, ley_id, reglas, divisiones_ids):
    """Inserta las reglas y sus fracciones."""
    print("   Insertando reglas...")

    reglas_insertadas = 0
    fracciones_insertadas = 0

    for i, regla in enumerate(reglas):
        numero = regla['numero']

        # Determinar división padre
        div_info = determinar_division(numero, divisiones_ids)
        div_id = div_info['id'] if div_info else None

        # Datos de calidad
        calidad = {
            'estatus': 'ok',
            'issues': [],
            'fuente': 'pdf'
        }

        # Insertar artículo (regla) con division_id
        cursor.execute("""
            INSERT INTO articulos (
                ley_id, division_id, numero_raw, numero_base, sufijo, tipo,
                titulo, contenido, es_transitorio, reformas, calidad, referencias
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            ley_id,
            div_id,
            numero,
            int(numero.split('.')[0]),  # numero_base = primer nivel
            '.'.join(numero.split('.')[1:]),  # sufijo = resto
            'regla',
            regla.get('titulo'),
            regla.get('contenido', ''),
            False,
            regla.get('nota_reforma'),
            Json(calidad),
            regla.get('referencias')
        ))
        art_id = cursor.fetchone()[0]
        reglas_insertadas += 1

        # Insertar fracciones
        for frac in regla.get('fracciones', []):
            # Mapear tipo a valores permitidos por la BD
            tipo_original = frac.get('tipo', 'fraccion')
            tipo_bd = {
                'romano': 'fraccion',
                'letra': 'inciso',
                'numero': 'numeral',
                'parrafo': 'parrafo'
            }.get(tipo_original, 'fraccion')

            cursor.execute("""
                INSERT INTO fracciones (
                    articulo_id, tipo, numero, contenido, orden
                )
                VALUES (%s, %s, %s, %s, %s)
            """, (
                art_id,
                tipo_bd,
                frac.get('numero'),
                frac.get('contenido', ''),
                fracciones_insertadas
            ))
            fracciones_insertadas += 1

        if (i + 1) % 100 == 0:
            print(f"      {i + 1}/{len(reglas)} reglas...")

    print(f"      {reglas_insertadas} reglas insertadas")
    print(f"      {fracciones_insertadas} fracciones insertadas")

    return reglas_insertadas


def actualizar_indice_oficial(cursor, reglas, estructura):
    """Actualiza la tabla indice_oficial con los datos extraídos."""
    print("   Actualizando índice oficial...")

    codigo = RMF_INFO['codigo']

    # Limpiar índice existente
    cursor.execute("DELETE FROM indice_oficial WHERE ley_codigo = %s", (codigo,))

    # Insertar estructura
    for titulo in estructura.get('titulos', []):
        cursor.execute("""
            INSERT INTO indice_oficial (ley_codigo, tipo, numero, nombre)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (ley_codigo, tipo, numero) DO UPDATE SET nombre = EXCLUDED.nombre
        """, (codigo, 'titulo', titulo['numero'], titulo['nombre']))

    for cap in estructura.get('capitulos', []):
        cursor.execute("""
            INSERT INTO indice_oficial (ley_codigo, tipo, numero, nombre)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (ley_codigo, tipo, numero) DO UPDATE SET nombre = EXCLUDED.nombre
        """, (codigo, 'capitulo', cap['numero'], cap['nombre']))

    for sec in estructura.get('secciones', []):
        cursor.execute("""
            INSERT INTO indice_oficial (ley_codigo, tipo, numero, nombre)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (ley_codigo, tipo, numero) DO UPDATE SET nombre = EXCLUDED.nombre
        """, (codigo, 'seccion', sec['numero'], sec['nombre']))

    for subsec in estructura.get('subsecciones', []):
        cursor.execute("""
            INSERT INTO indice_oficial (ley_codigo, tipo, numero, nombre)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (ley_codigo, tipo, numero) DO UPDATE SET nombre = EXCLUDED.nombre
        """, (codigo, 'subseccion', subsec['numero'], subsec['nombre']))

    # Insertar reglas
    for regla in reglas:
        cursor.execute("""
            INSERT INTO indice_oficial (ley_codigo, tipo, numero, nombre, pagina)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (ley_codigo, tipo, numero) DO UPDATE SET
                nombre = EXCLUDED.nombre,
                pagina = EXCLUDED.pagina
        """, (
            codigo, 'regla', regla['numero'],
            regla.get('titulo'), regla.get('pagina')
        ))

    print(f"      Índice actualizado con {len(reglas)} reglas")


def main():
    """Ejecuta la importación completa desde PDF."""
    limpiar = '--limpiar' in sys.argv

    print("=" * 60)
    print("IMPORTADOR RMF DESDE PDF")
    print("=" * 60)

    # Cargar JSON
    print("\n1. Cargando JSON extraído...")
    data = cargar_json()
    estructura = data.get('estructura', {})
    reglas = data.get('reglas', [])

    print(f"   Estructura: {data.get('stats', {})}")
    print(f"   Reglas: {len(reglas)}")

    # Conectar a PostgreSQL
    print("\n2. Conectando a PostgreSQL...")
    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()

    try:
        # Limpiar si se solicitó
        if limpiar:
            print("\n3. Limpiando datos existentes...")
            limpiar_rmf_existente(cursor, RMF_INFO['codigo'])
        else:
            # Verificar si ya existe
            cursor.execute("SELECT id FROM leyes WHERE codigo = %s", (RMF_INFO['codigo'],))
            if cursor.fetchone():
                print(f"\n   ADVERTENCIA: Ya existe {RMF_INFO['codigo']}.")
                print("   Usa --limpiar para reemplazar los datos existentes.")
                return

        # Insertar ley
        print("\n4. Insertando ley...")
        ley_id = insertar_ley(cursor)
        print(f"   Ley ID: {ley_id}")

        # Insertar estructura
        print("\n5. Insertando estructura...")
        divisiones_ids = insertar_estructura(cursor, ley_id, estructura)

        # Crear capítulos virtuales
        print("\n6. Creando capítulos virtuales...")
        divisiones_ids = crear_divisiones_virtuales(cursor, ley_id, reglas, divisiones_ids)

        # Insertar reglas
        print("\n7. Insertando reglas...")
        total_reglas = insertar_reglas(cursor, ley_id, reglas, divisiones_ids)

        # Actualizar índice oficial
        print("\n8. Actualizando índice oficial...")
        actualizar_indice_oficial(cursor, reglas, estructura)

        # Commit
        conn.commit()

        print("\n" + "=" * 60)
        print("IMPORTACIÓN COMPLETADA")
        print("=" * 60)
        print(f"   Reglas importadas: {total_reglas}")
        print(f"   Divisiones: {len(divisiones_ids)}")

        # Verificación rápida
        cursor.execute("""
            SELECT
                (SELECT COUNT(*) FROM articulos WHERE ley_id = %s) as reglas,
                (SELECT COUNT(*) FROM divisiones WHERE ley_id = %s) as divisiones,
                (SELECT COUNT(*) FROM fracciones f JOIN articulos a ON f.articulo_id = a.id WHERE a.ley_id = %s) as fracciones
        """, (ley_id, ley_id, ley_id))
        row = cursor.fetchone()
        print(f"\n   Verificación BD:")
        print(f"      Reglas:     {row[0]}")
        print(f"      Divisiones: {row[1]}")
        print(f"      Fracciones: {row[2]}")

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
