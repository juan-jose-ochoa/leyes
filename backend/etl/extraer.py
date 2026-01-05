#!/usr/bin/env python3
"""
Extractor unificado de leyes (nueva arquitectura).

Usa el sistema de extractores polimorficos:
- ExtractorGeneral: para leyes con estructura estandar
- ExtractorRMF: para Resolucion Miscelanea Fiscal

Uso:
    python backend/etl/extraer_nuevo.py CFF
    python backend/etl/extraer_nuevo.py RMF
    python backend/etl/extraer_nuevo.py --lista
"""
import sys
from pathlib import Path

# Agregar directorio al path para imports
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config, listar_leyes
from extractor import crear_extractor


def main():
    if len(sys.argv) < 2:
        print("Uso: python backend/etl/extraer_nuevo.py <CODIGO>")
        print("     python backend/etl/extraer_nuevo.py --lista")
        print(f"\nLeyes disponibles: {', '.join(listar_leyes())}")
        sys.exit(1)

    if sys.argv[1] == "--lista":
        print("Leyes disponibles:")
        for codigo in listar_leyes():
            config = get_config(codigo)
            tipo_ext = config.get("tipo_extractor", "general")
            print(f"  {codigo}: {config['nombre_corto']} (extractor: {tipo_ext})")
        sys.exit(0)

    codigo = sys.argv[1].upper()

    try:
        config = get_config(codigo)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Mostrar tipo de extractor que se usara
    tipo_ext = config.get("tipo_extractor", "general")
    print(f"Usando extractor: {tipo_ext}")

    # Crear extractor apropiado
    extractor = crear_extractor(codigo, config)

    # Ejecutar extraccion
    contenido = extractor.extraer()

    # Guardar resultado
    extractor.guardar(contenido)

    return 0


if __name__ == "__main__":
    sys.exit(main())
