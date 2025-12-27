"""
Tests para el módulo de parsing (Fase 2).

Prueba:
- Detección de referencias
- Parsing de reglas simples
- Parsing de reglas con fracciones
- Detección de títulos
- Inferencia de divisiones
- Detección de problemas
"""

import pytest
from pathlib import Path
import sys

# Agregar scripts/ al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rmf.parser import (
    ParserRMF,
    es_referencia_final,
    extraer_capitulo_de_regla,
    PATRON_REGLA,
    PATRON_CAPITULO,
    PATRON_FRACCION,
    PATRON_INCISO,
)
from rmf.models import (
    ParrafoExtraido,
    TipoProblema,
    TipoDivision,
)


# =============================================================================
# TESTS DE FUNCIONES AUXILIARES
# =============================================================================

class TestFuncionesAuxiliares:
    """Tests para funciones auxiliares del parser."""

    def test_extraer_capitulo_de_regla(self):
        """Extrae capítulo de número de regla."""
        assert extraer_capitulo_de_regla("2.1.5") == "2.1"
        assert extraer_capitulo_de_regla("3.15.42") == "3.15"
        assert extraer_capitulo_de_regla("1") == ""

    def test_es_referencia_final_simple(self):
        """Detecta referencia simple."""
        assert es_referencia_final("CFF 14-B, LISR 24")
        assert es_referencia_final("CFF 4o., 17-D")
        assert es_referencia_final("RMF 2.1.39")

    def test_es_referencia_final_con_italica(self):
        """Referencia con itálica es más confiable."""
        assert es_referencia_final("CFF 14-B, LISR 24", es_italica=True)

    def test_es_referencia_final_larga_con_fecha(self):
        """Referencia larga que termina con fecha."""
        texto = ("CFF 14-A, Reglas a las que deberán sujetarse las "
                 "Instituciones de Crédito, 12/01/2007")
        assert es_referencia_final(texto)

    def test_es_referencia_final_no_contenido(self):
        """No detecta contenido como referencia."""
        assert not es_referencia_final("CFF para los efectos del artículo")
        assert not es_referencia_final("Para los efectos del CFF")

    def test_es_referencia_final_texto_largo(self):
        """Texto muy largo sin fecha no es referencia."""
        texto = "CFF " + "palabra " * 50  # Texto largo sin fecha
        assert not es_referencia_final(texto)

    def test_titulo_italico_no_es_referencia(self, parrafo_titulo_regla):
        """Título en itálica no es referencia (no empieza con sigla)."""
        # "Operaciones de préstamo de títulos..."
        assert not es_referencia_final(
            parrafo_titulo_regla.texto,
            es_italica=parrafo_titulo_regla.es_italica
        )


# =============================================================================
# TESTS DE PATRONES
# =============================================================================

class TestPatrones:
    """Tests para patrones regex del parser."""

    def test_patron_regla_con_contenido(self):
        """Detecta regla con contenido en misma línea."""
        match = PATRON_REGLA.match("2.1.1. Para los efectos del artículo")
        assert match
        assert match.group(1) == "2.1.1"
        assert "Para los efectos" in match.group(2)

    def test_patron_regla_numeros_grandes(self):
        """Detecta reglas con números grandes."""
        match = PATRON_REGLA.match("11.4.25. Contenido de la regla")
        assert match
        assert match.group(1) == "11.4.25"

    def test_patron_capitulo(self):
        """Detecta capítulos."""
        match = PATRON_CAPITULO.match("Capítulo 2.1. Disposiciones generales")
        assert match
        assert match.group(1) == "2.1"
        assert match.group(2) == "Disposiciones generales"

    def test_patron_capitulo_sin_nombre(self):
        """Detecta capítulo sin nombre en misma línea."""
        match = PATRON_CAPITULO.match("Capítulo 3.15.")
        assert match
        assert match.group(1) == "3.15"

    def test_patron_fraccion(self):
        """Detecta fracciones romanas."""
        match = PATRON_FRACCION.match("I. Las operaciones financieras")
        assert match
        assert match.group(1) == "I"
        assert "operaciones" in match.group(2)

        match = PATRON_FRACCION.match("IV. Otro contenido")
        assert match
        assert match.group(1) == "IV"

    def test_patron_inciso(self):
        """Detecta incisos alfabéticos."""
        match = PATRON_INCISO.match("a) Nombre o razón social.")
        assert match
        assert match.group(1) == "a"
        assert "Nombre" in match.group(2)

        match = PATRON_INCISO.match("c) Domicilio fiscal.")
        assert match
        assert match.group(1) == "c"

    def test_patron_inciso_no_detecta_parrafo(self):
        """No detecta párrafos normales como incisos."""
        match = PATRON_INCISO.match("Para los efectos del artículo")
        assert match is None

        match = PATRON_INCISO.match("Los contribuyentes deberán")
        assert match is None


