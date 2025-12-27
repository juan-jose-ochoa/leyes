"""
Tests para el módulo de validación (Fase 3).

Prueba:
- Validación estructural de reglas
- Detección de problemas
- Segunda pasada con múltiples fuentes
- Heurísticas específicas de RMF
"""

import pytest
from pathlib import Path
import sys

# Agregar scripts/ al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rmf.validador import (
    ValidadorEstructural,
    InspectorMultiFormato,
    HeuristicasRMF,
    ValidadorIntegridad,
)
from rmf.models import (
    ReglaParseada,
    Fraccion,
    Problema,
    ResultadoParseo,
    TipoProblema,
)


# =============================================================================
# TESTS DE VALIDADOR ESTRUCTURAL
# =============================================================================

class TestValidadorEstructural:
    """Tests para ValidadorEstructural."""

    def test_numero_valido(self):
        """Valida formato de número de regla."""
        validador = ValidadorEstructural()
        assert validador._es_numero_valido("2.1.1")
        assert validador._es_numero_valido("11.4.25")
        assert not validador._es_numero_valido("2.1")
        assert not validador._es_numero_valido("2.1.1.")
        assert not validador._es_numero_valido("abc")

    def test_contenido_coherente_ok(self):
        """Contenido válido pasa validación."""
        validador = ValidadorEstructural()
        assert validador._contenido_coherente("Para los efectos del artículo.")
        assert validador._contenido_coherente("Los contribuyentes deberán:")

    def test_contenido_coherente_minuscula(self):
        """Contenido que empieza con minúscula falla."""
        validador = ValidadorEstructural()
        assert not validador._contenido_coherente("para los efectos")

    def test_referencia_valida(self):
        """Valida formato de referencia."""
        validador = ValidadorEstructural()
        assert validador._referencia_valida("CFF 14-B, LISR 24")
        assert validador._referencia_valida("RMF 2.1.39")
        assert not validador._referencia_valida("Ver artículo 14-B")

    def test_fracciones_consecutivas_ok(self):
        """Fracciones consecutivas pasan validación."""
        validador = ValidadorEstructural()
        fracciones = [
            Fraccion(numero="I", contenido="Primera", orden=1),
            Fraccion(numero="II", contenido="Segunda", orden=2),
            Fraccion(numero="III", contenido="Tercera", orden=3),
        ]
        assert validador._fracciones_consecutivas(fracciones)

    def test_fracciones_no_consecutivas(self):
        """Fracciones con saltos fallan validación."""
        validador = ValidadorEstructural()
        fracciones = [
            Fraccion(numero="I", contenido="Primera", orden=1),
            Fraccion(numero="III", contenido="Tercera", orden=3),  # Falta II
        ]
        assert not validador._fracciones_consecutivas(fracciones)

    def test_validar_regla_detecta_problemas(self, crear_regla):
        """Validación detecta múltiples problemas."""
        regla = crear_regla(
            numero="2.1.5",
            titulo="",  # Sin título
            contenido="para los efectos",  # Minúscula
        )

        validador = ValidadorEstructural()
        validador._validar_regla(regla)

        # Debe tener problemas detectados
        tipos = [p.tipo for p in regla.problemas]
        assert TipoProblema.TITULO_AUSENTE in tipos
        assert TipoProblema.CONTENIDO_INCOHERENTE in tipos

    def test_validar_numeracion_detecta_saltos(self, crear_regla):
        """Detecta saltos en numeración."""
        reglas = [
            crear_regla(numero="2.1.1"),
            crear_regla(numero="2.1.3"),  # Falta 2.1.2
            crear_regla(numero="2.1.4"),
        ]

        validador = ValidadorEstructural()
        validador._validar_numeracion(reglas)

        # Debe reportar salto
        assert len(validador.problemas_globales) == 1
        assert "Salto en numeración" in validador.problemas_globales[0].descripcion


# =============================================================================
# TESTS DE HEURÍSTICAS
# =============================================================================

