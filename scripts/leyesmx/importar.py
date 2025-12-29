#!/usr/bin/env python3
"""
Importador de leyes para esquema leyesmx.

Lee archivos JSON generados por extraer.py e inserta en PostgreSQL.
FAIL FAST: Valida antes de importar, verifica después.

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


def normalizar_numero(numero: str) -> str:
    """Normaliza número de artículo para comparación.

    Reglas:
    - Mayúsculas
    - Guiones y espacios tratados igual: '4o-A' == '4o A'
    - Múltiples espacios -> uno solo
    """
    s = numero.upper().strip()
    # Reemplazar guiones por espacios
    s = s.replace('-', ' ')
    # Colapsar múltiples espacios
    s = ' '.join(s.split())
    return s


def cargar_mapa_estructura(mapa_path: Path) -> dict:
    """Carga mapa_estructura.json y crea lookup artículo -> (titulo, capitulo)."""
    with open(mapa_path, 'r', encoding='utf-8') as f:
        mapa = json.load(f)

    # Crear lookup: numero_articulo_normalizado -> (titulo, capitulo, numero_original)
    articulo_a_division = {}

    for titulo_num, titulo_data in mapa.get("titulos", {}).items():
        for cap_num, cap_data in titulo_data.get("capitulos", {}).items():
            for articulo in cap_data.get("articulos", []):
                key = normalizar_numero(articulo)
                articulo_a_division[key] = (titulo_num, cap_num)

    return articulo_a_division


def validar_antes_de_importar(contenido_path: Path, mapa_path: Path) -> bool:
    """Valida que todos los artículos tengan división asignada. FAIL FAST."""
    print("\n   Validando asignación de divisiones...")

    if not mapa_path.exists():
        print(f"   ERROR: {mapa_path.name} no existe - requerido para asignar divisiones")
        return False

    with open(contenido_path, 'r', encoding='utf-8') as f:
        contenido = json.load(f)

    articulo_a_division = cargar_mapa_estructura(mapa_path)

    articulos = contenido.get("articulos", [])
    sin_division = []

    for art in articulos:
        numero = art["numero"]
        key = normalizar_numero(numero)
        if key not in articulo_a_division:
            sin_division.append(numero)

    if sin_division:
        print(f"   ERROR: {len(sin_division)} artículos sin división asignada:")
        print(f"   {sin_division[:10]}{'...' if len(sin_division) > 10 else ''}")
        return False

    print(f"   OK: {len(articulos)} artículos con división asignada")
    return True


def limpiar_ley(conn, codigo: str):
    """Elimina todos los datos de una ley."""
    with conn.cursor() as cur:
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


def importar_estructura(conn, codigo: str, estructura_path: Path) -> dict:
    """Importa divisiones y retorna mapeo (titulo, capitulo) -> id."""
    with open(estructura_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    divisiones = data.get("divisiones", [])
    if not divisiones:
        print("   No hay divisiones para importar")
        return {}

    orden_to_id = {}
    orden_to_numero = {}  # orden -> numero (para tracking de títulos)
    division_lookup = {}  # (titulo_num, cap_num) -> id

    with conn.cursor() as cur:
        current_titulo = None

        for div in divisiones:
            padre_id = orden_to_id.get(div["padre_orden"]) if div.get("padre_orden") else None

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
            orden_to_numero[div["orden"]] = div["numero"]

            if div["tipo"] == "titulo":
                current_titulo = div["numero"]
            elif div["tipo"] == "capitulo" and current_titulo:
                # Normalizar para lookup: (TITULO, CAP) -> id
                key = (normalizar_numero(current_titulo), normalizar_numero(div["numero"]))
                division_lookup[key] = div_id

        conn.commit()

    print(f"   {len(divisiones)} divisiones importadas")
    return division_lookup


def importar_contenido(conn, codigo: str, contenido_path: Path, mapa_path: Path,
                       division_lookup: dict, tipo_contenido: str):
    """Importa artículos asignando división correcta desde mapa_estructura."""
    with open(contenido_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    articulo_a_division = cargar_mapa_estructura(mapa_path)

    articulos = data.get("articulos", [])
    if not articulos:
        print("   No hay artículos para importar")
        return

    total_parrafos = 0
    errores = []

    with conn.cursor() as cur:
        for art in articulos:
            numero = art["numero"]
            key = normalizar_numero(numero)

            # Obtener división desde mapa_estructura
            division_info = articulo_a_division.get(key)
            if not division_info:
                errores.append(f"Artículo {numero}: sin división en mapa")
                continue

            titulo_num, cap_num = division_info

            # Buscar division_id usando (titulo, capitulo) normalizado
            lookup_key = (normalizar_numero(titulo_num), normalizar_numero(cap_num))
            division_id = division_lookup.get(lookup_key)

            if not division_id:
                errores.append(f"Artículo {numero}: {titulo_num}/{cap_num} no encontrado en BD")
                continue

            # Insertar artículo
            cur.execute("""
                INSERT INTO leyesmx.articulos (ley, division_id, numero, tipo, orden)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                codigo,
                division_id,
                numero,
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

    if errores:
        print(f"   ERRORES ({len(errores)}):")
        for err in errores[:5]:
            print(f"      {err}")
        if len(errores) > 5:
            print(f"      ... y {len(errores) - 5} más")

    print(f"   {len(articulos) - len(errores)} artículos, {total_parrafos} párrafos importados")
    return len(errores) == 0