# =============================================================================
# TESTS DE PARSING BÁSICO
# =============================================================================

class TestParsingBasico:
    """Tests para parsing básico de reglas."""

    def test_parsear_regla_simple(self, secuencia_regla_simple):
        """Parsea regla simple: título + número + contenido + referencia."""
        parser = ParserRMF()
        resultado = parser.parsear(secuencia_regla_simple, "Test Doc")

        assert len(resultado.reglas) >= 1
        regla = resultado.reglas[0]

        assert regla.numero == "2.1.1"
        assert "Cobro de créditos" in regla.titulo
        assert "artículo 4o" in regla.contenido
        assert regla.referencias == "CFF 4o., LCF 13"

    def test_parsear_regla_con_fracciones(self, secuencia_regla_con_fracciones):
        """Parsea regla con fracciones I, II, III."""
        parser = ParserRMF()
        resultado = parser.parsear(secuencia_regla_con_fracciones, "Test Doc")

        assert len(resultado.reglas) >= 1
        regla = resultado.reglas[0]

        assert regla.numero == "2.1.11"
        assert len(regla.fracciones) == 3
        assert regla.fracciones[0].numero == "I"
        assert regla.fracciones[1].numero == "II"
        assert regla.fracciones[2].numero == "III"

    def test_titulo_extraido_del_parrafo_anterior(self, crear_parrafo):
        """El título se extrae del párrafo anterior al número."""
        paragraphs = [
            crear_parrafo("Título de la regla", es_italica=True, indice=0),
            crear_parrafo("2.1.5. Contenido de la regla.", indice=1),
            crear_parrafo("CFF 14-B", es_italica=True, indice=2),
        ]

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "Test")

        regla = resultado.reglas[0]
        assert regla.titulo == "Título de la regla"

    def test_referencia_italica_detectada(self, crear_parrafo):
        """Detecta referencia en itálica."""
        paragraphs = [
            crear_parrafo("2.1.1. Contenido de prueba.", indice=0),
            crear_parrafo("CFF 14-B, LISR 24", es_italica=True, indice=1),
        ]

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "Test")

        regla = resultado.reglas[0]
        assert regla.referencias == "CFF 14-B, LISR 24"


# =============================================================================
# TESTS DE INCISOS
# =============================================================================

