#!/usr/bin/env python3
"""
Parser de leyes mexicanas v2
Extrae estructura jerárquica completa: Títulos, Capítulos, Secciones, Artículos

Salida: JSON estructurado listo para importar a PostgreSQL
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from docx import Document

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).parent.parent


@dataclass
class Division:
    """Representa una división estructural: Título, Capítulo, Sección"""
    tipo: str  # 'libro', 'titulo', 'capitulo', 'seccion'
    numero: str  # 'PRIMERO', 'I', 'UNICA'
    numero_orden: int  # 1, 2, 3 para ordenar
    nombre: str  # Descripción
    orden_global: int  # Posición en el documento
    hijos: list = field(default_factory=list)


@dataclass
class Articulo:
    """Representa un artículo de la ley"""
    numero_raw: str  # "1o", "2-Bis", "84-E"
    numero_base: int  # 1, 2, 84
    sufijo: Optional[str]  # None, "Bis", "E"
    ordinal: Optional[str]  # "o", "a"
    contenido: str
    es_transitorio: bool = False
    decreto_dof: Optional[str] = None
    reformas: Optional[str] = None
    orden_global: int = 0
    division_path: str = ""  # "TITULO I > CAPITULO II"


# Patrones regex mejorados
# Solo aceptan números válidos: romanos (I, II, III...) u ordinales (Primero, Segundo...)
# Esto evita falsos positivos como "título profesional"
_ORDINALES = r'(?:PRIMER[OA]?|SEGUND[OA]|TERCER[OA]?|CUART[OA]|QUINT[OA]|SEXT[OA]|S[ÉE]PTIM[OA]|OCTAV[OA]|NOVEN[OA]|D[ÉE]CIM[OA]|[ÚU]NIC[OA])'
_ROMANOS = r'(?:[IVX]+|[LC]+)'  # Romanos simples (no incluir C/L solos para evitar conflictos)
_NUMERO_VALIDO = rf'(?:{_ORDINALES}|{_ROMANOS})\b'  # \b asegura fin de palabra

PATRON_TITULO = re.compile(
    rf'^T[ÍI]TULO\s+({_ORDINALES}|{_ROMANOS})(?:\s*[-–]?\s*)(.*)$',
    re.IGNORECASE
)
PATRON_CAPITULO = re.compile(
    rf'^CAP[ÍI]TULO\s+({_ORDINALES}|{_ROMANOS})(?:\s*[-–]?\s*)(.*)$',
    re.IGNORECASE
)
PATRON_SECCION = re.compile(
    rf'^SECCI[ÓO]N\s+({_ORDINALES}|{_ROMANOS})(?:\s*[-–]?\s*)(.*)$',
    re.IGNORECASE
)

# Patrón de artículo mejorado - captura todos los sufijos posibles
# Ejemplos: "Artículo 1o.-", "Artículo 84-E.", "Artículo 32-B Bis.", "Artículo 4o.-A.-"
# IMPORTANTE: Solo mayúscula "Artículo" (no "artículo") para evitar capturar referencias
PATRON_ARTICULO = re.compile(
    r'^Art[íi]culo\s+'                          # DEBE empezar con A mayúscula
    r'(\d+)'                                    # Grupo 1: Número base: 84
    r'([oa])?'                                  # Grupo 2: Ordinal opcional: o, a
    r'[.\s]*[-–]?[.\s]*'                        # Separador inicial: .- o . o -
    r'(?:'                                      # Grupo para sufijos (letra y/o latino)
        r'([A-Z])'                              # Grupo 3: Letra sufijo: A, B, E
        r'(?:'
            r'(?=[.\-–])'                       # Seguida de puntuación (32-B.)
            r'|'
            r'(?=\s+(?:Bis|Ter|Qu[áa]ter|Quinquies|Sexies))' # O seguida de espacio+sufijo latino (32-B Bis)
        r')'
    r')?'
    r'[.\s]*[-–]?[.\s]*'                        # Separador post-letra
    r'(Bis|Ter|Qu[áa]ter|Quinquies|Sexies)?'    # Grupo 4: Sufijo latino
    r'[.\s\-–]*'                                # Puntuación final
    r'(.*)'                                     # Grupo 5: Resto del texto
    # NO usar IGNORECASE - queremos distinguir Artículo de artículo
)

PATRON_TRANSITORIOS = re.compile(r'^TRANSITORIOS?\s*$', re.IGNORECASE)

PATRON_PAGINA = re.compile(r'^\d+\s+de\s+\d+$')

PATRON_REFERENCIA_DOF = re.compile(
    r'(?:Art[íi]culo|P[áa]rrafo|Fracci[óo]n|Inciso).*'
    r'(?:reformad[oa]|adicionad[oa]|derogad[oa]).*DOF',
    re.IGNORECASE
)


def numero_romano_a_int(romano: str) -> int:
    """Convierte número romano a entero"""
    valores = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    romano = romano.upper().strip()

    # Si es palabra (PRIMERO, SEGUNDO, etc.)
    palabras = {
        'PRIMERO': 1, 'PRIMER': 1, 'PRIMERA': 1,
        'SEGUNDO': 2, 'SEGUNDA': 2,
        'TERCERO': 3, 'TERCERA': 3, 'TERCER': 3,
        'CUARTO': 4, 'CUARTA': 4,
        'QUINTO': 5, 'QUINTA': 5,
        'SEXTO': 6, 'SEXTA': 6,
        'SEPTIMO': 7, 'SÉPTIMO': 7, 'SEPTIMA': 7, 'SÉPTIMA': 7,
        'OCTAVO': 8, 'OCTAVA': 8,
        'NOVENO': 9, 'NOVENA': 9,
        'DECIMO': 10, 'DÉCIMO': 10, 'DECIMA': 10, 'DÉCIMA': 10,
        'UNICO': 1, 'ÚNICO': 1, 'UNICA': 1, 'ÚNICA': 1,
    }
    if romano in palabras:
        return palabras[romano]

    # Intentar como número romano
    try:
        total = 0
        prev = 0
        for char in reversed(romano):
            if char not in valores:
                return 0
            curr = valores[char]
            if curr < prev:
                total -= curr
            else:
                total += curr
            prev = curr
        return total
    except:
        return 0


def sufijo_a_orden(sufijo: Optional[str]) -> int:
    """Convierte sufijo a número para ordenamiento"""
    if not sufijo:
        return 0
    sufijo = sufijo.upper()
    sufijos_orden = {
        'BIS': 1, 'TER': 2, 'QUATER': 3, 'QUÁTER': 3,
        'QUINQUIES': 4, 'SEXIES': 5,
    }
    if sufijo in sufijos_orden:
        return sufijos_orden[sufijo]
    # Letras: A=1, B=2, etc.
    if len(sufijo) == 1 and sufijo.isalpha():
        return ord(sufijo) - ord('A') + 1
    return 0


def consolidar_parrafos(partes: list[str]) -> str:
    """
    Une fragmentos que son continuación del mismo párrafo.

    En los DOCX, cada línea visual puede ser un "párrafo" separado,
    aunque lógicamente sean continuación de la misma oración.

    Reglas:
    - Si una línea NO termina en puntuación final, es continuación
    - Unir con espacio en lugar de \\n
    - Usar \\n\\n para separar párrafos reales
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
            # Fin de oración/párrafo, guardar y empezar nuevo
            resultado.append(buffer)
            buffer = parte
        else:
            # Continuación del mismo párrafo, unir con espacio
            buffer = buffer + ' ' + parte

    if buffer:
        resultado.append(buffer)

    return '\n\n'.join(resultado)


