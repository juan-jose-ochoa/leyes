#!/usr/bin/env python3
"""
Genera JSON optimizado para Astro SSG.

Lee los datos de ETL (contenido.json, mapa_estructura.json) y genera:
- frontend-astro/src/data/catalogo.json - Lista de leyes con metadatos
- frontend-astro/src/data/{ley}/articulos.json - Artículos por ley
- frontend-astro/src/data/{ley}/estructura.json - Divisiones por ley

Uso:
    python backend/scripts/generar-datos-astro.py
"""

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Agregar backend/etl al path para importar config
sys.path.insert(0, str(Path(__file__).parent.parent / "etl"))
from config import LEYES

# Rutas
PROJECT_ROOT = Path(__file__).parent.parent.parent
ETL_DATA = PROJECT_ROOT / "backend" / "etl" / "data"
ASTRO_DATA = PROJECT_ROOT / "frontend-astro" / "src" / "data"

# =============================================================================
# SISTEMA DE REFERENCIAS DINÁMICAS
# =============================================================================

# Mapeo de nombres de ley en texto a códigos
NOMBRE_A_CODIGO = {
    # Referencias internas
    'esta ley': '_MISMA_',
    'la presente ley': '_MISMA_',
    'la misma': '_MISMA_',
    'este código': '_MISMA_',
    'el presente código': '_MISMA_',
    'este ordenamiento': '_MISMA_',
    'el presente ordenamiento': '_MISMA_',
    'esta constitución': 'CPEUM',
    'la constitución': 'CPEUM',
    'constitución política': 'CPEUM',
    # Códigos y leyes específicas (soportadas - generan links)
    'código fiscal de la federación': 'CFF',
    'código fiscal': 'CFF',
    'cff': 'CFF',
    'ley del impuesto sobre la renta': 'LISR',
    'ley del isr': 'LISR',
    'lisr': 'LISR',
    'ley del impuesto al valor agregado': 'LIVA',
    'ley del iva': 'LIVA',
    'liva': 'LIVA',
    'ley aduanera': 'LA',
    'ley del impuesto especial sobre producción y servicios': 'LIEPS',
    'ley del ieps': 'LIEPS',
    'lieps': 'LIEPS',
    'ley federal del trabajo': 'LFT',
    'ley del seguro social': 'LSS',
    'ley del instituto del fondo nacional de la vivienda': 'LINFONAVIT',
    'ley del infonavit': 'LINFONAVIT',
    'ley del issste': 'LISSSTE',
    'ley de ingresos de la federación': 'LIF',
    'ley de ingresos': 'LIF',
    'ley federal de derechos del contribuyente': 'LFDC',
    # Reglamentos soportados
    'reglamento del código fiscal de la federación': 'RCFF',
    'reglamento del cff': 'RCFF',
    'reglamento de la ley del impuesto sobre la renta': 'RLISR',
    'reglamento de la ley del isr': 'RLISR',
    'reglamento de la lisr': 'RLISR',
    'reglamento de la ley del impuesto al valor agregado': 'RLIVA',
    'reglamento de la ley del iva': 'RLIVA',
    'reglamento de la liva': 'RLIVA',
    'reglamento de la ley del impuesto especial sobre producción y servicios': 'RLIEPS',
    'reglamento de la ley del ieps': 'RLIEPS',
    'reglamento de la ley federal del trabajo': 'RLFT',
    'reglamento de la ley del seguro social': 'RLSS',
    # Leyes reconocidas pero no soportadas (no generan links, pero delimitan referencias)
    'ley de ingresos sobre hidrocarburos': None,
    'ley de hidrocarburos': None,
    'ley del mercado de valores': None,
    'ley de los sistemas de ahorro para el retiro': None,
    'ley federal de presupuesto y responsabilidad hacendaria': None,
    'ley federal de derechos': None,
    'ley general de sociedades mercantiles': None,
    'ley general de títulos y operaciones de crédito': None,
    'ley federal del impuesto sobre automóviles nuevos': None,
    'ley del isan': None,
    'ley general de educación': None,
    'ley de tesorería de la federación': None,
    'ley de navegación y comercio marítimos': None,
    'ley del servicio de administración tributaria': None,
    'ley sobre el contrato de seguro': None,
    'ley de los impuestos generales de importación y de exportación': None,
    'código civil federal': None,
    'código de comercio': None,
}

# Alternativas de ley para usar en ambos patrones
_LEY_ALTERNATIVAS = (
    # Referencias internas
    r'esta\s+ley|la\s+presente\s+ley|la\s+misma|'
    r'este\s+código|el\s+presente\s+código|'
    r'este\s+ordenamiento|el\s+presente\s+ordenamiento|'
    r'esta\s+constitución|la\s+constitución|'
    # Leyes soportadas
    r'código\s+fiscal(?:\s+de\s+la\s+federación)?|cff|'
    r'ley\s+del\s+impuesto\s+sobre\s+la\s+renta|ley\s+del\s+isr|lisr|'
    r'ley\s+del\s+impuesto\s+al\s+valor\s+agregado|ley\s+del\s+iva|liva|'
    r'ley\s+aduanera|'
    r'ley\s+del\s+impuesto\s+especial\s+sobre\s+producción\s+y\s+servicios|ley\s+del\s+ieps|lieps|'
    r'ley\s+federal\s+del\s+trabajo|'
    r'ley\s+del\s+seguro\s+social|'
    r'ley\s+del\s+infonavit|'
    r'ley\s+del\s+issste|'
    # Reglamentos soportados
    r'reglamento\s+del\s+c[oó]digo\s+fiscal(?:\s+de\s+la\s+federaci[oó]n)?|reglamento\s+del\s+cff|'
    r'reglamento\s+de\s+la\s+ley\s+del\s+impuesto\s+sobre\s+la\s+renta|reglamento\s+de\s+la\s+ley\s+del\s+isr|reglamento\s+de\s+la\s+lisr|'
    r'reglamento\s+de\s+la\s+ley\s+del\s+impuesto\s+al\s+valor\s+agregado|reglamento\s+de\s+la\s+ley\s+del\s+iva|reglamento\s+de\s+la\s+liva|'
    r'reglamento\s+de\s+la\s+ley\s+del\s+impuesto\s+especial\s+sobre\s+producci[oó]n\s+y\s+servicios|reglamento\s+de\s+la\s+ley\s+del\s+ieps|'
    r'reglamento\s+de\s+la\s+ley\s+federal\s+del\s+trabajo|'
    r'reglamento\s+de\s+la\s+ley\s+del\s+seguro\s+social|'
    # IMPORTANTE: patrones más específicos primero (ley de ingresos sobre hidrocarburos antes de ley de ingresos)
    r'ley\s+de\s+ingresos\s+sobre\s+hidrocarburos|'  # No soportada, pero delimita referencias
    r'ley\s+de\s+ingresos(?:\s+de\s+la\s+federación)?|'
    r'ley\s+federal\s+de\s+derechos\s+del\s+contribuyente|'
    # Leyes reconocidas pero no soportadas (delimitan referencias sin generar links)
    r'ley\s+de\s+hidrocarburos|'
    r'ley\s+del\s+mercado\s+de\s+valores|'
    r'ley\s+de\s+los\s+sistemas\s+de\s+ahorro\s+para\s+el\s+retiro|'
    r'ley\s+federal\s+de\s+presupuesto\s+y\s+responsabilidad\s+hacendaria|'
    r'ley\s+federal\s+de\s+derechos|'
    r'ley\s+general\s+de\s+sociedades\s+mercantiles|'
    r'ley\s+general\s+de\s+títulos\s+y\s+operaciones\s+de\s+crédito|'
    r'ley\s+federal\s+del\s+impuesto\s+sobre\s+automóviles\s+nuevos|'
    r'ley\s+del\s+isan|'
    r'ley\s+general\s+de\s+educación|'
    r'ley\s+de\s+tesorería\s+de\s+la\s+federación|'
    r'ley\s+de\s+navegación\s+y\s+comercio\s+marítimos|'
    r'ley\s+del\s+servicio\s+de\s+administración\s+tributaria|'
    r'ley\s+sobre\s+el\s+contrato\s+de\s+seguro|'
    r'ley\s+de\s+los\s+impuestos\s+generales\s+de\s+importación\s+y\s+de\s+exportación|'
    r'código\s+civil\s+federal|'
    r'código\s+de\s+comercio'
)

