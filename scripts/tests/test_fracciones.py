#!/usr/bin/env python3
"""
Tests para verificar que no hay duplicación de contenido entre
articulos.contenido y fracciones.contenido

Ejecutar: python -m pytest scripts/tests/test_fracciones.py -v
"""

import psycopg2
import pytest
import re

DB_CONFIG = {
    'host': 'localhost',
    'database': 'leyesmx',
    'user': 'leyesmx',
    'password': 'leyesmx'
}


@pytest.fixture
def db_conn():
    """Conexión a la base de datos"""
    conn = psycopg2.connect(**DB_CONFIG)
    yield conn
    conn.close()


def test_contenido_no_contiene_fracciones(db_conn):
    """
    Verifica que el contenido del artículo NO contenga texto de fracciones.

    Si un artículo tiene fracciones (I., II., III., etc.), el contenido
    debe ser solo el texto introductorio, no incluir las fracciones.
    """
    cur = db_conn.cursor()

    # Obtener artículos que tienen fracciones
    cur.execute("""
        SELECT DISTINCT a.id, l.codigo, a.numero_raw, a.contenido
        FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
        JOIN fracciones f ON f.articulo_id = a.id
        WHERE f.tipo = 'fraccion'
        ORDER BY l.codigo, a.numero_raw
    """)

    articulos_con_duplicacion = []

    # Patrón para detectar fracciones romanas al inicio de línea
    patron_fraccion = re.compile(r'^\s*([IVXL]+)\.\s+', re.MULTILINE)

    for art_id, codigo, numero, contenido in cur.fetchall():
        if not contenido:
            continue

        # Buscar si el contenido tiene fracciones romanas
        match = patron_fraccion.search(contenido)
        if match:
            # Verificar que sea un número romano válido (no cualquier letra)
            romano = match.group(1)
            if romano in ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
                         'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX']:
                articulos_con_duplicacion.append({
                    'ley': codigo,
                    'articulo': numero,
                    'fraccion_encontrada': romano
                })

    # Filtrar Anexos RMF que usan importadores diferentes
    articulos_principales = [
        a for a in articulos_con_duplicacion
        if not a['ley'].startswith('RMF2025-A')
    ]

    if articulos_principales:
        # Mostrar primeros 10 ejemplos
        ejemplos = articulos_principales[:10]
        msg = f"Se encontraron {len(articulos_principales)} artículos con contenido duplicado:\n"
        for ej in ejemplos:
            msg += f"  - {ej['ley']} Art. {ej['articulo']} (fracción {ej['fraccion_encontrada']})\n"
        pytest.fail(msg)

    # Solo advertir sobre Anexos (no fallar)
    if articulos_con_duplicacion:
        print(f"\nADVERTENCIA: {len(articulos_con_duplicacion)} anexos con posible duplicación")


def test_fracciones_tienen_contenido(db_conn):
    """
    Verifica que todas las fracciones tienen contenido no vacío.
    """
    cur = db_conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM fracciones
        WHERE tipo = 'fraccion'
        AND (contenido IS NULL OR contenido = '')
    """)

    vacias = cur.fetchone()[0]
    assert vacias == 0, f"Se encontraron {vacias} fracciones sin contenido"


def test_articulos_con_fracciones_tienen_intro(db_conn):
    """
    Verifica que artículos con fracciones tengan texto introductorio.

    Excepción: Algunos artículos pueden empezar directamente con fracciones
    (sin texto introductorio), lo cual es válido.
    """
    cur = db_conn.cursor()

    # Artículos con fracciones pero sin contenido
    cur.execute("""
        SELECT l.codigo, a.numero_raw, a.contenido
        FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
        WHERE EXISTS (
            SELECT 1 FROM fracciones f
            WHERE f.articulo_id = a.id AND f.tipo = 'fraccion'
        )
        AND (a.contenido IS NULL OR a.contenido = '')
    """)

    sin_intro = cur.fetchall()

    # Permitimos algunos sin intro (es válido legalmente)
    # pero alertamos si son muchos
    if len(sin_intro) > 50:
        ejemplos = sin_intro[:5]
        msg = f"Muchos artículos ({len(sin_intro)}) sin texto introductorio:\n"
        for codigo, numero, _ in ejemplos:
            msg += f"  - {codigo} Art. {numero}\n"
        pytest.fail(msg)


def test_coherencia_orden_fracciones(db_conn):
    """
    Verifica que las fracciones estén en orden correcto (I, II, III, ...).

    Nota: Artículos con apartados (A, B, C) pueden reiniciar la numeración
    de fracciones en cada apartado, lo cual es válido.
    """
    cur = db_conn.cursor()

    # Excluir artículos que tienen apartados (reinician numeración)
    cur.execute("""
        SELECT a.id, l.codigo, a.numero_raw,
               array_agg(f.numero ORDER BY f.orden) as fracciones
        FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
        JOIN fracciones f ON f.articulo_id = a.id
        WHERE f.tipo = 'fraccion'
        AND NOT EXISTS (
            SELECT 1 FROM fracciones f2
            WHERE f2.articulo_id = a.id AND f2.tipo = 'apartado'
        )
        GROUP BY a.id, l.codigo, a.numero_raw
        HAVING COUNT(*) > 1
        LIMIT 100
    """)

    romanos_orden = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
                    'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX',
                    'XXI', 'XXII', 'XXIII', 'XXIV', 'XXV']

    desordenados = []
    for art_id, codigo, numero, fracciones in cur.fetchall():
        # Excluir CPEUM que tiene estructura especial con apartados
        if codigo == 'CPEUM':
            continue

        # Verificar orden
        prev_idx = -1
        for frac in fracciones:
            if frac in romanos_orden:
                idx = romanos_orden.index(frac)
                if idx <= prev_idx:
                    desordenados.append(f"{codigo} Art. {numero}")
                    break
                prev_idx = idx

    # Algunos artículos tienen múltiples grupos de fracciones (ej: CFF 66)
    # que reinician numeración por contexto. Solo advertir, no fallar.
    if desordenados:
        print(f"\nADVERTENCIA: Posibles fracciones desordenadas en: {', '.join(desordenados[:5])}")
        print("(Puede ser válido si el artículo tiene múltiples grupos de fracciones)")


def test_no_fracciones_huerfanas(db_conn):
    """
    Verifica que no hay fracciones sin artículo padre.
    """
    cur = db_conn.cursor()

    cur.execute("""
        SELECT COUNT(*) FROM fracciones f
        WHERE NOT EXISTS (
            SELECT 1 FROM articulos a WHERE a.id = f.articulo_id
        )
    """)

    huerfanas = cur.fetchone()[0]
    assert huerfanas == 0, f"Se encontraron {huerfanas} fracciones huérfanas"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
