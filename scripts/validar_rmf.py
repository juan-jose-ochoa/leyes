#!/usr/bin/env python3
"""
Script de validación y conciliación de la RMF 2025.

Compara:
1. Estructura (títulos, capítulos, secciones) vs índice PDF
2. Reglas parseadas vs reglas en PDF
3. Detecta duplicados y faltantes

Uso:
    python scripts/validar_rmf.py [--json] [--fix]
"""

import json
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import sys

# Agregar path para imports
sys.path.insert(0, str(Path(__file__).parent))

from rmf.pdf_extractor import PDFExtractor


@dataclass
class ResultadoValidacion:
    """Resultado de la validación."""
    # Estructura
    titulos_esperados: int = 0
    titulos_encontrados: int = 0
    titulos_duplicados: int = 0
    titulos_faltantes: list[str] = None

    capitulos_esperados: int = 0
    capitulos_encontrados: int = 0
    capitulos_duplicados: int = 0
    capitulos_faltantes: list[str] = None

    secciones_esperadas: int = 0
    secciones_encontradas: int = 0
    secciones_duplicadas: int = 0
    secciones_faltantes: list[str] = None

    subsecciones_esperadas: int = 0
    subsecciones_encontradas: int = 0
    subsecciones_faltantes: list[str] = None

    # Reglas
    reglas_pdf: int = 0
    reglas_parseadas: int = 0
    reglas_faltantes: list[dict] = None

    def __post_init__(self):
        self.titulos_faltantes = self.titulos_faltantes or []
        self.capitulos_faltantes = self.capitulos_faltantes or []
        self.secciones_faltantes = self.secciones_faltantes or []
        self.subsecciones_faltantes = self.subsecciones_faltantes or []
        self.reglas_faltantes = self.reglas_faltantes or []

    @property
    def es_valido(self) -> bool:
        return (
            len(self.titulos_faltantes) == 0 and
            len(self.reglas_faltantes) == 0
        )


def cargar_indice_pdf(path: Path) -> dict:
    """Carga el índice del PDF desde JSON."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def cargar_reglas_parseadas(path: Path) -> dict:
    """Carga las reglas parseadas desde JSON."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def cargar_desde_bd() -> dict:
    """Carga reglas y divisiones desde PostgreSQL."""
    import psycopg2
    import os

    # Cargar .env
    base_dir = Path(__file__).parent.parent
    env_path = base_dir / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

    pg_config = {
        "host": os.environ.get("PG_HOST", "localhost"),
        "port": int(os.environ.get("PG_PORT", "5432")),
        "database": os.environ.get("PG_DB", "leyesmx"),
        "user": os.environ.get("PG_USER", "leyesmx"),
        "password": os.environ.get("PG_PASS", "leyesmx")
    }

    conn = psycopg2.connect(**pg_config)
    cursor = conn.cursor()

    # Cargar divisiones
    cursor.execute("""
        SELECT d.tipo, d.numero
        FROM divisiones d
        JOIN leyes l ON d.ley_id = l.id
        WHERE l.codigo = 'RMF2025'
    """)
    divisiones = [{'tipo': row[0], 'numero': row[1]} for row in cursor.fetchall()]

    # Cargar reglas
    cursor.execute("""
        SELECT a.numero_raw
        FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
        WHERE l.codigo = 'RMF2025' AND a.tipo = 'regla'
    """)
    reglas = [{'numero': row[0]} for row in cursor.fetchall()]

    conn.close()

    return {'divisiones': divisiones, 'reglas': reglas}