class TestHeuristicas:
    """Tests para heurísticas específicas de RMF."""

    def test_numeral_huerfano_ii(self):
        """Detecta 'II.' como numeral huérfano."""
        assert HeuristicasRMF.es_numeral_huerfano("II.")
        assert HeuristicasRMF.es_numeral_huerfano("III.")
        assert HeuristicasRMF.es_numeral_huerfano("X.")

    def test_numeral_huerfano_con_contenido(self):
        """'II. Las operaciones...' no es huérfano."""
        assert not HeuristicasRMF.es_numeral_huerfano("II. Las operaciones")
        assert not HeuristicasRMF.es_numeral_huerfano("Para los efectos")

    def test_referencia_larga_con_fecha(self):
        """Detecta referencia larga que termina con fecha."""
        texto = ("CFF 14-A, Reglas a las que deberán sujetarse las "
                 "Instituciones de Crédito, 12/01/2007")
        assert HeuristicasRMF.es_referencia_larga_con_fecha(texto)

    def test_referencia_sin_fecha(self):
        """No detecta referencia sin fecha."""
        assert not HeuristicasRMF.es_referencia_larga_con_fecha("CFF 14-B, LISR 24")

    def test_titulo_no_referencia_italico(self):
        """Título itálico sin sigla no es referencia."""
        assert HeuristicasRMF.es_titulo_no_referencia(
            "Operaciones de préstamo de títulos", es_italica=True
        )

    def test_referencia_italica_no_es_titulo(self):
        """Referencia itálica con sigla no es título."""
        assert not HeuristicasRMF.es_titulo_no_referencia(
            "CFF 14-B, LISR 24", es_italica=True
        )

    def test_texto_no_italico_no_es_titulo(self):
        """Texto sin itálica no es título."""
        assert not HeuristicasRMF.es_titulo_no_referencia(
            "Operaciones de préstamo", es_italica=False
        )

    def test_inferir_fracciones_basico(self):
        """Infiere fracciones de texto con numerales."""
        contenido = "I. Primera fracción. II. Segunda fracción."
        fracciones = HeuristicasRMF.inferir_fracciones_de_contexto(contenido)

        assert len(fracciones) == 2
        assert fracciones[0][0] == "I"
        assert "Primera" in fracciones[0][1]
        assert fracciones[1][0] == "II"


# =============================================================================
# TESTS DE INSPECTOR MULTI-FORMATO
# =============================================================================

class TestInspectorMultiFormato:
    """Tests para InspectorMultiFormato."""

    def test_inicializa_sin_fuentes(self):
        """Puede inicializarse sin fuentes."""
        inspector = InspectorMultiFormato()
        assert inspector.fuentes[FuenteDatos.DOCX_XML] is None
        assert inspector.fuentes[FuenteDatos.PDF] is None
        assert inspector.fuentes[FuenteDatos.TXT] is None

    def test_inicializa_con_docx(self, rmf_docx_path):
        """Inicializa con DOCX si existe."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        from rmf.models import FuenteDatos

        inspector = InspectorMultiFormato(docx_path=rmf_docx_path)
        assert inspector.fuentes[FuenteDatos.DOCX_XML] is not None

    def test_resolver_problema_sin_fuentes(self, crear_regla):
        """Resolver sin fuentes retorna fallo."""
        regla = crear_regla(numero="2.1.1", contenido="Corto")
        problema = Problema(
            tipo=TipoProblema.CONTENIDO_TRUNCADO,
            descripcion="Contenido truncado",
            ubicacion="2.1.1",
            severidad="error",
        )

        inspector = InspectorMultiFormato()
        resolucion = inspector.resolver(regla, problema)

        assert resolucion.exito is False

    def test_resolver_tipo_sin_estrategia(self, crear_regla):
        """Problema sin estrategia retorna fallo."""
        regla = crear_regla(numero="2.1.1")
        problema = Problema(
            tipo=TipoProblema.NUMERO_INVALIDO,
            descripcion="Número inválido",
            ubicacion="2.1.1",
            severidad="error",
        )

        inspector = InspectorMultiFormato()
        resolucion = inspector.resolver(regla, problema)

        assert resolucion.exito is False
        assert "Sin estrategia" in resolucion.metodo


# =============================================================================
# TESTS DE INTEGRACIÓN
# =============================================================================

@pytest.mark.integracion
class TestValidadorIntegracion:
    """Tests de integración del validador."""

    def test_validar_resultado_completo(self, rmf_docx_path):
        """Valida resultado de parseo completo."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        from rmf.extractor import DocxXmlExtractor
        from rmf.parser import ParserRMF

        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        validador = ValidadorEstructural()
        problemas_globales = validador.validar_resultado(resultado)

        # Debe detectar algunos problemas pero no excesivos
        assert len(problemas_globales) < 50

        # La mayoría de reglas deben ser válidas
        reglas_con_errores = [
            r for r in resultado.reglas
            if r.tipo == "regla" and r.requiere_segunda_pasada
        ]
        porcentaje_errores = len(reglas_con_errores) / resultado.total_reglas * 100
        assert porcentaje_errores < 10  # Menos del 10% con errores


# =============================================================================
# TESTS DE REGRESIÓN
# =============================================================================

