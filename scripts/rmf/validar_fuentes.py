#!/usr/bin/env python3
"""
Validación cruzada de extracción RMF usando múltiples fuentes.

Fuentes:
1. PyMuPDF (fitz) - extracción actual
2. pdftotext (poppler) - herramienta de línea de comandos
3. DOCX XML - documento Word convertido

Uso: python scripts/rmf/validar_fuentes.py
"""

import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import fitz


@dataclass
class ReglaExtraida:
    """Regla extraída de una fuente."""
    numero: str
    titulo: Optional[str]
    contenido_inicio: str  # Primeros 200 chars
    contenido_fin: str     # Últimos 100 chars
    fuente: str


def extraer_pymupdf(pdf_path: Path) -> dict[str, ReglaExtraida]:
    """Extrae reglas usando PyMuPDF."""
    doc = fitz.open(str(pdf_path))
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()

    reglas = {}
    # Patrón: número standalone seguido de contenido
    patron = re.compile(r'^(\d{1,2}\.\d{1,2}(?:\.\d{1,3})?)\.\s*$', re.MULTILINE)

    matches = list(patron.finditer(text))
    for i, match in enumerate(matches):
        numero = match.group(1)
        inicio = match.end()

        # Fin es el inicio del siguiente match o fin del texto
        if i + 1 < len(matches):
            fin = matches[i + 1].start()
        else:
            fin = min(inicio + 5000, len(text))

        contenido = text[inicio:fin].strip()

        # Extraer título (líneas antes del número)
        texto_antes = text[max(0, match.start() - 500):match.start()]
        lineas_antes = texto_antes.split('\n')
        titulo = None
        for linea in reversed(lineas_antes):
            linea = linea.strip()
            if linea and len(linea) > 10 and linea[0].isupper() and not linea.startswith('Regla'):
                if not re.match(r'^\d', linea) and 'Página' not in linea:
                    titulo = linea
                    break

        reglas[numero] = ReglaExtraida(
            numero=numero,
            titulo=titulo,
            contenido_inicio=contenido[:200],
            contenido_fin=contenido[-100:] if len(contenido) > 100 else contenido,
            fuente='pymupdf'
        )

    return reglas


def extraer_pdftotext(pdf_path: Path) -> dict[str, ReglaExtraida]:
    """Extrae reglas usando pdftotext (poppler)."""
    # Ejecutar pdftotext
    result = subprocess.run(
        ['pdftotext', '-layout', str(pdf_path), '-'],
        capture_output=True, text=True
    )
    text = result.stdout

    reglas = {}
    # En pdftotext, el formato es diferente: "X.Y.Z.    Contenido..."
    patron = re.compile(r'^\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,3})?)\.\s+(.+)', re.MULTILINE)

    for match in patron.finditer(text):
        numero = match.group(1)
        contenido_linea = match.group(2)

        # Buscar más contenido en líneas siguientes
        pos = match.end()
        contenido_extra = ""
        for linea in text[pos:pos+2000].split('\n')[:20]:
            if re.match(r'^\s*\d{1,2}\.\d{1,2}', linea):  # Nueva regla
                break
            if 'Regla' in linea:
                break
            contenido_extra += " " + linea.strip()

        contenido = (contenido_linea + contenido_extra).strip()

        reglas[numero] = ReglaExtraida(
            numero=numero,
            titulo=None,  # pdftotext no separa título
            contenido_inicio=contenido[:200],
            contenido_fin=contenido[-100:] if len(contenido) > 100 else contenido,
            fuente='pdftotext'
        )

    return reglas


def extraer_docx(docx_path: Path) -> dict[str, ReglaExtraida]:
    """Extrae reglas del DOCX descomprimido."""
    import zipfile
    import tempfile

    reglas = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(docx_path, 'r') as z:
            z.extractall(tmpdir)

        doc_xml = Path(tmpdir) / 'word' / 'document.xml'
        if not doc_xml.exists():
            return reglas

        tree = ET.parse(doc_xml)
        root = tree.getroot()

        # Extraer todo el texto
        text = ""
        for elem in root.iter():
            if elem.text:
                text += elem.text + " "

        # Buscar reglas con formato DOCX: "X.Y.Z. - Reforma... Título X.Y.Z. Contenido"
        # Patrón más flexible
        patron = re.compile(
            r'(\d{1,2}\.\d{1,2}(?:\.\d{1,3})?)\.\s+'
            r'(?:-[^\.]+\.\s+)?'  # Nota de reforma opcional
            r'([A-ZÁÉÍÓÚÑ][^\.]{10,100}?)\s+'  # Título (capitalizado)
            r'\1\.\s+'  # Número repetido
            r'(.{50,500}?)'  # Contenido
            r'(?=\d{1,2}\.\d{1,2}|\Z)',  # Hasta próxima regla
            re.DOTALL
        )

        for match in patron.finditer(text):
            numero = match.group(1)
            titulo = match.group(2).strip()
            contenido = match.group(3).strip()

            reglas[numero] = ReglaExtraida(
                numero=numero,
                titulo=titulo,
                contenido_inicio=contenido[:200],
                contenido_fin=contenido[-100:] if len(contenido) > 100 else contenido,
                fuente='docx'
            )

    return reglas


