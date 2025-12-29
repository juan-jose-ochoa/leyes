#!/usr/bin/env python3
"""
Importador de leyes para esquema leyesmx.

Lee archivos JSON generados por extraer.py e inserta en PostgreSQL.

Uso:
    python scripts/leyesmx/importar.py CFF
    python scripts/leyesmx/importar.py CFF --limpiar  # Borra datos anteriores
"""

import json
import os
import sys
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("Error: psycopg2 no instalado. Ejecuta: pip install psycopg2-binary")
    sys.exit(1)

from config import get_config

BASE_DIR = Path(__file__).parent.parent.parent


def get_connection():
    """Obtiene conexión a PostgreSQL usando variables de entorno."""
    return psycopg2.connect(
        host=os.environ.get("PG_HOST", "localhost"),
        port=os.environ.get("PG_PORT", "5432"),
        database=os.environ.get("PG_DB", "digiapps"),
        user=os.environ.get("PG_USER", "leyesmx"),
        password=os.environ.get("PG_PASS", "leyesmx")
    )


def limpiar_ley(conn, codigo: str):
    """Elimina todos los datos de una ley."""
    with conn.cursor() as cur:
        # El CASCADE en las FK debería limpiar todo
        cur.execute("DELETE FROM leyesmx.leyes WHERE codigo = %s", (codigo,))
        conn.commit()
        print(f"   Datos anteriores de {codigo} eliminados")


def importar_ley(conn, codigo: str, config: dict):
    """Inserta la ley en el catálogo."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO leyesmx.leyes (
                codigo, nombre, nombre_corto, tipo,
                ley_base, anio,
                url_fuente,
                divisiones_permitidas, parrafos_permitidos
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (codigo) DO UPDATE SET
                nombre = EXCLUDED.nombre,
                nombre_corto = EXCLUDED.nombre_corto,
                url_fuente = EXCLUDED.url_fuente
        """, (
            codigo,
            config["nombre"],
            config.get("nombre_corto"),
            config["tipo"],
            config.get("ley_base"),
            config.get("anio"),
            config.get("url_fuente"),
            config["divisiones_permitidas"],
            config["parrafos_permitidos"],
        ))
        conn.commit()


def importar_estructura(conn, codigo: str, estructura_path: Path):
    """Importa divisiones desde estructura.json."""
    with open(estructura_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    divisiones = data.get("divisiones", [])
    if not divisiones:
        print("   No hay divisiones para importar")
        return

    # Mapeo orden -> id para resolver padre_orden
    orden_to_id = {}

    with conn.cursor() as cur:
        for div in divisiones:
            padre_id = orden_to_id.get(div["padre_orden"]) if div["padre_orden"] else None

            cur.execute("""
                INSERT INTO leyesmx.divisiones (ley, padre_id, tipo, numero, numero_orden, nombre)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                codigo,
                padre_id,
                div["tipo"],
                div["numero"],
                div["orden"],
                div.get("nombre")
            ))

            div_id = cur.fetchone()[0]
            orden_to_id[div["orden"]] = div_id

        conn.commit()

    print(f"   {len(divisiones)} divisiones importadas")
    return orden_to_id


def importar_contenido(conn, codigo: str, contenido_path: Path, tipo_contenido: str):
    """Importa artículos y párrafos desde contenido.json."""
    with open(contenido_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    articulos = data.get("articulos", [])
    if not articulos:
        print("   No hay artículos para importar")
        return

    total_parrafos = 0

    with conn.cursor() as cur:
        # Obtener la primera división para asignar artículos
        # (simplificación: asignar todos a la primera división)
        cur.execute("""
            SELECT id FROM leyesmx.divisiones
            WHERE ley = %s
            ORDER BY numero_orden
            LIMIT 1
        """, (codigo,))
        result = cur.fetchone()
        default_division_id = result[0] if result else None

        if not default_division_id:
            print("   ERROR: No hay divisiones, no se pueden importar artículos")
            return

        for art in articulos:
            # Insertar artículo
            cur.execute("""
                INSERT INTO leyesmx.articulos (ley, division_id, numero, tipo, orden)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                codigo,
                default_division_id,  # TODO: mapear correctamente a división
                art["numero"],
                art.get("tipo", tipo_contenido),
                art["orden"]
            ))
            articulo_id = cur.fetchone()[0]

            # Insertar párrafos
            for parr in art.get("parrafos", []):
                cur.execute("""
                    INSERT INTO leyesmx.parrafos (
                        ley, articulo_id, numero, padre_numero,
                        tipo, identificador, contenido
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    codigo,
                    articulo_id,
                    parr["numero"],
                    parr.get("padre_numero"),
                    parr["tipo"],
                    parr.get("identificador"),
                    parr["contenido"]
                ))
                total_parrafos += 1

        conn.commit()

    print(f"   {len(articulos)} artículos, {total_parrafos} párrafos importados")


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/leyesmx/importar.py <CODIGO> [--limpiar]")
        sys.exit(1)

    codigo = sys.argv[1].upper()
    limpiar = '--limpiar' in sys.argv

    print("=" * 60)
    print(f"IMPORTADOR LEYESMX: {codigo}")
    print("=" * 60)

    # Obtener configuración
    try:
        config = get_config(codigo)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Rutas de archivos
    if config.get("pdf_path"):
        output_dir = BASE_DIR / Path(config["pdf_path"]).parent
    else:
        print("ERROR: pdf_path no configurado")
        sys.exit(1)

    estructura_path = output_dir / "estructura.json"
    contenido_path = output_dir / "contenido.json"

    # Verificar archivos
    print("\n1. Verificando archivos...")
    if not estructura_path.exists():
        print(f"   AVISO: {estructura_path.name} no existe")
    else:
        print(f"   {estructura_path.name} encontrado")

    if not contenido_path.exists():
        print(f"   ERROR: {contenido_path.name} no existe")
        print("   Ejecuta primero: python scripts/leyesmx/extraer.py", codigo)
        sys.exit(1)
    else:
        print(f"   {contenido_path.name} encontrado")

    # Conectar a BD
    print("\n2. Conectando a PostgreSQL...")
    try:
        conn = get_connection()
        print(f"   Conectado a {os.environ.get('PGDATABASE', 'digiapps')}")
    except Exception as e:
        print(f"   ERROR: {e}")
        sys.exit(1)

    try:
        # Limpiar si se solicita
        if limpiar:
            print("\n3. Limpiando datos anteriores...")
            limpiar_ley(conn, codigo)

        # Importar ley
        print("\n4. Importando catálogo de ley...")
        importar_ley(conn, codigo, config)
        print(f"   Ley {codigo} registrada")

        # Importar estructura
        if estructura_path.exists():
            print("\n5. Importando estructura...")
            importar_estructura(conn, codigo, estructura_path)
        else:
            print("\n5. Saltando estructura (archivo no existe)")

        # Importar contenido
        print("\n6. Importando contenido...")
        importar_contenido(conn, codigo, contenido_path, config["tipo_contenido"])

    finally:
        conn.close()

    print("\n" + "=" * 60)
    print("IMPORTACIÓN COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()
