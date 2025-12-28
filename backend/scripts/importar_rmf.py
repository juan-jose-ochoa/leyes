#!/usr/bin/env python3
"""
Importador de RMF - Resolución Miscelánea Fiscal

Lee el archivo DOCX de RMF, parsea con estructura jerárquica y carga a PostgreSQL.
Las reglas se guardan en la tabla articulos con tipo='regla'.

Incluye campo 'calidad' con registro de issues y acciones correctivas.
"""

import json
import os
import sys
from pathlib import Path

# Agregar directorio de scripts al path para importar parser
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from rmf import (
    DocxXmlExtractor,
    ParserRMF,
    ValidadorEstructural,
    InspectorMultiFormato,
)

# Directorio de RMF
BASE_DIR = Path(__file__).parent.parent.parent
RMF_DIR = BASE_DIR / "doc" / "rmf"

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 no instalado. Ejecuta: pip install psycopg2-binary")
    sys.exit(1)

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).parent.parent.parent

# Cargar .env si existe
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

# Configuración de PostgreSQL (desde variables de entorno)
PG_CONFIG = {
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": int(os.environ.get("PG_PORT", "5432")),
    "database": os.environ.get("PG_DB", "leyesmx"),
    "user": os.environ.get("PG_USER", "leyesmx"),
    "password": os.environ.get("PG_PASS", "leyesmx")
}


def find_rmf_docx():
    """Encuentra el archivo DOCX de RMF"""
    if not RMF_DIR.exists():
        return None

    # Preferir el archivo convertido completo
    preferred = RMF_DIR / "rmf_2025_full_converted.docx"
    if preferred.exists():
        return preferred

    docx_files = list(RMF_DIR.glob("*.docx"))
    if docx_files:
        return docx_files[0]

    # Si no hay DOCX, intentar convertir PDF
    pdf_files = list(RMF_DIR.glob("*.pdf"))
    if pdf_files:
        try:
            from pdf2docx import Converter

            pdf_path = pdf_files[0]
            docx_path = pdf_path.with_suffix('.docx')

            print(f"   Convirtiendo PDF a DOCX...")
            cv = Converter(str(pdf_path))
            cv.convert(str(docx_path))
            cv.close()

            return docx_path
        except ImportError:
            print("ERROR: pdf2docx no instalado. Ejecuta: pip install pdf2docx")
            return None
        except Exception as e:
            print(f"ERROR convirtiendo PDF: {e}")
            return None

    return None


