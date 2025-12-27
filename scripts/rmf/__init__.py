"""
Módulo de parseo de RMF (Resolución Miscelánea Fiscal)

Arquitectura en 4 fases:
1. Extracción: Obtener texto de múltiples fuentes (DOCX XML, PDF, TXT)
2. Parsing: Parsear según estructura esperada ("deber ser")
3. Validación: Detectar problemas + segunda pasada para casos atípicos
4. Output: Generar salida estructurada con métricas de calidad
"""

from .models import (
    ParrafoExtraido,
    Fraccion,
    Inciso,
    ReglaParseada,
    Division,
    Problema,
    Resolucion,
    ResultadoParseo,
    TipoProblema,
    TipoDivision,
    FuenteDatos,
)
from .extractor import (
    Extractor,
    DocxXmlExtractor,
    PdfExtractor,
    TxtExtractor,
    crear_extractor,
)
from .parser import ParserRMF, es_referencia_final
from .validador import ValidadorEstructural, InspectorMultiFormato, HeuristicasRMF

__all__ = [
    # Models
    'ParrafoExtraido',
    'Fraccion',
    'Inciso',
    'ReglaParseada',
    'Division',
    'Problema',
    'Resolucion',
    'ResultadoParseo',
    'TipoProblema',
    'TipoDivision',
    'FuenteDatos',
    # Extractor
    'Extractor',
    'DocxXmlExtractor',
    'PdfExtractor',
    'TxtExtractor',
    'crear_extractor',
    # Parser
    'ParserRMF',
    'es_referencia_final',
    # Validador
    'ValidadorEstructural',
    'InspectorMultiFormato',
    'HeuristicasRMF',
]
