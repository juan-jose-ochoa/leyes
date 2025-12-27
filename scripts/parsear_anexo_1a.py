#!/usr/bin/env python3
"""
Parser para Anexo 1-A de la RMF - Fichas de Trámite

Estructura detectada:
- Patrón: {numero}/{ley} {título}
- Ejemplos: 1/CFF, 7/CFF, 5/ISR
- Contiene secciones como ¿Quién puede solicitar?, ¿Qué requisitos?, etc.
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import fitz  # PyMuPDF


@dataclass
class FichaTramite:
    """Representa una ficha de trámite del Anexo 1-A."""
    numero_raw: str          # "1/CFF"
    numero: int              # 1
    ley_referencia: str      # "CFF"
    titulo: str              # "Obtén tu opinión del cumplimiento..."
    contenido: str           # Texto completo de la ficha
    descripcion: Optional[str] = None
    quien_presenta: Optional[str] = None
    cuando_presenta: Optional[str] = None
    donde_presenta: Optional[str] = None
    requisitos: Optional[str] = None
    condiciones: Optional[str] = None
    fundamento_juridico: Optional[str] = None
    pagina_inicio: int = 0


# Patrón para detectar inicio de ficha
# Formato: "1/CFF Título de la ficha" o "123/ISR Título"
PATRON_FICHA = re.compile(
    r'^(\d+)/([A-Z]+)\s+(.+?)(?:\s*Trámite|\s*Servicio|\s*$)',
    re.MULTILINE
)

# Patrón más flexible para capturar fichas
PATRON_FICHA_INICIO = re.compile(
    r'(?:^|\n)(\d+)/([A-Z]+)\s+([^\n]+)',
    re.MULTILINE
)

# Patrones para secciones
SECCIONES = {
    'descripcion': r'Descripción del trámite o servicio\s*(?:Monto)?\s*(.+?)(?=¿Quién|¿Cuándo|$)',
    'quien_presenta': r'¿Quién puede solicitar[^\?]*\?\s*(.+?)(?=¿Cuándo|¿Dónde|$)',
    'cuando_presenta': r'¿Cuándo se presenta\?\s*(.+?)(?=¿Dónde|¿Qué tengo|$)',
    'donde_presenta': r'¿Dónde puedo presentarlo\?\s*(.+?)(?=INFORMACIÓN|¿Qué tengo|$)',
    'requisitos': r'¿Qué requisitos debo cumplir\?\s*(.+?)(?=¿Con qué condiciones|SEGUIMIENTO|$)',
    'condiciones': r'¿Con qué condiciones debo cumplir\?\s*(.+?)(?=SEGUIMIENTO|CANALES|$)',
    'fundamento_juridico': r'Fundamento jurídico\s*(.+?)(?=Ficha de trámite|\d+/[A-Z]+|$)',
}


def extraer_texto_pdf(pdf_path: Path) -> tuple[str, dict[int, int]]:
    """
    Extrae todo el texto del PDF y mapea posiciones a páginas.

    Returns:
        tuple: (texto_completo, mapa_posicion_pagina)
    """
    doc = fitz.open(pdf_path)
    texto_completo = ""
    mapa_paginas = {}  # posición -> número de página

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


def extraer_seccion(texto: str, patron: str) -> Optional[str]:
    """Extrae una sección del texto usando el patrón dado."""
    match = re.search(patron, texto, re.DOTALL | re.IGNORECASE)
    if match:
        contenido = match.group(1).strip()
        # Limpiar espacios múltiples
        contenido = re.sub(r'\s+', ' ', contenido)
        return contenido if contenido else None
    return None


def parsear_fichas(texto: str, mapa_paginas: dict[int, int]) -> list[FichaTramite]:
    """
    Parsea el texto completo y extrae las fichas de trámite.
    """
    fichas = []

    # Encontrar donde termina el índice y empieza el contenido real
    # El contenido real tiene secciones como "Descripción del trámite"
    inicio_contenido = texto.find("Descripción del trámite o servicio")
    if inicio_contenido == -1:
        print("  ERROR: No se encontró el inicio del contenido real")
        return []

    # Retroceder para encontrar el inicio de la primera ficha con contenido
    texto_antes = texto[:inicio_contenido]
    ultimo_patron = None
    for m in PATRON_FICHA_INICIO.finditer(texto_antes):
        ultimo_patron = m

    if ultimo_patron:
        inicio_contenido = ultimo_patron.start()

    texto = texto[inicio_contenido:]
    print(f"  Índice saltado, contenido inicia en posición: {inicio_contenido:,}")

    # Encontrar todas las fichas
    matches = list(PATRON_FICHA_INICIO.finditer(texto))

    print(f"  Fichas encontradas: {len(matches)}")

    for i, match in enumerate(matches):
        numero = int(match.group(1))
        ley = match.group(2)
        titulo = match.group(3).strip()
        numero_raw = f"{numero}/{ley}"

        # Determinar límites del contenido de esta ficha
        inicio = match.start()
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(texto)

        contenido_ficha = texto[inicio:fin].strip()

        # Limpiar título (remover Trámite/Servicio si está pegado)
        titulo = re.sub(r'\s*(Trámite|Servicio)\s*$', '', titulo).strip()

        # Ignorar fichas derogadas
        if '(Se deroga)' in titulo or '(Se deroga)' in contenido_ficha[:200]:
            continue

        # Extraer secciones
        ficha = FichaTramite(
            numero_raw=numero_raw,
            numero=numero,
            ley_referencia=ley,
            titulo=titulo,
            contenido=contenido_ficha,
            descripcion=extraer_seccion(contenido_ficha, SECCIONES['descripcion']),
            quien_presenta=extraer_seccion(contenido_ficha, SECCIONES['quien_presenta']),
            cuando_presenta=extraer_seccion(contenido_ficha, SECCIONES['cuando_presenta']),
            donde_presenta=extraer_seccion(contenido_ficha, SECCIONES['donde_presenta']),
            requisitos=extraer_seccion(contenido_ficha, SECCIONES['requisitos']),
            condiciones=extraer_seccion(contenido_ficha, SECCIONES['condiciones']),
            fundamento_juridico=extraer_seccion(contenido_ficha, SECCIONES['fundamento_juridico']),
            pagina_inicio=obtener_pagina(inicio, mapa_paginas)
        )

        fichas.append(ficha)

    return fichas


def agrupar_por_ley(fichas: list[FichaTramite]) -> dict[str, list[FichaTramite]]:
    """Agrupa las fichas por ley de referencia."""
    grupos = {}
    for ficha in fichas:
        if ficha.ley_referencia not in grupos:
            grupos[ficha.ley_referencia] = []
        grupos[ficha.ley_referencia].append(ficha)
    return grupos


def main():
    print("=" * 60)
    print("PARSER ANEXO 1-A - FICHAS DE TRÁMITE")
    print("=" * 60)

    # Buscar el PDF del Anexo 1-A
    base_dir = Path(__file__).parent.parent / "doc" / "rmf" / "anexos"
    pdf_files = list(base_dir.glob("*Anexo_1-A*.pdf")) + list(base_dir.glob("*Anexo_1_A*.pdf"))

    if not pdf_files:
        print("ERROR: No se encontró el PDF del Anexo 1-A")
        return 1

    pdf_path = pdf_files[0]
    print(f"\nProcesando: {pdf_path.name}")

    # Extraer texto
    print("\n1. Extrayendo texto del PDF...")
    texto, mapa_paginas = extraer_texto_pdf(pdf_path)
    print(f"   Caracteres extraídos: {len(texto):,}")

    # Parsear fichas
    print("\n2. Parseando fichas de trámite...")
    fichas = parsear_fichas(texto, mapa_paginas)
    print(f"   Fichas parseadas: {len(fichas)}")

    # Agrupar por ley
    grupos = agrupar_por_ley(fichas)
    print("\n3. Fichas por ley:")
    for ley, lista in sorted(grupos.items()):
        print(f"   {ley}: {len(lista)} fichas")

    # Guardar resultado
    output_path = base_dir.parent / "anexo_1a_fichas.json"

    resultado = {
        "anexo": "1-A",
        "titulo": "Trámites Fiscales",
        "total_fichas": len(fichas),
        "fichas_por_ley": {ley: len(lista) for ley, lista in grupos.items()},
        "fichas": [asdict(f) for f in fichas]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"\n4. Guardado: {output_path}")

    # Mostrar ejemplos
    print("\n" + "=" * 60)
    print("EJEMPLOS DE FICHAS PARSEADAS")
    print("=" * 60)

    for ficha in fichas[:3]:
        print(f"\n{ficha.numero_raw} - {ficha.titulo[:60]}...")
        print(f"  Página: {ficha.pagina_inicio}")
        if ficha.descripcion:
            print(f"  Descripción: {ficha.descripcion[:100]}...")
        if ficha.fundamento_juridico:
            print(f"  Fundamento: {ficha.fundamento_juridico[:80]}...")

    return 0


if __name__ == "__main__":
    exit(main())