def validar_estructura(indice_pdf: dict, reglas_parseadas: dict) -> ResultadoValidacion:
    """Valida la estructura contra el índice del PDF."""
    resultado = ResultadoValidacion()

    # Contar elementos del índice PDF
    resultado.titulos_esperados = len(indice_pdf.get('titulos', []))
    resultado.capitulos_esperados = len(indice_pdf.get('capitulos', []))
    resultado.secciones_esperadas = len(indice_pdf.get('secciones', []))
    resultado.subsecciones_esperadas = len(indice_pdf.get('subsecciones', []))
    resultado.reglas_pdf = len(indice_pdf.get('reglas', []))

    # Obtener divisiones parseadas
    divisiones = reglas_parseadas.get('divisiones', [])

    # Contar por tipo
    titulos_parseados = [d for d in divisiones if d.get('tipo') == 'titulo']
    capitulos_parseados = [d for d in divisiones if d.get('tipo') == 'capitulo']
    secciones_parseadas = [d for d in divisiones if d.get('tipo') == 'seccion']
    subsecciones_parseadas = [d for d in divisiones if d.get('tipo') == 'subseccion']

    resultado.titulos_encontrados = len(titulos_parseados)
    resultado.capitulos_encontrados = len(capitulos_parseados)
    resultado.secciones_encontradas = len(secciones_parseadas)
    resultado.subsecciones_encontradas = len(subsecciones_parseadas)

    # Detectar duplicados
    titulos_nums = [d.get('numero') for d in titulos_parseados]
    capitulos_nums = [d.get('numero') for d in capitulos_parseados]
    secciones_nums = [d.get('numero') for d in secciones_parseadas]

    resultado.titulos_duplicados = len(titulos_nums) - len(set(titulos_nums))
    resultado.capitulos_duplicados = len(capitulos_nums) - len(set(capitulos_nums))
    resultado.secciones_duplicadas = len(secciones_nums) - len(set(secciones_nums))

    # Detectar faltantes
    titulos_pdf = {t['numero'] for t in indice_pdf.get('titulos', [])}
    capitulos_pdf = {c['numero'] for c in indice_pdf.get('capitulos', [])}
    secciones_pdf = {s['numero'] for s in indice_pdf.get('secciones', [])}
    subsecciones_pdf = {ss['numero'] for ss in indice_pdf.get('subsecciones', [])}

    titulos_parseados_set = set(titulos_nums)
    capitulos_parseados_set = set(capitulos_nums)
    secciones_parseadas_set = set(secciones_nums)
    subsecciones_parseadas_set = {d.get('numero') for d in subsecciones_parseadas}

    resultado.titulos_faltantes = sorted(titulos_pdf - titulos_parseados_set, key=lambda x: int(x))
    resultado.capitulos_faltantes = sorted(
        capitulos_pdf - capitulos_parseados_set,
        key=lambda x: [int(p) for p in x.split('.')]
    )
    resultado.secciones_faltantes = sorted(
        secciones_pdf - secciones_parseadas_set,
        key=lambda x: [int(p) for p in x.split('.')]
    )
    resultado.subsecciones_faltantes = sorted(
        subsecciones_pdf - subsecciones_parseadas_set,
        key=lambda x: [int(p) for p in x.split('.')]
    )

    # Contar reglas parseadas
    resultado.reglas_parseadas = len(reglas_parseadas.get('reglas', []))

    # Detectar reglas faltantes
    reglas_pdf_nums = {r['numero'] for r in indice_pdf.get('reglas', [])}
    reglas_parseadas_nums = {r['numero'] for r in reglas_parseadas.get('reglas', [])}

    reglas_faltantes_nums = sorted(
        reglas_pdf_nums - reglas_parseadas_nums,
        key=lambda x: [int(p) for p in x.split('.')]
    )

    # Obtener info de cada regla faltante del índice
    reglas_pdf_dict = {r['numero']: r for r in indice_pdf.get('reglas', [])}
    resultado.reglas_faltantes = [
        {
            'numero': num,
            'pagina': reglas_pdf_dict.get(num, {}).get('pagina', 0),
            'titulo': reglas_pdf_dict.get(num, {}).get('titulo')
        }
        for num in reglas_faltantes_nums
    ]

    return resultado


