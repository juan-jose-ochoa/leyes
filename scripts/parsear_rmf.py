#!/usr/bin/env python3
"""
Parser de Resolución Miscelánea Fiscal (RMF)

Extrae estructura jerárquica: Títulos, Capítulos, Secciones, Reglas

Diferencias con leyes normales:
- Unidad básica: "regla" (no "artículo")
- Numeración compuesta: 2.1.1., 2.1.2. (no simple: 1, 2, 3)
- Referencias al final: CFF 4o., 17-D, RMF 2.1.39.

Salida: JSON estructurado listo para importar a PostgreSQL
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from docx import Document

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).parent.parent
RMF_DIR = BASE_DIR / "doc" / "rmf"
RMF_DOCX_NAME = "rmf_2025_full_converted.docx"  # Archivo preferido


@dataclass
class Division:
    """Representa una división estructural: Título, Capítulo, Sección"""
    tipo: str  # 'titulo', 'capitulo', 'seccion'
    numero: str  # '2', '2.1', '2.1.1'
    numero_orden: int  # Para ordenamiento
    nombre: str  # Descripción
    orden_global: int  # Posición en el documento


@dataclass
class Regla:
    """Representa una regla de la RMF"""
    numero: str  # "2.1.1.", "2.1.2."
    titulo: str  # Título de la regla
    contenido: str  # Contenido completo
    referencias: Optional[str]  # "CFF 4o., 17-D, RMF 2.1.39."
    orden_global: int = 0
    division_path: str = ""  # "TITULO 2 > CAPITULO 2.1"
    titulo_padre: Optional[str] = None
    capitulo_padre: Optional[str] = None
    seccion_padre: Optional[str] = None


# Patrones regex para RMF
# Título: "2. Código Fiscal de la Federación"
PATRON_TITULO_RMF = re.compile(
    r'^(\d+)\.\s+(.+)$'
)

# Capítulo: "Capítulo 2.1. Disposiciones generales"
PATRON_CAPITULO_RMF = re.compile(
    r'^Cap[íi]tulo\s+(\d+\.\d+)\.?\s*(.*)$',
    re.IGNORECASE
)

# Sección: "Sección 2.6.1. Disposiciones generales"
PATRON_SECCION_RMF = re.compile(
    r'^Secci[óo]n\s+(\d+\.\d+\.\d+)\.?\s*(.*)$',
    re.IGNORECASE
)

# Regla: "2.1.1. Cobro de créditos fiscales..."
# La regla empieza con X.X.X. donde X son números
PATRON_REGLA = re.compile(
    r'^(\d+\.\d+\.\d+)\.?\s+(.*)$'
)

# Referencias al final de regla: CFF, LISR, LIVA, RMF, etc.
PATRON_REFERENCIAS = re.compile(
    r'^((?:CFF|LISR|LIVA|LIESPS|LIEPS|LIF|LA|RMF|RGCE|RCFF|RLISR|RLIVA|RLIESPS)'
    r'(?:\s+\d+[oa]?(?:-[A-Z])?(?:,\s*\d+[oa]?(?:-[A-Z])?)*'
    r'(?:,?\s*(?:CFF|LISR|LIVA|LIESPS|LIEPS|LIF|LA|RMF|RGCE|RCFF|RLISR|RLIVA|RLIESPS)'
    r'\s+\d+[oa]?(?:-[A-Z])?(?:,\s*\d+[oa]?(?:-[A-Z])?)*)*))$'
)

# Patrón más flexible para referencias (última línea con siglas de ley)
PATRON_REFERENCIAS_SIMPLE = re.compile(
    r'^((?:CFF|LISR|LIVA|LIESPS|LIEPS|LIF|LA|RMF|RGCE|RCFF|RLISR|RLIVA|RLIESPS|Ley del ISR|Ley del IVA).*?)$',
    re.IGNORECASE
)

PATRON_PAGINA = re.compile(r'^\d+\s+de\s+\d+$')

# Nombres oficiales de los Títulos de la RMF
# Se usan para inferir el título cuando se parsea un capítulo
NOMBRES_TITULOS_RMF = {
    "1": "Disposiciones Generales",
    "2": "Código Fiscal de la Federación",
    "3": "Impuesto sobre la Renta",
    "4": "Impuesto al Valor Agregado",
    "5": "Impuesto Especial sobre Producción y Servicios",
    "6": "Contribuciones de Mejoras",
    "7": "Derechos",
    "8": "Impuesto sobre Automóviles Nuevos",
    "9": "Ley de Ingresos de la Federación",
    "10": "Ley de Ingresos sobre Hidrocarburos",
    "11": "De los Decretos, Acuerdos, Convenios y Resoluciones de carácter general",
    "12": "De la Prestación de Servicios Digitales",
}


def extraer_texto_docx(doc_path: Path) -> list[str]:
    """Extrae párrafos del DOCX, limpiando páginas y espacios"""
    doc = Document(doc_path)
    paragraphs = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        # Ignorar números de página
        if PATRON_PAGINA.match(text):
            continue
        # Ignorar encabezados repetitivos
        if text.startswith("Resolución Miscelánea Fiscal"):
            continue
        paragraphs.append(text)

    return paragraphs


def consolidar_parrafos(partes: list[str]) -> str:
    """
    Une fragmentos que son continuación del mismo párrafo.
    Igual que en parsear_ley.py
    """
    if not partes:
        return ""

    resultado = []
    buffer = ""

    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue

        if not buffer:
            buffer = parte
        elif buffer[-1] in '.;:?!':
            resultado.append(buffer)
            buffer = parte
        else:
            buffer = buffer + ' ' + parte

    if buffer:
        resultado.append(buffer)

    return '\n\n'.join(resultado)


def es_referencia_final(texto: str) -> bool:
    """Detecta si una línea es la referencia legal al final de una regla"""
    # Patrones típicos de referencias
    siglas = ['CFF', 'LISR', 'LIVA', 'LIESPS', 'LIEPS', 'LIF', 'LA', 'RMF', 'RGCE',
              'RCFF', 'RLISR', 'RLIVA', 'RLIESPS', 'DECRETO', 'DOF']

    texto_upper = texto.upper().strip()

    # Si empieza con una sigla de ley
    for sigla in siglas:
        if texto_upper.startswith(sigla):
            return True

    # Si contiene muchas comas y números (típico de referencias)
    if texto.count(',') >= 2 and re.search(r'\d+[oa]?', texto):
        for sigla in siglas:
            if sigla in texto_upper:
                return True

    return False


def parsear_rmf(paragraphs: list[str], nombre_doc: str) -> dict:
    """
    Parsea los párrafos de la RMF en estructura jerárquica

    Retorna:
    {
        "documento": nombre_doc,
        "tipo": "rmf",
        "divisiones": [...],
        "reglas": [...]
    }
    """
    divisiones = []
    reglas = []

    # Estado actual de la jerarquía
    titulo_actual = None
    capitulo_actual = None
    seccion_actual = None

    orden_division = 0
    orden_regla = 0

    i = 0
    while i < len(paragraphs):
        text = paragraphs[i]

        # === TÍTULO RMF ===
        # NO parseamos títulos explícitamente porque el documento tiene muchos falsos positivos
        # (glosario, numerales, etc.). En su lugar, los títulos se INFIEREN de los capítulos.
        # Cuando vemos "Capítulo 2.1", creamos automáticamente "Título 2" si no existe.

        # === CAPÍTULO RMF (ej: "Capítulo 2.1. Disposiciones generales") ===
        match = PATRON_CAPITULO_RMF.match(text)
        if match:
            numero = match.group(1)
            nombre = match.group(2) or ""

            # Si el nombre está en la siguiente línea
            if not nombre and i + 1 < len(paragraphs):
                next_text = paragraphs[i + 1]
                if not PATRON_CAPITULO_RMF.match(next_text) and not PATRON_SECCION_RMF.match(next_text) and not PATRON_REGLA.match(next_text):
                    nombre = next_text
                    i += 1

            # INFERIR TÍTULO del número de capítulo (ej: "2.1" -> Título "2")
            titulo_numero = numero.split('.')[0]  # "2.1" -> "2"
            if titulo_actual is None or titulo_actual["numero"] != titulo_numero:
                # Crear nuevo título inferido
                orden_division += 1
                titulo_actual = {
                    "tipo": "titulo",
                    "numero": titulo_numero,
                    "numero_orden": int(titulo_numero),
                    "nombre": NOMBRES_TITULOS_RMF.get(titulo_numero, f"Título {titulo_numero}"),
                    "orden_global": orden_division,
                    "path_texto": f"TITULO {titulo_numero}"
                }
                divisiones.append(titulo_actual)
                capitulo_actual = None
                seccion_actual = None

            orden_division += 1
            path = titulo_actual["path_texto"] if titulo_actual else ""
            capitulo_actual = {
                "tipo": "capitulo",
                "numero": numero,
                "numero_orden": orden_division,
                "nombre": nombre.strip(),
                "orden_global": orden_division,
                "padre_tipo": "titulo",
                "padre_numero": titulo_actual["numero"] if titulo_actual else None,
                "path_texto": f"{path} > CAPITULO {numero}" if path else f"CAPITULO {numero}"
            }
            divisiones.append(capitulo_actual)
            seccion_actual = None
            i += 1
            continue

        # === SECCIÓN RMF (ej: "Sección 2.6.1. Del pago") ===
        match = PATRON_SECCION_RMF.match(text)
        if match:
            numero = match.group(1)
            nombre = match.group(2) or ""

            if not nombre and i + 1 < len(paragraphs):
                next_text = paragraphs[i + 1]
                if not PATRON_SECCION_RMF.match(next_text) and not PATRON_REGLA.match(next_text):
                    nombre = next_text
                    i += 1

            orden_division += 1
            path = capitulo_actual["path_texto"] if capitulo_actual else (
                titulo_actual["path_texto"] if titulo_actual else ""
            )
            seccion_actual = {
                "tipo": "seccion",
                "numero": numero,
                "numero_orden": orden_division,
                "nombre": nombre.strip(),
                "orden_global": orden_division,
                "padre_tipo": "capitulo" if capitulo_actual else "titulo",
                "padre_numero": capitulo_actual["numero"] if capitulo_actual else (
                    titulo_actual["numero"] if titulo_actual else None
                ),
                "path_texto": f"{path} > SECCION {numero}" if path else f"SECCION {numero}"
            }
            divisiones.append(seccion_actual)
            i += 1
            continue

        # === REGLA (ej: "2.1.1. Cobro de créditos fiscales...") ===
        match = PATRON_REGLA.match(text)
        if match:
            numero = match.group(1)
            titulo_inicial = match.group(2).strip()
            parrafo_inicio = i  # Guardar índice de inicio para validación de títulos

            # Recolectar contenido de la regla
            contenido_partes = [titulo_inicial] if titulo_inicial else []
            referencias = None

            i += 1
            while i < len(paragraphs):
                next_text = paragraphs[i]

                # ¿Termina la regla?
                if PATRON_REGLA.match(next_text):
                    break
                if PATRON_CAPITULO_RMF.match(next_text):
                    break
                if PATRON_SECCION_RMF.match(next_text):
                    break
                # Título nuevo (número simple + texto largo)
                titulo_match = PATRON_TITULO_RMF.match(next_text)
                if titulo_match and int(titulo_match.group(1)) <= 15:
                    break

                # Detectar referencias al final
                if es_referencia_final(next_text):
                    referencias = next_text
                else:
                    contenido_partes.append(next_text)

                i += 1

            # Determinar título de la regla (primera oración hasta el primer punto)
            contenido_completo = consolidar_parrafos(contenido_partes)
            titulo_regla = ""
            if contenido_completo:
                # El título es la primera parte significativa
                primer_parrafo = contenido_completo.split('\n\n')[0] if '\n\n' in contenido_completo else contenido_completo
                # Truncar si es muy largo
                if len(primer_parrafo) > 200:
                    titulo_regla = primer_parrafo[:200] + "..."
                else:
                    titulo_regla = primer_parrafo

            # Determinar división actual
            division_actual = seccion_actual or capitulo_actual or titulo_actual
            division_path = division_actual["path_texto"] if division_actual else ""

            orden_regla += 1
            regla = {
                "numero": numero,
                "titulo": titulo_regla,
                "contenido": contenido_completo,
                "referencias": referencias,
                "orden_global": orden_regla,
                "division_path": division_path,
                "titulo_padre": titulo_actual["numero"] if titulo_actual else None,
                "capitulo_padre": capitulo_actual["numero"] if capitulo_actual else None,
                "seccion_padre": seccion_actual["numero"] if seccion_actual else None,
                "_parrafo_inicio": parrafo_inicio,  # Para validación interna
            }
            reglas.append(regla)
            continue

        i += 1

    return {
        "documento": nombre_doc,
        "tipo": "rmf",
        "total_divisiones": len(divisiones),
        "total_reglas": len(reglas),
        "divisiones": divisiones,
        "reglas": reglas
    }


def procesar_rmf(docx_path: Path, output_path: Path):
    """Procesa el documento RMF y genera JSON estructurado"""
    print(f"   Leyendo DOCX: {docx_path.name}")
    paragraphs = extraer_texto_docx(docx_path)
    print(f"   {len(paragraphs)} párrafos extraídos")

    print(f"   Parseando estructura...")
    nombre_doc = docx_path.stem.replace("_", " ").title()
    resultado = parsear_rmf(paragraphs, nombre_doc)
    print(f"   {resultado['total_divisiones']} divisiones, {resultado['total_reglas']} reglas")

    print(f"   Guardando JSON...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    return resultado


def main():
    """Procesa la RMF principal"""
    print("=" * 60)
    print("Parser de RMF - Resolución Miscelánea Fiscal")
    print("=" * 60)

    # Buscar DOCX de RMF compilada
    if not RMF_DIR.exists():
        print(f"ERROR: No existe directorio {RMF_DIR}")
        print("Ejecuta primero: python scripts/descargar_rmf.py")
        return 1

    # Buscar archivos DOCX (la RMF puede venir en DOCX o necesitar conversión)
    docx_files = list(RMF_DIR.glob("*.docx"))

    if not docx_files:
        # Intentar convertir PDF a DOCX
        pdf_files = list(RMF_DIR.glob("*.pdf"))
        if pdf_files:
            print(f"\nEncontrado PDF: {pdf_files[0].name}")
            print("Convirtiendo a DOCX...")

            try:
                from pdf2docx import Converter

                pdf_path = pdf_files[0]
                docx_path = pdf_path.with_suffix('.docx')

                cv = Converter(str(pdf_path))
                cv.convert(str(docx_path))
                cv.close()

                print(f"   Convertido: {docx_path.name}")
                docx_files = [docx_path]
            except ImportError:
                print("ERROR: pdf2docx no instalado. Ejecuta: pip install pdf2docx")
                return 1
            except Exception as e:
                print(f"ERROR convirtiendo PDF: {e}")
                return 1

    if not docx_files:
        print("ERROR: No se encontró DOCX ni PDF de RMF")
        return 1

    # Procesar RMF principal
    docx_path = docx_files[0]
    json_path = RMF_DIR / "rmf_parsed.json"

    try:
        resultado = procesar_rmf(docx_path, json_path)
        print(f"\n   Guardado: {json_path}")

        # Mostrar estadísticas
        print("\n" + "=" * 60)
        print("RESUMEN")
        print("=" * 60)
        print(f"Documento: {resultado['documento']}")
        print(f"Divisiones: {resultado['total_divisiones']}")
        print(f"Reglas: {resultado['total_reglas']}")

        # Mostrar primeras reglas como ejemplo
        if resultado['reglas']:
            print(f"\nPrimeras 5 reglas:")
            for regla in resultado['reglas'][:5]:
                titulo = regla['titulo'][:60] + "..." if len(regla['titulo']) > 60 else regla['titulo']
                print(f"   {regla['numero']} - {titulo}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