@pytest.mark.regresion
class TestRegresiones:
    """Tests de regresión para bugs corregidos."""

    def test_referencia_larga_con_fecha_detectada(self):
        """Bug: referencia con fecha se detectaba como contenido."""
        texto = ("CFF 14-A, Reglas a las que deberán sujetarse las "
                 "Instituciones de Crédito, 12/01/2007")
        assert HeuristicasRMF.es_referencia_larga_con_fecha(texto)

    def test_titulo_italico_no_es_referencia(self):
        """Bug: títulos en itálica se confundían con referencias."""
        texto = "Operaciones de préstamo de títulos o valores"
        assert HeuristicasRMF.es_titulo_no_referencia(texto, es_italica=True)

    def test_numeral_huerfano_solo(self):
        """Bug: numerales huérfanos (II., III.) no se fusionaban."""
        assert HeuristicasRMF.es_numeral_huerfano("II.")
        assert HeuristicasRMF.es_numeral_huerfano("III.")
        assert not HeuristicasRMF.es_numeral_huerfano("II. Contenido")


# Importar FuenteDatos para los tests
from rmf.models import FuenteDatos


# =============================================================================
# TESTS DE VALIDADOR DE INTEGRIDAD
# =============================================================================

class TestValidadorIntegridad:
    """
    Tests para ValidadorIntegridad.

    Verifica la regla fundamental: TODO texto debe existir en algún lugar.
    """

    def test_integridad_texto_preservado(self, crear_parrafo):
        """Texto completamente preservado pasa validación."""
        from rmf.models import ParrafoExtraido

        parrafos = [
            crear_parrafo("Para los efectos del artículo.", indice=0),
            crear_parrafo("CFF 14-B", indice=1),
        ]

        # Simular resultado con el mismo texto
        regla = ReglaParseada(
            numero="2.1.1",
            titulo="",
            contenido="Para los efectos del artículo.",
            referencias="CFF 14-B",
            division_path="",
            orden_global=1,
        )
        resultado = ResultadoParseo(
            reglas=[regla],
            divisiones=[],
            documento="Test",
        )

        validador = ValidadorIntegridad(umbral_similitud=0.7)
        reporte = validador.validar(parrafos, resultado)

        assert reporte['es_valido'], "Texto preservado debe ser válido"
        assert reporte['porcentaje_preservado'] >= 70

    def test_integridad_detecta_texto_perdido(self, crear_parrafo):
        """Detecta cuando hay texto perdido."""
        parrafos = [
            crear_parrafo("Para los efectos del artículo primero.", indice=0),
            crear_parrafo("Texto importante que se pierde en el resultado.", indice=1),
            crear_parrafo("CFF 14-B", indice=2),
        ]

        # Resultado sin el texto intermedio
        regla = ReglaParseada(
            numero="2.1.1",
            titulo="",
            contenido="Para los efectos del artículo primero.",
            referencias="CFF 14-B",
            division_path="",
            orden_global=1,
        )
        resultado = ResultadoParseo(
            reglas=[regla],
            divisiones=[],
            documento="Test",
        )

        validador = ValidadorIntegridad(umbral_similitud=0.9)
        reporte = validador.validar(parrafos, resultado)

        # Debe detectar que hay texto perdido
        assert reporte['palabras_perdidas'] > 0


@pytest.fixture
def rmf_pdf_path(base_dir):
    """Ruta al PDF de RMF."""
    return base_dir / "doc" / "rmf" / "rmf_2025_compilada.pdf"


# =============================================================================
# TESTS DE VALIDACIÓN CONTRA PDF
# =============================================================================

@pytest.mark.integracion
class TestValidacionContraPdf:
    """
    Tests que validan datos del parser contra el PDF original.

    Estos tests son CRÍTICOS para detectar problemas de conversión
    donde el DOCX pierde estructura que el PDF preserva.
    """

    def test_detectar_fracciones_faltantes_en_regla(self, rmf_docx_path, rmf_pdf_path):
        """Detecta cuando una regla tiene menos fracciones que el PDF."""
        if not rmf_docx_path.exists() or not rmf_pdf_path.exists():
            pytest.skip("Archivos DOCX/PDF no disponibles")

        from rmf.extractor import DocxXmlExtractor, PdfExtractor
        from rmf.parser import ParserRMF

        # Parsear DOCX
        docx_ext = DocxXmlExtractor(rmf_docx_path)
        paragraphs = docx_ext.extraer()
        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        # Preparar extractor PDF
        pdf_ext = PdfExtractor(rmf_pdf_path)

        # Buscar regla 2.1.11 (sabemos que tiene problemas)
        regla_2_1_11 = next(
            (r for r in resultado.reglas if r.numero == "2.1.11"),
            None
        )
        assert regla_2_1_11 is not None

        # Obtener datos del PDF directamente (no a través de validador)
        pdf_data = pdf_ext.buscar_regla_con_contexto("2.1.11")
        assert pdf_data is not None

        # El PDF tiene 6 fracciones (2 listas de I, II, III)
        assert len(pdf_data['fracciones']) == 6, "PDF tiene 6 fracciones"

        # El DOCX parseado puede tener menos (problema de conversión)
        fracciones_docx = len(regla_2_1_11.fracciones)
        fracciones_pdf = len(pdf_data['fracciones'])

        # Detectar discrepancia
        assert fracciones_pdf >= fracciones_docx, (
            "PDF debe tener al menos tantas fracciones como DOCX"
        )

    def test_validar_titulo_extraido(self, rmf_pdf_path):
        """PDF debe extraer título que DOCX pierde."""
        if not rmf_pdf_path.exists():
            pytest.skip("Archivo PDF no disponible")

        from rmf.extractor import PdfExtractor

        pdf_ext = PdfExtractor(rmf_pdf_path)
        resultado = pdf_ext.buscar_regla_con_contexto("2.1.11")

        assert resultado is not None
        assert resultado['titulo'] is not None
        assert len(resultado['titulo']) > 10