def insertar_ley_rmf(cursor, rmf_info):
    """Inserta la RMF como ley y retorna su ID"""
    cursor.execute("""
        INSERT INTO leyes (codigo, nombre, nombre_corto, tipo, url_fuente, fecha_descarga)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        rmf_info["codigo"],
        rmf_info["nombre"],
        rmf_info["codigo"],
        'resolucion',  # Tipo especial para RMF
        rmf_info.get("url"),
        rmf_info.get("fecha_descarga")
    ))
    return cursor.fetchone()[0]


def cargar_reglas_dos_niveles():
    """
    Carga las reglas de dos niveles extraídas del PDF.

    Estas reglas (formato X.Y) pertenecen a títulos sin capítulos:
    - Título 1: reglas 1.1-1.11
    - Título 6: regla 6.1
    - Título 7: reglas 7.1-7.40
    - Título 8: reglas 8.1-8.7
    - Título 9: reglas 9.1-9.31
    - Título 10: reglas 10.1-10.33
    """
    json_path = RMF_DIR / "reglas_dos_niveles.json"

    if not json_path.exists():
        print(f"   ADVERTENCIA: No existe {json_path}")
        print("   Ejecuta: python scripts/rmf/pdf_extractor.py")
        return []

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get('reglas', [])


def crear_divisiones_y_reglas_dos_niveles(divisiones_dict, reglas_dict):
    """
    Crea capítulos virtuales y reglas para las reglas de dos niveles.

    Para cada regla X.Y:
    - Crea un capítulo virtual "Capítulo X.Y" bajo el título correspondiente
    - Agrega la regla bajo ese capítulo virtual

    Estructura resultante:
        Título X > Capítulo X.Y [nombre de la regla]
            └── Regla X.Y [nombre de la regla]
    """
    reglas_pdf = cargar_reglas_dos_niveles()

    if not reglas_pdf:
        return divisiones_dict, reglas_dict

    print(f"   Agregando {len(reglas_pdf)} reglas de dos niveles del PDF...")

    # Mapeo de número de título -> nombre del título
    titulos_nombres = {
        '1': 'Disposiciones Generales',
        '6': 'Contribuciones de Mejoras',
        '7': 'Derechos',
        '8': 'Del Impuesto Sobre la Renta para el Régimen de Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras',
        '9': 'Del Impuesto Especial sobre Producción y Servicios',
        '10': 'De Hidrocarburos',
    }

    # Buscar el mayor orden_global actual para continuar la numeración
    max_orden_div = max((d.get('orden_global', 0) or 0 for d in divisiones_dict), default=0)
    max_orden_regla = max((r.get('orden_global', 0) or 0 for r in reglas_dict), default=0)

    nuevas_divisiones = []
    nuevas_reglas = []

    for regla in reglas_pdf:
        numero = regla['numero']  # e.g., "1.1"
        titulo_num = numero.split('.')[0]  # e.g., "1"
        titulo_nombre = titulos_nombres.get(titulo_num, f'Título {titulo_num}')

        # Crear path para el título (si no existe, será creado)
        path_titulo = f"Título {titulo_num}"

        # Crear path para el capítulo virtual
        path_capitulo = f"{path_titulo} > Capítulo {numero}"

        # Nombre del capítulo = nombre de la regla
        nombre_capitulo = regla.get('titulo') or f"Regla {numero}"

        # Crear división para el título si no existe
        titulo_existente = any(
            d.get('tipo') == 'titulo' and d.get('numero') == titulo_num
            for d in divisiones_dict + nuevas_divisiones
        )

        if not titulo_existente:
            max_orden_div += 1
            nuevas_divisiones.append({
                'tipo': 'titulo',
                'numero': titulo_num,
                'numero_orden': int(titulo_num),
                'nombre': titulo_nombre,
                'path_texto': path_titulo,
                'orden_global': max_orden_div,
            })

        # Verificar si el capítulo ya existe (por tipo + numero)
        capitulo_existente = None
        for d in divisiones_dict:
            if d.get('tipo') == 'capitulo' and d.get('numero') == numero:
                capitulo_existente = d
                break

        if capitulo_existente:
            # El capítulo ya existe - actualizar nombre si es mejor
            nombre_actual = capitulo_existente.get('nombre', '')
            if nombre_actual in ('', None, f'(Capítulo inferido)', f'Regla {numero}.'):
                # El nombre actual es genérico, actualizar con el del PDF
                capitulo_existente['nombre'] = nombre_capitulo
                # También actualizar path_texto para consistencia
                capitulo_existente['path_texto'] = path_capitulo
        else:
            # Crear el capítulo virtual
            max_orden_div += 1
            nuevas_divisiones.append({
                'tipo': 'capitulo',
                'numero': numero,
                'numero_orden': float(numero),  # Para ordenar correctamente
                'nombre': nombre_capitulo,
                'path_texto': path_capitulo,
                'orden_global': max_orden_div,
            })

        # Verificar si la regla ya existe
        regla_existente = None
        for r in reglas_dict:
            if r.get('numero') == numero:
                regla_existente = r
                break

        if regla_existente:
            # La regla ya existe - actualizar division_path si es necesario
            # y mejorar título si está vacío
            if not regla_existente.get('titulo'):
                regla_existente['titulo'] = regla.get('titulo')
            # Actualizar division_path al capítulo correcto (puede haber cambiado)
            regla_existente['division_path'] = path_capitulo
        else:
            # Crear la regla
            max_orden_regla += 1
            nuevas_reglas.append({
                'numero': numero,
                'titulo': regla.get('titulo'),
                'contenido': regla.get('contenido', ''),
                'referencias': regla.get('referencias'),
                'division_path': path_capitulo,
                'orden_global': max_orden_regla,
                'tipo': 'regla',
                'calidad': {
                    'estatus': 'ok',
                    'issues': [],
                    'fuente': 'pdf',  # Marcar que viene del PDF
                },
                'fracciones': [],  # Las reglas del PDF no tienen fracciones parseadas
            })

    # Agregar a las listas existentes
    divisiones_dict.extend(nuevas_divisiones)
    reglas_dict.extend(nuevas_reglas)

    # Reportar por título
    por_titulo = {}
    for r in nuevas_reglas:
        t = r['numero'].split('.')[0]
        por_titulo[t] = por_titulo.get(t, 0) + 1

    for t in sorted(por_titulo.keys(), key=int):
        print(f"      Título {t}: {por_titulo[t]} reglas")

    return divisiones_dict, reglas_dict


def eliminar_divisiones_duplicadas(divisiones):
    """
    Elimina divisiones duplicadas, manteniendo la primera instancia.
    Los duplicados se identifican por path_texto.
    """
    seen = set()
    resultado = []

    for div in divisiones:
        path = div.get("path_texto", "")
        if path not in seen:
            seen.add(path)
            resultado.append(div)

    eliminados = len(divisiones) - len(resultado)
    if eliminados > 0:
        print(f"   Eliminados {eliminados} divisiones duplicadas")

    return resultado


def insertar_divisiones_rmf(cursor, ley_id, divisiones):
    """
    Inserta divisiones RMF y construye la jerarquía.
    Retorna un diccionario path_texto -> division_id
    """
    # Eliminar duplicados antes de insertar
    divisiones = eliminar_divisiones_duplicadas(divisiones)

    division_map = {}

    for div in divisiones:
        padre_id = None
        path_texto = div.get("path_texto", "")

        # Buscar padre basándonos en path_texto
        if " > " in path_texto:
            partes = path_texto.split(" > ")
            path_padre = " > ".join(partes[:-1])
            if path_padre in division_map:
                padre_id = division_map[path_padre]

        cursor.execute("""
            INSERT INTO divisiones (ley_id, padre_id, tipo, numero, numero_orden, nombre, path_texto, orden_global)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            ley_id,
            padre_id,
            div["tipo"],
            div["numero"],
            div.get("numero_orden"),
            div.get("nombre"),
            path_texto,
            div.get("orden_global")
        ))

        division_id = cursor.fetchone()[0]
        division_map[path_texto] = division_id

    # Actualizar path_ids y nivel
    for path_texto, division_id in division_map.items():
        path_ids = []
        current_path = path_texto
        while current_path:
            if current_path in division_map:
                path_ids.insert(0, division_map[current_path])
            partes = current_path.split(" > ")
            if len(partes) > 1:
                current_path = " > ".join(partes[:-1])
            else:
                break

        nivel = len(path_ids) - 1 if path_ids else 0

        cursor.execute("""
            UPDATE divisiones
            SET path_ids = %s, nivel = %s
            WHERE id = %s
        """, (path_ids, nivel, division_id))

    return division_map