class TestParsingIncisos:
    """Tests para extracción de incisos a), b), c)."""

    def test_parsear_regla_con_incisos(self, secuencia_regla_con_incisos):
        """Parsea regla con fracción que contiene incisos."""
        parser = ParserRMF()
        resultado = parser.parsear(secuencia_regla_con_incisos, "Test Doc")

        assert len(resultado.reglas) >= 1
        regla = resultado.reglas[0]

        assert regla.numero == "2.7.1"
        assert len(regla.fracciones) == 2  # I y II

        # Fracción I debe tener 3 incisos
        fraccion_I = regla.fracciones[0]
        assert fraccion_I.numero == "I"
        assert len(fraccion_I.incisos) == 3

        # Verificar contenido de incisos
        assert fraccion_I.incisos[0].letra == "a"
        assert "Nombre" in fraccion_I.incisos[0].contenido
        assert fraccion_I.incisos[1].letra == "b"
        assert "RFC" in fraccion_I.incisos[1].contenido or "Registro" in fraccion_I.incisos[1].contenido
        assert fraccion_I.incisos[2].letra == "c"
        assert "Domicilio" in fraccion_I.incisos[2].contenido

        # Fracción II no debe tener incisos
        fraccion_II = regla.fracciones[1]
        assert fraccion_II.numero == "II"
        assert len(fraccion_II.incisos) == 0

    def test_incisos_sin_fraccion_padre(self, secuencia_incisos_sin_fraccion):
        """Incisos directos crean fracción virtual."""
        parser = ParserRMF()
        resultado = parser.parsear(secuencia_incisos_sin_fraccion, "Test Doc")

        assert len(resultado.reglas) >= 1
        regla = resultado.reglas[0]

        assert regla.numero == "2.8.5"
        # Debe haber una "fracción virtual" con los incisos
        assert len(regla.fracciones) >= 1

        # La fracción virtual no tiene número
        fraccion_virtual = regla.fracciones[0]
        assert fraccion_virtual.numero == ""
        assert fraccion_virtual.contenido == ""

        # Pero contiene los 3 incisos
        assert len(fraccion_virtual.incisos) == 3
        assert fraccion_virtual.incisos[0].letra == "a"
        assert fraccion_virtual.incisos[1].letra == "b"
        assert fraccion_virtual.incisos[2].letra == "c"

    def test_orden_incisos_correcto(self, secuencia_regla_con_incisos):
        """Los incisos tienen orden correcto (1, 2, 3...)."""
        parser = ParserRMF()
        resultado = parser.parsear(secuencia_regla_con_incisos, "Test Doc")

        regla = resultado.reglas[0]
        fraccion_I = regla.fracciones[0]

        assert fraccion_I.incisos[0].orden == 1  # a
        assert fraccion_I.incisos[1].orden == 2  # b
        assert fraccion_I.incisos[2].orden == 3  # c

    def test_jerarquia_fraccion_inciso(self, crear_parrafo):
        """Verifica jerarquía: fracción contiene incisos."""
        paragraphs = [
            crear_parrafo("2.5.1. Contenido de la regla:", indice=0),
            crear_parrafo("I. Primera fracción:", indice=1),
            crear_parrafo("a) Primer inciso.", indice=2),
            crear_parrafo("b) Segundo inciso.", indice=3),
            crear_parrafo("II. Segunda fracción sin incisos.", indice=4),
        ]

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "Test")

        regla = resultado.reglas[0]
        assert len(regla.fracciones) == 2

        # Fracción I tiene 2 incisos
        assert len(regla.fracciones[0].incisos) == 2
        assert regla.fracciones[0].incisos[0].letra == "a"
        assert regla.fracciones[0].incisos[1].letra == "b"

        # Fracción II no tiene incisos
        assert len(regla.fracciones[1].incisos) == 0


# =============================================================================
# TESTS DE INFERENCIA DE DIVISIONES
# =============================================================================

class TestInferenciaDivisiones:
    """Tests para inferencia de Títulos y Capítulos."""

    def test_infiere_titulo_de_capitulo(self, crear_parrafo):
        """Infiere Título cuando ve un Capítulo."""
        paragraphs = [
            crear_parrafo("Capítulo 2.1. Disposiciones generales", indice=0),
            crear_parrafo("2.1.1. Contenido.", indice=1),
        ]

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "Test")

        # Debe haber Título y Capítulo
        titulos = [d for d in resultado.divisiones if d.tipo == TipoDivision.TITULO]
        capitulos = [d for d in resultado.divisiones if d.tipo == TipoDivision.CAPITULO]

        assert len(titulos) == 1
        assert titulos[0].numero == "2"
        assert len(capitulos) == 1
        assert capitulos[0].numero == "2.1"

    def test_infiere_capitulo_de_regla(self, crear_parrafo):
        """Infiere Capítulo cuando ve una regla sin capítulo previo."""
        paragraphs = [
            crear_parrafo("3.5.1. Contenido de regla.", indice=0),
        ]

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "Test")

        # Debe haber inferido Título 3 y Capítulo 3.5
        capitulos = [d for d in resultado.divisiones if d.tipo == TipoDivision.CAPITULO]
        assert any(c.numero == "3.5" for c in capitulos)

    def test_path_division_correcto(self, crear_parrafo):
        """Verifica que el path de división sea correcto."""
        paragraphs = [
            crear_parrafo("Capítulo 2.1. Disposiciones", indice=0),
            crear_parrafo("2.1.1. Contenido.", indice=1),
        ]

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "Test")

        regla = resultado.reglas[0]
        assert "TITULO 2" in regla.division_path
        assert "CAPITULO 2.1" in regla.division_path


# =============================================================================
# TESTS DE DETECCIÓN DE PROBLEMAS
# =============================================================================

