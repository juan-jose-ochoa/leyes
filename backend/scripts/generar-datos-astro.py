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
    'esta constitución': 'CPEUM',
    'la constitución': 'CPEUM',
    'constitución política': 'CPEUM',
    # Códigos y leyes específicas
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
}

# Alternativas de ley para usar en ambos patrones
_LEY_ALTERNATIVAS = (
    r'esta\s+ley|la\s+presente\s+ley|la\s+misma|'
    r'este\s+código|el\s+presente\s+código|'
    r'esta\s+constitución|la\s+constitución|'
    r'código\s+fiscal(?:\s+de\s+la\s+federación)?|cff|'
    r'ley\s+del\s+impuesto\s+sobre\s+la\s+renta|ley\s+del\s+isr|lisr|'
    r'ley\s+del\s+impuesto\s+al\s+valor\s+agregado|ley\s+del\s+iva|liva|'
    r'ley\s+aduanera|'
    r'ley\s+del\s+impuesto\s+especial\s+sobre\s+producción\s+y\s+servicios|ley\s+del\s+ieps|lieps|'
    r'ley\s+federal\s+del\s+trabajo|'
    r'ley\s+del\s+seguro\s+social|'
    r'ley\s+del\s+infonavit|'
    r'ley\s+del\s+issste|'
    r'ley\s+de\s+ingresos(?:\s+de\s+la\s+federación)?|'
    r'ley\s+federal\s+de\s+derechos\s+del\s+contribuyente'
)

# Regex para detectar referencias a artículos (patrón estándar)
# Captura: artículo(s) NUM (fracción ROMAN)? (inciso LETRA)? de LEY
PATRON_REFERENCIA = re.compile(
    r'artículos?\s+'
    r'(\d+[o]?(?:-[A-Z]+)?)'                           # Número de artículo (grupo 1)
    r'(?:\s*,?\s*(?:fracci[oó]ne?s?)\s+([IVXLCDM]+))?'  # Fracción opcional (grupo 2)
    r'(?:\s*,?\s*(?:inciso)\s+([a-z])\))?'            # Inciso opcional (grupo 3)
    r'\s+(?:de\s+|del\s+)'
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
    r'\s+(?:de\s+|del\s+)'
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


def extraer_referencias(contenido: dict, ley_codigo: str, indice: dict) -> dict:
    """
    Extrae todas las referencias de una ley y genera mapa para renderizado.

    Usa tres patrones:
    - Estándar: artículo N fracción X de LEY
    - Invertido: fracción X del artículo N de LEY
    - Lista: artículos 94, 97, 116 fracción III de LEY

    Estructura de salida:
    {
        "123": {
            "artículo 4o de esta Constitución": {
                "ley": "CPEUM",
                "articulo": "4",
                "parrafo": 1
            }
        }
    }
    """
    referencias_ley = {}

    for art in contenido.get("articulos", []):
        art_num = art.get("numero")
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

            # Buscar todas las referencias estructurales
            for match in PATRON_ESTRUCTURA.finditer(texto):
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

    # Resumen
    print("\n" + "=" * 60)
    print("Resumen:")
    print(f"  - Leyes procesadas: {leyes_procesadas}")
    print(f"  - Artículos totales: {articulos_total}")
    print(f"  - Referencias mapeadas: {referencias_total}")
    print(f"  - Tooltips estructurales: {tooltips_total}")
    print(f"  - TOC consolidado: {len(toc_global)} leyes")
    print(f"  - Destino: {ASTRO_DATA.relative_to(PROJECT_ROOT)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