def insertar_reglas(cursor, ley_id, reglas, division_map):
    """Inserta reglas RMF como artículos con tipo='regla' o 'inexistente'"""
    total_fracciones = 0

    for regla in reglas:
        # Encontrar la división correspondiente
        division_id = None
        division_path = regla.get("division_path", "")
        if division_path and division_path in division_map:
            division_id = division_map[division_path]

        # Usar tipo de la regla si existe, sino default 'regla'
        tipo = regla.get("tipo", "regla")

        # Obtener calidad si existe (solo reglas con issues)
        calidad_json = None
        if regla.get("calidad"):
            calidad_json = json.dumps(regla["calidad"], ensure_ascii=False)

        cursor.execute("""
            INSERT INTO articulos (
                ley_id, division_id, numero_raw, numero_base, sufijo, ordinal,
                titulo, contenido, es_transitorio, tipo, referencias, orden_global, calidad
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            ley_id,
            division_id,
            regla["numero"],
            None,  # numero_base no aplica para reglas RMF
            None,  # sufijo no aplica
            None,  # ordinal no aplica
            regla.get("titulo"),  # Título de la regla
            regla["contenido"],
            False,  # es_transitorio
            tipo,  # 'regla' o 'inexistente'
            regla.get("referencias"),  # referencias legales al final
            regla.get("orden_global"),
            calidad_json  # registro de calidad (JSONB)
        ))

        articulo_id = cursor.fetchone()[0]

        # Insertar fracciones si existen
        fracciones = regla.get("fracciones", [])
        if fracciones:
            total_fracciones += insertar_fracciones(cursor, articulo_id, fracciones)

    return total_fracciones


def insertar_fracciones(cursor, articulo_id, fracciones):
    """Inserta fracciones e incisos de una regla."""
    count = 0
    orden_global = 0

    for fraccion in fracciones:
        numero_fraccion = fraccion.get("numero")  # Puede ser None para párrafos
        contenido_fraccion = fraccion.get("contenido", "")
        tipo_fraccion = fraccion.get("tipo", "fraccion")  # "fraccion" o "parrafo"
        incisos = fraccion.get("incisos", [])

        # Si es una fracción virtual (sin número ni contenido), solo insertar los incisos directamente
        if not numero_fraccion and not contenido_fraccion:
            for inciso in incisos:
                orden_global += 1
                count += 1

                cursor.execute("""
                    INSERT INTO fracciones (articulo_id, padre_id, tipo, numero, numero_orden, contenido, orden)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    articulo_id,
                    None,  # sin padre - inciso directo
                    'inciso',
                    inciso.get("letra"),
                    inciso.get("orden", orden_global),
                    inciso.get("contenido", ""),
                    orden_global
                ))
            continue

        # Insertar fracción o párrafo intermedio
        orden_global += 1
        count += 1

        cursor.execute("""
            INSERT INTO fracciones (articulo_id, padre_id, tipo, numero, numero_orden, contenido, orden)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            articulo_id,
            None,  # padre_id - fracciones y párrafos son de nivel superior
            tipo_fraccion,  # Usa el tipo del JSON: 'fraccion' o 'parrafo'
            numero_fraccion,  # Puede ser None para párrafos
            fraccion.get("orden", orden_global),
            contenido_fraccion,
            orden_global
        ))

        fraccion_id = cursor.fetchone()[0]

        # Insertar incisos si existen (solo para fracciones, no párrafos)
        for inciso in incisos:
            orden_global += 1
            count += 1

            cursor.execute("""
                INSERT INTO fracciones (articulo_id, padre_id, tipo, numero, numero_orden, contenido, orden)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                articulo_id,
                fraccion_id,  # padre es la fracción
                'inciso',
                inciso.get("letra"),
                inciso.get("orden", orden_global),
                inciso.get("contenido", ""),
                orden_global
            ))

    return count


