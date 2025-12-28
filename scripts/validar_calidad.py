#!/usr/bin/env python3
"""
Validación de calidad de datos importados.

Detecta problemas de extracción sin modificar datos.
Ejecutar: python scripts/validar_calidad.py
"""

import psycopg2
import re
from collections import defaultdict

DB_CONFIG = {
    'host': 'localhost',
    'database': 'leyesmx',
    'user': 'leyesmx',
    'password': 'leyesmx'
}


def conectar():
    return psycopg2.connect(**DB_CONFIG)


def validar_titulos_truncados(cur):
    """
    Detecta títulos que empiezan con minúscula (probable truncamiento).
    """
    cur.execute("""
        SELECT l.codigo, a.numero_raw, a.titulo
        FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
        WHERE a.titulo IS NOT NULL
        AND a.titulo ~ '^[a-z]'
        ORDER BY l.codigo, a.numero_raw
    """)

    resultados = cur.fetchall()

    if resultados:
        print("\n" + "=" * 70)
        print("⚠️  TÍTULOS TRUNCADOS (empiezan con minúscula)")
        print("=" * 70)

        por_ley = defaultdict(list)
        for codigo, numero, titulo in resultados:
            por_ley[codigo].append((numero, titulo[:60] + "..." if len(titulo) > 60 else titulo))

        for ley, items in sorted(por_ley.items()):
            print(f"\n{ley}: {len(items)} títulos truncados")
            for numero, titulo in items[:5]:
                print(f"  {numero}: \"{titulo}\"")
            if len(items) > 5:
                print(f"  ... y {len(items) - 5} más")

        return len(resultados)
    return 0


def validar_parrafos_sin_punto(cur):
    """
    Detecta contenido que no termina con puntuación (posible corte abrupto).
    """
    cur.execute("""
        SELECT l.codigo, a.numero_raw, RIGHT(a.contenido, 100) as final
        FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
        WHERE a.contenido IS NOT NULL
        AND LENGTH(a.contenido) > 50
        AND a.contenido !~ '[.;:!?")]\\s*$'
        ORDER BY l.codigo, a.numero_raw
    """)

    resultados = cur.fetchall()

    if resultados:
        print("\n" + "=" * 70)
        print("⚠️  CONTENIDO SIN PUNTUACIÓN FINAL (posible corte abrupto)")
        print("=" * 70)

        por_ley = defaultdict(list)
        for codigo, numero, final in resultados:
            # Mostrar últimos 50 caracteres
            final_clean = final.strip().replace('\n', ' ')[-50:]
            por_ley[codigo].append((numero, final_clean))

        for ley, items in sorted(por_ley.items()):
            print(f"\n{ley}: {len(items)} artículos sin puntuación final")
            for numero, final in items[:5]:
                print(f"  {numero}: ...{final}")
            if len(items) > 5:
                print(f"  ... y {len(items) - 5} más")

        return len(resultados)
    return 0


def validar_fracciones_sin_punto(cur):
    """
    Detecta fracciones que no terminan con puntuación.
    """
    cur.execute("""
        SELECT l.codigo, a.numero_raw, f.tipo, f.numero, RIGHT(f.contenido, 80) as final
        FROM fracciones f
        JOIN articulos a ON f.articulo_id = a.id
        JOIN leyes l ON a.ley_id = l.id
        WHERE f.contenido IS NOT NULL
        AND LENGTH(f.contenido) > 30
        AND f.tipo IN ('fraccion', 'inciso')
        AND f.contenido !~ '[.;:!?")]\\s*$'
        ORDER BY l.codigo, a.numero_raw, f.orden
    """)

    resultados = cur.fetchall()

    if resultados:
        print("\n" + "=" * 70)
        print("⚠️  FRACCIONES SIN PUNTUACIÓN FINAL")
        print("=" * 70)

        por_ley = defaultdict(list)
        for codigo, numero, tipo, frac_num, final in resultados:
            final_clean = final.strip().replace('\n', ' ')[-40:]
            por_ley[codigo].append((numero, tipo, frac_num, final_clean))

        for ley, items in sorted(por_ley.items()):
            print(f"\n{ley}: {len(items)} fracciones sin puntuación")
            for numero, tipo, frac_num, final in items[:5]:
                print(f"  Art. {numero} {tipo} {frac_num or ''}: ...{final}")
            if len(items) > 5:
                print(f"  ... y {len(items) - 5} más")

        return len(resultados)
    return 0


def validar_parrafos_minuscula(cur):
    """
    Detecta párrafos que empiezan con minúscula (posible continuación truncada).
    """
    cur.execute("""
        SELECT l.codigo, a.numero_raw, LEFT(a.contenido, 80) as inicio
        FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
        WHERE a.contenido IS NOT NULL
        AND a.contenido ~ '^[a-z]'
        ORDER BY l.codigo, a.numero_raw
    """)

    resultados = cur.fetchall()

    if resultados:
        print("\n" + "=" * 70)
        print("⚠️  CONTENIDO QUE EMPIEZA CON MINÚSCULA")
        print("=" * 70)

        por_ley = defaultdict(list)
        for codigo, numero, inicio in resultados:
            inicio_clean = inicio.strip().replace('\n', ' ')[:60]
            por_ley[codigo].append((numero, inicio_clean))

        for ley, items in sorted(por_ley.items()):
            print(f"\n{ley}: {len(items)} artículos empiezan con minúscula")
            for numero, inicio in items[:5]:
                print(f"  {numero}: \"{inicio}...\"")
            if len(items) > 5:
                print(f"  ... y {len(items) - 5} más")

        return len(resultados)
    return 0


def validar_contenido_muy_corto(cur):
    """
    Detecta artículos con contenido sospechosamente corto.
    """
    cur.execute("""
        SELECT l.codigo, a.numero_raw, a.contenido, LENGTH(a.contenido) as len
        FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
        WHERE a.contenido IS NOT NULL
        AND LENGTH(a.contenido) < 20
        AND LENGTH(a.contenido) > 0
        ORDER BY LENGTH(a.contenido), l.codigo, a.numero_raw
    """)

    resultados = cur.fetchall()

    if resultados:
        print("\n" + "=" * 70)
        print("⚠️  CONTENIDO MUY CORTO (<20 caracteres)")
        print("=" * 70)

        for codigo, numero, contenido, length in resultados[:10]:
            print(f"  {codigo} {numero} ({length} chars): \"{contenido}\"")
        if len(resultados) > 10:
            print(f"  ... y {len(resultados) - 10} más")

        return len(resultados)
    return 0


def main():
    print("=" * 70)
    print("VALIDACIÓN DE CALIDAD DE DATOS")
    print("=" * 70)

    conn = conectar()
    cur = conn.cursor()

    problemas = {
        'titulos_truncados': validar_titulos_truncados(cur),
        'contenido_sin_punto': validar_parrafos_sin_punto(cur),
        'fracciones_sin_punto': validar_fracciones_sin_punto(cur),
        'contenido_minuscula': validar_parrafos_minuscula(cur),
        'contenido_muy_corto': validar_contenido_muy_corto(cur),
    }

    conn.close()

    # Resumen
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)

    total = sum(problemas.values())
    for tipo, count in problemas.items():
        status = "✓" if count == 0 else "⚠️"
        print(f"  {status} {tipo}: {count}")

    print(f"\nTotal problemas detectados: {total}")

    if total > 0:
        print("\nNOTA: Estos son warnings, no errores críticos.")
        print("Algunos pueden ser válidos (ej: títulos legales que empiezan con minúscula).")

    return total


if __name__ == '__main__':
    exit(0 if main() == 0 else 1)
