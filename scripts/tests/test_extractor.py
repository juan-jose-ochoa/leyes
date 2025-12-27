"""
Tests para el módulo de extracción (Fase 1).

Prueba:
- Extracción de párrafos de DOCX
- Detección de formato (itálica, negrita)
- Pre-procesamiento de fragmentación
- Filtrado de elementos no-contenido
"""

import pytest
from pathlib import Path
import sys

# Agregar scripts/ al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rmf.extractor import (
    DocxXmlExtractor,
    TxtExtractor,
    crear_extractor,
    PATRON_PAGINA,
    PATRON_ROMANO_SOLO,
)
from rmf.models import ParrafoExtraido, FuenteDatos


# =============================================================================
# TESTS DE PATRONES
# =============================================================================

class TestPatrones:
    """Tests para patrones regex de filtrado."""

    def test_patron_pagina_simple(self):
        """Detecta '27 de 812'."""
        assert PATRON_PAGINA.match("27 de 812")

    def test_patron_pagina_con_texto(self):
        """Detecta 'Página 27 de 812'."""
        assert PATRON_PAGINA.match("Página 27 de 812")

    def test_patron_pagina_no_match(self):
        """No detecta texto normal."""
        assert not PATRON_PAGINA.match("Para los efectos del artículo")

    def test_patron_romano_solo_ii(self):
        """Detecta 'II.' solo."""
        assert PATRON_ROMANO_SOLO.match("II.")

    def test_patron_romano_solo_iii(self):
        """Detecta 'III.' solo."""
        assert PATRON_ROMANO_SOLO.match("III.")

    def test_patron_romano_solo_con_contenido(self):
        """No detecta 'II. Las operaciones...' (tiene contenido)."""
        assert not PATRON_ROMANO_SOLO.match("II. Las operaciones financieras")

    def test_patron_romano_solo_x(self):
        """Detecta 'X.' solo."""
        assert PATRON_ROMANO_SOLO.match("X.")

    def test_patron_romano_solo_vi(self):
        """Detecta 'VI.' solo."""
        assert PATRON_ROMANO_SOLO.match("VI.")


# =============================================================================
# TESTS DE PREPROCESAMIENTO
# =============================================================================

class TestPreprocesamiento:
    """Tests para lógica de preprocesamiento de párrafos."""

    def test_fusionar_numeral_huerfano_simple(self, crear_parrafo):
        """Fusiona un numeral huérfano con su contenido."""
        paragraphs = [
            crear_parrafo("II.", indice=0),
            crear_parrafo("Las operaciones financieras derivadas.", indice=1),
        ]

        extractor = DocxXmlExtractor.__new__(DocxXmlExtractor)
        resultado = extractor._preprocesar(paragraphs)

        assert len(resultado) == 1
        assert resultado[0].texto == "II. Las operaciones financieras derivadas."

    def test_fusionar_numerales_consecutivos(self, crear_parrafo):
        """Fusiona múltiples numerales huérfanos consecutivos."""
        paragraphs = [
            crear_parrafo("II.", indice=0),
            crear_parrafo("III.", indice=1),
            crear_parrafo("Las operaciones tipo A.", indice=2),
            crear_parrafo("Las operaciones tipo B.", indice=3),
        ]

        extractor = DocxXmlExtractor.__new__(DocxXmlExtractor)
        resultado = extractor._preprocesar(paragraphs)

        assert len(resultado) == 2
        assert resultado[0].texto == "II. Las operaciones tipo A."
        assert resultado[1].texto == "III. Las operaciones tipo B."

    def test_no_fusionar_referencia(self, crear_parrafo):
        """No fusiona párrafos que son referencias legales."""
        paragraphs = [
            crear_parrafo("CFF 14-B, LISR 24", indice=0),
            crear_parrafo("Título de la siguiente regla", indice=1),
        ]

        extractor = DocxXmlExtractor.__new__(DocxXmlExtractor)
        # _es_fragmento_continuacion debe retornar False para referencias
        assert not extractor._es_fragmento_continuacion("CFF 14-B, LISR 24")

    def test_fragmento_corto_sin_punto(self, crear_parrafo):
        """Identifica fragmento corto sin punto como continuación."""
        extractor = DocxXmlExtractor.__new__(DocxXmlExtractor)
        assert extractor._es_fragmento_continuacion("forwards")
        assert extractor._es_fragmento_continuacion("con fechas")

    def test_fragmento_largo_no_es_continuacion(self, crear_parrafo):
        """Texto largo no es fragmento de continuación."""
        extractor = DocxXmlExtractor.__new__(DocxXmlExtractor)
        texto_largo = "Para los efectos del artículo 14-B del CFF"
        assert not extractor._es_fragmento_continuacion(texto_largo)


# =============================================================================
# TESTS DE FILTRADO
# =============================================================================