# Ordinales para referencias a párrafos
_ORDINALES_PARRAFO = (
    r'primer|segundo|tercer|cuarto|quinto|sexto|séptimo|octavo|noveno|décimo|'
    r'antepenúltimo|penúltimo|último'
)

# Regex para detectar referencias a artículos (patrón estándar)
# Captura: artículo(s) NUM (fracción ROMAN)? (inciso LETRA)? (párrafo)? de LEY
PATRON_REFERENCIA = re.compile(
    r'artículos?\s+'
    r'(\d+[o]?\.?(?:-[A-Z]+)?)'                         # Número de artículo (grupo 1) - incluye 4o.
    r'(?:\s*,?\s*(?:fracci[oó]ne?s?)\s+([IVXLCDM]+))?'  # Fracción opcional (grupo 2)
    r'(?:\s*,?\s*(?:inciso)\s+([a-z])\))?'            # Inciso opcional (grupo 3)
    r'(?:\s*,?\s*(?:' + _ORDINALES_PARRAFO + r')'     # Párrafo opcional (primer, último, etc.)
    r'(?:\s+(?:y|e)\s+(?:' + _ORDINALES_PARRAFO + r'))?'  # Segundo ordinal opcional (penúltimo y último)
    r'\s+párrafos?)?'                                  # "párrafo" o "párrafos"
    r'\s+(?:de\s+la\s+|de\s+|del\s+)'                 # "de la", "de" o "del" antes de ley
    r'(' + _LEY_ALTERNATIVAS + r')',                   # Ley destino (grupo 4)
    re.IGNORECASE
)

# Regex para detectar referencias invertidas
# Captura: (inciso LETRA de la)? fracción ROMAN del artículo NUM (apartado LETRA)? de LEY
PATRON_REFERENCIA_INVERTIDO = re.compile(
    r'(?:inciso\s+([a-z])\)\s+de\s+la\s+)?'           # Inciso opcional (grupo 1)
    r'fracci[oó]ne?s?\s+([IVXLCDM]+)'                 # Fracción (grupo 2)
    r'\s+del\s+'
    r'artículos?\s+'
    r'(\d+[o]?(?:-[A-Z]+)?)'                          # Número de artículo (grupo 3)
    r'(?:,?\s*apartado\s+([A-Z]))?'                   # Apartado opcional (grupo 4)
    r'\s+(?:de\s+|del?\s+)'
    r'(' + _LEY_ALTERNATIVAS + r')',                  # Ley destino (grupo 5)
    re.IGNORECASE
)

# Regex para detectar listas de artículos
# Captura: artículos 94, 97, 116 fracción III, y 122 Apartado A, fracción IV de LEY
# Grupo 1: lista de artículos (todo antes de "de LEY")
# Grupo 2: ley destino
PATRON_LISTA_ARTICULOS = re.compile(
    r'artículos\s+'
    r'(.+?)'                                              # Lista de artículos (grupo 1) - non-greedy
    r'\s+(?:de\s+la\s+|de\s+|del\s+)'                     # "de la", "de" o "del" antes de ley
    r'(' + _LEY_ALTERNATIVAS + r')',                      # Ley destino (grupo 2)
    re.IGNORECASE
)

# Regex para listas de artículos implícitas (después de ";", sin "artículos")
# Ejemplo: "; 5, quinto párrafo, 26, segundo párrafo y 205 de la Ley del ISR"
PATRON_LISTA_ARTICULOS_IMPLICITA = re.compile(
    r';\s*'
    r'(\d+[^;]*?)'                                        # Lista de artículos (grupo 1) - empieza con número
    r'\s+(?:de\s+la\s+|de\s+|del\s+)'                     # "de la", "de" o "del" antes de ley
    r'(' + _LEY_ALTERNATIVAS + r')',                      # Ley destino (grupo 2)
    re.IGNORECASE
)

# Regex para parsear cada elemento de la lista
# Captura: NUM (Apartado LETRA)? (fracción ROMAN)?
_PATRON_ELEMENTO_LISTA = re.compile(
    r'(\d+[o]?(?:-[A-Z]+)?)'                              # Número de artículo (grupo 1)
    r'(?:\s+[Aa]partado\s+([A-Z]))?'                      # Apartado opcional (grupo 2)
    r'(?:,?\s*[Ff]racci[oó]ne?s?\s+([IVXLCDM]+))?',       # Fracción opcional (grupo 3)
    re.IGNORECASE
)

# Términos de referencia contextual (citado, dicho, mismo)
_REFERENCIA_CONTEXTUAL = r'(?:citad[oa]|dich[oa]|mism[oa])'
_TIPO_LEY_CONTEXTUAL = r'(?:Código|Ley|ordenamiento)'

# Regex para detectar referencias contextuales
# Captura: artículo NUM (fracción ROMAN)? del citado/dicho Código/Ley
PATRON_REFERENCIA_CONTEXTUAL = re.compile(
    r'artículos?\s+'
    r'(\d+[o]?(?:-[A-Z]+)?)'                              # Número de artículo (grupo 1)
    r'(?:\s*,?\s*fracci[oó]ne?s?\s+([IVXLCDM]+))?'        # Fracción opcional (grupo 2)
    r'(?:\s*,?\s*inciso\s+([a-z])\))?'                    # Inciso opcional (grupo 3)
    r'\s+(?:del?|de\s+la)\s+'
    r'(' + _REFERENCIA_CONTEXTUAL + r')\s+'              # citado/dicho/mismo (grupo 4)
    r'(' + _TIPO_LEY_CONTEXTUAL + r')',                  # Código/Ley (grupo 5)
    re.IGNORECASE
)

# Regex para detectar artículo con lista de fracciones
# Captura: artículo 140 fracciones I y II de esta Ley
PATRON_REFERENCIA_FRACCIONES_LISTA = re.compile(
    r'artículos?\s+'
    r'(\d+[o]?(?:-[A-Z]+)?)\s+'                          # Número de artículo (grupo 1)
    r'fraccione?s?\s+'
    r'([IVXLCDM]+(?:(?:[,\s]+(?:y|e)\s+|[,\s]+)[IVXLCDM]+)+)'  # Lista de fracciones (grupo 2)
    r'\s+(?:de\s+la\s+|de\s+|del\s+)'                    # "de la", "de" o "del" antes de ley
    r'(' + _LEY_ALTERNATIVAS + r')',                     # Ley destino (grupo 3)
    re.IGNORECASE
)

# Regex para referencias internas al mismo artículo
# Captura: fracción I de este artículo, párrafo segundo de este artículo
PATRON_REFERENCIA_INTERNA = re.compile(
    r'(fracci[oó]ne?s?|párrafos?|incisos?)\s+'
    r'([IVXLCDM]+|[a-z]\)|primero|segundo|tercero|cuarto|quinto|sexto|séptimo|octavo|noveno|décimo|anterior)\s+'
    r'de\s+este\s+artículo',
    re.IGNORECASE
)

# Patrón para referencias a reglas internas (RMF y similares)
# Detecta: "regla 3.1.4.", "reglas 3.1.20., primer párrafo, fracción I", "3.1.4."
# Captura número de regla (grupo 1) y opcionalmente párrafo/fracción
PATRON_REGLA_INTERNA = re.compile(
    r'(?:reglas?\s+)?'                                # "regla(s)" opcional
    r'(\d+\.\d+\.\d+(?:\.\d+)?\.?)'                   # Número de regla (grupo 1)
    r'(?:,?\s*(?:' + _ORDINALES_PARRAFO + r')\s+párrafo)?'  # Párrafo opcional
    r'(?:,?\s*fracci[oó]n\s+[IVXLCDM]+)?',           # Fracción opcional
    re.IGNORECASE
)

