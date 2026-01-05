"""
Modulo de extractores de leyes.

Proporciona extractores especializados para diferentes tipos de documentos legales:
- ExtractorGeneral: Para leyes con estructura estandar (CFF, LISR, etc.)
- ExtractorRMF: Para Resolucion Miscelanea Fiscal

Uso:
    from extractor import crear_extractor

    extractor = crear_extractor(codigo, config)
    contenido = extractor.extraer()
    extractor.guardar(contenido)
"""

from .base import (
    ExtractorBase,
    Parrafo,
    Articulo,
    Division,
    crear_extractor,
    BASE_DIR,
)

# Imports lazy - solo se cargan cuando se necesitan
# Esto evita errores si falta pdfplumber o pymupdf

__all__ = [
    'ExtractorBase',
    'Parrafo',
    'Articulo',
    'Division',
    'crear_extractor',
    'BASE_DIR',
]


def __getattr__(name):
    """Lazy loading de clases de extractor."""
    if name == 'ExtractorGeneral':
        from .general import ExtractorGeneral
        return ExtractorGeneral
    elif name == 'ExtractorRMF':
        from .rmf import ExtractorRMF
        return ExtractorRMF
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