def comparar_fuentes(reglas_por_fuente: dict[str, dict[str, ReglaExtraida]]) -> None:
    """Compara las reglas extraídas de diferentes fuentes."""

    # Obtener todas las reglas únicas
    todas_reglas = set()
    for fuente, reglas in reglas_por_fuente.items():
        todas_reglas.update(reglas.keys())

    print(f"\n{'='*70}")
    print("COMPARACIÓN DE FUENTES")
    print(f"{'='*70}")

    for fuente, reglas in reglas_por_fuente.items():
        print(f"  {fuente}: {len(reglas)} reglas")

    print(f"  Total únicas: {len(todas_reglas)}")

    # Comparar reglas específicas
    reglas_test = ['2.2.2', '2.2.3', '1.11', '5.1.3', '10.10']

    print(f"\n{'='*70}")
    print("COMPARACIÓN DETALLADA")
    print(f"{'='*70}")

    for num in reglas_test:
        print(f"\n--- Regla {num} ---")
        for fuente, reglas in reglas_por_fuente.items():
            if num in reglas:
                r = reglas[num]
                print(f"\n[{fuente}]")
                if r.titulo:
                    print(f"  Título: {r.titulo[:60]}...")
                print(f"  Inicio: {r.contenido_inicio[:80]}...")
                print(f"  Fin: ...{r.contenido_fin[-60:]}")
            else:
                print(f"\n[{fuente}] NO ENCONTRADA")

    # Detectar discrepancias
    print(f"\n{'='*70}")
    print("DISCREPANCIAS DETECTADAS")
    print(f"{'='*70}")

    discrepancias = []
    fuentes = list(reglas_por_fuente.keys())

    for numero in sorted(todas_reglas, key=lambda x: [int(p) for p in x.split('.')]):
        # Verificar si todas las fuentes la tienen
        presentes = [f for f in fuentes if numero in reglas_por_fuente[f]]
        if len(presentes) < len(fuentes):
            ausentes = [f for f in fuentes if f not in presentes]
            discrepancias.append(f"{numero}: falta en {ausentes}")

    if discrepancias:
        print(f"  {len(discrepancias)} reglas con discrepancias de presencia")
        for d in discrepancias[:10]:
            print(f"    {d}")
        if len(discrepancias) > 10:
            print(f"    ... y {len(discrepancias) - 10} más")
    else:
        print("  ✓ Todas las fuentes tienen las mismas reglas")


def main():
    base_dir = Path(__file__).parent.parent.parent
    pdf_path = base_dir / "doc/rmf/rmf_2025_compilada.pdf"
    docx_path = base_dir / "doc/rmf/rmf_2025_full_converted.docx"

    print("="*70)
    print("VALIDACIÓN CRUZADA DE FUENTES RMF")
    print("="*70)

    reglas_por_fuente = {}

    print("\n1. Extrayendo con PyMuPDF...")
    reglas_por_fuente['pymupdf'] = extraer_pymupdf(pdf_path)
    print(f"   {len(reglas_por_fuente['pymupdf'])} reglas encontradas")

    print("\n2. Extrayendo con pdftotext...")
    reglas_por_fuente['pdftotext'] = extraer_pdftotext(pdf_path)
    print(f"   {len(reglas_por_fuente['pdftotext'])} reglas encontradas")

    if docx_path.exists():
        print("\n3. Extrayendo de DOCX...")
        reglas_por_fuente['docx'] = extraer_docx(docx_path)
        print(f"   {len(reglas_por_fuente['docx'])} reglas encontradas")
    else:
        print("\n3. DOCX no disponible, saltando...")

    comparar_fuentes(reglas_por_fuente)


if __name__ == "__main__":
    main()
