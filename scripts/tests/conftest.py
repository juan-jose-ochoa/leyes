"""
Fixtures para tests del parser RMF.

Proporciona datos de prueba para:
- Reglas simples y complejas
- Casos atípicos (numerales huérfanos, referencias largas, etc.)
- Rutas a archivos de prueba
"""

import pytest
from pathlib import Path
import sys

# Agregar scripts/ al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rmf.models import (
    ParrafoExtraido,
    Fraccion,
    Inciso,
    ReglaParseada,
    Division,
    Problema,
    TipoProblema,
    TipoDivision,
    FuenteDatos,
)


# =============================================================================
# RUTAS DE ARCHIVOS
# =============================================================================

@pytest.fixture
def base_dir():
    """Directorio raíz del proyecto."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def rmf_docx_path(base_dir):
    """Ruta al DOCX de RMF."""
    return base_dir / "doc" / "rmf" / "rmf_2025_full_converted.docx"


@pytest.fixture
def rmf_json_path(base_dir):
    """Ruta al JSON parseado de RMF."""
    return base_dir / "doc" / "rmf" / "rmf_parsed.json"


@pytest.fixture
def fixtures_multi_formato(base_dir):
    """Rutas a múltiples formatos para segunda pasada."""
    rmf_dir = base_dir / "doc" / "rmf"
    return {
        "docx_path": rmf_dir / "rmf_2025_full_converted.docx",
        "pdf_path": next(rmf_dir.glob("*.pdf"), None),
        "txt_path": next(rmf_dir.glob("*.txt"), None),
    }


# =============================================================================
# PÁRRAFOS DE PRUEBA
# =============================================================================

@pytest.fixture
def parrafo_regla_simple():
    """Párrafo con número de regla y contenido."""
    return ParrafoExtraido(
        texto="2.1.1. Para los efectos del artículo 4o., penúltimo párrafo del CFF.",
        es_italica=False,
        indice_original=100,
    )


@pytest.fixture
def parrafo_referencia():
    """Párrafo con referencia legal (itálica)."""
    return ParrafoExtraido(
        texto="CFF 4o., 17-D, RMF 2.1.39.",
        es_italica=True,
        indice_original=105,
    )


@pytest.fixture
def parrafo_referencia_larga():
    """Referencia larga con fecha al final."""
    return ParrafoExtraido(
        texto="CFF 14-A, Reglas a las que deberán sujetarse las Instituciones de Crédito, "
              "Casas de Bolsa, Fondos de Inversión, Sociedades de Inversión Especializadas "
              "de Fondos para el Retiro, Instituciones de Seguros, Instituciones de Fianzas "
              "y la Financiera Nacional de Desarrollo Agropecuario, Rural, Forestal y Pesquero, "
              "en sus Operaciones de Préstamo de Valores, 12/01/2007",
        es_italica=True,
        indice_original=200,
    )


@pytest.fixture
def parrafo_titulo_regla():
    """Párrafo con título de regla (itálica pero NO empieza con sigla)."""
    return ParrafoExtraido(
        texto="Operaciones de préstamo de títulos o valores. Casos en los que se considera que no hay enajenación",
        es_italica=True,
        indice_original=99,
    )


@pytest.fixture
def parrafo_fraccion():
    """Párrafo con fracción romana."""
    return ParrafoExtraido(
        texto="I. Las de cobertura cambiaria de corto plazo.",
        es_italica=False,
        indice_original=110,
    )


@pytest.fixture
def parrafo_romano_huerfano():
    """Numeral romano solo (problema de PDF→DOCX)."""
    return ParrafoExtraido(
        texto="II.",
        es_italica=False,
        indice_original=115,
    )


# =============================================================================
# SECUENCIAS DE PÁRRAFOS
# =============================================================================

@pytest.fixture
def secuencia_regla_simple():
    """Secuencia típica: título + número + contenido + referencia."""
    return [
        ParrafoExtraido(
            texto="Cobro de créditos fiscales determinados por autoridades federativas",
            es_italica=True,
            indice_original=100,
        ),
        ParrafoExtraido(
            texto="2.1.1. Para los efectos del artículo 4o., penúltimo párrafo del CFF.",
            es_italica=False,
            indice_original=101,
        ),
        ParrafoExtraido(
            texto="CFF 4o., LCF 13",
            es_italica=True,
            indice_original=102,
        ),
    ]


@pytest.fixture
def secuencia_regla_con_fracciones():
    """Regla con fracciones I., II., III."""
    return [
        ParrafoExtraido(
            texto="Concepto de operaciones financieras derivadas de deuda y de capital",
            es_italica=True,
            indice_original=200,
        ),
        ParrafoExtraido(
            texto="2.1.11. Para los efectos de los artículos 16-A del CFF y 20 de la Ley del ISR, "
                  "se consideran operaciones financieras derivadas de capital, entre otras, las siguientes:",
            es_italica=False,
            indice_original=201,
        ),
        ParrafoExtraido(
            texto="I. Las de cobertura cambiaria de corto plazo.",
            es_italica=False,
            indice_original=202,
        ),
        ParrafoExtraido(
            texto="II. Las realizadas con títulos opcionales 'warrants'.",
            es_italica=False,
            indice_original=203,
        ),
        ParrafoExtraido(
            texto="III. Los futuros extrabursátiles referidos a una divisa.",
            es_italica=False,
            indice_original=204,
        ),
        ParrafoExtraido(
            texto="CFF 16-A, LISR 20",
            es_italica=True,
            indice_original=205,
        ),
    ]


@pytest.fixture
def secuencia_numerales_huerfanos():
    """Caso atípico: numerales romanos huérfanos (II. y III. solos)."""
    return [
        ParrafoExtraido(
            texto="I. Las operaciones con títulos opcionales 'warrants', referidos al INPC.",
            es_italica=False,
            indice_original=300,
        ),
        ParrafoExtraido(
            texto="II.",
            es_italica=False,
            indice_original=301,
        ),
        ParrafoExtraido(
            texto="III.",
            es_italica=False,
            indice_original=302,
        ),
        ParrafoExtraido(
            texto="Las operaciones con futuros sobre tasas de interés nominales.",
            es_italica=False,
            indice_original=303,
        ),
        ParrafoExtraido(
            texto="Las operaciones con futuros sobre el nivel del INPC.",
            es_italica=False,
            indice_original=304,
        ),
    ]


# =============================================================================
# REGLAS PARSEADAS
# =============================================================================

@pytest.fixture
def regla_simple():
    """Regla parseada simple sin problemas."""
    return ReglaParseada(
        numero="2.1.1",
        titulo="Cobro de créditos fiscales determinados por autoridades federativas",
        contenido="Para los efectos del artículo 4o., penúltimo párrafo del CFF.",
        referencias="CFF 4o., LCF 13",
        division_path="TITULO 2 > CAPITULO 2.1",
        titulo_padre="2",
        capitulo_padre="2.1",
        orden_global=1,
        confianza=1.0,
    )


@pytest.fixture
def regla_con_fracciones():
    """Regla parseada con fracciones."""
    return ReglaParseada(
        numero="2.1.11",
        titulo="Concepto de operaciones financieras derivadas de deuda y de capital",
        contenido="Para los efectos de los artículos 16-A del CFF y 20 de la Ley del ISR.",
        referencias="CFF 16-A, LISR 20",
        fracciones=[
            Fraccion(numero="I", contenido="Las de cobertura cambiaria de corto plazo.", orden=1),
            Fraccion(numero="II", contenido="Las realizadas con títulos opcionales.", orden=2),
            Fraccion(numero="III", contenido="Los futuros extrabursátiles.", orden=3),
        ],
        division_path="TITULO 2 > CAPITULO 2.1",
        orden_global=11,
        confianza=1.0,
    )


@pytest.fixture
def regla_con_problema():
    """Regla con problema detectado."""
    regla = ReglaParseada(
        numero="2.1.5",
        titulo="",  # Sin título
        contenido="para los efectos del artículo",  # Inicia minúscula
        referencias=None,
        division_path="TITULO 2 > CAPITULO 2.1",
        orden_global=5,
    )
    regla.agregar_problema(Problema(
        tipo=TipoProblema.TITULO_AUSENTE,
        descripcion="No se encontró título para la regla",
        ubicacion="2.1.5",
        severidad="error",
    ))
    regla.agregar_problema(Problema(
        tipo=TipoProblema.CONTENIDO_INCOHERENTE,
        descripcion="El contenido inicia con minúscula",
        ubicacion="2.1.5",
        severidad="warning",
    ))
    return regla


# =============================================================================
# DIVISIONES
# =============================================================================

@pytest.fixture
def division_titulo():
    """División tipo Título."""
    return Division(
        tipo=TipoDivision.TITULO,
        numero="2",
        nombre="Código Fiscal de la Federación",
        numero_orden=2,
        orden_global=1,
        path_texto="TITULO 2",
        nivel=0,
    )


@pytest.fixture
def division_capitulo():
    """División tipo Capítulo."""
    return Division(
        tipo=TipoDivision.CAPITULO,
        numero="2.1",
        nombre="Disposiciones generales",
        numero_orden=1,
        orden_global=2,
        path_texto="TITULO 2 > CAPITULO 2.1",
        padre_tipo=TipoDivision.TITULO,
        padre_numero="2",
        nivel=1,
    )


# =============================================================================
# HELPERS
# =============================================================================

@pytest.fixture
def crear_regla():
    """Factory para crear reglas de prueba."""
    def _crear(
        numero: str = "2.1.1",
        titulo: str = "Título de prueba",
        contenido: str = "Contenido de prueba.",
        referencias: str = None,
        **kwargs
    ) -> ReglaParseada:
        return ReglaParseada(
            numero=numero,
            titulo=titulo,
            contenido=contenido,
            referencias=referencias,
            **kwargs
        )
    return _crear


@pytest.fixture
def crear_parrafo():
    """Factory para crear párrafos de prueba."""
    def _crear(
        texto: str,
        es_italica: bool = False,
        indice: int = 0,
    ) -> ParrafoExtraido:
        return ParrafoExtraido(
            texto=texto,
            es_italica=es_italica,
            indice_original=indice,
        )
    return _crear
