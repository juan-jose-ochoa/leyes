# LeyesMX

Leyes fiscales y laborales mexicanas en formato web. Sitio estático generado con Astro.

## Quick Start

### Prerrequisitos

```bash
# Node.js 20+
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs

# Python 3.12+ (para extracción de PDFs)
sudo apt install python3.12 python3.12-venv
```

### Desarrollo

```bash
# Instalar dependencias
cd frontend-astro && npm install

# Iniciar servidor de desarrollo
npm run dev
```

**URL:** http://localhost:4321

## Arquitectura

```
PDF (fuente oficial)
    ↓ extraer_mapa.py + extraer.py
backend/etl/data/{ley}/*.json
    ↓ generar-datos-astro.py
frontend-astro/src/data/{ley}/*.json
    ↓ astro build
Cloudflare Pages (SSG)
```

## Estructura

```
backend/
├── etl/                        # Extracción de PDFs
│   ├── extraer_mapa.py         # Estructura (títulos, capítulos)
│   ├── extraer.py              # Contenido (artículos, párrafos)
│   ├── config.py               # Configuración por ley
│   └── data/                   # JSONs extraídos
│       └── {ley}/
│           ├── mapa_estructura.json
│           └── contenido.json
├── scripts/
│   └── generar-datos-astro.py  # Genera datos para Astro
└── docs/
    ├── DESARROLLO.md           # Flujo de desarrollo
    └── PRODUCCION.md           # Despliegue

frontend-astro/
├── src/
│   ├── components/             # Componentes Astro
│   ├── pages/                  # Rutas (SSG)
│   ├── layouts/                # Layouts
│   └── data/                   # Datos JSON para leyes
│       └── {ley}/
│           ├── articulos.json
│           ├── estructura.json
│           ├── referencias.json
│           └── tooltips.json
└── public/                     # Assets estáticos
```

## Flujo de Trabajo

### Actualizar una ley

```bash
# 1. Activar entorno virtual
source .venv/bin/activate

# 2. Extraer estructura y contenido
python backend/etl/extraer_mapa.py LISR
python backend/etl/extraer.py LISR

# 3. Generar datos para Astro
python backend/scripts/generar-datos-astro.py

# 4. Verificar en desarrollo
cd frontend-astro && npm run dev
```

### Desplegar

```bash
git push origin main
# Cloudflare Pages rebuilds automáticamente
```

## Documentación

- [backend/docs/DESARROLLO.md](backend/docs/DESARROLLO.md) - Pipeline completo de extracción
- [backend/docs/PRODUCCION.md](backend/docs/PRODUCCION.md) - Despliegue en Cloudflare Pages

## Tests

```bash
pytest backend/etl/tests/ -v
```