def verificar_post_importacion(conn, codigo: str, mapa_path: Path) -> bool:
    """Verifica integridad después de importar. FAIL FAST."""
    print("\n7. Verificando integridad post-importación...")

    articulo_a_division = cargar_mapa_estructura(mapa_path)

    # Contar artículos esperados por capítulo
    esperado_por_cap = {}
    for numero, (titulo, cap) in articulo_a_division.items():
        key = cap
        esperado_por_cap[key] = esperado_por_cap.get(key, 0) + 1

    # Contar artículos reales por capítulo en BD
    with conn.cursor() as cur:
        cur.execute("""
            SELECT d.numero as capitulo, COUNT(a.id) as total
            FROM leyesmx.divisiones d
            LEFT JOIN leyesmx.articulos a ON a.division_id = d.id AND a.ley = d.ley
            WHERE d.ley = %s AND d.tipo = 'capitulo'
            GROUP BY d.numero
        """, (codigo,))

        real_por_cap = {row[0]: row[1] for row in cur.fetchall()}

    errores = []
    for cap, esperado in esperado_por_cap.items():
        real = real_por_cap.get(cap, 0)
        if real != esperado:
            errores.append(f"   Capítulo {cap}: esperado {esperado}, real {real}")

    if errores:
        print("   ERRORES de integridad:")
        for err in errores:
            print(err)
        return False

    print(f"   OK: {len(esperado_por_cap)} capítulos verificados")
    return True


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
    # estructura_esperada.json es la fuente autoritativa verificada
    mapa_path = output_dir / "estructura_esperada.json"

    # Verificar archivos
    print("\n1. Verificando archivos...")
    archivos_ok = True

    for path, requerido in [(estructura_path, False), (contenido_path, True), (mapa_path, True)]:
        if path.exists():
            print(f"   {path.name} encontrado")
        elif requerido:
            print(f"   ERROR: {path.name} no existe (REQUERIDO)")
            archivos_ok = False
        else:
            print(f"   AVISO: {path.name} no existe")

    if not archivos_ok:
        print("\nABORTANDO: Archivos requeridos faltantes")
        sys.exit(1)

    # FAIL FAST: Validar antes de importar
    print("\n2. Validación pre-importación...")
    if not validar_antes_de_importar(contenido_path, mapa_path):
        print("\nABORTANDO: Validación fallida")
        sys.exit(1)

    # Conectar a BD
    print("\n3. Conectando a PostgreSQL...")
    try:
        conn = get_connection()
        print(f"   Conectado a {os.environ.get('PG_DB', 'digiapps')}")
    except Exception as e:
        print(f"   ERROR: {e}")
        sys.exit(1)

    exito = True
    try:
        # Limpiar si se solicita
        if limpiar:
            print("\n4. Limpiando datos anteriores...")
            limpiar_ley(conn, codigo)

        # Importar ley
        print("\n4. Importando catálogo de ley...")
        importar_ley(conn, codigo, config)
        print(f"   Ley {codigo} registrada")

        # Importar estructura
        division_lookup = {}
        if estructura_path.exists():
            print("\n5. Importando estructura...")
            division_lookup = importar_estructura(conn, codigo, estructura_path)
        else:
            print("\n5. Saltando estructura (archivo no existe)")

        # Importar contenido
        print("\n6. Importando contenido...")
        if not importar_contenido(conn, codigo, contenido_path, mapa_path,
                                   division_lookup, config["tipo_contenido"]):
            exito = False

        # FAIL FAST: Verificar después de importar
        if exito and not verificar_post_importacion(conn, codigo, mapa_path):
            exito = False

    finally:
        conn.close()

    print("\n" + "=" * 60)
    if exito:
        print("IMPORTACIÓN COMPLETADA EXITOSAMENTE")
    else:
        print("IMPORTACIÓN COMPLETADA CON ERRORES")
    print("=" * 60)

    sys.exit(0 if exito else 1)


if __name__ == "__main__":
    main()