def procesar_rmf(cursor, docx_path):
    """
    Procesa el documento RMF: parsea DOCX e inserta en PostgreSQL.

    Pipeline completo con validación y segunda pasada:
    1. Extracción de párrafos
    2. Parsing estructural
    3. Validación + segunda pasada para corregir issues
    4. Inserción en PostgreSQL con campo calidad
    """
    print(f"   Leyendo {docx_path.name}...")

    # Fase 1: Extracción
    extractor = DocxXmlExtractor(docx_path)
    paragraphs = extractor.extraer()
    print(f"   {len(paragraphs)} párrafos extraídos")

    # Fase 2: Parsing
    nombre_doc = "Resolución Miscelánea Fiscal 2025"
    parser = ParserRMF()
    resultado = parser.parsear(paragraphs, nombre_doc)

    # Fase 3: Validación (primera pasada)
    validador = ValidadorEstructural()
    validador.validar_resultado(resultado)

    reglas_con_problemas = len([r for r in resultado.reglas
                                if r.tipo == "regla" and r.problemas])
    print(f"   {reglas_con_problemas} reglas con problemas detectados")

    # Segunda pasada: intentar corregir problemas usando PDF como fuente de verdad
    if reglas_con_problemas > 0:
        print(f"   Ejecutando segunda pasada...")

        # Buscar PDF correspondiente para corrección
        pdf_path = RMF_DIR / (docx_path.stem.replace('_converted', '').replace('_full', '') + '.pdf')
        if not pdf_path.exists():
            pdfs = list(RMF_DIR.glob("*.pdf"))
            pdf_path = pdfs[0] if pdfs else None

        if pdf_path:
            print(f"   Usando PDF: {pdf_path.name}")

        inspector = InspectorMultiFormato(docx_path=docx_path, pdf_path=pdf_path)
        resoluciones, pendientes = inspector.procesar_resultado(resultado)
        print(f"   {len(resoluciones) - len(pendientes)} correcciones, {len(pendientes)} pendientes")

    print(f"   {len(resultado.divisiones)} divisiones, {resultado.total_reglas} reglas")

    if resultado.total_reglas == 0:
        return {"status": "sin_reglas", "reglas": 0, "divisiones": 0}

    # Convertir a diccionarios para inserción
    divisiones_dict = [
        {
            "tipo": div.tipo.value,
            "numero": div.numero,
            "numero_orden": div.numero_orden,
            "nombre": div.nombre,
            "path_texto": div.path_texto,
            "orden_global": div.orden_global,
        }
        for div in resultado.divisiones
    ]

    reglas_dict = [
        {
            "numero": regla.numero,
            "titulo": regla.titulo,  # Título de la regla
            "contenido": regla.contenido,
            "referencias": regla.referencias,
            "division_path": regla.division_path,
            "orden_global": regla.orden_global,
            "tipo": regla.tipo,
            "calidad": regla.calidad.to_dict() if regla.calidad else None,
            "fracciones": [
                {
                    "numero": f.numero,
                    "contenido": f.contenido,
                    "orden": f.orden,
                    "tipo": getattr(f, 'tipo', 'fraccion'),  # 'fraccion' o 'parrafo'
                    "incisos": [
                        {"letra": i.letra, "contenido": i.contenido, "orden": i.orden}
                        for i in f.incisos
                    ]
                }
                for f in regla.fracciones
            ] if regla.fracciones else [],
        }
        for regla in resultado.reglas
    ]

    # Agregar reglas de dos niveles del PDF (Títulos 1, 6, 7, 8, 9, 10)
    # Estas reglas tienen formato X.Y y no están en el DOCX parseado
    divisiones_dict, reglas_dict = crear_divisiones_y_reglas_dos_niveles(
        divisiones_dict, reglas_dict
    )

    # Preparar info para insertar
    rmf_info = {
        "codigo": "RMF2025",
        "nombre": nombre_doc,
        "url": "https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/normatividad_rmf_rgce2025.html",
        "fecha_descarga": None
    }

    # Insertar en PostgreSQL
    ley_id = insertar_ley_rmf(cursor, rmf_info)

    division_map = {}
    if divisiones_dict:
        division_map = insertar_divisiones_rmf(cursor, ley_id, divisiones_dict)

    total_fracciones = insertar_reglas(cursor, ley_id, reglas_dict, division_map)
    print(f"   {total_fracciones} fracciones/incisos insertados")

    # Métricas de calidad
    reglas_ok = len([r for r in resultado.reglas
                     if r.tipo == "regla" and r.calidad is None])
    reglas_corregidas = len([r for r in resultado.reglas
                              if r.tipo == "regla" and r.calidad
                              and r.calidad.estatus.value == "corregida"])
    reglas_con_error = len([r for r in resultado.reglas
                             if r.tipo == "regla" and r.calidad
                             and r.calidad.estatus.value == "con_error"])

    print(f"\n   Métricas de calidad:")
    print(f"   OK: {reglas_ok}, Corregidas: {reglas_corregidas}, Con error: {reglas_con_error}")

    return {
        "status": "ok",
        "reglas": resultado.total_reglas,
        "divisiones": len(resultado.divisiones),
        "reglas_ok": reglas_ok,
        "reglas_corregidas": reglas_corregidas,
        "reglas_con_error": reglas_con_error,
    }


