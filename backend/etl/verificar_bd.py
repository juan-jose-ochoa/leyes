#!/usr/bin/env python3
"""
Verificador de integridad de base de datos para leyesmx.

Verifica que los datos importados coincidan con la estructura esperada.
Usar después de importar para confirmar integridad.

Uso:
    python backend/etl/verificar_bd.py CFF
    python backend/etl/verificar_bd.py CFF --detalle
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
    """Obtiene conexión a PostgreSQL."""
    return psycopg2.connect(
        host=os.environ.get("PG_HOST", "localhost"),
        port=os.environ.get("PG_PORT", "5432"),
        database=os.environ.get("PG_DB", "digiapps"),
        user=os.environ.get("PG_USER", "leyesmx"),
        password=os.environ.get("PG_PASS", "leyesmx")
    )


def cargar_mapa_estructura(mapa_path: Path) -> dict:
    """Carga mapa_estructura.json y retorna datos completos."""
    with open(mapa_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def verificar_ley_existe(conn, codigo: str) -> bool:
    """Verifica que la ley exista en el catálogo."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM leyesmx.leyes WHERE codigo = %s", (codigo,))
        return cur.fetchone() is not None


def verificar_divisiones(conn, codigo: str, mapa: dict, detalle: bool) -> tuple:
    """Verifica que las divisiones en BD coincidan con mapa_estructura."""
    errores = []

    # Contar divisiones esperadas
    titulos_esperados = len(mapa.get("titulos", {}))
    capitulos_esperados = sum(
        len(t.get("capitulos", {}))
        for t in mapa.get("titulos", {}).values()
    )

    with conn.cursor() as cur:
        # Contar divisiones reales
        cur.execute("""
            SELECT tipo, COUNT(*) FROM leyesmx.divisiones
            WHERE ley = %s GROUP BY tipo
        """, (codigo,))

        reales = {row[0]: row[1] for row in cur.fetchall()}

    titulos_reales = reales.get("titulo", 0)
    capitulos_reales = reales.get("capitulo", 0)

    if titulos_reales != titulos_esperados:
        errores.append(f"Títulos: esperado {titulos_esperados}, real {titulos_reales}")

    if capitulos_reales != capitulos_esperados:
        errores.append(f"Capítulos: esperado {capitulos_esperados}, real {capitulos_reales}")

    return len(errores) == 0, errores


def verificar_articulos_por_capitulo(conn, codigo: str, mapa: dict, detalle: bool) -> tuple:
    """Verifica que cada capítulo tenga los artículos correctos."""
    errores = []

    # Construir esperado por (titulo, capitulo) para evitar colisiones
    esperado_por_cap = {}
    for titulo_num, titulo_data in mapa.get("titulos", {}).items():
        for cap_num, cap_data in titulo_data.get("capitulos", {}).items():
            articulos = cap_data.get("articulos", [])
            key = (titulo_num, cap_num)
            esperado_por_cap[key] = {
                "titulo": titulo_num,
                "capitulo": cap_num,
                "total": len(articulos),
                "articulos": set(articulos)
            }

    # Obtener real de BD con título padre
    with conn.cursor() as cur:
        cur.execute("""
            SELECT p.numero as titulo, d.numero as capitulo, a.numero as articulo
            FROM leyesmx.divisiones d
            JOIN leyesmx.divisiones p ON p.id = d.padre_id AND p.ley = d.ley
            JOIN leyesmx.articulos a ON a.division_id = d.id AND a.ley = d.ley
            WHERE d.ley = %s AND d.tipo = 'capitulo'
            ORDER BY p.numero, d.numero, a.orden
        """, (codigo,))

        real_por_cap = {}
        for row in cur.fetchall():
            titulo_num = row[0]
            cap_num = row[1]
            art_num = row[2]
            key = (titulo_num, cap_num)
            if key not in real_por_cap:
                real_por_cap[key] = set()
            real_por_cap[key].add(art_num)

    # Comparar
    for key, esperado in esperado_por_cap.items():
        real = real_por_cap.get(key, set())
        titulo_num, cap_num = key

        if len(real) != esperado["total"]:
            errores.append(f"Título {titulo_num}, Cap {cap_num}: esperado {esperado['total']}, real {len(real)}")

            if detalle:
                faltantes = esperado["articulos"] - real
                extras = real - esperado["articulos"]
                if faltantes:
                    errores.append(f"  Faltantes: {sorted(faltantes)[:10]}")
                if extras:
                    errores.append(f"  Extras: {sorted(extras)[:10]}")

    # Verificar capítulos huérfanos (en BD pero no en mapa)
    for key in real_por_cap:
        if key not in esperado_por_cap:
            titulo_num, cap_num = key
            errores.append(f"Título {titulo_num}, Cap {cap_num}: existe en BD pero no en mapa_estructura")

    return len(errores) == 0, errores


