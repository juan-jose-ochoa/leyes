#!/usr/bin/env python3
"""
Importador de leyes para esquema leyesmx.

Lee archivos JSON generados por extraer.py e inserta en PostgreSQL.
FAIL FAST: Valida antes de importar, verifica después.

Uso:
    python backend/etl/importar.py CFF
    python backend/etl/importar.py CFF --limpiar  # Borra datos anteriores
"""

import json
import os
import re
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 no instalado. Ejecuta: pip install psycopg2-binary")
    sys.exit(1)

try:
    import pdfplumber
    PDFPLUMBER_DISPONIBLE = True
except ImportError:
    PDFPLUMBER_DISPONIBLE = False

from config import get_config


# Meses en español para parsear fechas
MESES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
}

BASE_DIR = Path(__file__).parent.parent.parent


def extraer_fecha_ultima_reforma(pdf_path: Path) -> date | None:
    """Extrae la fecha de última reforma de la primera página del PDF.

    Busca patrones como:
    - "Última reforma publicada DOF 14-11-2025"
    - "Última Reforma DOF 14-11-2025"
    - "DOF 14 de noviembre de 2025"

    Returns:
        date object o None si no se encuentra
    """
    if not PDFPLUMBER_DISPONIBLE or not pdf_path.exists():
        return None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Solo revisar primera página
            text = pdf.pages[0].extract_text() or ""

            # Patrón 1: "DOF DD-MM-YYYY" o "DOF DD/MM/YYYY"
            match = re.search(r'DOF\s+(\d{1,2})[-/](\d{1,2})[-/](\d{4})', text)
            if match:
                dia, mes, anio = int(match.group(1)), int(match.group(2)), int(match.group(3))
                return date(anio, mes, dia)

            # Patrón 2: "DOF DD de MES de YYYY"
            match = re.search(
                r'DOF\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',
                text, re.IGNORECASE
            )
            if match:
                dia = int(match.group(1))
                mes_texto = match.group(2).lower()
                anio = int(match.group(3))
                mes = MESES.get(mes_texto)
                if mes:
                    return date(anio, mes, dia)

    except Exception as e:
        print(f"   AVISO: No se pudo extraer fecha de reforma: {e}")

    return None


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
    """Carga mapa_estructura.json y crea lookup artículo -> (titulo, capitulo, seccion).

    Si el capítulo tiene secciones, el lookup apunta a la sección.
    Si no tiene secciones, apunta al capítulo directamente.

    Returns:
        Diccionario articulo_a_division
    """
    with open(mapa_path, 'r', encoding='utf-8') as f:
        mapa = json.load(f)

    # Crear lookup: numero_articulo_normalizado -> (titulo, capitulo, seccion_or_None)
    articulo_a_division = {}

    for titulo_num, titulo_data in mapa.get("titulos", {}).items():
        for cap_num, cap_data in titulo_data.get("capitulos", {}).items():
            # Si tiene secciones, los artículos están en las secciones
            if "secciones" in cap_data:
                for sec_num, sec_data in cap_data["secciones"].items():
                    for articulo in sec_data.get("articulos", []):
                        key = normalizar_numero(articulo)
                        articulo_a_division[key] = (titulo_num, cap_num, sec_num)
            else:
                # Sin secciones, artículos directamente en capítulo
                for articulo in cap_data.get("articulos", []):
                    key = normalizar_numero(articulo)
                    articulo_a_division[key] = (titulo_num, cap_num, None)

    return articulo_a_division


def convertir_estructura_esperada(mapa_path: Path) -> list:
    """
    Convierte estructura_esperada.json (formato anidado) al formato plano
    que espera importar_estructura().

    Entrada (anidado):
        {"titulos": {"PRIMERO": {"nombre": "...", "capitulos": {"I": {...}, "II": {...}}}}}

    Salida (plano):
        [{"tipo": "titulo", "numero": "PRIMERO", "orden": 1, "padre_orden": null, "nombre": "..."},
         {"tipo": "capitulo", "numero": "I", "orden": 2, "padre_orden": 1, "nombre": null},
         {"tipo": "seccion", "numero": "I", "orden": 3, "padre_orden": 2, "nombre": null}, ...]
    """
    with open(mapa_path, 'r', encoding='utf-8') as f:
        mapa = json.load(f)

    divisiones = []
    orden = 0

    for titulo_num, titulo_data in mapa.get("titulos", {}).items():
        orden += 1
        titulo_orden = orden
        divisiones.append({
            "tipo": "titulo",
            "numero": titulo_num,
            "nombre": titulo_data.get("nombre"),
            "orden": titulo_orden,
            "padre_orden": None
        })

        for cap_num, cap_data in titulo_data.get("capitulos", {}).items():
            orden += 1
            cap_orden = orden
            divisiones.append({
                "tipo": "capitulo",
                "numero": cap_num,
                "nombre": cap_data.get("nombre"),
                "orden": cap_orden,
                "padre_orden": titulo_orden
            })

            # Si el capítulo tiene secciones, agregarlas
            if "secciones" in cap_data:
                for sec_num, sec_data in cap_data["secciones"].items():
                    orden += 1
                    divisiones.append({
                        "tipo": "seccion",
                        "numero": sec_num,
                        "nombre": sec_data.get("nombre"),
                        "orden": orden,
                        "padre_orden": cap_orden
                    })

    return divisiones


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