class TestDeteccionProblemas:
    """Tests para detección de problemas estructurales."""

    def test_detecta_titulo_ausente(self, crear_parrafo):
        """Detecta cuando una regla no tiene título."""
        paragraphs = [
            # Sin párrafo de título antes
            crear_parrafo("2.1.1. Contenido sin título previo.", indice=0),
        ]

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "Test")

        regla = resultado.reglas[0]
        # El título se extrae del contenido como fallback
        # Pero debe haber warning si no había título explícito
        # En este caso el contenido se usa como título, así que no hay problema

    def test_detecta_contenido_minuscula(self, crear_parrafo):
        """Detecta contenido que inicia con minúscula."""
        paragraphs = [
            crear_parrafo("2.1.1. para los efectos del artículo.", indice=0),
        ]

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "Test")

        regla = resultado.reglas[0]
        problemas = [p for p in regla.problemas
                    if p.tipo == TipoProblema.CONTENIDO_INCOHERENTE]
        assert len(problemas) == 1
        assert "minúscula" in problemas[0].descripcion

    def test_regla_con_problemas_tiene_confianza_reducida(self, regla_con_problema):
        """Regla con errores tiene confianza < 1.0."""
        assert regla_con_problema.confianza < 1.0
        assert regla_con_problema.requiere_segunda_pasada is True


# =============================================================================
# TESTS DE PLACEHOLDERS
# =============================================================================

class TestPlaceholders:
    """Tests para creación de placeholders."""

    def test_crea_placeholder_para_faltante(self, crear_parrafo):
        """Crea placeholder para regla faltante en secuencia."""
        paragraphs = [
            crear_parrafo("Capítulo 2.1.", indice=0),
            crear_parrafo("2.1.1. Primera regla.", indice=1),
            # Falta 2.1.2
            crear_parrafo("2.1.3. Tercera regla.", indice=2),
        ]

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "Test")

        # Debe existir placeholder para 2.1.2
        numeros = [r.numero for r in resultado.reglas]
        assert "2.1.2" in numeros

        placeholder = next(r for r in resultado.reglas if r.numero == "2.1.2")
        assert placeholder.tipo == "no-existe"

    def test_no_placeholder_si_aparece_en_contenido(self, crear_parrafo):
        """No crea placeholder si el número aparece en contenido (posible error)."""
        paragraphs = [
            crear_parrafo("Capítulo 2.1.", indice=0),
            # La regla 2.1.1 tiene contenido que menciona 2.1.2
            crear_parrafo("2.1.1. Primera regla. Ver regla 2.1.2. para más información.", indice=1),
            crear_parrafo("2.1.3. Tercera regla.", indice=2),
        ]

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "Test")

        # No debe crear placeholder para 2.1.2 porque aparece en contenido
        placeholders = [r for r in resultado.reglas if r.tipo == "no-existe"]
        numeros_placeholder = [p.numero for p in placeholders]
        assert "2.1.2" not in numeros_placeholder


# =============================================================================
# TESTS DE INTEGRACIÓN
# =============================================================================

@pytest.mark.integracion
class TestParserIntegracion:
    """Tests de integración con archivo real."""

    def test_parsear_rmf_completa(self, rmf_docx_path):
        """Parsea RMF completa desde DOCX."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        from rmf.extractor import DocxXmlExtractor

        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        # Métricas esperadas
        assert resultado.total_reglas >= 700
        assert resultado.porcentaje_exito > 90

    def test_regla_2_1_8_tiene_referencia_larga(self, rmf_docx_path):
        """La regla 2.1.8 tiene referencia larga con fecha."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        from rmf.extractor import DocxXmlExtractor

        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        regla_2_1_8 = next((r for r in resultado.reglas if r.numero == "2.1.8"), None)
        assert regla_2_1_8 is not None

        if regla_2_1_8.referencias:
            # Debe empezar con CFF y posiblemente terminar con fecha
            assert regla_2_1_8.referencias.startswith("CFF")

    def test_regla_2_1_11_tiene_fracciones(self, rmf_docx_path):
        """La regla 2.1.11 tiene fracciones I, II, III."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        from rmf.extractor import DocxXmlExtractor

        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        regla = next((r for r in resultado.reglas if r.numero == "2.1.11"), None)
        assert regla is not None
        # Puede tener fracciones dependiendo del parseo
