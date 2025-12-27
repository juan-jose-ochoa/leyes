#!/usr/bin/env python3
"""
Parser para Anexo 3 de la RMF - Criterios No Vinculativos

Estructura detectada:
- Patrón: {numero}/{ley}/NV {título}
- Ejemplos: 1/CFF/NV, 3/ISR/NV
- Contiene texto completo del criterio y sección "Origen"
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import fitz  # PyMuPDF


@dataclass
class CriterioNV:
    """Representa un criterio no vinculativo del Anexo 3."""
    numero_raw: str          # "1/CFF/NV"
    numero: int              # 1
    ley_referencia: str      # "CFF"
    titulo: str              # "Entrega o puesta a disposición..."
    contenido: str           # Texto completo del criterio
    origen: Optional[str] = None
    practicas_indebidas: Optional[str] = None
    pagina_inicio: int = 0


# Patrón para detectar inicio de criterio
# Formato: "1/CFF/NV Título del criterio"
PATRON_CRITERIO = re.compile(
    r'(?:^|\n)(\d+)/([A-Z]+)/NV\s+([^\n]+)',
    re.MULTILINE
)


def extraer_texto_pdf(pdf_path: Path) -> tuple[str, dict[int, int]]:
    """
    Extrae todo el texto del PDF y mapea posiciones a páginas.
    """
    doc = fitz.open(pdf_path)
    texto_completo = ""
    mapa_paginas = {}

    for num_pagina, pagina in enumerate(doc):
        pos_inicio = len(texto_completo)
        texto_pagina = pagina.get_text()

        # Remover header repetido del SAT
        texto_pagina = re.sub(
            r'NOTA: Este documento constituye una compilación.*?Federación\.',
            '',
            texto_pagina,
            flags=re.DOTALL
        )
        # Remover paginación
        texto_pagina = re.sub(r'Página \d+ de \d+', '', texto_pagina)

        texto_completo += texto_pagina + "\n"
        mapa_paginas[pos_inicio] = num_pagina + 1

    doc.close()
    return texto_completo, mapa_paginas


def obtener_pagina(posicion: int, mapa_paginas: dict[int, int]) -> int:
    """Obtiene el número de página para una posición en el texto."""
    pagina = 1
    for pos, num in sorted(mapa_paginas.items()):
        if pos <= posicion:
            pagina = num
        else:
            break
    return pagina


def extraer_origen(texto: str) -> Optional[str]:
    """Extrae la sección de Origen del criterio."""
    match = re.search(r'Origen\s*(.+?)(?=\d+/[A-Z]+/NV|$)', texto, re.DOTALL)
    if match:
        origen = match.group(1).strip()
        # Limpiar espacios múltiples
        origen = re.sub(r'\s+', ' ', origen)
        return origen if len(origen) > 10 else None
    return None


def extraer_practicas(texto: str) -> Optional[str]:
    """Extrae la lista de prácticas fiscales indebidas."""
    match = re.search(
        r'se considera[n]? que realizan? una práctica fiscal indebida[:\s]*(.+?)(?=Origen|$)',
        texto,
        re.DOTALL | re.IGNORECASE
    )
    if match:
        practicas = match.group(1).strip()
        return practicas if len(practicas) > 10 else None
    return None


def parsear_criterios(texto: str, mapa_paginas: dict[int, int]) -> list[CriterioNV]:
    """
    Parsea el texto completo y extrae los criterios no vinculativos.
    """
    criterios = []

    # Encontrar donde termina el índice y empieza el contenido real
    # Buscar "Criterios del CFF" o similar que marca el inicio
    inicio_contenido = texto.find("I. \nCriterios del CFF")
    if inicio_contenido == -1:
        inicio_contenido = texto.find("Criterios del CFF")
    if inicio_contenido == -1:
        # Buscar el primer criterio con contenido extenso
        match = re.search(r'\d+/[A-Z]+/NV\s+.{50,}', texto)
        if match:
            inicio_contenido = match.start()
        else:
            print("  ERROR: No se encontró el inicio del contenido real")
            return []

    texto = texto[inicio_contenido:]
    print(f"  Índice saltado, contenido inicia en posición: {inicio_contenido:,}")

    # Encontrar todos los criterios
    matches = list(PATRON_CRITERIO.finditer(texto))
    print(f"  Criterios encontrados: {len(matches)}")

    for i, match in enumerate(matches):
        numero = int(match.group(1))
        ley = match.group(2)
        titulo = match.group(3).strip()
        numero_raw = f"{numero}/{ley}/NV"

        # Determinar límites del contenido
        inicio = match.start()
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(texto)

        contenido_criterio = texto[inicio:fin].strip()

        # Limpiar título
        titulo = re.sub(r'\s+', ' ', titulo).strip()

        criterio = CriterioNV(
            numero_raw=numero_raw,
            numero=numero,
            ley_referencia=ley,
            titulo=titulo,
            contenido=contenido_criterio,
            origen=extraer_origen(contenido_criterio),
            practicas_indebidas=extraer_practicas(contenido_criterio),
            pagina_inicio=obtener_pagina(inicio + inicio_contenido, mapa_paginas)
        )

        criterios.append(criterio)

    return criterios


def agrupar_por_ley(criterios: list[CriterioNV]) -> dict[str, list[CriterioNV]]:
    """Agrupa los criterios por ley de referencia."""
    grupos = {}
    for criterio in criterios:
        if criterio.ley_referencia not in grupos:
            grupos[criterio.ley_referencia] = []
        grupos[criterio.ley_referencia].append(criterio)
    return grupos


def main():
    print("=" * 60)
    print("PARSER ANEXO 3 - CRITERIOS NO VINCULATIVOS")
    print("=" * 60)

    # Buscar el PDF del Anexo 3
    base_dir = Path(__file__).parent.parent / "doc" / "rmf" / "anexos"
    pdf_files = list(base_dir.glob("*Anexo_3*.pdf")) + list(base_dir.glob("*Anexo3*.pdf"))

    if not pdf_files:
        print("ERROR: No se encontró el PDF del Anexo 3")
        return 1

    pdf_path = pdf_files[0]
    print(f"\nProcesando: {pdf_path.name}")

    # Extraer texto
    print("\n1. Extrayendo texto del PDF...")
    texto, mapa_paginas = extraer_texto_pdf(pdf_path)
    print(f"   Caracteres extraídos: {len(texto):,}")

    # Parsear criterios
    print("\n2. Parseando criterios no vinculativos...")
    criterios = parsear_criterios(texto, mapa_paginas)
    print(f"   Criterios parseados: {len(criterios)}")

    # Agrupar por ley
    grupos = agrupar_por_ley(criterios)
    print("\n3. Criterios por ley:")
    for ley, lista in sorted(grupos.items()):
        print(f"   {ley}: {len(lista)} criterios")

    # Guardar resultado
    output_path = base_dir.parent / "anexo_3_criterios.json"

    resultado = {
        "anexo": "3",
        "titulo": "Criterios No Vinculativos del SAT",
        "total_criterios": len(criterios),
        "criterios_por_ley": {ley: len(lista) for ley, lista in grupos.items()},
        "criterios": [asdict(c) for c in criterios]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"\n4. Guardado: {output_path}")

    # Mostrar ejemplos
    print("\n" + "=" * 60)
    print("EJEMPLOS DE CRITERIOS PARSEADOS")
    print("=" * 60)

    for criterio in criterios[:3]:
        print(f"\n{criterio.numero_raw} - {criterio.titulo[:60]}...")
        print(f"  Página: {criterio.pagina_inicio}")
        print(f"  Contenido: {len(criterio.contenido):,} chars")
        if criterio.origen:
            print(f"  Origen: {criterio.origen[:100]}...")

    return 0


if __name__ == "__main__":
    exit(main())
