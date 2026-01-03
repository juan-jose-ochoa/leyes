# LeyesMX - Arquitectura del Proyecto

Parsea documentos legales mexicanos (leyes, RMF) y los carga a PostgreSQL para consulta.

## Quick Start

### Prerrequisitos

```bash
# PostgreSQL 17
sudo apt install postgresql-17 postgresql-contrib-17

# Node.js 20+
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs

# Python 3.12+
sudo apt install python3.12 python3.12-venv

# PostgREST
wget https://github.com/PostgREST/postgrest/releases/download/v12.0.2/postgrest-v12.0.2-linux-static-x64.tar.xz
tar xJf postgrest-v12.0.2-linux-static-x64.tar.xz
mv postgrest ~/.local/bin/
```

### Configurar Base de Datos

```bash
sudo -u postgres psql << 'EOF'
CREATE USER leyesmx WITH PASSWORD 'leyesmx';
CREATE DATABASE digiapps OWNER leyesmx;
\c digiapps
CREATE SCHEMA leyesmx AUTHORIZATION leyesmx;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
EOF
```

### Iniciar Servicios

```bash
./start.sh          # Backend + Frontend
./start.sh backend  # Solo API (puerto 3010)
./start.sh frontend # Solo Frontend (puerto 5173)
```

**URLs:** Frontend http://localhost:5173 | API http://localhost:3010

## Estructura

```
scripts/
├── leyesmx/                    # Módulo principal
│   ├── importar.py             # CLI para importar leyes
│   ├── extraer_parrafos_x.py   # Extracción con coordenadas PDF
│   ├── extraer_mapa.py         # Extrae jerarquía del outline
│   ├── validar.py              # Valida extracción vs estructura esperada
│   └── verificar_bd.py         # Verifica integridad post-importación
├── rmf/                        # Módulo RMF (DOCX)
└── tests/                      # Tests pytest

backend/sql/                    # Funciones PostgreSQL/PostgREST

frontend/src/
├── components/                 # Componentes React reutilizables
├── pages/                      # Vistas principales
├── hooks/                      # Custom hooks
└── lib/                        # API client

doc/leyes/<ley>/
├── mapa_estructura.json        # Estructura extraída del outline (fuente de verdad)
├── estructura.json             # Divisiones extraídas
└── contenido.json              # Artículos/párrafos
```

## Base de Datos

- **Database:** `digiapps`
- **Schema:** `leyesmx`

### Tablas

| Tabla | Propósito |
|-------|-----------|
| `leyes` | Catálogo + estructura JSONB |
| `divisiones` | Títulos, capítulos (jerárquico) |
| `articulos` | Artículos/reglas/transitorios |
| `parrafos` | Contenido (texto, fracciones, incisos) |

### Variables de Entorno

```bash
export LEYESMX_DB_HOST=localhost
export LEYESMX_DB_PORT=5432
export LEYESMX_DB_NAME=digiapps
export LEYESMX_DB_USER=leyesmx
export LEYESMX_DB_PASSWORD=leyesmx
```

## API REST (PostgREST)

### Vistas

| Endpoint | Descripción |
|----------|-------------|
| `GET /v_leyes` | Lista de leyes |
| `GET /v_articulos?ley=eq.CFF` | Artículos de una ley |

### Funciones RPC

| Endpoint | Body |
|----------|------|
| `POST /rpc/buscar` | `{"q": "impuesto", "leyes": "CFF,LISR"}` |
| `POST /rpc/articulo` | `{"art_id": 123}` |
| `POST /rpc/estructura_ley` | `{"ley_codigo": "CFF"}` |
| `POST /rpc/navegar` | `{"art_id": 123}` |
| `POST /rpc/fracciones_articulo` | `{"art_id": 123}` |

## Troubleshooting

### PostgREST no encontrado
```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Error 401 en /rpc/buscar
Falta permiso para `web_anon`. Verificar GRANTs en SQL.

### Puerto 3010 ocupado
```bash
lsof -i :3010
./start.sh stop
```

## Tests

```bash
pytest scripts/tests/ -v
```
