#!/usr/bin/env python3
"""
Convertidor genérico de leyes/reglamentos mexicanos
Convierte PDF -> DOCX -> Markdown, JSON y SQLite
"""

import re
import json
import sqlite3
import sys
from pathlib import Path
from pdf2docx import Converter
from docx import Document

# Directorio raíz del proyecto (padre de scripts/)
BASE_DIR = Path(__file__).parent.parent

def convertir_pdf_a_docx(pdf_path: Path, docx_path: Path):
    """Convierte PDF a DOCX usando pdf2docx"""
    print(f"   Convirtiendo PDF a DOCX...")
    cv = Converter(str(pdf_path))
    cv.convert(str(docx_path), start=0, end=None)
    cv.close()
    print(f"   ✓ DOCX generado")

def extraer_texto_docx(doc_path: Path) -> list:
    """Extrae todo el texto del documento DOCX"""
    doc = Document(doc_path)
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            # Ignorar números de página
            if re.match(r'^\d+ de \d+$', text):
                continue
            paragraphs.append(text)
    return paragraphs

def parsear_ley(paragraphs: list) -> list:
    """Parsea el texto en estructura de títulos, artículos y contenido"""
    articulos = []
    titulo_actual = ""
    capitulo_actual = ""
    seccion_actual = ""

    i = 0
    while i < len(paragraphs):
        text = paragraphs[i]

        # Detectar TÍTULO
        if re.match(r'^T[ÍI]TULO\s+', text, re.IGNORECASE):
            titulo_actual = text.replace('\n', ' ').strip()
            capitulo_actual = ""
            seccion_actual = ""
            i += 1
            continue

        # Detectar CAPÍTULO
        if re.match(r'^CAP[ÍI]TULO\s+', text, re.IGNORECASE):
            capitulo_actual = text.replace('\n', ' ').strip()
            seccion_actual = ""
            i += 1
            continue

        # Detectar SECCIÓN
        if re.match(r'^SECCI[ÓO]N\s+', text, re.IGNORECASE):
            seccion_actual = text.replace('\n', ' ').strip()
            i += 1
            continue

        # Detectar Artículo
        articulo_match = re.match(
            r'^Art[íi]culo\s+(\d+[a-zA-Z]?(?:[-\s]*(?:Bis|Ter|Qu[áa]ter|Quinquies|Sexies|A|B|C|D|E|F))?)\s*[.\-]?\s*[-–]?\s*(.*)',
            text,
            re.IGNORECASE
        )
        if articulo_match:
            num_articulo = articulo_match.group(1).strip()
            num_articulo = re.sub(r'\s+', ' ', num_articulo)
            contenido_inicial = articulo_match.group(2).strip()

            contenido_partes = [contenido_inicial] if contenido_inicial else []
            referencias = []

            i += 1
            while i < len(paragraphs):
                next_text = paragraphs[i]

                # ¿Es el inicio de otro artículo, título, capítulo o sección?
                if re.match(r'^Art[íi]culo\s+\d+', next_text, re.IGNORECASE):
                    break
                if re.match(r'^T[ÍI]TULO\s+', next_text, re.IGNORECASE):
                    break
                if re.match(r'^CAP[ÍI]TULO\s+', next_text, re.IGNORECASE):
                    break
                if re.match(r'^SECCI[ÓO]N\s+', next_text, re.IGNORECASE):
                    break
                if re.match(r'^TRANSITORIOS?$', next_text, re.IGNORECASE):
                    break

                # Detectar referencias DOF
                if re.match(r'^(Art[íi]culo|P[áa]rrafo|Fracci[óo]n|Inciso|Numeral|Apartado).*(?:reformad[oa]|adicionad[oa]|derogad[oa]).*DOF', next_text, re.IGNORECASE):
                    referencias.append(next_text)
                    i += 1
                    continue

                contenido_partes.append(next_text)
                i += 1

            # Construir ubicación jerárquica
            ubicacion_partes = []
            if titulo_actual:
                ubicacion_partes.append(titulo_actual)
            if capitulo_actual:
                ubicacion_partes.append(capitulo_actual)
            if seccion_actual:
                ubicacion_partes.append(seccion_actual)

            articulo = {
                "titulo": " > ".join(ubicacion_partes) if ubicacion_partes else "General",
                "articulo": f"Artículo {num_articulo}",
                "contenido": "\n".join(contenido_partes),
                "referencia": " | ".join(referencias) if referencias else ""
            }
            articulos.append(articulo)
            continue

        i += 1

    return articulos

def generar_markdown(articulos: list, output_path: Path, nombre_ley: str):
    """Genera archivo Markdown"""
    md_lines = [f"# {nombre_ley}\n\n", "---\n\n"]
    titulo_anterior = ""

    for art in articulos:
        if art["titulo"] != titulo_anterior:
            md_lines.append(f"## {art['titulo']}\n\n")
            titulo_anterior = art["titulo"]

        md_lines.append(f"### {art['articulo']}\n\n")
        md_lines.append(f"{art['contenido']}\n\n")

        if art["referencia"]:
            md_lines.append(f"*{art['referencia']}*\n\n")

        md_lines.append("---\n\n")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("".join(md_lines))
    print(f"   ✓ Markdown generado")