# Leyes que usan "reglas" en lugar de "artículos"
LEYES_CON_REGLAS = {'RMF'}

# Patrones para buscar leyes mencionadas previamente en el texto
_PATRONES_CONTEXTO_CODIGO = [
    (re.compile(r'código\s+fiscal(?:\s+de\s+la\s+federación)?', re.IGNORECASE), 'CFF'),
    (re.compile(r'\bCFF\b'), 'CFF'),
]

_PATRONES_CONTEXTO_LEY = [
    (re.compile(r'ley\s+del\s+impuesto\s+sobre\s+la\s+renta', re.IGNORECASE), 'LISR'),
    (re.compile(r'ley\s+del\s+isr', re.IGNORECASE), 'LISR'),
    (re.compile(r'\bLISR\b'), 'LISR'),
    (re.compile(r'ley\s+del\s+impuesto\s+al\s+valor\s+agregado', re.IGNORECASE), 'LIVA'),
    (re.compile(r'ley\s+del\s+iva', re.IGNORECASE), 'LIVA'),
    (re.compile(r'\bLIVA\b'), 'LIVA'),
    (re.compile(r'ley\s+aduanera', re.IGNORECASE), 'LA'),
    (re.compile(r'ley\s+del\s+impuesto\s+especial\s+sobre\s+producción\s+y\s+servicios', re.IGNORECASE), 'LIEPS'),
    (re.compile(r'ley\s+del\s+ieps', re.IGNORECASE), 'LIEPS'),
    (re.compile(r'\bLIEPS\b'), 'LIEPS'),
    (re.compile(r'ley\s+federal\s+del\s+trabajo', re.IGNORECASE), 'LFT'),
    (re.compile(r'ley\s+del\s+seguro\s+social', re.IGNORECASE), 'LSS'),
    (re.compile(r'ley\s+del\s+infonavit', re.IGNORECASE), 'LINFONAVIT'),
    (re.compile(r'ley\s+del\s+issste', re.IGNORECASE), 'LISSSTE'),
    (re.compile(r'ley\s+de\s+ingresos(?:\s+de\s+la\s+federación)?', re.IGNORECASE), 'LIF'),
    (re.compile(r'ley\s+federal\s+de\s+derechos\s+del\s+contribuyente', re.IGNORECASE), 'LFDC'),
]


def resolver_contexto_ley(texto: str, posicion: int, tipo: str) -> str | None:
    """
    Busca hacia atrás en el texto para encontrar la última ley/código mencionado.

    Args:
        texto: Texto completo del párrafo
        posicion: Posición donde se encontró "citado Código/Ley"
        tipo: "código", "ley" o "ordenamiento"

    Returns:
        Código de ley (CFF, LISR, etc.) o None si no se encuentra
    """
    texto_anterior = texto[:posicion]

    # Seleccionar patrones según el tipo
    tipo_lower = tipo.lower()
    if tipo_lower in ('código', 'ordenamiento'):
        patrones = _PATRONES_CONTEXTO_CODIGO
    else:  # ley
        patrones = _PATRONES_CONTEXTO_LEY

    # Buscar la última mención
    ultima_pos = -1
    ley_encontrada = None

    for patron, codigo in patrones:
        for match in patron.finditer(texto_anterior):
            if match.end() > ultima_pos:
                ultima_pos = match.end()
                ley_encontrada = codigo

    return ley_encontrada


def _parsear_lista_articulos(lista_texto: str) -> list[tuple[str, str | None, str | None]]:
    """
    Parsea una lista de artículos separados por coma y "y".

    Ejemplo: "94, 97, 116 fracción III, y 122 Apartado A, fracción IV"
    Retorna: [('94', None, None), ('97', None, None), ('116', None, 'III'), ('122', 'A', 'IV')]
    """
    resultados = []

    # Dividir por "," y "y" pero mantener los modificadores juntos
    # Estrategia: buscar todos los números de artículo y sus modificadores
    for match in _PATRON_ELEMENTO_LISTA.finditer(lista_texto):
        articulo = match.group(1)
        apartado = match.group(2)
        fraccion = match.group(3)

        # Evitar duplicados (el regex puede encontrar el mismo número varias veces)
        if articulo and (not resultados or resultados[-1][0] != articulo):
            resultados.append((articulo, apartado, fraccion))

    return resultados


# Separadores para listas de elementos (y, o, u, e)
_SEPARADORES_LISTA = r'(?:\s+(?:y|o|u|e)\s+)'

# Regex para detectar referencias estructurales (títulos, capítulos, secciones)
# Patrones: "Título II de esta Ley", "Capítulo IV de este Título", "Sección I del Capítulo II"
# Soporta listas con coma y separadores (y/o/u/e): "Título II, III, V o VI de esta Ley"
PATRON_ESTRUCTURA = re.compile(
    r'(Títulos?|Capítulos?|Seccione?s?)\s+'
    r'([IVXLCDM0-9]+(?:(?:[,\s]+|' + _SEPARADORES_LISTA + r')[IVXLCDM0-9]+)*)\s+'
    r'(?:del?\s+)?'
    r'(este\s+Título|esta\s+Ley|el\s+Capítulo\s+[IVXLCDM]+|este\s+Capítulo)',
    re.IGNORECASE
)

# Regex para referencias jerárquicas: "Capítulo X del Título Y de esta Ley"
# Captura tanto el capítulo como el título para mostrar contexto completo
PATRON_CAPITULO_TITULO = re.compile(
    r'(Capítulos?)\s+([IVXLCDM0-9]+)\s+'
    r'del\s+(Títulos?)\s+([IVXLCDM0-9]+)\s+'
    r'de\s+esta\s+Ley',
    re.IGNORECASE
)

# Regex para referencias con 3 niveles: "Sección X, del Capítulo Y del Título Z de esta Ley"
PATRON_SECCION_CAPITULO_TITULO = re.compile(
    r'(Secci[oó]ne?s?)\s+([IVXLCDM0-9]+),?\s+'
    r'del\s+(Capítulos?)\s+([IVXLCDM0-9]+)\s+'
    r'del\s+(Títulos?)\s+([IVXLCDM0-9]+)\s+'
    r'de\s+esta\s+Ley',
    re.IGNORECASE
)


def normalizar_articulo(articulo: str, ley_codigo: str, indice: dict) -> str | None:
    """
    Normaliza el número de artículo para encontrarlo en el índice.

    Maneja variantes como:
    - Ordinales: "9" ↔ "9o"
    - Sufijos: "5-A", "14-B"

    Args:
        articulo: Número de artículo extraído del texto
        ley_codigo: Código de la ley (ej: "CFF", "LISR")
        indice: Índice global de artículos

    Returns:
        Número de artículo normalizado si existe en el índice, None si no se encuentra
    """
    ley_indice = indice.get(ley_codigo, {})

    # Limpiar punto final de ordinales (4o. → 4o)
    if articulo.endswith('.'):
        articulo = articulo[:-1]

    # Intento 1: exacto
    if articulo in ley_indice:
        return articulo

    # Intento 2: agregar "o" (ordinal) - para "9" → "9o"
    articulo_ordinal = f"{articulo}o"
    if articulo_ordinal in ley_indice:
        return articulo_ordinal

    # Intento 3: quitar "o" si termina en "o" - para "9o" → "9"
    if articulo.endswith('o') and not articulo.endswith('-o'):
        articulo_sin_ordinal = articulo[:-1]
        if articulo_sin_ordinal in ley_indice:
            return articulo_sin_ordinal

    return None