def importar_ley(conn, codigo: str, config: dict, pdf_path: Path = None):
    """Inserta la ley en el catálogo, extrayendo fecha de última reforma del PDF."""
    # Extraer fecha de última reforma del PDF
    ultima_reforma = None
    if pdf_path:
        ultima_reforma = extraer_fecha_ultima_reforma(pdf_path)
        if ultima_reforma:
            print(f"   Última reforma: {ultima_reforma.strftime('%d-%m-%Y')}")

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO leyesmx.leyes (
                codigo, nombre, nombre_corto, tipo,
                ley_base, anio,
                url_fuente, ultima_reforma,
                divisiones_permitidas, parrafos_permitidos
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (codigo) DO UPDATE SET
                nombre = EXCLUDED.nombre,
                nombre_corto = EXCLUDED.nombre_corto,
                url_fuente = EXCLUDED.url_fuente,
                ultima_reforma = EXCLUDED.ultima_reforma
        """, (
            codigo,
            config["nombre"],
            config.get("nombre_corto"),
            config["tipo"],
            config.get("ley_base"),
            config.get("anio"),
            config.get("url_fuente"),
            ultima_reforma,
            config["divisiones_permitidas"],
            config["parrafos_permitidos"],
        ))
        conn.commit()


def importar_estructura_desde_lista(conn, codigo: str, divisiones: list) -> dict:
    """Importa divisiones desde lista y retorna mapeo (titulo, capitulo, seccion) -> id.

    El lookup tiene dos formatos:
    - Para capítulos sin secciones: (titulo, capitulo, None) -> id
    - Para secciones: (titulo, capitulo, seccion) -> id
    """
    if not divisiones:
        print("   No hay divisiones para importar")
        return {}

    orden_to_id = {}
    orden_to_numero = {}  # orden -> (tipo, numero)
    division_lookup = {}  # (titulo_num, cap_num, sec_num_or_None) -> id

    with conn.cursor() as cur:
        current_titulo = None
        current_capitulo = None
        caps_con_secciones = set()  # Capítulos que tienen secciones

        # Primera pasada: detectar qué capítulos tienen secciones
        for div in divisiones:
            if div["tipo"] == "seccion":
                caps_con_secciones.add(div["padre_orden"])

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
            orden_to_numero[div["orden"]] = (div["tipo"], div["numero"])

            if div["tipo"] == "titulo":
                current_titulo = div["numero"]
            elif div["tipo"] == "capitulo":
                current_capitulo = div["numero"]
                # Solo agregar capítulo al lookup si NO tiene secciones
                if div["orden"] not in caps_con_secciones and current_titulo:
                    key = (normalizar_numero(current_titulo),
                           normalizar_numero(div["numero"]),
                           None)
                    division_lookup[key] = div_id
            elif div["tipo"] == "seccion" and current_titulo and current_capitulo:
                # Agregar sección al lookup
                key = (normalizar_numero(current_titulo),
                       normalizar_numero(current_capitulo),
                       normalizar_numero(div["numero"]))
                division_lookup[key] = div_id

        conn.commit()

    print(f"   {len(divisiones)} divisiones importadas")
    return division_lookup


def importar_contenido(conn, codigo: str, contenido_path: Path, mapa_path: Path,
                       division_lookup: dict, tipo_contenido: str):
    """Importa artículos y párrafos desde el JSON."""
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
        for i, art in enumerate(articulos):
            numero = art["numero"]
            key = normalizar_numero(numero)

            # Obtener división desde mapa_estructura (retorna 3 elementos)
            division_info = articulo_a_division.get(key)
            if not division_info:
                errores.append(f"Artículo {numero}: sin división en mapa")
                continue

            titulo_num, cap_num, sec_num = division_info

            # Buscar division_id usando (titulo, capitulo, seccion) normalizado
            lookup_key = (normalizar_numero(titulo_num),
                          normalizar_numero(cap_num),
                          normalizar_numero(sec_num) if sec_num else None)
            division_id = division_lookup.get(lookup_key)

            if not division_id:
                div_desc = f"{titulo_num}/{cap_num}" + (f"/{sec_num}" if sec_num else "")
                errores.append(f"Artículo {numero}: {div_desc} no encontrado en BD")
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

            # Insertar párrafos desde JSON
            parrafos = art.get("parrafos", [])
            for parr in parrafos:
                cur.execute("""
                    INSERT INTO leyesmx.parrafos (
                        ley, articulo_id, numero, padre_numero,
                        tipo, identificador, contenido, x_id, x_texto, referencias
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    codigo,
                    articulo_id,
                    parr["numero"],
                    parr.get("padre_numero"),
                    parr["tipo"],
                    parr.get("identificador"),
                    parr["contenido"],
                    parr.get("x_id"),
                    parr.get("x_texto"),
                    parr.get("referencias")
                ))
                total_parrafos += 1

            # Progreso cada 50 artículos
            if (i + 1) % 50 == 0:
                print(f"   ... {i + 1}/{len(articulos)} artículos procesados")

        conn.commit()

    if errores:
        print(f"   ERRORES ({len(errores)}):")
        for err in errores[:5]:
            print(f"      {err}")
        if len(errores) > 5:
            print(f"      ... y {len(errores) - 5} más")

    articulos_importados = len(articulos) - len(errores)
    print(f"   {articulos_importados} artículos, {total_parrafos} párrafos importados")
    return len(errores) == 0


