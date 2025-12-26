#!/usr/bin/env python3
"""
Extractor de referencias cruzadas entre artículos.

Fuentes:
1. Campo 'referencias' de RMF: "CFF 10, LISR 27, RCFF 13"
2. Contenido de artículos: "artículo 14-B de este Código"
"""

import re
import psycopg2
from collections import defaultdict

# Configuración
DB_CONFIG = {
    'host': 'localhost',
    'database': 'leyesmx',
    'user': 'leyesmx',
    'password': 'leyesmx'
}

# Mapeo de nombres de leyes a códigos
LEY_ALIASES = {
    # Códigos directos
    'CFF': 'CFF',
    'LISR': 'LISR',
    'LIVA': 'LIVA',
    'LIEPS': 'LIEPS',
    'LFT': 'LFT',
    'LSS': 'LSS',
    'RCFF': 'RCFF',
    'RISR': 'RISR',
    'RIVA': 'RIVA',
    'RLIEPS': 'RLIEPS',
    'RLSS': 'RLSS',
    'RMF': 'RMF2025',
    'RMF2025': 'RMF2025',
    # Nombres completos
    'CÓDIGO FISCAL': 'CFF',
    'CODIGO FISCAL': 'CFF',
    'LEY DEL ISR': 'LISR',
    'LEY DEL IMPUESTO SOBRE LA RENTA': 'LISR',
    'LEY DEL IVA': 'LIVA',
    'LEY DEL IMPUESTO AL VALOR AGREGADO': 'LIVA',
    'LEY DEL IEPS': 'LIEPS',
    'LEY FEDERAL DEL TRABAJO': 'LFT',
    'LEY DEL SEGURO SOCIAL': 'LSS',
    'REGLAMENTO DEL CFF': 'RCFF',
    'REGLAMENTO DEL CÓDIGO FISCAL': 'RCFF',
}

# Referencias pronominales
PRONOMINAL_REFS = {
    'ESTE CÓDIGO': None,  # Se resuelve según la ley del artículo origen
    'ESTA LEY': None,
    'EL PRESENTE CÓDIGO': None,
    'LA PRESENTE LEY': None,
    'DEL MISMO': None,
    'DE LA MISMA': None,
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_leyes(conn):
    """Obtiene mapeo de código -> id de leyes."""
    cur = conn.cursor()
    cur.execute("SELECT id, codigo FROM leyes")
    return {row[1]: row[0] for row in cur.fetchall()}


def get_articulos_index(conn):
    """
    Crea índice de artículos: (ley_codigo, numero_raw) -> id
    Normaliza números para matching flexible.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, l.codigo, a.numero_raw
        FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
    """)

    index = {}
    for art_id, ley_codigo, numero_raw in cur.fetchall():
        # Índice exacto
        key = (ley_codigo, numero_raw)
        index[key] = art_id

        # Índice normalizado (sin 'o' ordinal)
        numero_norm = re.sub(r'[oº°]$', '', numero_raw)
        if numero_norm != numero_raw:
            index[(ley_codigo, numero_norm)] = art_id

    return index


def parse_rmf_referencias(referencias_text, origen_ley):
    """
    Parsea campo referencias de RMF.
    Ejemplo: "CFF 10, 14-A, LISR 27, 31"

    Returns: [(ley_codigo, numero_raw), ...]
    """
    if not referencias_text:
        return []

    # Ignorar notas
    if 'NOTA:' in referencias_text.upper() or 'Reformada' in referencias_text:
        return []

    refs = []
    current_ley = None

    # Dividir por comas y espacios
    tokens = re.split(r'[,\s]+', referencias_text)

    for token in tokens:
        token = token.strip().upper()
        if not token:
            continue

        # ¿Es un código de ley?
        if token in LEY_ALIASES:
            current_ley = LEY_ALIASES[token]
        elif re.match(r'^[\d\-A-Z]+$', token) and current_ley:
            # Es un número de artículo
            refs.append((current_ley, token.lower().replace('-', '-')))

    return refs


def parse_contenido_referencias(contenido, origen_ley):
    """
    Parsea referencias en el texto del artículo.
    Patrones:
    - "artículo 14"
    - "artículo 14-B"
    - "artículos 14, 15 y 16"
    - "artículo 14 de este Código"
    - "artículo 14 de la Ley del ISR"
    """
    refs = []

    # Patrón para "artículo(s) X, Y y Z [de/del ...]"
    pattern = r'''
        (?:art[íi]culos?|arts?\.?)\s+
        ([\d\-A-Za-zº°]+(?:\s*(?:,|y)\s*[\d\-A-Za-zº°]+)*)
        (?:\s+(?:
            de\s+(?:este|la\s+presente)\s+(?:C[óo]digo|Ley)|
            del?\s+(?:mismo|misma)|
            de\s+la\s+(.+?)(?=\s*[,;.]|\s+y\s+|\s+o\s+|$)|
            del\s+(.+?)(?=\s*[,;.]|\s+y\s+|\s+o\s+|$)
        ))?
    '''

    for match in re.finditer(pattern, contenido, re.IGNORECASE | re.VERBOSE):
        numeros_str = match.group(1)
        ley_ref = match.group(2) or match.group(3)

        # Determinar ley destino
        if ley_ref:
            ley_ref_upper = ley_ref.upper().strip()
            ley_destino = None
            for alias, codigo in LEY_ALIASES.items():
                if alias in ley_ref_upper:
                    ley_destino = codigo
                    break
            if not ley_destino:
                continue  # Ley no reconocida
        else:
            # Referencia a la misma ley
            ley_destino = origen_ley

        # Extraer números individuales
        numeros = re.findall(r'([\d]+[-A-Za-z]*[ºo°]?)', numeros_str)

        for num in numeros:
            # Normalizar
            num_norm = num.lower().rstrip('oº°')
            refs.append((ley_destino, num_norm))

    return refs