def construir_indice_global(contenidos: dict) -> dict:
    """
    Construye índice global para resolver referencias.

    Estructura:
    {
        "CPEUM": {
            "123": {
                "parrafos": [...],  # Lista de todos los párrafos
                "por_tipo": {
                    "fraccion": {
                        "I": [
                            {"numero": 5, "apartado_padre": "A"},
                            {"numero": 107, "apartado_padre": "B"}
                        ]
                    },
                    "inciso": { ... }
                }
            }
        }
    }
    """
    indice = {}

    for ley_codigo, contenido in contenidos.items():
        indice[ley_codigo] = {}

        for articulo in contenido.get("articulos", []):
            art_num = articulo.get("numero")
            parrafos = articulo.get("parrafos", [])

            # Construir mapa de párrafos con jerarquía
            parrafos_por_numero = {p["numero"]: p for p in parrafos}

            # Índice por tipo e identificador
            por_tipo = defaultdict(lambda: defaultdict(list))

            # Rastrear apartado actual para cada párrafo
            ultimo_apartado = None

            for p in parrafos:
                tipo = p.get("tipo")
                ident = p.get("identificador")
                numero = p.get("numero")

                if tipo == "apartado":
                    ultimo_apartado = ident

                if tipo in ("fraccion", "inciso", "numeral") and ident:
                    # Determinar apartado padre
                    apartado_padre = None
                    if p.get("padre_numero"):
                        padre = parrafos_por_numero.get(p["padre_numero"])
                        while padre:
                            if padre.get("tipo") == "apartado":
                                apartado_padre = padre.get("identificador")
                                break
                            padre = parrafos_por_numero.get(padre.get("padre_numero"))

                    # Si no encontramos por jerarquía, usar el último apartado visto
                    if not apartado_padre:
                        apartado_padre = ultimo_apartado

                    por_tipo[tipo][ident].append({
                        "numero": numero,
                        "apartado_padre": apartado_padre,
                        "fraccion_padre": None  # TODO: para incisos
                    })

            indice[ley_codigo][art_num] = {
                "parrafos": parrafos,
                "por_tipo": dict(por_tipo)
            }

    return indice


def resolver_referencia(
    ley_destino: str,
    articulo: str,
    fraccion: str | None,
    inciso: str | None,
    indice: dict
) -> tuple[int | None, str | None]:
    """
    Resuelve una referencia a un número de párrafo específico.

    Returns:
        Tupla (número_párrafo, artículo_normalizado):
        - número_párrafo: si se resuelve sin ambigüedad, None si no se encuentra
        - artículo_normalizado: el número de artículo como aparece en el índice
    """
    if ley_destino not in indice:
        return None, None

    # Normalizar artículo (maneja variantes como 9 vs 9o)
    articulo_norm = normalizar_articulo(articulo, ley_destino, indice)
    if articulo_norm is None:
        return None, None

    art_data = indice[ley_destino][articulo_norm]

    # Si no hay fracción/inciso, enlazar al artículo (primer párrafo)
    if not fraccion:
        parrafos = art_data.get("parrafos", [])
        if parrafos:
            return parrafos[0]["numero"], articulo_norm
        return None, None

    # Buscar fracción
    por_tipo = art_data.get("por_tipo", {})
    fracciones = por_tipo.get("fraccion", {}).get(fraccion, [])

    if not fracciones:
        # Fracción no encontrada, enlazar al artículo
        parrafos = art_data.get("parrafos", [])
        if parrafos:
            return parrafos[0]["numero"], articulo_norm
        return None, None

    if len(fracciones) == 1:
        # Sin ambigüedad
        fraccion_num = fracciones[0]["numero"]
        if not inciso:
            return fraccion_num, articulo_norm
        # Buscar inciso que sea hijo de esta fracción
        parrafos = art_data.get("parrafos", [])
        for p in parrafos:
            if (p.get("tipo") == "inciso" and
                p.get("identificador", "").lower() == inciso.lower() and
                p.get("padre_numero") == fraccion_num):
                return p["numero"], articulo_norm
        # Inciso no encontrado, retornar fracción
        return fraccion_num, articulo_norm

    # Ambiguo: múltiples fracciones con mismo identificador
    # Retornamos la primera (arbitrario pero consistente)
    return fracciones[0]["numero"], articulo_norm


def procesar_referencias(texto: str, ley_actual: str, indice: dict) -> str:
    """
    Detecta referencias en el texto y las convierte a marcadores de link.

    Formato de marcador: [[ref:LEY:ARTICULO:PARRAFO|texto original]]
    """
    def reemplazar(match):
        texto_original = match.group(0)
        articulo = match.group(1)
        fraccion = match.group(2)  # Puede ser None
        inciso = match.group(3)    # Puede ser None
        ley_texto = match.group(4).lower().strip()

        # Resolver código de ley
        ley_codigo = NOMBRE_A_CODIGO.get(ley_texto)
        if not ley_codigo:
            return texto_original  # No reconocida, dejar como está

        # Si es referencia interna, usar ley actual
        if ley_codigo == '_MISMA_':
            ley_codigo = ley_actual

        # Resolver a número de párrafo
        parrafo_num, articulo_norm = resolver_referencia(ley_codigo, articulo, fraccion, inciso, indice)

        if parrafo_num is None:
            return texto_original  # No se pudo resolver

        # Crear marcador (usar artículo normalizado para URL correcta)
        return f"[[ref:{ley_codigo}:{articulo_norm}:{parrafo_num}|{texto_original}]]"

    return PATRON_REFERENCIA.sub(reemplazar, texto)