def verificar_post_importacion(conn, codigo: str, mapa_path: Path) -> bool:
    """Verifica integridad después de importar. FAIL FAST."""
    print("\n7. Verificando integridad post-importación...")

    articulo_a_division = cargar_mapa_estructura(mapa_path)

    # Contar artículos esperados por división (capítulo o sección)
    # El lookup retorna (titulo, cap, sec_or_None)
    esperado_por_div = {}
    for numero, (titulo, cap, sec) in articulo_a_division.items():
        # Usar sección si existe, si no usar capítulo
        if sec:
            key = ('seccion', sec)
        else:
            key = ('capitulo', cap)
        esperado_por_div[key] = esperado_por_div.get(key, 0) + 1

    # Contar artículos reales por división en BD (capítulos y secciones)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT d.tipo, d.numero, COUNT(a.id) as total
            FROM leyesmx.divisiones d
            LEFT JOIN leyesmx.articulos a ON a.division_id = d.id AND a.ley = d.ley
            WHERE d.ley = %s AND d.tipo IN ('capitulo', 'seccion')
            GROUP BY d.tipo, d.numero
        """, (codigo,))

        real_por_div = {(row[0], row[1]): row[2] for row in cur.fetchall()}

    errores = []
    for div_key, esperado in esperado_por_div.items():
        tipo, numero = div_key
        real = real_por_div.get(div_key, 0)
        if real != esperado:
            errores.append(f"   {tipo.capitalize()} {numero}: esperado {esperado}, real {real}")

    if errores:
        print("   ERRORES de integridad:")
        for err in errores:
            print(err)
        return False

    print(f"   OK: {len(esperado_por_div)} divisiones verificadas")
    return True


def main():
    if len(sys.argv) < 2:
        print("Uso: python backend/etl/importar.py <CODIGO> [--limpiar]")
        print("  --limpiar  Borra datos anteriores antes de importar")
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
        pdf_path = BASE_DIR / config["pdf_path"]
    else:
        print("ERROR: pdf_path no configurado")
        sys.exit(1)

    contenido_path = output_dir / "contenido.json"
    # estructura_esperada.json es la fuente autoritativa (del outline aprobado)
    estructura_path = output_dir / "estructura_esperada.json"

    # Verificar archivos
    print("\n1. Verificando archivos...")
    archivos_ok = True

    for path in [contenido_path, estructura_path]:
        if path.exists():
            print(f"   {path.name} encontrado")
        else:
            print(f"   ERROR: {path.name} no existe (REQUERIDO)")
            archivos_ok = False

    if not archivos_ok:
        print("\nABORTANDO: Archivos requeridos faltantes")
        sys.exit(1)

    # FAIL FAST: Validar antes de importar
    print("\n2. Validación pre-importación...")
    if not validar_antes_de_importar(contenido_path, estructura_path):
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
        importar_ley(conn, codigo, config, pdf_path)
        print(f"   Ley {codigo} registrada")

        # Importar estructura desde estructura_esperada.json (formato anidado)
        print("\n5. Importando estructura...")
        divisiones = convertir_estructura_esperada(estructura_path)
        division_lookup = importar_estructura_desde_lista(conn, codigo, divisiones)

        # Importar contenido
        print("\n6. Importando contenido...")
        if not importar_contenido(conn, codigo, contenido_path, estructura_path,
                                   division_lookup, config["tipo_contenido"]):
            exito = False

        # FAIL FAST: Verificar después de importar
        if exito and not verificar_post_importacion(conn, codigo, estructura_path):
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