def main():
    print("=" * 60)
    print("IMPORTADOR DE RMF")
    print("Resolución Miscelánea Fiscal")
    print("=" * 60)

    # Buscar DOCX
    print("\nBuscando archivo DOCX de RMF...")
    docx_path = find_rmf_docx()

    if not docx_path:
        print("ERROR: No se encontró archivo RMF")
        print("Ejecuta primero: python scripts/descargar_rmf.py")
        return 1

    print(f"Encontrado: {docx_path}")

    # Conectar a PostgreSQL
    print(f"\nConectando a PostgreSQL ({PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']})...")
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        conn.autocommit = False
        cursor = conn.cursor()
        print("Conectado")
    except psycopg2.Error as e:
        print(f"Error de conexion: {e}")
        return 1

    # Eliminar RMF existente si existe
    print("\nEliminando RMF existente si existe...")
    cursor.execute("""
        DELETE FROM leyes WHERE codigo = 'RMF2025'
    """)

    # Procesar RMF
    print("\nProcesando RMF...")
    try:
        resultado = procesar_rmf(cursor, docx_path)

        if resultado["status"] == "sin_reglas":
            print("Sin reglas encontradas")
            conn.rollback()
            return 1
        else:
            print(f"\nOK: {resultado['reglas']} reglas, {resultado['divisiones']} divisiones")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return 1

    # Commit
    conn.commit()

    # Refrescar vista materializada
    print("\nRefrescando vista materializada...")
    cursor.execute("REFRESH MATERIALIZED VIEW jerarquia_completa")
    conn.commit()

    # Verificar
    print("\n" + "=" * 60)
    print("VERIFICACION")
    print("=" * 60)

    cursor.execute("""
        SELECT COUNT(*) FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
        WHERE l.codigo = 'RMF2025' AND a.tipo = 'regla'
    """)
    total_reglas = cursor.fetchone()[0]
    print(f"Total reglas RMF: {total_reglas}")

    # Test búsqueda
    cursor.execute("""
        SELECT COUNT(*) FROM articulos
        WHERE tipo = 'regla'
        AND search_vector @@ websearch_to_tsquery('spanish_unaccent', 'factura')
    """)
    factura_count = cursor.fetchone()[0]
    print(f"Test busqueda 'factura' en reglas: {factura_count} resultados")

    conn.close()
    print("\nImportacion completada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
