#!/usr/bin/env python3
"""
Importador de leyes para esquema leyesmx.

Lee archivos JSON generados por extraer.py e inserta en PostgreSQL.
Usa extracción de párrafos basada en coordenadas X del PDF para jerarquía correcta.
FAIL FAST: Valida antes de importar, verifica después.

Uso:
    python backend/etl/importar.py CFF
    python backend/etl/importar.py CFF --limpiar  # Borra datos anteriores
    python backend/etl/importar.py CFF --sin-x    # Usa párrafos del JSON (sin re-extraer)
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
from extraer_parrafos_x import extraer_articulo


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


def extraer_parrafos_x(pdf_path: str, numero_articulo: str, pdf=None) -> list:
    """
    Extrae párrafos de un artículo usando coordenadas X del PDF.
    Retorna lista de dicts con: numero, tipo, identificador, contenido, padre_numero

    Args:
        pdf_path: Ruta al PDF (ignorado si se pasa pdf)
        numero_articulo: Número del artículo
        pdf: Objeto pdfplumber.PDF ya abierto (opcional, para optimizar)
    """
    try:
        parrafos = extraer_articulo(pdf_path, numero_articulo, quiet=True, pdf=pdf)
        return [
            {
                "numero": p.numero,
                "tipo": p.tipo,
                "identificador": p.identificador,
                "contenido": p.contenido,
                "padre_numero": p.padre_numero
            }
            for p in parrafos
        ]
    except Exception as e:
        # Si falla, retornar lista vacía (se usará fallback del JSON)
        return []


def importar_contenido(conn, codigo: str, contenido_path: Path, mapa_path: Path,
                       division_lookup: dict, tipo_contenido: str,
                       pdf_path: str = None, usar_extractor_x: bool = True):
    """Importa artículos asignando división correcta desde mapa_estructura.

    Si usar_extractor_x=True y pdf_path está disponible, re-extrae los párrafos
    usando coordenadas X del PDF para obtener jerarquía correcta.
    """
    with open(contenido_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    articulo_a_division = cargar_mapa_estructura(mapa_path)

    articulos = data.get("articulos", [])
    if not articulos:
        print("   No hay artículos para importar")
        return

    # Determinar si usamos extractor X
    usar_x = usar_extractor_x and pdf_path and PDFPLUMBER_DISPONIBLE
    if usar_x:
        print(f"   Usando extractor de párrafos con coordenadas X")
    else:
        if usar_extractor_x and not PDFPLUMBER_DISPONIBLE:
            print("   AVISO: pdfplumber no disponible, usando párrafos del JSON")
        elif usar_extractor_x and not pdf_path:
            print("   AVISO: PDF no especificado, usando párrafos del JSON")

    total_parrafos = 0
    total_x_extraidos = 0
    total_x_fallback = 0
    errores = []

    # Abrir PDF una sola vez si usamos extractor X
    pdf_obj = None
    if usar_x:
        try:
            pdf_obj = pdfplumber.open(pdf_path)
        except Exception as e:
            print(f"   ERROR abriendo PDF: {e}")
            usar_x = False

    try:
        with conn.cursor() as cur:
            for i, art in enumerate(articulos):
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

                # Obtener párrafos: extraer con X o usar JSON
                if usar_x:
                    parrafos = extraer_parrafos_x(pdf_path, numero, pdf=pdf_obj)
                    if parrafos:
                        total_x_extraidos += 1
                    else:
                        # Fallback a JSON si la extracción X falla
                        parrafos = art.get("parrafos", [])
                        total_x_fallback += 1
                else:
                    parrafos = art.get("parrafos", [])

                # Insertar párrafos
                for parr in parrafos:
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

                # Progreso cada 50 artículos
                if (i + 1) % 50 == 0:
                    print(f"   ... {i + 1}/{len(articulos)} artículos procesados")

            conn.commit()
    finally:
        if pdf_obj:
            pdf_obj.close()

    if errores:
        print(f"   ERRORES ({len(errores)}):")
        for err in errores[:5]:
            print(f"      {err}")
        if len(errores) > 5:
            print(f"      ... y {len(errores) - 5} más")

    print(f"   {len(articulos) - len(errores)} artículos, {total_parrafos} párrafos importados")
    if usar_x:
        print(f"   Extracción X: {total_x_extraidos} exitosos, {total_x_fallback} fallback a JSON")
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
        print("Uso: python backend/etl/importar.py <CODIGO> [--limpiar] [--sin-x]")
        print("  --limpiar  Borra datos anteriores antes de importar")
        print("  --sin-x    No usa extractor X (usa párrafos del JSON)")
        sys.exit(1)

    codigo = sys.argv[1].upper()
    limpiar = '--limpiar' in sys.argv
    usar_extractor_x = '--sin-x' not in sys.argv

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

    # Verificar PDF si usamos extractor X
    if usar_extractor_x:
        if pdf_path.exists():
            print(f"   {pdf_path.name} encontrado (para extracción X)")
        else:
            print(f"   AVISO: {pdf_path.name} no existe, se usarán párrafos del JSON")
            pdf_path = None
    else:
        pdf_path = None
        print("   Extractor X deshabilitado (--sin-x)")

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
        importar_ley(conn, codigo, config, pdf_path)
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
                                   division_lookup, config["tipo_contenido"],
                                   pdf_path=str(pdf_path) if pdf_path else None,
                                   usar_extractor_x=usar_extractor_x):
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
