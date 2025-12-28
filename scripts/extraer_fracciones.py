#!/usr/bin/env python3
"""
Extractor de fracciones, incisos y numerales de artículos.

Estructura jerárquica:
  Artículo
  ├── Párrafo introductorio
  ├── Fracción I
  │   ├── Inciso a)
  │   │   ├── Numeral 1.
  │   │   └── Numeral 2.
  │   └── Inciso b)
  ├── Fracción II
  └── Párrafo final

Patrones reconocidos:
  - Fracciones: I., II., III., IV., V., VI., VII., VIII., IX., X., XI., XII., etc.
  - Incisos: a), b), c), ..., z)
  - Numerales: 1., 2., 3., etc.
  - Apartados: A., B., C., etc. (mayúsculas con punto)
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

# Números romanos válidos (hasta L para cubrir casos extremos)
ROMANOS = [
    'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
    'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX',
    'XXI', 'XXII', 'XXIII', 'XXIV', 'XXV', 'XXVI', 'XXVII', 'XXVIII', 'XXIX', 'XXX',
    'XXXI', 'XXXII', 'XXXIII', 'XXXIV', 'XXXV', 'XXXVI', 'XXXVII', 'XXXVIII', 'XXXIX', 'XL',
    'XLI', 'XLII', 'XLIII', 'XLIV', 'XLV', 'XLVI', 'XLVII', 'XLVIII', 'XLIX', 'L'
]
ROMANOS_SET = set(ROMANOS)

# Patrón para detectar fracciones fusionadas con notas DOF
# Ej: "...DOF 25-10-1967, 06-06-2011 XI. La demanda..."
# Captura: grupo 1 = todo hasta el año, grupo 2 = fracción romana + resto
PATRON_DOF_FRACCION = re.compile(
    r'(.*\d{2}-\d{2}-\d{4})\s+'   # Nota DOF terminando con fecha DD-MM-YYYY
    r'([IVXL]+\.\s+.+)$'          # Fracción romana + contenido
)

# Patrones de reconocimiento
# Fracción: I., II., III. (con espacios opcionales después)
PATRON_FRACCION = re.compile(r'^([IVXL]+)\.\s+(.*)$', re.MULTILINE)

# Inciso: a), b), c)
PATRON_INCISO = re.compile(r'^([a-zñ])\)\s+(.*)$', re.MULTILINE)

# Numeral: 1., 2., 3.
PATRON_NUMERAL = re.compile(r'^(\d+)\.\s+(.*)$', re.MULTILINE)

# Apartado: A., B., C. (mayúscula sola con punto, no confundir con romano)
PATRON_APARTADO = re.compile(r'^([A-Z])\.\s+(.*)$', re.MULTILINE)


def romano_a_int(romano):
    """Convierte número romano a entero para ordenamiento."""
    try:
        return ROMANOS.index(romano) + 1
    except ValueError:
        return 999


def preprocesar_contenido(contenido):
    """
    Preprocesa el contenido para separar notas DOF de fracciones.

    Algunos PDFs fusionan las notas de reforma con las fracciones:
    "...DOF 25-10-1967, 06-06-2011 XI. La demanda..."

    Esto separa en dos bloques:
    "...DOF 25-10-1967, 06-06-2011"
    "XI. La demanda..."
    """
    bloques = contenido.split('\n\n')
    nuevos_bloques = []

    for bloque in bloques:
        bloque = bloque.strip()
        if not bloque:
            continue

        # Intentar separar nota DOF de fracción
        match = PATRON_DOF_FRACCION.match(bloque)
        if match:
            nota_dof = match.group(1).strip()
            fraccion = match.group(2).strip()
            # Verificar que la fracción empieza con romano válido
            romano_match = re.match(r'^([IVXL]+)\.', fraccion)
            if romano_match and romano_match.group(1) in ROMANOS_SET:
                nuevos_bloques.append(nota_dof)
                nuevos_bloques.append(fraccion)
                continue

        nuevos_bloques.append(bloque)

    return '\n\n'.join(nuevos_bloques)


def detectar_tipo_linea(linea):
    """
    Detecta el tipo de una línea y extrae su número y contenido.

    Returns: (tipo, numero, contenido, orden) o None si es párrafo normal
    """
    linea = linea.strip()
    if not linea:
        return None

    # Fracción (números romanos)
    match = PATRON_FRACCION.match(linea)
    if match:
        romano = match.group(1)
        if romano in ROMANOS_SET:
            return ('fraccion', romano, match.group(2), romano_a_int(romano))

    # Inciso (letras minúsculas con paréntesis)
    match = PATRON_INCISO.match(linea)
    if match:
        letra = match.group(1)
        return ('inciso', letra, match.group(2), ord(letra) - ord('a') + 1)

    # Numeral (números arábigos)
    match = PATRON_NUMERAL.match(linea)
    if match:
        num = match.group(1)
        # Evitar confundir con años o cantidades grandes
        if int(num) <= 100:
            return ('numeral', num, match.group(2), int(num))

    # Apartado (letras mayúsculas solas, no romanos)
    match = PATRON_APARTADO.match(linea)
    if match:
        letra = match.group(1)
        # Evitar confundir con romanos de una letra
        if letra not in ('I', 'V', 'X', 'L', 'C', 'D', 'M'):
            return ('apartado', letra, match.group(2), ord(letra) - ord('A') + 1)

    # Es un párrafo normal
    return None


def parsear_articulo(contenido):
    """
    Parsea el contenido de un artículo y extrae la estructura jerárquica.

    Returns: lista de diccionarios con la estructura
    """
    elementos = []

    # Preprocesar para separar notas DOF de fracciones
    contenido = preprocesar_contenido(contenido)

    # Dividir por líneas dobles (párrafos)
    bloques = contenido.split('\n\n')

    # Stack para mantener jerarquía: [(tipo, indice_elemento), ...]
    # Jerarquía: fraccion > inciso > numeral
    JERARQUIA = {'fraccion': 1, 'apartado': 1, 'inciso': 2, 'numeral': 3, 'parrafo': 0}

    ultimo_por_nivel = {}  # nivel -> índice del último elemento de ese nivel
    orden_global = 0

    for bloque in bloques:
        bloque = bloque.strip()
        if not bloque:
            continue

        orden_global += 1
        deteccion = detectar_tipo_linea(bloque)

        if deteccion:
            tipo, numero, texto, numero_orden = deteccion
            nivel = JERARQUIA.get(tipo, 0)

            # Determinar padre según jerarquía
            padre_idx = None
            for n in range(nivel - 1, 0, -1):
                if n in ultimo_por_nivel:
                    padre_idx = ultimo_por_nivel[n]
                    break

            elemento = {
                'tipo': tipo,
                'numero': numero,
                'contenido': texto,
                'numero_orden': numero_orden,
                'orden': orden_global,
                'padre_idx': padre_idx
            }
            elementos.append(elemento)
            ultimo_por_nivel[nivel] = len(elementos) - 1

            # Limpiar niveles inferiores cuando cambia un nivel superior
            for n in list(ultimo_por_nivel.keys()):
                if n > nivel:
                    del ultimo_por_nivel[n]
        else:
            # Párrafo normal
            elemento = {
                'tipo': 'parrafo',
                'numero': None,
                'contenido': bloque,
                'numero_orden': orden_global,
                'orden': orden_global,
                'padre_idx': None
            }
            elementos.append(elemento)

    return elementos


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def calcular_contenido_limpio(elementos):
    """
    Calcula el contenido limpio: solo párrafos antes de la primera fracción.

    Esto evita duplicación cuando el artículo tiene fracciones que se muestran
    separadamente en la UI.
    """
    contenido_partes = []

    for elem in elementos:
        if elem['tipo'] == 'parrafo':
            contenido_partes.append(elem['contenido'])
        else:
            # Primera fracción encontrada, detenerse
            break

    return '\n\n'.join(contenido_partes) if contenido_partes else ''


def extraer_todas_fracciones(conn, actualizar_contenido=True):
    """
    Extrae fracciones de todos los artículos.

    Args:
        conn: Conexión a PostgreSQL
        actualizar_contenido: Si True, actualiza articulos.contenido para quitar
                             el texto de las fracciones (evita duplicación en UI)
    """
    cur = conn.cursor()

    # Obtener todos los artículos
    cur.execute("""
        SELECT a.id, l.codigo, a.numero_raw, a.contenido
        FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
        ORDER BY a.ley_id, a.orden_global
    """)

    articulos = cur.fetchall()
    print(f"Procesando {len(articulos)} artículos...")

    # Limpiar tabla existente
    cur.execute("DELETE FROM fracciones")
    conn.commit()
    print("Tabla fracciones limpiada")

    total_fracciones = 0
    articulos_con_fracciones = 0
    articulos_actualizados = 0
    stats_por_tipo = defaultdict(int)

    for art_id, ley, numero, contenido in articulos:
        if not contenido:
            continue

        elementos = parsear_articulo(contenido)

        # Solo insertar si hay elementos estructurados (no solo párrafos)
        elementos_estructurados = [e for e in elementos if e['tipo'] != 'parrafo']

        if not elementos_estructurados:
            continue

        articulos_con_fracciones += 1

        # Calcular contenido limpio (solo intro, sin fracciones)
        if actualizar_contenido:
            contenido_limpio = calcular_contenido_limpio(elementos)
            if contenido_limpio != contenido:
                cur.execute("""
                    UPDATE articulos SET contenido = %s WHERE id = %s
                """, (contenido_limpio, art_id))
                articulos_actualizados += 1

        # Mapeo de índice local a ID de BD para resolver padres
        idx_a_id = {}

        for i, elem in enumerate(elementos):
            # Resolver padre_idx a padre_id
            padre_id = None
            if elem['padre_idx'] is not None and elem['padre_idx'] in idx_a_id:
                padre_id = idx_a_id[elem['padre_idx']]

            cur.execute("""
                INSERT INTO fracciones
                (articulo_id, padre_id, tipo, numero, numero_orden, contenido, orden)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                art_id,
                padre_id,
                elem['tipo'],
                elem['numero'],
                elem['numero_orden'],
                elem['contenido'],
                elem['orden']
            ))

            nuevo_id = cur.fetchone()[0]
            idx_a_id[i] = nuevo_id
            total_fracciones += 1
            stats_por_tipo[elem['tipo']] += 1

        # Commit cada 100 artículos
        if articulos_con_fracciones % 100 == 0:
            conn.commit()
            print(f"  Procesados {articulos_con_fracciones} artículos...")

    conn.commit()

    return {
        'total_elementos': total_fracciones,
        'articulos_con_estructura': articulos_con_fracciones,
        'articulos_contenido_actualizado': articulos_actualizados,
        'por_tipo': dict(stats_por_tipo)
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Extrae fracciones de artículos')
    parser.add_argument('--no-limpiar', action='store_true',
                       help='No actualizar contenido de artículos (mantener duplicados)')
    parser.add_argument('--solo-ley', type=str,
                       help='Procesar solo una ley específica (ej: CFF)')
    args = parser.parse_args()

    print("Extrayendo fracciones de artículos...")
    print("=" * 50)
    if not args.no_limpiar:
        print("NOTA: Se limpiará el contenido de artículos (--no-limpiar para desactivar)")

    conn = get_connection()

    stats = extraer_todas_fracciones(conn, actualizar_contenido=not args.no_limpiar)

    print("\n" + "=" * 50)
    print("RESUMEN")
    print("=" * 50)
    print(f"Artículos con estructura: {stats['articulos_con_estructura']}")
    print(f"Artículos actualizados: {stats['articulos_contenido_actualizado']}")
    print(f"Total elementos extraídos: {stats['total_elementos']}")
    print("\nPor tipo:")
    for tipo, count in sorted(stats['por_tipo'].items(), key=lambda x: -x[1]):
        print(f"  {tipo}: {count}")

    # Verificar algunos ejemplos
    cur = conn.cursor()
    cur.execute("""
        SELECT a.numero_raw, f.tipo, f.numero, substring(f.contenido, 1, 60) as contenido
        FROM fracciones f
        JOIN articulos a ON f.articulo_id = a.id
        JOIN leyes l ON a.ley_id = l.id
        WHERE l.codigo = 'CFF' AND a.numero_raw = '9o'
        ORDER BY f.orden
        LIMIT 15
    """)

    print("\n" + "=" * 50)
    print("EJEMPLO: CFF Artículo 9o")
    print("=" * 50)
    for row in cur.fetchall():
        print(f"  [{row[1]:8}] {row[2] or '-':5} | {row[3]}...")

    conn.close()
    print("\nListo!")


if __name__ == '__main__':
    main()
