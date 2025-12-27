"""
Tests de integración para el pipeline completo.

Prueba el flujo end-to-end:
1. Extracción de DOCX
2. Parsing con detección de problemas
3. Validación estructural
4. Segunda pasada (si hay problemas)
5. Generación de resultado final
"""

import pytest
from pathlib import Path
import sys
import json

# Agregar scripts/ al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rmf import (
    DocxXmlExtractor,
    ParserRMF,
    ValidadorEstructural,
    InspectorMultiFormato,
    ResultadoParseo,
)


# =============================================================================
# TESTS DE PIPELINE COMPLETO
# =============================================================================

@pytest.mark.integracion
class TestPipelineCompleto:
    """Tests end-to-end del pipeline de parseo."""

    def test_pipeline_basico(self, rmf_docx_path):
        """Test del pipeline básico sin segunda pasada."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        # Fase 1: Extracción
        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        assert len(paragraphs) > 1000, "Debe extraer muchos párrafos"

        # Fase 2: Parsing
        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        assert resultado.total_reglas >= 700, "Debe parsear muchas reglas"

        # Fase 3: Validación
        validador = ValidadorEstructural()
        problemas = validador.validar_resultado(resultado)

        # Puede haber algunos problemas, pero no excesivos
        assert len(problemas) < 100

        # Métricas
        resultado.calcular_metricas()
        assert resultado.porcentaje_exito > 85

    def test_pipeline_con_segunda_pasada(self, rmf_docx_path):
        """Test del pipeline con segunda pasada."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        # Pipeline completo
        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        # Segunda pasada
        inspector = InspectorMultiFormato(docx_path=rmf_docx_path)
        resoluciones, pendientes = inspector.procesar_resultado(resultado)

        # Debe haber intentado resolver algunos problemas
        # (aunque no todos se resuelven sin PDF/TXT)
        assert isinstance(resoluciones, list)
        assert isinstance(pendientes, list)

    def test_resultado_serializable(self, rmf_docx_path):
        """El resultado debe ser serializable a JSON."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        # Convertir a dict para JSON
        resultado_dict = {
            "documento": resultado.documento,
            "total_reglas": resultado.total_reglas,
            "divisiones": [
                {
                    "tipo": d.tipo.value,
                    "numero": d.numero,
                    "nombre": d.nombre,
                    "path_texto": d.path_texto,
                }
                for d in resultado.divisiones
            ],
            "reglas": [
                {
                    "numero": r.numero,
                    "titulo": r.titulo,
                    "contenido": r.contenido[:100] if r.contenido else "",
                    "referencias": r.referencias,
                    "tipo": r.tipo,
                }
                for r in resultado.reglas[:10]  # Solo primeras 10 para test
            ],
        }

        # Debe serializar sin errores
        json_str = json.dumps(resultado_dict, ensure_ascii=False, indent=2)
        assert len(json_str) > 0

        # Debe deserializar sin errores
        parsed = json.loads(json_str)
        assert parsed["documento"] == "RMF 2025"


# =============================================================================
# TESTS DE REGLAS ESPECÍFICAS
# =============================================================================

@pytest.mark.integracion
class TestReglasEspecificas:
    """Tests para reglas específicas conocidas."""

    def test_regla_2_1_1_existe(self, rmf_docx_path):
        """La regla 2.1.1 debe existir y tener contenido."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        regla = next((r for r in resultado.reglas if r.numero == "2.1.1"), None)
        assert regla is not None
        assert len(regla.contenido) > 0
        assert regla.tipo == "regla"

    def test_regla_2_1_8_tiene_referencia_larga(self, rmf_docx_path):
        """La regla 2.1.8 tiene referencia larga con instituciones."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        regla = next((r for r in resultado.reglas if r.numero == "2.1.8"), None)
        assert regla is not None

        # Si tiene referencia, debe empezar con CFF
        if regla.referencias:
            assert regla.referencias.startswith("CFF")

    def test_capitulo_2_1_tiene_reglas(self, rmf_docx_path):
        """El capítulo 2.1 debe tener múltiples reglas."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        reglas_2_1 = [
            r for r in resultado.reglas
            if r.numero.startswith("2.1.") and r.tipo == "regla"
        ]
        assert len(reglas_2_1) >= 10


# =============================================================================
# TESTS DE METRICAS
# =============================================================================

@pytest.mark.integracion
class TestMetricas:
    """Tests para métricas de calidad."""

    def test_metricas_calculadas(self, rmf_docx_path):
        """Las métricas se calculan correctamente."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        # Métricas deben estar calculadas
        assert resultado.total_reglas > 0
        assert resultado.porcentaje_exito >= 0
        assert resultado.porcentaje_perfectas >= 0

    def test_porcentaje_exito_alto(self, rmf_docx_path):
        """El porcentaje de éxito debe ser alto."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        # Objetivo: >90% de éxito
        assert resultado.porcentaje_exito > 90, \
            f"Porcentaje de éxito muy bajo: {resultado.porcentaje_exito:.1f}%"


# =============================================================================
# TESTS DE COMPATIBILIDAD
# =============================================================================

@pytest.mark.integracion
class TestCompatibilidad:
    """Tests de compatibilidad con estructura existente."""

    def test_estructura_compatible_con_json_anterior(self, rmf_docx_path):
        """La estructura debe ser compatible con el JSON anterior."""
        if not rmf_docx_path.exists():
            pytest.skip("Archivo DOCX no disponible")

        extractor = DocxXmlExtractor(rmf_docx_path)
        paragraphs = extractor.extraer()

        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")

        # Verificar campos requeridos en reglas
        regla = resultado.reglas[0]
        assert hasattr(regla, 'numero')
        assert hasattr(regla, 'titulo')
        assert hasattr(regla, 'contenido')
        assert hasattr(regla, 'referencias')
        assert hasattr(regla, 'orden_global')
        assert hasattr(regla, 'division_path')

        # Verificar campos requeridos en divisiones
        if resultado.divisiones:
            div = resultado.divisiones[0]
            assert hasattr(div, 'tipo')
            assert hasattr(div, 'numero')
            assert hasattr(div, 'nombre')
            assert hasattr(div, 'path_texto')