def cargar_contenido(ley_codigo: str) -> dict | None:
    """Carga contenido.json de una ley."""
    path = ETL_DATA / ley_codigo.lower() / "contenido.json"
    if not path.exists():
        print(f"  ⚠ No existe: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cargar_estructura(ley_codigo: str) -> dict | None:
    """Carga mapa_estructura.json de una ley."""
    path = ETL_DATA / ley_codigo.lower() / "mapa_estructura.json"
    if not path.exists():
        print(f"  ⚠ No existe estructura: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generar_articulos_json(contenido: dict, ley_config: dict) -> list:
    """
    Transforma contenido.json a formato optimizado para Astro.

    NO modifica el contenido de los párrafos - se mantiene texto puro.
    Las referencias se generan en archivo separado (referencias.json).

    Estructura de salida por artículo:
    {
        "numero": "1o",
        "tipo": "articulo",
        "orden": 1,
        "pagina": 1,
        "y": 434,  # Coordenada Y del primer párrafo
        "contenido": "Texto completo...",
        "parrafos": [...]
    }
    """
    articulos = []

    for art in contenido.get("articulos", []):
        parrafos = art.get("parrafos", [])

        # Concatenar contenido de todos los párrafos (texto original)
        contenido_texto = "\n\n".join(
            p.get("contenido", "") for p in parrafos
        )

        # Obtener coordenadas del primer párrafo
        primer_parrafo = parrafos[0] if parrafos else {}

        articulo_astro = {
            "numero": art.get("numero"),
            "nombre": art.get("nombre"),  # Título/nombre del artículo (para RMF)
            "tipo": art.get("tipo", "articulo"),
            "orden": art.get("orden"),
            "pagina": art.get("pagina") or primer_parrafo.get("pagina", 1),
            "y": primer_parrafo.get("y", 0),
            "contenido": contenido_texto,
            "parrafos": parrafos,
            "referencias": art.get("referencias"),
        }

        articulos.append(articulo_astro)

    return articulos


def generar_toc_json(articulos: list) -> dict:
    """
    Genera índice TOC (Table of Contents) para navegación.

    Extrae solo los párrafos navegables (apartado, fraccion, inciso, numeral)
    con su estructura jerárquica mínima.

    Estructura de salida:
    {
        "122": [
            {"n": 2, "t": "apartado", "i": "A"},
            {"n": 17, "t": "fraccion", "i": "IV", "p": 2},
            ...
        ]
    }

    Campos compactos:
    - n: numero (párrafo)
    - t: tipo
    - i: identificador
    - p: padre_numero (opcional, solo si existe)
    """
    toc = {}
    tipos_navegables = {'apartado', 'fraccion', 'inciso', 'numeral'}

    for art in articulos:
        art_num = art.get("numero")
        items = []

        for parrafo in art.get("parrafos", []):
            tipo = parrafo.get("tipo")
            identificador = parrafo.get("identificador")

            # Solo incluir navegables con identificador
            if tipo in tipos_navegables and identificador:
                item = {
                    "n": parrafo.get("numero"),
                    "t": tipo,
                    "i": identificador
                }
                # Solo incluir padre si existe
                if parrafo.get("padre_numero"):
                    item["p"] = parrafo.get("padre_numero")

                items.append(item)

        if items:
            toc[art_num] = items

    return toc


def _resolver_parrafo_interno(parrafos: list, tipo: str, identificador: str) -> int | None:
    """
    Resuelve el número de párrafo de una fracción/inciso/párrafo dentro del mismo artículo.

    Args:
        parrafos: Lista de párrafos del artículo
        tipo: "fraccion", "inciso", "parrafo"
        identificador: "I", "II", "a", "primero", etc.

    Returns:
        Número de párrafo o None si no se encuentra
    """
    # Mapeo de ordinales a números para párrafos
    ORDINALES = {
        'primero': 1, 'segundo': 2, 'tercero': 3, 'cuarto': 4,
        'quinto': 5, 'sexto': 6, 'séptimo': 7, 'octavo': 8,
        'noveno': 9, 'décimo': 10, 'anterior': -1
    }

    tipo_norm = tipo.lower().rstrip('s')  # fracciones -> fraccion
    if tipo_norm.startswith('fracc'):
        tipo_norm = 'fraccion'
    elif tipo_norm.startswith('párr') or tipo_norm.startswith('parr'):
        tipo_norm = 'texto'  # Los párrafos son tipo 'texto'
    elif tipo_norm.startswith('incis'):
        tipo_norm = 'inciso'

    ident_norm = identificador.lower().rstrip(')')

    # Caso especial: párrafo por ordinal
    if tipo_norm == 'texto' and ident_norm in ORDINALES:
        ordinal = ORDINALES[ident_norm]
        if ordinal == -1:  # "anterior" - no podemos resolver sin contexto
            return None
        # Contar párrafos de tipo texto
        texto_count = 0
        for p in parrafos:
            if p.get('tipo') in (None, 'texto'):
                texto_count += 1
                if texto_count == ordinal:
                    return p.get('numero')
        return None

    # Buscar por tipo e identificador
    for p in parrafos:
        p_tipo = p.get('tipo') or 'texto'
        p_ident = (p.get('identificador') or '').lower()

        if p_tipo == tipo_norm and p_ident == ident_norm:
            return p.get('numero')

    return None


def extraer_referencias(contenido: dict, ley_codigo: str, indice: dict) -> dict:
    """
    Extrae todas las referencias de una ley y genera mapa para renderizado.

    Usa varios patrones:
    - Estándar: artículo N fracción X de LEY
    - Invertido: fracción X del artículo N de LEY
    - Lista: artículos 94, 97, 116 fracción III de LEY
    - Interno: fracción I de este artículo

    Estructura de salida:
    {
        "123": {
            "artículo 4o de esta Constitución": {
                "ley": "CPEUM",
                "articulo": "4",
                "parrafo": 1
            },
            "fracción I de este artículo": {
                "interno": true,
                "parrafo": 2
            }
        }
    }
    """
    referencias_ley = {}

    for art in contenido.get("articulos", []):
        art_num = art.get("numero")
        art_parrafos = art.get("parrafos", [])
        referencias_articulo = {}

        for p in art.get("parrafos", []):
            texto = p.get("contenido", "")

            # Buscar listas de artículos primero (más específico)
            for match in PATRON_LISTA_ARTICULOS.finditer(texto):
                texto_original = match.group(0)
                lista_texto = match.group(1)
                ley_texto = match.group(2).lower().strip()

                # Parsear cada elemento de la lista
                elementos = _parsear_lista_articulos(lista_texto)
                if len(elementos) >= 2:  # Solo si hay múltiples artículos
                    # Resolver ley destino
                    ley_destino = NOMBRE_A_CODIGO.get(ley_texto)
                    if ley_destino == '_MISMA_':
                        ley_destino = ley_codigo

                    if ley_destino:
                        # Construir DSL query con todos los artículos
                        partes_dsl = []
                        primer_parrafo = None
                        for articulo_ref, apartado, fraccion in elementos:
                            parte = articulo_ref
                            if apartado:
                                parte += f"/{apartado}"
                            if fraccion:
                                parte += f"/{fraccion}"
                            partes_dsl.append(parte)

                            # Obtener párrafo del primer artículo para el link
                            if primer_parrafo is None:
                                parrafo_res, _ = resolver_referencia(
                                    ley_destino, articulo_ref, fraccion, None, indice
                                )
                                primer_parrafo = parrafo_res or 1

                        query_dsl = f"{ley_destino.lower()}:{','.join(partes_dsl)}"

                        # Usar texto completo como clave, incluir query DSL
                        referencias_articulo[texto_original] = {
                            "ley": ley_destino.lower(),
                            "articulo": elementos[0][0],  # Primer artículo
                            "parrafo": primer_parrafo,
                            "query": query_dsl
                        }

            # Buscar listas de artículos implícitas (después de ";", sin "artículos")
            for match in PATRON_LISTA_ARTICULOS_IMPLICITA.finditer(texto):
                texto_completo = match.group(0)
                lista_texto = match.group(1)
                ley_texto = match.group(2).lower().strip()

                # El texto del link no incluye el ";" inicial
                texto_original = texto_completo.lstrip('; ')

                # Evitar duplicados: saltar si este texto ya es parte de una referencia existente
                es_duplicado = any(texto_original in ref_existente for ref_existente in referencias_articulo)
                if es_duplicado:
                    continue

                # Parsear cada elemento de la lista
                elementos = _parsear_lista_articulos(lista_texto)
                if elementos:  # Al menos un artículo
                    # Resolver ley destino
                    ley_destino = NOMBRE_A_CODIGO.get(ley_texto)
                    if ley_destino == '_MISMA_':
                        ley_destino = ley_codigo

                    # Solo procesar si la ley es soportada (no None)
                    if ley_destino and ley_destino != '_MISMA_':
                        # Construir DSL query con todos los artículos
                        partes_dsl = []
                        primer_parrafo = None
                        for articulo_ref, apartado, fraccion in elementos:
                            parte = articulo_ref
                            if apartado:
                                parte += f"/{apartado}"
                            if fraccion:
                                parte += f"/{fraccion}"
                            partes_dsl.append(parte)

                            # Obtener párrafo del primer artículo para el link
                            if primer_parrafo is None:
                                parrafo_res, _ = resolver_referencia(
                                    ley_destino, articulo_ref, fraccion, None, indice
                                )
                                primer_parrafo = parrafo_res or 1

                        if len(elementos) >= 2:
                            query_dsl = f"{ley_destino.lower()}:{','.join(partes_dsl)}"
                            referencias_articulo[texto_original] = {
                                "ley": ley_destino.lower(),
                                "articulo": elementos[0][0],
                                "parrafo": primer_parrafo,
                                "query": query_dsl
                            }
                        else:
                            # Solo un artículo, referencia simple
                            referencias_articulo[texto_original] = {
                                "ley": ley_destino.lower(),
                                "articulo": elementos[0][0],
                                "parrafo": primer_parrafo
                            }

            # Buscar referencias con lista de fracciones (artículo 140 fracciones I y II)
            for match in PATRON_REFERENCIA_FRACCIONES_LISTA.finditer(texto):
                texto_original = match.group(0)
                articulo_ref = match.group(1)
                fracciones_texto = match.group(2)
                ley_texto = match.group(3).lower().strip()

                # Resolver ley destino
                ley_destino = NOMBRE_A_CODIGO.get(ley_texto)
                if ley_destino == '_MISMA_':
                    ley_destino = ley_codigo

                if ley_destino:
                    # Normalizar artículo
                    articulo_norm = normalizar_articulo(articulo_ref, ley_destino, indice)
                    if articulo_norm:
                        # Parsear lista de fracciones (I y II, I, II y III)
                        fracciones = re.split(r'[,\s]+(?:y|e)\s+|[,\s]+', fracciones_texto.strip())
                        fracciones = [f.strip() for f in fracciones if f.strip()]

                        if len(fracciones) >= 2:
                            # Construir DSL query con artículo y fracciones
                            partes_dsl = [f"{articulo_norm}/{frac}" for frac in fracciones]
                            query_dsl = f"{ley_destino.lower()}:{','.join(partes_dsl)}"

                            # Resolver párrafo de la primera fracción
                            parrafo_num, _ = resolver_referencia(
                                ley_destino, articulo_norm, fracciones[0], None, indice
                            )

                            referencias_articulo[texto_original] = {
                                "ley": ley_destino.lower(),
                                "articulo": articulo_norm,
                                "parrafo": parrafo_num or 1,
                                "query": query_dsl
                            }

            # Buscar referencias con patrón estándar
            for match in PATRON_REFERENCIA.finditer(texto):
                texto_original = match.group(0)
                articulo_ref = match.group(1)
                fraccion = match.group(2)
                inciso = match.group(3)
                ley_texto = match.group(4).lower().strip()

                ref = _procesar_match_referencia(
                    texto_original, articulo_ref, fraccion, inciso, ley_texto,
                    ley_codigo, indice
                )
                if ref:
                    referencias_articulo[texto_original] = ref

            # Buscar referencias con patrón invertido
            for match in PATRON_REFERENCIA_INVERTIDO.finditer(texto):
                texto_original = match.group(0)
                # Grupos invertidos: inciso(1), fraccion(2), articulo(3), apartado(4), ley(5)
                inciso = match.group(1)
                fraccion = match.group(2)
                articulo_ref = match.group(3)
                # apartado = match.group(4)  # Para uso futuro
                ley_texto = match.group(5).lower().strip()

                ref = _procesar_match_referencia(
                    texto_original, articulo_ref, fraccion, inciso, ley_texto,
                    ley_codigo, indice
                )
                if ref:
                    referencias_articulo[texto_original] = ref

            # Buscar referencias contextuales (citado/dicho Código/Ley)
            for match in PATRON_REFERENCIA_CONTEXTUAL.finditer(texto):
                texto_original = match.group(0)
                articulo_ref = match.group(1)
                fraccion = match.group(2)
                inciso = match.group(3)
                # ref_contextual = match.group(4)  # citado/dicho/mismo
                tipo_ley = match.group(5)  # Código/Ley/ordenamiento

                # Resolver qué ley se menciona antes en el texto
                ley_destino = resolver_contexto_ley(texto, match.start(), tipo_ley)
                if ley_destino:
                    # Normalizar artículo y resolver párrafo
                    parrafo_num, articulo_norm = resolver_referencia(
                        ley_destino, articulo_ref, fraccion, inciso, indice
                    )
                    if parrafo_num is not None:
                        referencias_articulo[texto_original] = {
                            "ley": ley_destino.lower(),
                            "articulo": articulo_norm,
                            "parrafo": parrafo_num
                        }

            # Buscar referencias internas al mismo artículo
            for match in PATRON_REFERENCIA_INTERNA.finditer(texto):
                texto_original = match.group(0)
                tipo = match.group(1)        # fracción, párrafo, inciso
                identificador = match.group(2)  # I, II, a), primero, etc.

                parrafo_num = _resolver_parrafo_interno(art_parrafos, tipo, identificador)
                if parrafo_num is not None:
                    referencias_articulo[texto_original] = {
                        "interno": True,
                        "parrafo": parrafo_num
                    }

            # Buscar referencias a reglas internas (solo para leyes que usan reglas, como RMF)
            if ley_codigo in LEYES_CON_REGLAS:
                for match in PATRON_REGLA_INTERNA.finditer(texto):
                    texto_original = match.group(0)
                    regla_num = match.group(1).rstrip('.')  # Quitar punto final: "2.9.3." → "2.9.3"

                    # Verificar que la regla existe en el índice
                    ley_indice = indice.get(ley_codigo, {})
                    if regla_num in ley_indice:
                        referencias_articulo[texto_original] = {
                            "ley": ley_codigo.lower(),
                            "articulo": regla_num,
                            "parrafo": 1
                        }

        if referencias_articulo:
            referencias_ley[art_num] = referencias_articulo

    return referencias_ley


def _procesar_match_referencia(
    texto_original: str,
    articulo_ref: str,
    fraccion: str | None,
    inciso: str | None,
    ley_texto: str,
    ley_codigo: str,
    indice: dict
) -> dict | None:
    """
    Procesa un match de referencia y retorna el diccionario de referencia.

    Helper compartido entre patrón estándar e invertido.
    """
    # Resolver código de ley
    ley_destino = NOMBRE_A_CODIGO.get(ley_texto)
    if not ley_destino:
        return None

    # Si es referencia interna, usar ley actual
    if ley_destino == '_MISMA_':
        ley_destino = ley_codigo

    # Resolver a número de párrafo
    parrafo_num, articulo_norm = resolver_referencia(
        ley_destino, articulo_ref, fraccion, inciso, indice
    )

    if parrafo_num is not None:
        return {
            "ley": ley_destino.lower(),
            "articulo": articulo_norm,  # Usar artículo normalizado
            "parrafo": parrafo_num
        }

    return None


def construir_indice_estructura(estructura: dict) -> dict:
    """
    Construye índice de artículo → ubicación estructural.

    Retorna:
    {
        "152": {
            "titulo": {"numero": "IV", "nombre": "DE LAS PERSONAS FÍSICAS"},
            "capitulo": {"numero": "X", "nombre": "DE LOS REQUISITOS..."},
            "seccion": None
        }
    }
    """
    indice = {}

    def procesar_division(div, contexto):
        """Procesa recursivamente las divisiones."""
        tipo = div.get("tipo")
        nuevo_contexto = contexto.copy()
        nuevo_contexto[tipo] = {
            "numero": div.get("numero"),
            "nombre": div.get("nombre")
        }

        # Registrar artículos de esta división
        for art_num in div.get("articulos", []):
            indice[art_num] = nuevo_contexto.copy()

        # Procesar hijos
        for hijo in div.get("hijos", []):
            procesar_division(hijo, nuevo_contexto)

    # Procesar todas las divisiones de nivel superior
    for div in estructura.get("divisiones", []):
        procesar_division(div, {})

    return indice


def buscar_division_por_numero(estructura: dict, tipo: str, numero: str,
                                titulo_contexto: str = None) -> str | None:
    """
    Busca el nombre de una división por su tipo y número.

    Para capítulos, necesita el título como contexto.
    """
    numero_upper = numero.upper()

    for div in estructura.get("divisiones", []):
        # Buscar títulos
        if tipo == "titulo" and div.get("tipo") == "titulo":
            if div.get("numero", "").upper() == numero_upper:
                return div.get("nombre")

        # Buscar capítulos dentro del título correcto
        if tipo == "capitulo":
            # Si hay contexto de título, buscar solo en ese título
            if titulo_contexto:
                if div.get("tipo") == "titulo" and div.get("numero", "").upper() == titulo_contexto.upper():
                    for cap in div.get("hijos", []):
                        if cap.get("tipo") == "capitulo" and cap.get("numero", "").upper() == numero_upper:
                            return cap.get("nombre")
            else:
                # Sin contexto, buscar en todos los títulos
                if div.get("tipo") == "titulo":
                    for cap in div.get("hijos", []):
                        if cap.get("tipo") == "capitulo" and cap.get("numero", "").upper() == numero_upper:
                            return cap.get("nombre")

        # Buscar secciones
        if tipo == "seccion":
            if div.get("tipo") == "titulo":
                for cap in div.get("hijos", []):
                    if cap.get("tipo") == "capitulo":
                        for sec in cap.get("hijos", []):
                            if sec.get("tipo") == "seccion" and sec.get("numero", "").upper() == numero_upper:
                                return sec.get("nombre")

    return None


def extraer_tooltips(contenido: dict, estructura: dict, indice_estructura: dict) -> dict:
    """
    Extrae referencias estructurales y genera mapa de tooltips.

    Estructura de salida:
    {
        "152": {
            "Título II de esta Ley": [
                {"tipo": "Título", "numero": "II", "nombre": "DE LAS DEDUCCIONES"}
            ],
            "Título II, III, V o VI de esta Ley": [
                {"tipo": "Título", "numero": "II", "nombre": "DE LAS PERSONAS MORALES"},
                {"tipo": "Título", "numero": "III", "nombre": "DEL RÉGIMEN..."},
                ...
            ]
        }
    }
    """
    tooltips_ley = {}

    for art in contenido.get("articulos", []):
        art_num = art.get("numero")
        tooltips_articulo = {}

        # Obtener contexto del artículo (en qué título/capítulo está)
        contexto = indice_estructura.get(art_num, {})
        titulo_actual = contexto.get("titulo", {}).get("numero")

        for p in art.get("parrafos", []):
            texto = p.get("contenido", "")
            textos_procesados = set()  # Evitar doble procesamiento

            # PRIMERO: Buscar referencias de 3 niveles (Sección X del Capítulo Y del Título Z)
            for match in PATRON_SECCION_CAPITULO_TITULO.finditer(texto):
                texto_original = match.group(0)
                textos_procesados.add(texto_original)

                num_sec = match.group(2)    # Número de sección
                num_cap = match.group(4)    # Número de capítulo
                num_tit = match.group(6)    # Número de título

                # Marcar subcadenas como procesadas para evitar duplicados
                textos_procesados.add(f"Capítulo {num_cap} del Título {num_tit} de esta Ley")
                textos_procesados.add(f"Título {num_tit} de esta Ley")

                # Buscar nombres en la estructura
                nombre_sec = buscar_division_por_numero(estructura, "seccion", num_sec, None)
                nombre_cap = buscar_division_por_numero(estructura, "capitulo", num_cap, num_tit)
                nombre_tit = buscar_division_por_numero(estructura, "titulo", num_tit, None)

                # Construir items (Sección, Capítulo, Título - de específico a general)
                items = []
                if nombre_sec:
                    items.append({
                        "tipo": "Sección",
                        "numero": num_sec,
                        "nombre": nombre_sec
                    })
                if nombre_cap:
                    items.append({
                        "tipo": "Capítulo",
                        "numero": num_cap,
                        "nombre": nombre_cap
                    })
                if nombre_tit:
                    items.append({
                        "tipo": "Título",
                        "numero": num_tit,
                        "nombre": nombre_tit
                    })

                if items:
                    tooltips_articulo[texto_original] = items

            # SEGUNDO: Buscar referencias jerárquicas (Capítulo X del Título Y)
            for match in PATRON_CAPITULO_TITULO.finditer(texto):
                texto_original = match.group(0)
                textos_procesados.add(texto_original)

                tipo_cap = match.group(1)   # "Capítulo" o "Capítulos"
                num_cap = match.group(2)    # Número romano del capítulo
                tipo_tit = match.group(3)   # "Título" o "Títulos"
                num_tit = match.group(4)    # Número romano del título

                # Marcar también "Título X de esta Ley" como procesado para evitar duplicados
                texto_titulo_parcial = f"Título {num_tit} de esta Ley"
                textos_procesados.add(texto_titulo_parcial)

                # Buscar nombre del Capítulo (dentro del Título especificado)
                nombre_cap = buscar_division_por_numero(
                    estructura, "capitulo", num_cap, num_tit
                )
                # Buscar nombre del Título
                nombre_tit = buscar_division_por_numero(
                    estructura, "titulo", num_tit, None
                )

                # Construir items (Capítulo primero, luego Título como contexto)
                items = []
                if nombre_cap:
                    items.append({
                        "tipo": "Capítulo",
                        "numero": num_cap,
                        "nombre": nombre_cap
                    })
                if nombre_tit:
                    items.append({
                        "tipo": "Título",
                        "numero": num_tit,
                        "nombre": nombre_tit
                    })

                if items:
                    tooltips_articulo[texto_original] = items

            # TERCERO: Buscar referencias estructurales simples
            for match in PATRON_ESTRUCTURA.finditer(texto):
                texto_original = match.group(0)
                # Saltar si ya fue procesado por patrón jerárquico
                if texto_original in textos_procesados:
                    continue
                texto_original = match.group(0)
                tipo_ref = match.group(1).lower()  # título, capítulo, sección
                numeros = match.group(2)           # II, IV, I, III, IV...
                contexto_ref = match.group(3).lower()  # "este título", "esta ley"

                # Normalizar tipo para búsqueda y display
                if tipo_ref.startswith("título"):
                    tipo_buscar = "titulo"
                    tipo_display = "Título"
                elif tipo_ref.startswith("capítulo"):
                    tipo_buscar = "capitulo"
                    tipo_display = "Capítulo"
                elif tipo_ref.startswith("sección") or tipo_ref.startswith("seccion"):
                    tipo_buscar = "seccion"
                    tipo_display = "Sección"
                else:
                    continue

                # Parsear números (puede ser lista: "I, III, IV y IX" o "II, III, V o VI")
                numeros_lista = re.split(r'[,\s]+(?:y|o)\s+|[,\s]+', numeros.strip())
                numeros_lista = [n.strip() for n in numeros_lista if n.strip()]

                # Determinar contexto de título para capítulos
                titulo_contexto = None
                if tipo_buscar == "capitulo" and "este título" in contexto_ref:
                    titulo_contexto = titulo_actual

                # Buscar nombres para cada número y construir lista estructurada
                items = []
                for num in numeros_lista:
                    nombre = buscar_division_por_numero(
                        estructura, tipo_buscar, num, titulo_contexto
                    )
                    if nombre:
                        items.append({
                            "tipo": tipo_display,
                            "numero": num,
                            "nombre": nombre
                        })

                # Guardar tooltip estructurado
                if items:
                    tooltips_articulo[texto_original] = items

        # Eliminar entradas que son subcadenas de otras más largas
        # (evita doble tooltip cuando "Título II de esta Ley" está dentro de
        # "Capítulo V del Título II de esta Ley")
        if tooltips_articulo:
            keys = list(tooltips_articulo.keys())
            keys_ordenadas = sorted(keys, key=len, reverse=True)
            keys_a_eliminar = set()
            for i, key_larga in enumerate(keys_ordenadas):
                for key_corta in keys_ordenadas[i+1:]:
                    if key_corta in key_larga and key_corta not in keys_a_eliminar:
                        keys_a_eliminar.add(key_corta)
            for key in keys_a_eliminar:
                del tooltips_articulo[key]

        if tooltips_articulo:
            tooltips_ley[art_num] = tooltips_articulo

    return tooltips_ley


def generar_estructura_json(mapa: dict) -> dict:
    """
    Transforma mapa_estructura.json a formato optimizado para Astro.

    Mantiene la jerarquía pero simplifica para navegación.
    """
    if not mapa:
        return {}

    estructura = {
        "ley": mapa.get("ley"),
        "estadisticas": mapa.get("estadisticas", {}),
        "divisiones": []
    }

    # Procesar títulos -> capítulos -> secciones
    for titulo_num, titulo_data in mapa.get("titulos", {}).items():
        titulo = {
            "tipo": "titulo",
            "numero": titulo_num,
            "nombre": titulo_data.get("nombre"),
            "pagina": titulo_data.get("pagina"),
            "hijos": []
        }

        for cap_num, cap_data in titulo_data.get("capitulos", {}).items():
            capitulo = {
                "tipo": "capitulo",
                "numero": cap_num,
                "nombre": cap_data.get("nombre"),
                "pagina": cap_data.get("pagina"),
                "articulos": cap_data.get("articulos", []),
                "hijos": []
            }

            # Secciones si existen
            for sec_num, sec_data in cap_data.get("secciones", {}).items():
                seccion = {
                    "tipo": "seccion",
                    "numero": sec_num,
                    "nombre": sec_data.get("nombre"),
                    "pagina": sec_data.get("pagina"),
                    "articulos": sec_data.get("articulos", []),
                }
                capitulo["hijos"].append(seccion)

            titulo["hijos"].append(capitulo)

        estructura["divisiones"].append(titulo)

    # Procesar libros si existen (para algunas leyes como LSS)
    for libro_num, libro_data in mapa.get("libros", {}).items():
        libro = {
            "tipo": "libro",
            "numero": libro_num,
            "nombre": libro_data.get("nombre"),
            "pagina": libro_data.get("pagina"),
            "hijos": []
        }

        for titulo_num, titulo_data in libro_data.get("titulos", {}).items():
            titulo = {
                "tipo": "titulo",
                "numero": titulo_num,
                "nombre": titulo_data.get("nombre"),
                "pagina": titulo_data.get("pagina"),
                "articulos": titulo_data.get("articulos", []),
                "hijos": []
            }
            libro["hijos"].append(titulo)

        estructura["divisiones"].append(libro)

    return estructura


def generar_catalogo() -> dict:
    """
    Genera catálogo de todas las leyes con metadatos.
    """
    catalogo = {
        "_generado": datetime.now().isoformat(),
        "_version": "1.1",
        "leyes": []
    }

    for codigo, config in LEYES.items():
        # Cargar estadísticas si existen
        estructura = cargar_estructura(codigo)
        stats = estructura.get("estadisticas", {}) if estructura else {}

        # Cargar contenido para ultima_reforma_dof
        contenido = cargar_contenido(codigo)
        ultima_reforma = contenido.get("ultima_reforma_dof") if contenido else None

        ley = {
            "codigo": codigo,
            "nombre": config.get("nombre"),
            "nombre_corto": config.get("nombre_corto"),
            "tipo": config.get("tipo"),
            "categoria": config.get("categoria"),
            "reglamentos": config.get("reglamentos"),
            "reglamento_de": config.get("reglamento_de"),
            "url_fuente": config.get("url_fuente"),
            "tipo_contenido": config.get("tipo_contenido", "articulo"),
            "total_articulos": stats.get("total", 0) or stats.get("articulos_vigentes", 0),
            "divisiones_permitidas": config.get("divisiones_permitidas", []),
            "ultima_reforma_dof": ultima_reforma,
        }

        # Eliminar campos None
        ley = {k: v for k, v in ley.items() if v is not None}

        catalogo["leyes"].append(ley)

    # Orden de leyes por frecuencia de consulta (UX priority)
    ORDEN_LEYES = [
        'CFF', 'LISR', 'LIVA', 'RMF', 'LIF', 'LIEPS', 'LA', 'LFDC',
        'LFT', 'LSS', 'LINFONAVIT', 'LISSSTE',
        'CPEUM',
        # Reglamentos al final, ordenados por ley base
        'RCFF', 'RLISR', 'RLIVA', 'RLIEPS', 'RLFT', 'RACERF', 'RLSS',
    ]

    def orden_key(ley):
        try:
            return ORDEN_LEYES.index(ley["codigo"])
        except ValueError:
            return 999  # Al final si no está en la lista

    catalogo["leyes"].sort(key=orden_key)

    return catalogo


def guardar_json(data: dict | list, path: Path):
    """Guarda JSON con formato legible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ {path.relative_to(PROJECT_ROOT)}")


def main():
    print("=" * 60)
    print("Generando datos para Astro SSG")
    print("=" * 60)

    # Crear directorio base
    ASTRO_DATA.mkdir(parents=True, exist_ok=True)

    # 1. Generar catálogo
    print("\n[1/4] Generando catálogo de leyes...")
    catalogo = generar_catalogo()
    guardar_json(catalogo, ASTRO_DATA / "catalogo.json")

    # 2. Cargar todos los contenidos y construir índice global
    print("\n[2/4] Construyendo índice global para referencias...")
    contenidos = {}
    for codigo in LEYES.keys():
        contenido = cargar_contenido(codigo)
        if contenido:
            contenidos[codigo] = contenido

    indice = construir_indice_global(contenidos)
    print(f"  ✓ Índice construido: {len(indice)} leyes")

    # 3. Cargar estructuras para tooltips
    print("\n[3/5] Cargando estructuras para tooltips...")
    estructuras = {}
    indices_estructura = {}
    for codigo in LEYES.keys():
        mapa = cargar_estructura(codigo)
        if mapa:
            estructura = generar_estructura_json(mapa)
            estructuras[codigo] = estructura
            indices_estructura[codigo] = construir_indice_estructura(estructura)
    print(f"  ✓ Estructuras cargadas: {len(estructuras)} leyes")

    # 4. Generar datos por ley
    print("\n[4/5] Generando artículos, referencias y tooltips por ley...")
    leyes_procesadas = 0
    articulos_total = 0
    referencias_total = 0
    toc_global: dict = {}  # TOC consolidado para runtime
    tooltips_total = 0
    apartados_index: dict = {}  # Índice de artículos con apartados para DSL parser

    for codigo in LEYES.keys():
        print(f"\n  Procesando {codigo}...")

        contenido = contenidos.get(codigo)
        if not contenido:
            continue

        # Generar artículos (texto puro, sin marcadores)
        articulos = generar_articulos_json(contenido, LEYES[codigo])
        if articulos:
            ley_dir = ASTRO_DATA / codigo.lower()
            guardar_json(articulos, ley_dir / "articulos.json")
            leyes_procesadas += 1
            articulos_total += len(articulos)

            # Generar TOC (navegación compacta) para build-time
            toc = generar_toc_json(articulos)
            if toc:
                guardar_json(toc, ley_dir / "toc.json")
                # Acumular para índice consolidado (runtime)
                toc_global[codigo.lower()] = toc

        # Generar mapa de referencias (archivo separado)
        referencias = extraer_referencias(contenido, codigo, indice)
        if referencias:
            ley_dir = ASTRO_DATA / codigo.lower()
            guardar_json(referencias, ley_dir / "referencias.json")
            for art_refs in referencias.values():
                referencias_total += len(art_refs)

        # Generar mapa de tooltips estructurales
        estructura = estructuras.get(codigo, {})
        indice_est = indices_estructura.get(codigo, {})
        tooltips = extraer_tooltips(contenido, estructura, indice_est)
        if tooltips:
            ley_dir = ASTRO_DATA / codigo.lower()
            guardar_json(tooltips, ley_dir / "tooltips.json")
            for art_tips in tooltips.values():
                tooltips_total += len(art_tips)

        # Extraer artículos con apartados para índice DSL
        arts_con_apartados = []
        for art in contenido.get("articulos", []):
            for p in art.get("parrafos", []):
                if p.get("tipo") == "apartado":
                    arts_con_apartados.append(art.get("numero"))
                    break
        if arts_con_apartados:
            apartados_index[codigo.lower()] = arts_con_apartados

    # 5. Generar estructura por ley
    print("\n[5/6] Generando estructura por ley...")

    for codigo in LEYES.keys():
        mapa = cargar_estructura(codigo)
        if not mapa:
            continue

        estructura = generar_estructura_json(mapa)
        if estructura:
            ley_dir = ASTRO_DATA / codigo.lower()
            guardar_json(estructura, ley_dir / "estructura.json")

    # 6. Generar TOC consolidado para runtime (buscar.astro)
    print("\n[6/6] Generando TOC consolidado para runtime...")
    toc_index_path = ASTRO_DATA.parent.parent / "public" / "toc-index.json"
    guardar_json(toc_global, toc_index_path)
    print(f"  ✓ {toc_index_path.relative_to(PROJECT_ROOT)}")

    # 7. Generar índice de apartados para DSL parser
    apartados_index_path = ASTRO_DATA.parent.parent / "public" / "apartados-index.json"
    guardar_json(apartados_index, apartados_index_path)
    print(f"  ✓ {apartados_index_path.relative_to(PROJECT_ROOT)}")

    # Resumen
    total_arts_apartados = sum(len(arts) for arts in apartados_index.values())
    print("\n" + "=" * 60)
    print("Resumen:")
    print(f"  - Leyes procesadas: {leyes_procesadas}")
    print(f"  - Artículos totales: {articulos_total}")
    print(f"  - Referencias mapeadas: {referencias_total}")
    print(f"  - Tooltips estructurales: {tooltips_total}")
    print(f"  - Artículos con apartados: {total_arts_apartados}")
    print(f"  - TOC consolidado: {len(toc_global)} leyes")
    print(f"  - Destino: {ASTRO_DATA.relative_to(PROJECT_ROOT)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
