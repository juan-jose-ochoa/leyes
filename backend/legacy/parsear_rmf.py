#!/usr/bin/env python3
"""
Parser de Resolución Miscelánea Fiscal (RMF)

Extrae estructura jerárquica: Títulos, Capítulos, Secciones, Reglas

Diferencias con leyes normales:
- Unidad básica: "regla" (no "artículo")
- Numeración compuesta: 2.1.1., 2.1.2. (no simple: 1, 2, 3)
- Referencias al final: CFF 4o., 17-D, RMF 2.1.39.

Salida: JSON estructurado listo para importar a PostgreSQL

Usa el módulo rmf/ para extracción, parsing y validación.
"""

import json
from pathlib import Path

# Importar módulo rmf
from rmf import (
    DocxXmlExtractor,
    ParserRMF,
    ValidadorEstructural,
    InspectorMultiFormato,
    ResultadoParseo,
)

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).parent.parent
RMF_DIR = BASE_DIR / "doc" / "rmf"


def resultado_a_dict(resultado: ResultadoParseo) -> dict:
    """
    Convierte ResultadoParseo a diccionario compatible con JSON/DB.

    Mantiene compatibilidad con el formato anterior para cargar a PostgreSQL.
    """
    # Convertir divisiones
    divisiones = []
    for div in resultado.divisiones:
        divisiones.append({
            "tipo": div.tipo.value,
            "numero": div.numero,
            "numero_orden": div.numero_orden,
            "nombre": div.nombre,
            "orden_global": div.orden_global,
            "path_texto": div.path_texto,
            "padre_tipo": div.padre_tipo.value if div.padre_tipo else None,
            "padre_numero": div.padre_numero,
        })

    # Convertir reglas
    reglas = []
    for regla in resultado.reglas:
        regla_dict = {
            "numero": regla.numero,
            "titulo": regla.titulo,
            "contenido": regla.contenido,
            "referencias": regla.referencias,
            "orden_global": regla.orden_global,
            "division_path": regla.division_path,
            "titulo_padre": regla.titulo_padre,
            "capitulo_padre": regla.capitulo_padre,
            "seccion_padre": regla.seccion_padre,
            "tipo": regla.tipo,
        }
        # Incluir fracciones si hay
        if regla.fracciones:
            regla_dict["fracciones"] = [
                {
                    "numero": f.numero,
                    "contenido": f.contenido,
                    "orden": f.orden,
                    "tipo": getattr(f, 'tipo', 'fraccion'),  # 'fraccion' o 'parrafo'
                    "incisos": [
                        {"letra": inc.letra, "contenido": inc.contenido, "orden": inc.orden}
                        for inc in f.incisos
                    ] if f.incisos else [],
                }
                for f in regla.fracciones
            ]
        # Incluir calidad solo si hay issues (OK implícito si no hay)
        if regla.calidad:
            calidad_dict = regla.calidad.to_dict()
            if calidad_dict:
                regla_dict["calidad"] = calidad_dict
        reglas.append(regla_dict)

    # Contar placeholders
    total_placeholders = len([r for r in resultado.reglas if r.tipo == "no-existe"])
    total_reglas_reales = len([r for r in resultado.reglas if r.tipo == "regla"])

    # Métricas de calidad
    reglas_ok = len([r for r in resultado.reglas
                     if r.tipo == "regla" and r.calidad is None])
    reglas_corregidas = len([r for r in resultado.reglas
                              if r.tipo == "regla" and r.calidad
                              and r.calidad.estatus.value == "corregida"])
    reglas_con_error = len([r for r in resultado.reglas
                             if r.tipo == "regla" and r.calidad
                             and r.calidad.estatus.value == "con_error"])

    return {
        "documento": resultado.documento,
        "tipo": "rmf",
        "total_divisiones": len(divisiones),
        "total_reglas": len(reglas),
        "total_reglas_reales": total_reglas_reales,
        "total_placeholders": total_placeholders,
        "metricas_calidad": {
            "reglas_ok": reglas_ok,
            "reglas_corregidas": reglas_corregidas,
            "reglas_con_error": reglas_con_error,
            "porcentaje_ok": round(reglas_ok / total_reglas_reales * 100, 1) if total_reglas_reales else 0,
        },
        "divisiones": divisiones,
        "reglas": reglas,
    }


