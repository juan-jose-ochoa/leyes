#!/usr/bin/env python3
"""
Gestión de checksums para verificar cambios en artículos.

Uso:
    python backend/etl/checksums.py CFF --guardar    # Guarda checksums actuales como referencia
    python backend/etl/checksums.py CFF --comparar  # Compara BD contra referencia guardada
    python backend/etl/checksums.py CFF --diff 66   # Muestra diferencia de un artículo específico
"""

import hashlib
import json
import os
import sys
from pathlib import Path

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 no instalado")
    sys.exit(1)

BASE_DIR = Path(__file__).parent.parent.parent


def get_connection():
    return psycopg2.connect(
        host=os.environ.get("PG_HOST", "localhost"),
        port=os.environ.get("PG_PORT", "5432"),
        database=os.environ.get("PG_DB", "digiapps"),
        user=os.environ.get("PG_USER", "leyesmx"),
        password=os.environ.get("PG_PASS", "leyesmx")
    )


def calcular_checksum(texto: str) -> str:
    """Calcula SHA256 de un texto."""
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()[:16]


def obtener_checksums_bd(conn, ley: str) -> dict:
    """Obtiene checksums de todos los artículos de una ley desde la BD."""
    checksums = {}

    with conn.cursor() as cur:
        # Obtener contenido concatenado de párrafos por artículo
        cur.execute("""
            SELECT
                a.numero,
                STRING_AGG(p.contenido, E'\n' ORDER BY p.numero) as contenido_completo
            FROM leyesmx.articulos a
            JOIN leyesmx.parrafos p ON p.articulo_id = a.id AND p.ley = a.ley
            WHERE a.ley = %s
            GROUP BY a.numero, a.orden
            ORDER BY a.orden
        """, (ley,))

        for numero, contenido in cur.fetchall():
            checksums[numero] = calcular_checksum(contenido)

    return checksums


def obtener_contenido_articulo(conn, ley: str, numero: str) -> str:
    """Obtiene el contenido completo de un artículo."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT STRING_AGG(p.contenido, E'\n' ORDER BY p.numero)
            FROM leyesmx.articulos a
            JOIN leyesmx.parrafos p ON p.articulo_id = a.id AND p.ley = a.ley
            WHERE a.ley = %s AND a.numero = %s
        """, (ley, numero))
        result = cur.fetchone()
        return result[0] if result and result[0] else ""


def ruta_checksums(ley: str) -> Path:
    """Retorna la ruta del archivo de checksums para una ley."""
    ley_lower = ley.lower()
    return BASE_DIR / f"backend/etl/data/{ley_lower}/checksums_verificados.json"


def guardar_checksums(ley: str):
    """Guarda checksums actuales de la BD como referencia verificada."""
    conn = get_connection()
    try:
        checksums = obtener_checksums_bd(conn, ley)

        if not checksums:
            print(f"No se encontraron artículos para {ley}")
            return False

        ruta = ruta_checksums(ley)
        ruta.parent.mkdir(parents=True, exist_ok=True)

        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(checksums, f, indent=2, ensure_ascii=False)

        print(f"Guardados {len(checksums)} checksums en {ruta.name}")
        return True
    finally:
        conn.close()


def comparar_checksums(ley: str) -> dict:
    """Compara checksums actuales contra los verificados."""
    ruta = ruta_checksums(ley)

    if not ruta.exists():
        print(f"No existe archivo de referencia: {ruta}")
        print(f"Ejecuta primero: python backend/etl/checksums.py {ley} --guardar")
        return None

    with open(ruta, 'r', encoding='utf-8') as f:
        verificados = json.load(f)

    conn = get_connection()
    try:
        actuales = obtener_checksums_bd(conn, ley)

        cambios = {
            'modificados': [],
            'nuevos': [],
            'eliminados': []
        }

        # Detectar modificados y nuevos
        for numero, checksum in actuales.items():
            if numero not in verificados:
                cambios['nuevos'].append(numero)
            elif verificados[numero] != checksum:
                cambios['modificados'].append(numero)

        # Detectar eliminados
        for numero in verificados:
            if numero not in actuales:
                cambios['eliminados'].append(numero)

        return cambios
    finally:
        conn.close()


def mostrar_diff(ley: str, numero: str):
    """Muestra el contenido actual de un artículo para revisión."""
    conn = get_connection()
    try:
        contenido = obtener_contenido_articulo(conn, ley, numero)
        if contenido:
            print(f"\n{'='*60}")
            print(f"Artículo {numero} - {ley}")
            print('='*60)
            print(contenido)
            print('='*60)
        else:
            print(f"Artículo {numero} no encontrado en {ley}")
    finally:
        conn.close()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    ley = sys.argv[1].upper()
    accion = sys.argv[2]

    if accion == '--guardar':
        guardar_checksums(ley)

    elif accion == '--comparar':
        cambios = comparar_checksums(ley)
        if cambios is None:
            sys.exit(1)

        total = len(cambios['modificados']) + len(cambios['nuevos']) + len(cambios['eliminados'])

        if total == 0:
            print(f"✓ Sin cambios - todos los artículos coinciden con la referencia")
        else:
            print(f"\nCambios detectados en {ley}:")

            if cambios['modificados']:
                print(f"\n  MODIFICADOS ({len(cambios['modificados'])}):")
                for num in cambios['modificados']:
                    print(f"    - Art. {num}")

            if cambios['nuevos']:
                print(f"\n  NUEVOS ({len(cambios['nuevos'])}):")
                for num in cambios['nuevos']:
                    print(f"    + Art. {num}")

            if cambios['eliminados']:
                print(f"\n  ELIMINADOS ({len(cambios['eliminados'])}):")
                for num in cambios['eliminados']:
                    print(f"    x Art. {num}")

            print(f"\nTotal: {total} cambios")
            print(f"\nPara ver contenido: python backend/etl/checksums.py {ley} --diff <numero>")
            print(f"Para aceptar cambios: python backend/etl/checksums.py {ley} --guardar")

    elif accion == '--diff':
        if len(sys.argv) < 4:
            print("Falta número de artículo")
            sys.exit(1)
        numero = sys.argv[3]
        mostrar_diff(ley, numero)

    else:
        print(f"Acción desconocida: {accion}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