def imprimir_resultado(resultado: ResultadoValidacion, verbose: bool = True):
    """Imprime el resultado de la validación."""
    print("\n" + "=" * 60)
    print("         VALIDACIÓN RMF 2025")
    print("=" * 60)

    # Estructura
    print("\n📁 ESTRUCTURA:")
    print("-" * 40)

    def status_icon(esperado, encontrado, duplicados, faltantes):
        if faltantes:
            return "❌"
        if duplicados > 0:
            return "⚠️"
        return "✅"

    # Títulos
    icon = status_icon(
        resultado.titulos_esperados,
        resultado.titulos_encontrados,
        resultado.titulos_duplicados,
        resultado.titulos_faltantes
    )
    print(f"  {icon} Títulos:      {resultado.titulos_esperados} esperados, "
          f"{resultado.titulos_encontrados} parseados", end="")
    if resultado.titulos_duplicados:
        print(f" ({resultado.titulos_duplicados} duplicados)", end="")
    if resultado.titulos_faltantes:
        print(f" [faltan: {', '.join(resultado.titulos_faltantes)}]", end="")
    print()

    # Capítulos
    icon = status_icon(
        resultado.capitulos_esperados,
        resultado.capitulos_encontrados,
        resultado.capitulos_duplicados,
        resultado.capitulos_faltantes
    )
    print(f"  {icon} Capítulos:    {resultado.capitulos_esperados} esperados, "
          f"{resultado.capitulos_encontrados} parseados", end="")
    if resultado.capitulos_duplicados:
        print(f" ({resultado.capitulos_duplicados} duplicados)", end="")
    print()

    # Secciones
    icon = status_icon(
        resultado.secciones_esperadas,
        resultado.secciones_encontradas,
        resultado.secciones_duplicadas,
        resultado.secciones_faltantes
    )
    print(f"  {icon} Secciones:    {resultado.secciones_esperadas} esperadas, "
          f"{resultado.secciones_encontradas} parseadas", end="")
    if resultado.secciones_duplicadas:
        print(f" ({resultado.secciones_duplicadas} duplicadas)", end="")
    print()

    # Subsecciones
    icon = "❌" if resultado.subsecciones_faltantes else "✅"
    print(f"  {icon} Subsecciones: {resultado.subsecciones_esperadas} esperadas, "
          f"{resultado.subsecciones_encontradas} parseadas", end="")
    if resultado.subsecciones_faltantes:
        print(f" [faltan: {', '.join(resultado.subsecciones_faltantes)}]", end="")
    print()

    # Reglas
    print("\n📋 REGLAS:")
    print("-" * 40)
    icon = "✅" if not resultado.reglas_faltantes else "❌"
    print(f"  {icon} PDF: {resultado.reglas_pdf} | "
          f"Parseadas: {resultado.reglas_parseadas} | "
          f"Faltantes: {len(resultado.reglas_faltantes)}")

    if resultado.reglas_faltantes and verbose:
        print("\n  Reglas no parseadas:")
        for r in resultado.reglas_faltantes:
            titulo = r.get('titulo') or '[sin título]'
            print(f"    - {r['numero']}: {titulo[:50]} (pág. {r['pagina']})")

    # Resumen
    print("\n" + "=" * 60)
    if resultado.es_valido:
        print("✅ VALIDACIÓN EXITOSA")
    else:
        problemas = []
        if resultado.titulos_faltantes:
            problemas.append(f"{len(resultado.titulos_faltantes)} títulos faltantes")
        if resultado.reglas_faltantes:
            problemas.append(f"{len(resultado.reglas_faltantes)} reglas faltantes")
        if resultado.titulos_duplicados:
            problemas.append(f"{resultado.titulos_duplicados} títulos duplicados")
        if resultado.capitulos_duplicados:
            problemas.append(f"{resultado.capitulos_duplicados} capítulos duplicados")
        print(f"⚠️  PROBLEMAS DETECTADOS: {', '.join(problemas)}")
    print("=" * 60)