def extraer_texto_docx(doc_path: Path) -> list[str]:
    """Extrae párrafos del DOCX, limpiando páginas y espacios.

    Nota: Algunos PDFs convertidos tienen newlines internos en párrafos
    (ej: "Capítulo I \nDe los Derechos Humanos"). Los dividimos para
    que el parser pueda detectar correctamente títulos, capítulos, etc.
    """
    doc = Document(doc_path)
    paragraphs = []

    # Patrón para detectar artículos fusionados con notas de reforma
    # Ej: "Artículo reformado DOF... Artículo 105. La Suprema Corte..."
    patron_articulo_fusionado = re.compile(
        r'(.*?(?:DOF|reformad[oa]|adicionad[oa]|derogad[oa]).*?)\s+'
        r'(Art[íi]culo\s+\d+[oºa]?\.?\s+\S)',
        re.IGNORECASE
    )

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        # Ignorar números de página
        if PATRON_PAGINA.match(text):
            continue

        # Dividir párrafos con newlines internos
        # Esto es común en PDFs convertidos (CPEUM, etc.)
        subparas = text.split('\n') if '\n' in text else [text]

        for subpara in subparas:
            subpara = subpara.strip()
            if not subpara or PATRON_PAGINA.match(subpara):
                continue

            # Detectar y separar artículos fusionados con notas DOF
            # Ej: "Artículo reformado DOF... Artículo 105. La Suprema Corte..."
            match = patron_articulo_fusionado.match(subpara)
            if match:
                # Separar: nota de reforma + nuevo artículo
                nota = match.group(1).strip()
                resto = subpara[match.start(2):].strip()
                if nota:
                    paragraphs.append(nota)
                if resto:
                    paragraphs.append(resto)
            else:
                paragraphs.append(subpara)

    return paragraphs


