# LeyesMX Backend

Pipeline de extracción de leyes fiscales y laborales mexicanas desde PDFs oficiales.

## Estructura

```
backend/
├── etl/                    # Extracción, transformación, carga
│   ├── extraer_mapa.py     # Extrae estructura (títulos, capítulos)
│   ├── extraer.py          # Extrae contenido (artículos, párrafos)
│   ├── validar.py          # Valida integridad de datos
│   ├── config.py           # Configuración por ley
│   └── data/               # JSONs extraídos por ley
│       ├── cff/
│       │   ├── mapa_estructura.json
│       │   └── contenido.json
│       ├── lisr/
│       └── ...
├── scripts/
│   └── generar-datos-astro.py  # Genera datos para frontend Astro
└── docs/
    ├── DESARROLLO.md       # Flujo de desarrollo
    └── PRODUCCION.md       # Despliegue
```

## Quick Start

```bash
# Activar entorno virtual
source .venv/bin/activate

# Extraer una ley
python backend/etl/extraer_mapa.py CFF
python backend/etl/extraer.py CFF

# Generar datos para Astro
python backend/scripts/generar-datos-astro.py
```

## Documentación

- [DESARROLLO.md](docs/DESARROLLO.md) - Flujo completo de extracción
- [PRODUCCION.md](docs/PRODUCCION.md) - Despliegue en Cloudflare Pages

## Requisitos

```bash
pip install pymupdf  # Extracción de PDFs
```