def exportar_json(resultado: ResultadoValidacion, output_path: Path):
    """Exporta el resultado en formato JSON."""
    data = {
        'estructura': {
            'titulos': {
                'esperados': resultado.titulos_esperados,
                'encontrados': resultado.titulos_encontrados,
                'duplicados': resultado.titulos_duplicados,
                'faltantes': resultado.titulos_faltantes
            },
            'capitulos': {
                'esperados': resultado.capitulos_esperados,
                'encontrados': resultado.capitulos_encontrados,
                'duplicados': resultado.capitulos_duplicados,
                'faltantes': resultado.capitulos_faltantes
            },
            'secciones': {
                'esperadas': resultado.secciones_esperadas,
                'encontradas': resultado.secciones_encontradas,
                'duplicadas': resultado.secciones_duplicadas,
                'faltantes': resultado.secciones_faltantes
            },
            'subsecciones': {
                'esperadas': resultado.subsecciones_esperadas,
                'encontradas': resultado.subsecciones_encontradas,
                'faltantes': resultado.subsecciones_faltantes
            }
        },
        'reglas': {
            'pdf': resultado.reglas_pdf,
            'parseadas': resultado.reglas_parseadas,
            'faltantes': resultado.reglas_faltantes
        },
        'es_valido': resultado.es_valido
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nResultado exportado a: {output_path}")


def extraer_reglas_faltantes(resultado: ResultadoValidacion, pdf_path: Path) -> list[dict]:
    """Extrae el contenido de las reglas faltantes del PDF."""
    if not resultado.reglas_faltantes:
        return []

    print(f"\n📥 Extrayendo {len(resultado.reglas_faltantes)} reglas faltantes del PDF...")

    reglas_extraidas = []

    with PDFExtractor(pdf_path) as extractor:
        for regla_info in resultado.reglas_faltantes:
            numero = regla_info['numero']
            print(f"  Extrayendo {numero}...", end=" ")

            regla = extractor.extraer_regla_contenido(numero)
            if regla:
                reglas_extraidas.append({
                    'numero': numero,
                    'titulo': regla.titulo,
                    'contenido': regla.contenido,
                    'pagina': regla.pagina,
                    'fuente': 'pdf'
                })
                print(f"✅ ({len(regla.contenido or '')} chars)")
            else:
                print("❌ No encontrada")

    return reglas_extraidas


def main():
    parser = argparse.ArgumentParser(description='Validar RMF 2025 contra índice PDF')
    parser.add_argument('--json', action='store_true', help='Exportar resultado en JSON')
    parser.add_argument('--fix', action='store_true', help='Extraer reglas faltantes del PDF')
    parser.add_argument('--quiet', action='store_true', help='Solo mostrar resumen')
    parser.add_argument('--db', action='store_true', help='Leer datos desde PostgreSQL en vez de JSON')
    args = parser.parse_args()

    # Paths
    base_dir = Path(__file__).parent.parent
    indice_path = base_dir / "doc/rmf/indice_rmf_2025.json"
    parsed_path = base_dir / "doc/rmf/rmf_parsed.json"
    pdf_path = base_dir / "doc/rmf/rmf_2025_compilada.pdf"

    # Verificar archivos
    if not indice_path.exists():
        print(f"Error: No se encontró el índice en {indice_path}")
        print("Ejecuta primero: python scripts/rmf/pdf_extractor.py")
        sys.exit(1)

    # Cargar datos
    print("Cargando datos...")
    indice_pdf = cargar_indice_pdf(indice_path)

    if args.db:
        print("  (desde PostgreSQL)")
        reglas_parseadas = cargar_desde_bd()
    else:
        if not parsed_path.exists():
            print(f"Error: No se encontró el archivo parseado en {parsed_path}")
            sys.exit(1)
        reglas_parseadas = cargar_reglas_parseadas(parsed_path)

    # Validar
    resultado = validar_estructura(indice_pdf, reglas_parseadas)

    # Imprimir resultado
    imprimir_resultado(resultado, verbose=not args.quiet)

    # Exportar JSON si se solicita
    if args.json:
        output_path = base_dir / "doc/rmf/validacion_rmf.json"
        exportar_json(resultado, output_path)

    # Extraer faltantes si se solicita
    if args.fix and resultado.reglas_faltantes:
        reglas_extraidas = extraer_reglas_faltantes(resultado, pdf_path)

        if reglas_extraidas:
            # Guardar reglas extraídas
            output_path = base_dir / "doc/rmf/reglas_extraidas_pdf.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(reglas_extraidas, f, ensure_ascii=False, indent=2)
            print(f"\n✅ {len(reglas_extraidas)} reglas guardadas en: {output_path}")

    return 0 if resultado.es_valido else 1


if __name__ == "__main__":
    sys.exit(main())