def verificar_articulos_huerfanos(conn, codigo: str) -> tuple:
    """Verifica que no haya artículos sin división o con división inválida."""
    errores = []

    with conn.cursor() as cur:
        # Artículos cuya división no existe
        cur.execute("""
            SELECT a.numero, a.division_id
            FROM leyesmx.articulos a
            LEFT JOIN leyesmx.divisiones d ON d.id = a.division_id AND d.ley = a.ley
            WHERE a.ley = %s AND d.id IS NULL
        """, (codigo,))

        huerfanos = cur.fetchall()
        if huerfanos:
            errores.append(f"{len(huerfanos)} artículos con división inválida")
            for art in huerfanos[:5]:
                errores.append(f"  Art {art[0]}: division_id={art[1]} no existe")

    return len(errores) == 0, errores


def verificar_divisiones_vacias(conn, codigo: str) -> tuple:
    """Verifica que no haya divisiones (capítulos) sin artículos.

    Un capítulo NO está vacío si:
    - Tiene artículos directos, O
    - Tiene secciones que contienen artículos
    """
    errores = []

    with conn.cursor() as cur:
        # Capítulos sin artículos directos Y sin secciones con artículos
        cur.execute("""
            SELECT d.tipo, d.numero, d.nombre
            FROM leyesmx.divisiones d
            WHERE d.ley = %s AND d.tipo = 'capitulo'
              -- Sin artículos directos
              AND NOT EXISTS (
                  SELECT 1 FROM leyesmx.articulos a
                  WHERE a.division_id = d.id AND a.ley = d.ley
              )
              -- Sin secciones con artículos
              AND NOT EXISTS (
                  SELECT 1 FROM leyesmx.divisiones sec
                  JOIN leyesmx.articulos a ON a.division_id = sec.id AND a.ley = sec.ley
                  WHERE sec.padre_id = d.id AND sec.ley = d.ley AND sec.tipo = 'seccion'
              )
        """, (codigo,))

        vacias = cur.fetchall()
        if vacias:
            errores.append(f"{len(vacias)} capítulos sin artículos:")
            for div in vacias:
                errores.append(f"  {div[0]} {div[1]}: {div[2] or '(sin nombre)'}")

    return len(errores) == 0, errores


def main():
    if len(sys.argv) < 2:
        print("Uso: python backend/etl/verificar_bd.py <CODIGO> [--detalle]")
        sys.exit(1)

    codigo = sys.argv[1].upper()
    detalle = '--detalle' in sys.argv

    print("=" * 60)
    print(f"VERIFICADOR DE BD: {codigo}")
    print("=" * 60)

    # Obtener configuración
    try:
        config = get_config(codigo)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Ruta del mapa - mapa_estructura.json es la fuente autoritativa
    output_dir = BASE_DIR / Path(config["pdf_path"]).parent
    mapa_path = output_dir / "mapa_estructura.json"

    if not mapa_path.exists():
        print(f"ERROR: {mapa_path.name} no existe")
        sys.exit(1)

    mapa = cargar_mapa_estructura(mapa_path)

    # Conectar
    print("\n1. Conectando a PostgreSQL...")
    try:
        conn = get_connection()
        print(f"   Conectado a {os.environ.get('PG_DB', 'digiapps')}")
    except Exception as e:
        print(f"   ERROR: {e}")
        sys.exit(1)

    exito_total = True

    try:
        # Verificar ley existe
        print("\n2. Verificando ley en catálogo...")
        if not verificar_ley_existe(conn, codigo):
            print(f"   ERROR: Ley {codigo} no existe en BD")
            sys.exit(1)
        print(f"   OK: Ley {codigo} encontrada")

        # Verificar divisiones
        print("\n3. Verificando divisiones...")
        ok, errores = verificar_divisiones(conn, codigo, mapa, detalle)
        if ok:
            print("   OK: Divisiones correctas")
        else:
            exito_total = False
            for err in errores:
                print(f"   ERROR: {err}")

        # Verificar artículos por capítulo
        print("\n4. Verificando artículos por capítulo...")
        ok, errores = verificar_articulos_por_capitulo(conn, codigo, mapa, detalle)
        if ok:
            print("   OK: Artículos correctamente asignados")
        else:
            exito_total = False
            for err in errores:
                print(f"   ERROR: {err}")

        # Verificar huérfanos
        print("\n5. Verificando artículos huérfanos...")
        ok, errores = verificar_articulos_huerfanos(conn, codigo)
        if ok:
            print("   OK: No hay artículos huérfanos")
        else:
            exito_total = False
            for err in errores:
                print(f"   ERROR: {err}")

        # Verificar divisiones vacías
        print("\n6. Verificando divisiones vacías...")
        ok, errores = verificar_divisiones_vacias(conn, codigo)
        if ok:
            print("   OK: Todos los capítulos tienen artículos")
        else:
            exito_total = False
            for err in errores:
                print(f"   ERROR: {err}")

    finally:
        conn.close()

    print("\n" + "=" * 60)
    if exito_total:
        print("VERIFICACIÓN EXITOSA - Integridad OK")
    else:
        print("VERIFICACIÓN FALLIDA - Ver errores arriba")
    print("=" * 60)

    sys.exit(0 if exito_total else 1)


if __name__ == "__main__":
    main()