def procesar_rmf(docx_path: Path, output_path: Path) -> dict:
    """
    Procesa el documento RMF y genera JSON estructurado.

    Pipeline:
    1. Extracción (DocxXmlExtractor)
    2. Parsing (ParserRMF)
    3. Validación + Segunda pasada (ValidadorEstructural + InspectorMultiFormato)
    4. Exportación a JSON con métricas de calidad
    """
    print(f"   Leyendo DOCX: {docx_path.name}")

    # Fase 1: Extracción
    extractor = DocxXmlExtractor(docx_path)
    paragraphs = extractor.extraer()
    print(f"   {len(paragraphs)} párrafos extraídos")

    # Fase 2: Parsing
    print(f"   Parseando estructura...")
    nombre_doc = docx_path.stem.replace("_", " ").title()
    parser = ParserRMF()
    resultado = parser.parsear(paragraphs, nombre_doc)

    # Fase 3: Validación (primera pasada)
    validador = ValidadorEstructural()
    problemas_globales = validador.validar_resultado(resultado)

    reglas_con_problemas = len([r for r in resultado.reglas
                                if r.tipo == "regla" and r.problemas])
    print(f"   {reglas_con_problemas} reglas con problemas detectados")

    # Segunda pasada: intentar corregir problemas usando PDF como fuente de verdad
    if reglas_con_problemas > 0:
        print(f"   Ejecutando segunda pasada...")

        # Buscar PDF correspondiente
        pdf_path = RMF_DIR / (docx_path.stem.replace('_converted', '').replace('_full', '') + '.pdf')
        if not pdf_path.exists():
            # Buscar cualquier PDF en el directorio
            pdfs = list(RMF_DIR.glob("*.pdf"))
            pdf_path = pdfs[0] if pdfs else None

        if pdf_path:
            print(f"   Usando PDF: {pdf_path.name}")

        inspector = InspectorMultiFormato(docx_path=docx_path, pdf_path=pdf_path)
        resoluciones, pendientes = inspector.procesar_resultado(resultado)
        print(f"   {len(resoluciones) - len(pendientes)} correcciones exitosas, {len(pendientes)} pendientes")

    # Mostrar estadísticas
    print(f"   {len(resultado.divisiones)} divisiones, {resultado.total_reglas} reglas")

    # Fase 4: Exportación
    print(f"   Guardando JSON...")
    resultado_dict = resultado_a_dict(resultado)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(resultado_dict, f, ensure_ascii=False, indent=2)

    return resultado_dict


def convertir_pdf_a_docx(pdf_path: Path) -> Path:
    """Convierte PDF a DOCX usando pdf2docx."""
    from pdf2docx import Converter

    docx_path = pdf_path.with_suffix('.docx')

    print(f"   Convirtiendo PDF a DOCX...")
    cv = Converter(str(pdf_path))
    cv.convert(str(docx_path))
    cv.close()

    print(f"   Convertido: {docx_path.name}")
    return docx_path


def main():
    """Procesa la RMF principal"""
    print("=" * 60)
    print("Parser de RMF - Resolución Miscelánea Fiscal")
    print("=" * 60)

    # Buscar DOCX de RMF compilada
    if not RMF_DIR.exists():
        print(f"ERROR: No existe directorio {RMF_DIR}")
        print("Ejecuta primero: python scripts/descargar_rmf.py")
        return 1

    # Buscar archivos DOCX
    docx_files = list(RMF_DIR.glob("*.docx"))

    if not docx_files:
        # Intentar convertir PDF a DOCX
        pdf_files = list(RMF_DIR.glob("*.pdf"))
        if pdf_files:
            print(f"\nEncontrado PDF: {pdf_files[0].name}")
            try:
                docx_path = convertir_pdf_a_docx(pdf_files[0])
                docx_files = [docx_path]
            except ImportError:
                print("ERROR: pdf2docx no instalado. Ejecuta: pip install pdf2docx")
                return 1
            except Exception as e:
                print(f"ERROR convirtiendo PDF: {e}")
                return 1

    if not docx_files:
        print("ERROR: No se encontró DOCX ni PDF de RMF")
        return 1

    # Procesar RMF principal
    docx_path = docx_files[0]
    json_path = RMF_DIR / "rmf_parsed.json"

    try:
        resultado = procesar_rmf(docx_path, json_path)
        print(f"\n   Guardado: {json_path}")

        # Mostrar estadísticas
        print("\n" + "=" * 60)
        print("RESUMEN")
        print("=" * 60)
        print(f"Documento: {resultado['documento']}")
        print(f"Divisiones: {resultado['total_divisiones']}")
        print(f"Reglas: {resultado['total_reglas']} ({resultado['total_reglas_reales']} reales + {resultado['total_placeholders']} placeholders)")

        metricas = resultado['metricas_calidad']
        print(f"\nMétricas de calidad:")
        print(f"   OK (primera pasada): {metricas['reglas_ok']} ({metricas['porcentaje_ok']}%)")
        print(f"   Corregidas (segunda pasada): {metricas['reglas_corregidas']}")
        print(f"   Con errores pendientes: {metricas['reglas_con_error']}")

        # Mostrar primeras reglas como ejemplo
        if resultado['reglas']:
            print(f"\nPrimeras 5 reglas:")
            for regla in resultado['reglas'][:5]:
                titulo = regla['titulo'][:60] + "..." if len(regla['titulo']) > 60 else regla['titulo']
                print(f"   {regla['numero']} - {titulo}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