class TestFiltrado:
    """Tests para filtrado de elementos no-contenido."""

    def test_filtrar_numero_pagina(self):
        """Filtra números de página."""
        extractor = DocxXmlExtractor.__new__(DocxXmlExtractor)
        assert extractor._debe_filtrar("Página 27 de 812")
        assert extractor._debe_filtrar("27 de 812")

    def test_filtrar_encabezado_rmf(self):
        """Filtra encabezado repetitivo de RMF."""
        extractor = DocxXmlExtractor.__new__(DocxXmlExtractor)
        assert extractor._debe_filtrar("Resolución Miscelánea Fiscal para 2025")

    def test_filtrar_nota_documento(self):
        """Filtra notas del documento."""
        extractor = DocxXmlExtractor.__new__(DocxXmlExtractor)
        assert extractor._debe_filtrar(
            "NOTA: Este documento constituye una compilación de disposiciones"
        )

    def test_no_filtrar_contenido_normal(self):
        """No filtra contenido normal."""
        extractor = DocxXmlExtractor.__new__(DocxXmlExtractor)
        assert not extractor._debe_filtrar("Para los efectos del artículo 4o.")
        assert not extractor._debe_filtrar("2.1.1. Cobro de créditos fiscales")


# =============================================================================
# TESTS DE FACTORY
# =============================================================================

class TestFactory:
    """Tests para factory de extractores."""

    def test_crear_extractor_docx(self, rmf_docx_path):
        """Crea DocxXmlExtractor para .docx."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        extractor = crear_extractor(rmf_docx_path)
        assert isinstance(extractor, DocxXmlExtractor)
        assert extractor.fuente == FuenteDatos.DOCX_XML

    def test_crear_extractor_txt(self, tmp_path):
        """Crea TxtExtractor para .txt."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Línea de prueba")

        extractor = crear_extractor(txt_file)
        assert isinstance(extractor, TxtExtractor)
        assert extractor.fuente == FuenteDatos.TXT

    def test_crear_extractor_tipo_invalido(self, tmp_path):
        """Lanza error para tipo de archivo no soportado."""
        file = tmp_path / "test.xyz"
        file.write_text("contenido")

        with pytest.raises(ValueError, match="no soportado"):
            crear_extractor(file)


# =============================================================================
# TESTS DE EXTRACTOR TXT
# =============================================================================

class TestTxtExtractor:
    """Tests para extractor de texto plano."""

    def test_extraer_lineas(self, tmp_path):
        """Extrae líneas de archivo TXT."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Línea 1\nLínea 2\n\nLínea 3")

        extractor = TxtExtractor(txt_file)
        paragraphs = extractor.extraer()

        assert len(paragraphs) == 3
        assert paragraphs[0].texto == "Línea 1"
        assert paragraphs[1].texto == "Línea 2"
        assert paragraphs[2].texto == "Línea 3"

    def test_txt_sin_formato(self, tmp_path):
        """TXT no tiene información de formato."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Texto de prueba")

        extractor = TxtExtractor(txt_file)
        paragraphs = extractor.extraer()

        assert paragraphs[0].es_italica is False
        assert paragraphs[0].es_negrita is False
        assert paragraphs[0].fuente == FuenteDatos.TXT


# =============================================================================
# TESTS DE INTEGRACIÓN CON DOCX REAL
# =============================================================================

@pytest.mark.integracion
class TestDocxExtractorIntegracion:
    """Tests de integración con archivo DOCX real."""

    def test_extraer_docx_real(self, rmf_docx_path):
        """Extrae párrafos de DOCX real."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        # Debe tener muchos párrafos
        assert len(paragraphs) > 1000

        # Verificar que hay contenido
        textos = [p.texto for p in paragraphs]
        assert any("2.1.1" in t for t in textos)

    def test_detectar_italica_en_docx_real(self, rmf_docx_path):
        """Detecta párrafos en itálica en DOCX real."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        # Debe haber párrafos en itálica (referencias)
        italicos = [p for p in paragraphs if p.es_italica]
        assert len(italicos) > 0

        # Las referencias empiezan con sigla de ley
        siglas = ('CFF', 'LISR', 'LIVA', 'RMF')
        referencias = [
            p for p in italicos
            if any(p.texto.upper().startswith(s) for s in siglas)
        ]
        assert len(referencias) > 0

    def test_buscar_regla_especifica(self, rmf_docx_path):
        """Busca una regla específica por número."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        extractor = DocxXmlExtractor(rmf_docx_path)
        contenido = extractor.buscar_regla("2.1.1")

        assert contenido is not None
        assert len(contenido) > 0

    def test_cache_funciona(self, rmf_docx_path):
        """Verifica que el cache de párrafos funciona."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        extractor = DocxXmlExtractor(rmf_docx_path)

        # Primera extracción
        p1 = extractor.extraer()

        # Segunda extracción (debe usar cache)
        p2 = extractor.extraer()

        # Deben ser el mismo objeto (cache)
        assert p1 is p2