def extract_all_referencias(conn):
    """Extrae todas las referencias de todos los artículos."""
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, l.codigo, a.numero_raw, a.contenido, a.referencias
        FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
    """)

    all_refs = []

    for art_id, ley_codigo, numero_raw, contenido, referencias in cur.fetchall():
        # 1. Referencias del campo 'referencias' (RMF)
        if referencias:
            for ref in parse_rmf_referencias(referencias, ley_codigo):
                all_refs.append((art_id, ley_codigo, ref[0], ref[1], 'cita'))

        # 2. Referencias en el contenido
        if contenido:
            for ref in parse_contenido_referencias(contenido, ley_codigo):
                all_refs.append((art_id, ley_codigo, ref[0], ref[1], 'cita'))

    return all_refs


def resolve_and_insert(conn, refs, articulos_index):
    """Resuelve referencias a IDs y las inserta en la BD."""
    cur = conn.cursor()

    # Limpiar referencias existentes
    cur.execute("DELETE FROM referencias_cruzadas")
    print(f"Referencias previas eliminadas")

    inserted = 0
    not_found = defaultdict(int)

    for origen_id, origen_ley, destino_ley, destino_num, tipo in refs:
        # Intentar encontrar el artículo destino
        destino_id = articulos_index.get((destino_ley, destino_num))

        # Intentar variantes
        if not destino_id:
            # Con 'o' ordinal
            destino_id = articulos_index.get((destino_ley, destino_num + 'o'))
        if not destino_id:
            # Con guión
            destino_id = articulos_index.get((destino_ley, destino_num.replace(' ', '-')))
        if not destino_id:
            # Sufijo en mayúsculas (29-a -> 29-A)
            destino_id = articulos_index.get((destino_ley, destino_num.upper()))
        if not destino_id:
            # Solo la parte numérica en mayúsculas (17-h -> 17-H)
            num_upper = re.sub(r'-([a-z]+)$', lambda m: '-' + m.group(1).upper(), destino_num)
            destino_id = articulos_index.get((destino_ley, num_upper))

        if destino_id and destino_id != origen_id:
            try:
                cur.execute("""
                    INSERT INTO referencias_cruzadas
                    (articulo_origen_id, articulo_destino_id, tipo)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (articulo_origen_id, articulo_destino_id, tipo) DO NOTHING
                """, (origen_id, destino_id, tipo))
                inserted += 1
            except Exception as e:
                pass  # Ignorar duplicados
        else:
            not_found[(destino_ley, destino_num)] += 1

    conn.commit()

    print(f"Referencias insertadas: {inserted}")
    print(f"Referencias no resueltas: {len(not_found)}")

    # Mostrar top 10 no encontradas
    if not_found:
        print("\nTop 10 referencias no encontradas:")
        sorted_nf = sorted(not_found.items(), key=lambda x: -x[1])[:10]
        for (ley, num), count in sorted_nf:
            print(f"  {ley} {num}: {count} veces")


def main():
    print("Extrayendo referencias cruzadas...")

    conn = get_connection()

    print("Construyendo índice de artículos...")
    articulos_index = get_articulos_index(conn)
    print(f"  {len(articulos_index)} artículos indexados")

    print("Extrayendo referencias del contenido...")
    refs = extract_all_referencias(conn)
    print(f"  {len(refs)} referencias encontradas")

    print("Resolviendo e insertando...")
    resolve_and_insert(conn, refs, articulos_index)

    # Estadísticas finales
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM referencias_cruzadas")
    total = cur.fetchone()[0]
    print(f"\nTotal referencias en BD: {total}")

    cur.execute("""
        SELECT l.codigo, COUNT(*)
        FROM referencias_cruzadas r
        JOIN articulos a ON r.articulo_origen_id = a.id
        JOIN leyes l ON a.ley_id = l.id
        GROUP BY l.codigo
        ORDER BY COUNT(*) DESC
    """)
    print("\nReferencias por ley origen:")
    for ley, count in cur.fetchall():
        print(f"  {ley}: {count}")

    conn.close()
    print("\nListo!")


if __name__ == '__main__':
    main()