def parsear_ley(paragraphs: list[str], nombre_ley: str) -> dict:
    """
    Parsea los párrafos en estructura jerárquica

    Retorna:
    {
        "ley": nombre_ley,
        "divisiones": [...],
        "articulos": [...]
    }
    """
    divisiones = []
    articulos = []

    # Estado actual de la jerarquía
    titulo_actual = None
    capitulo_actual = None
    seccion_actual = None
    en_transitorios = False
    decreto_actual = None

    orden_division = 0
    orden_articulo = 0

    i = 0
    while i < len(paragraphs):
        text = paragraphs[i]

        # === TRANSITORIOS ===
        if PATRON_TRANSITORIOS.match(text):
            en_transitorios = True
            # Intentar capturar el decreto si está en la siguiente línea
            if i + 1 < len(paragraphs):
                next_line = paragraphs[i + 1]
                if 'DOF' in next_line or 'Decreto' in next_line.lower():
                    decreto_actual = next_line.strip()
            i += 1
            continue

        # === TÍTULO ===
        match = PATRON_TITULO.match(text)
        if match and not en_transitorios:
            numero = match.group(1)
            nombre = match.group(2) or ""

            # Si el nombre está en la siguiente línea
            if not nombre and i + 1 < len(paragraphs):
                next_text = paragraphs[i + 1]
                if not any(p.match(next_text) for p in [PATRON_TITULO, PATRON_CAPITULO, PATRON_SECCION, PATRON_ARTICULO]):
                    nombre = next_text
                    i += 1

            orden_division += 1
            titulo_actual = {
                "tipo": "titulo",
                "numero": numero,
                "numero_orden": numero_romano_a_int(numero),
                "nombre": nombre.strip(),
                "orden_global": orden_division,
                "path_texto": f"TITULO {numero}"
            }
            divisiones.append(titulo_actual)
            capitulo_actual = None
            seccion_actual = None
            i += 1
            continue

        # === CAPÍTULO ===
        match = PATRON_CAPITULO.match(text)
        if match and not en_transitorios:
            numero = match.group(1)
            nombre = match.group(2) or ""

            if not nombre and i + 1 < len(paragraphs):
                next_text = paragraphs[i + 1]
                if not any(p.match(next_text) for p in [PATRON_TITULO, PATRON_CAPITULO, PATRON_SECCION, PATRON_ARTICULO]):
                    nombre = next_text
                    i += 1

            orden_division += 1
            path = titulo_actual["path_texto"] if titulo_actual else ""
            capitulo_actual = {
                "tipo": "capitulo",
                "numero": numero,
                "numero_orden": numero_romano_a_int(numero),
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

        # === SECCIÓN ===
        match = PATRON_SECCION.match(text)
        if match and not en_transitorios:
            numero = match.group(1)
            nombre = match.group(2) or ""

            if not nombre and i + 1 < len(paragraphs):
                next_text = paragraphs[i + 1]
                if not any(p.match(next_text) for p in [PATRON_TITULO, PATRON_CAPITULO, PATRON_SECCION, PATRON_ARTICULO]):
                    nombre = next_text
                    i += 1

            orden_division += 1
            path = capitulo_actual["path_texto"] if capitulo_actual else (
                titulo_actual["path_texto"] if titulo_actual else ""
            )
            seccion_actual = {
                "tipo": "seccion",
                "numero": numero,
                "numero_orden": numero_romano_a_int(numero),
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

        # === ARTÍCULO ===
        match = PATRON_ARTICULO.match(text)
        if match:
            numero_base = int(match.group(1))
            ordinal = match.group(2)           # "o" o "a"
            letra_sufijo = match.group(3)      # "A", "B", "E"
            sufijo_latino = match.group(4)     # "Bis", "Ter", "Quáter"
            contenido_inicial = match.group(5) or ""

            # Construir sufijo combinado: "B", "B BIS", "BIS"
            sufijo_partes = []
            if letra_sufijo:
                sufijo_partes.append(letra_sufijo.upper())
            if sufijo_latino:
                sufijo_partes.append(sufijo_latino.upper())
            sufijo = " ".join(sufijo_partes) if sufijo_partes else None

            # Construir numero_raw
            numero_raw = str(numero_base)
            if ordinal:
                numero_raw += ordinal
            if sufijo:
                numero_raw += f"-{sufijo}"

            # Recolectar contenido del artículo
            contenido_partes = [contenido_inicial] if contenido_inicial else []
            reformas = []

            i += 1
            while i < len(paragraphs):
                next_text = paragraphs[i]

                # ¿Termina el artículo?
                if PATRON_ARTICULO.match(next_text):
                    break
                if PATRON_TITULO.match(next_text):
                    break
                if PATRON_CAPITULO.match(next_text):
                    break
                if PATRON_SECCION.match(next_text):
                    break
                if PATRON_TRANSITORIOS.match(next_text):
                    break

                # Detectar referencias DOF
                if PATRON_REFERENCIA_DOF.match(next_text):
                    reformas.append(next_text)
                else:
                    contenido_partes.append(next_text)

                i += 1

            # Determinar división actual
            division_actual = seccion_actual or capitulo_actual or titulo_actual
            division_path = division_actual["path_texto"] if division_actual else ""

            orden_articulo += 1
            articulo = {
                "numero_raw": numero_raw,
                "numero_base": numero_base,
                "sufijo": sufijo.upper() if sufijo else None,
                "ordinal": ordinal.lower() if ordinal else None,
                "contenido": consolidar_parrafos(contenido_partes),
                "es_transitorio": en_transitorios,
                "decreto_dof": decreto_actual if en_transitorios else None,
                "reformas": " | ".join(reformas) if reformas else None,
                "orden_global": orden_articulo,
                "division_path": division_path,
                "division_tipo": division_actual["tipo"] if division_actual else None,
                "division_numero": division_actual["numero"] if division_actual else None,
            }
            articulos.append(articulo)
            continue

        i += 1

    return {
        "ley": nombre_ley,
        "total_divisiones": len(divisiones),
        "total_articulos": len(articulos),
        "divisiones": divisiones,
        "articulos": articulos
    }


def procesar_documento(docx_path: Path, nombre_ley: str, output_path: Path):
    """Procesa un documento DOCX y genera JSON estructurado"""
    print(f"   Leyendo DOCX...")
    paragraphs = extraer_texto_docx(docx_path)
    print(f"   {len(paragraphs)} párrafos")

    print(f"   Parseando estructura...")
    resultado = parsear_ley(paragraphs, nombre_ley)
    print(f"   {resultado['total_divisiones']} divisiones, {resultado['total_articulos']} artículos")

    print(f"   Guardando JSON...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    return resultado


def main():
    """Procesa todas las leyes disponibles"""
    from convertir_ley import DOCUMENTOS

    print("=" * 60)
    print("Parser de Leyes v2 - Estructura Jerárquica")
    print("=" * 60)

    for carpeta, nombre in DOCUMENTOS.items():
        print(f"\n📂 {nombre}")

        # Buscar DOCX
        docx_files = list(carpeta.glob("*.docx"))
        if not docx_files:
            print(f"   ⚠ No se encontró DOCX")
            continue

        docx_path = docx_files[0]
        json_path = docx_path.with_suffix('.v2.json')

        try:
            resultado = procesar_documento(docx_path, nombre, json_path)
            print(f"   ✓ Guardado: {json_path.name}")

            # Mostrar estadísticas
            transitorios = sum(1 for a in resultado['articulos'] if a['es_transitorio'])
            print(f"   📊 {resultado['total_articulos']} artículos ({transitorios} transitorios)")

        except Exception as e:
            print(f"   ✗ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