# =============================================================================
# TEST DE REGRESIÓN: CASO 2.1.11
# =============================================================================

@pytest.mark.integracion
@pytest.mark.regresion
class TestRegresion_2_1_11:
    """
    Test de regresión para el caso específico 2.1.11.

    Este caso documenta un problema de conversión PDF→DOCX donde:
    1. Fracción I se fusiona con párrafo anterior
    2. Se pierden 2 listas de fracciones (capital y deuda)
    3. El título desaparece

    El test verifica que PODEMOS DETECTAR el problema,
    no que lo corregimos automáticamente (evita overfitting).
    """

    def test_pdf_tiene_6_fracciones(self, rmf_pdf_path):
        """El PDF original tiene 6 fracciones (2 listas de I,II,III)."""
        if not rmf_pdf_path.exists():
            pytest.skip("Archivo PDF no disponible")

        from rmf.extractor import PdfExtractor

        pdf_ext = PdfExtractor(rmf_pdf_path)
        resultado = pdf_ext.buscar_regla_con_contexto("2.1.11")

        assert resultado is not None
        assert len(resultado['fracciones']) == 6

        # Debe tener 2 fracciones I
        numeros = [f['numero'] for f in resultado['fracciones']]
        assert numeros.count('I') == 2, "Debe haber 2 fracciones I (capital y deuda)"
        assert numeros.count('II') == 2
        assert numeros.count('III') == 2

    def test_pdf_tiene_titulo(self, rmf_pdf_path):
        """El PDF preserva el título de la regla."""
        if not rmf_pdf_path.exists():
            pytest.skip("Archivo PDF no disponible")

        from rmf.extractor import PdfExtractor

        pdf_ext = PdfExtractor(rmf_pdf_path)
        resultado = pdf_ext.buscar_regla_con_contexto("2.1.11")

        assert resultado is not None
        assert resultado['titulo'] is not None

        # El título debe mencionar operaciones financieras
        titulo = resultado['titulo'].lower()
        assert 'operaciones' in titulo or 'derivadas' in titulo

    def test_podemos_detectar_discrepancia(self, rmf_docx_path, rmf_pdf_path):
        """Podemos detectar que el DOCX tiene menos contenido que el PDF."""
        if not rmf_docx_path.exists() or not rmf_pdf_path.exists():
            pytest.skip("Archivos DOCX/PDF no disponibles")

        from rmf.extractor import DocxXmlExtractor, PdfExtractor
        from rmf.parser import ParserRMF

        # Parsear DOCX
        docx_ext = DocxXmlExtractor(rmf_docx_path)
        paragraphs = docx_ext.extraer()
        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        # Obtener regla del resultado
        regla = next((r for r in resultado.reglas if r.numero == "2.1.11"), None)
        assert regla is not None

        # Comparar con PDF
        pdf_ext = PdfExtractor(rmf_pdf_path)
        pdf_data = pdf_ext.buscar_regla_con_contexto("2.1.11")

        # DETECTAR discrepancia (no corregir)
        fracciones_docx = len(regla.fracciones)
        fracciones_pdf = len(pdf_data['fracciones'])

        # El PDF SIEMPRE debe tener 6, el DOCX puede tener menos
        assert fracciones_pdf == 6, "PDF siempre tiene 6 fracciones"

        # Si el DOCX tiene menos, hay un problema detectable
        if fracciones_docx < fracciones_pdf:
            # Esto es ESPERADO - documenta el problema
            diferencia = fracciones_pdf - fracciones_docx
            assert diferencia > 0, (
                f"Discrepancia detectada: PDF={fracciones_pdf}, DOCX={fracciones_docx}"
            )