def generar_json(articulos: list, output_path: Path, nombre_ley: str):
    """Genera archivo JSON"""
    data = {
        "ley": nombre_ley,
        "total_articulos": len(articulos),
        "articulos": articulos
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   ✓ JSON generado")

def generar_sqlite(articulos: list, output_path: Path, nombre_ley: str):
    """Genera base de datos SQLite"""
    if output_path.exists():
        output_path.unlink()

    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)
    ''')
    cursor.execute('INSERT INTO metadata VALUES (?, ?)', ('ley', nombre_ley))
    cursor.execute('INSERT INTO metadata VALUES (?, ?)', ('total_articulos', str(len(articulos))))

    cursor.execute('''
        CREATE TABLE articulos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            articulo TEXT NOT NULL,
            contenido TEXT NOT NULL,
            referencia TEXT
        )
    ''')

    cursor.execute('CREATE INDEX idx_titulo ON articulos(titulo)')
    cursor.execute('CREATE INDEX idx_articulo ON articulos(articulo)')

    cursor.execute('''
        CREATE VIRTUAL TABLE articulos_fts USING fts5(
            titulo, articulo, contenido, referencia,
            content='articulos', content_rowid='id'
        )
    ''')

    for art in articulos:
        cursor.execute('''
            INSERT INTO articulos (titulo, articulo, contenido, referencia)
            VALUES (?, ?, ?, ?)
        ''', (art["titulo"], art["articulo"], art["contenido"], art["referencia"]))

    cursor.execute("INSERT INTO articulos_fts(articulos_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()
    print(f"   ✓ SQLite generado")

def convertir_documento(carpeta: Path, nombre_ley: str):
    """Convierte un documento completo"""
    # Buscar el PDF
    pdfs = list(carpeta.glob("*.pdf"))
    if not pdfs:
        print(f"   ⚠ No se encontró PDF en {carpeta}")
        return False

    pdf_path = pdfs[0]
    base_name = pdf_path.stem

    # Rutas de salida
    docx_path = carpeta / f"{base_name}.docx"
    md_path = carpeta / f"{base_name}.md"
    json_path = carpeta / f"{base_name}.json"
    db_path = carpeta / f"{base_name}.db"

    # Verificar si ya está convertido
    if db_path.exists() and md_path.exists() and json_path.exists():
        print(f"   ✓ Ya convertido")
        return True

    try:
        # Paso 1: PDF a DOCX
        if not docx_path.exists():
            convertir_pdf_a_docx(pdf_path, docx_path)

        # Paso 2: Extraer texto
        print(f"   Extrayendo texto...")
        paragraphs = extraer_texto_docx(docx_path)
        print(f"   {len(paragraphs)} párrafos extraídos")

        # Paso 3: Parsear estructura
        print(f"   Parseando estructura...")
        articulos = parsear_ley(paragraphs)
        print(f"   {len(articulos)} artículos encontrados")

        if len(articulos) == 0:
            print(f"   ⚠ No se encontraron artículos")
            return False

        # Paso 4: Generar formatos
        generar_markdown(articulos, md_path, nombre_ley)
        generar_json(articulos, json_path, nombre_ley)
        generar_sqlite(articulos, db_path, nombre_ley)

        return True

    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

# Configuración de documentos a convertir
DOCUMENTOS = {
    # Constitución
    BASE_DIR / "doc/leyes/cpeum": "Constitución Política de los Estados Unidos Mexicanos",
    # Leyes
    BASE_DIR / "doc/leyes/lieps": "Ley del Impuesto Especial sobre Producción y Servicios",
    BASE_DIR / "doc/leyes/lisr": "Ley del Impuesto Sobre la Renta",
    BASE_DIR / "doc/leyes/liva": "Ley del Impuesto al Valor Agregado",
    BASE_DIR / "doc/leyes/lss": "Ley del Seguro Social",
    # Reglamentos
    BASE_DIR / "doc/reglamentos/rcff": "Reglamento del Código Fiscal de la Federación",
    BASE_DIR / "doc/reglamentos/rlieps": "Reglamento de la Ley del IEPS",
    BASE_DIR / "doc/reglamentos/risr": "Reglamento de la Ley del ISR",
    BASE_DIR / "doc/reglamentos/riva": "Reglamento de la Ley del IVA",
    BASE_DIR / "doc/reglamentos/rlft": "Reglamento de la Ley Federal del Trabajo",
    BASE_DIR / "doc/reglamentos/rlss": "Reglamento de la Ley del Seguro Social",
    BASE_DIR / "doc/reglamentos/racerf": "Reglamento de Afiliación del IMSS",
}

def main():
    print("=" * 60)
    print("Convertidor de Leyes y Reglamentos")
    print("=" * 60)

    exitosos = 0
    fallidos = 0

    for carpeta, nombre in DOCUMENTOS.items():
        print(f"\n📂 {nombre}")
        print(f"   Carpeta: {carpeta}")

        if not carpeta.exists():
            print(f"   ⚠ Carpeta no existe")
            fallidos += 1
            continue

        if convertir_documento(carpeta, nombre):
            exitosos += 1
        else:
            fallidos += 1

    print("\n" + "=" * 60)
    print(f"COMPLETADO: {exitosos} exitosos, {fallidos} fallidos")
    print("=" * 60)

if __name__ == "__main__":
    main()
