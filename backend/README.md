# LeyesMX Backend

API REST para búsqueda de leyes fiscales y laborales mexicanas.

## Stack

- **PostgreSQL 17** - Base de datos con FTS y pgvector
- **PostgREST** - API REST automática desde PostgreSQL
- **Nginx** - Reverse proxy y SSL (producción)

## Quick Start

```bash
# Desde la raíz del proyecto:
./start.sh backend   # Inicia solo PostgREST en puerto 3010
./start.sh           # Inicia backend + frontend
```

## Instalación Manual

### 1. Requisitos

```bash
# Ubuntu 24.04
sudo apt update
sudo apt install postgresql-17 postgresql-contrib-17

# PostgREST v12.0.2+
wget https://github.com/PostgREST/postgrest/releases/download/v12.0.2/postgrest-v12.0.2-linux-static-x64.tar.xz
tar xJf postgrest-v12.0.2-linux-static-x64.tar.xz
mv postgrest ~/.local/bin/  # O /usr/local/bin/

# Python (para importación)
pip install psycopg2-binary python-docx
```

### 2. Crear Base de Datos

```bash
# Crear usuario, base de datos y extensiones
sudo -u postgres psql << 'EOF'
CREATE USER leyesmx WITH PASSWORD 'leyesmx';
CREATE DATABASE leyesmx OWNER leyesmx;
\c leyesmx
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
EOF

# Ejecutar scripts SQL en orden
PGPASSWORD=leyesmx psql -h localhost -U leyesmx -d leyesmx -f sql/001_schema.sql
PGPASSWORD=leyesmx psql -h localhost -U leyesmx -d leyesmx -f sql/002_functions.sql
PGPASSWORD=leyesmx psql -h localhost -U leyesmx -d leyesmx -f sql/003_api_views.sql
```

### 3. Importar Datos

```bash
# Desde la raíz del proyecto
source .venv/bin/activate

# Importar leyes y reglamentos
python backend/scripts/importar_leyes.py

# Importar RMF (Resolución Miscelánea Fiscal)
python backend/scripts/importar_rmf.py

# Extraer referencias cruzadas entre artículos
python scripts/extraer_referencias.py
```

### 4. Iniciar PostgREST

```bash
postgrest backend/postgrest.conf
# API disponible en http://localhost:3010
```

### 5. Probar API

```bash
# Lista de leyes
curl http://localhost:3010/leyes

# Buscar artículos
curl -X POST http://localhost:3010/rpc/buscar \
  -H "Content-Type: application/json" \
  -d '{"q": "vacaciones"}'

# Artículo específico
curl -X POST http://localhost:3010/rpc/articulo \
  -H "Content-Type: application/json" \
  -d '{"art_id": 1}'
```

## Endpoints API

### Vistas (GET)

| Endpoint | Descripción |
|----------|-------------|
| `/leyes` | Lista de leyes y reglamentos |
| `/articulos` | Todos los artículos (paginado) |
| `/articulos?ley=eq.CFF` | Artículos del CFF |
| `/articulos?id=eq.123` | Artículo por ID |
| `/estadisticas` | Stats generales |

### Funciones RPC (POST)

| Endpoint | Body | Descripción |
|----------|------|-------------|
| `/rpc/buscar` | `{"q": "...", "leyes": "CFF,LISR", "limite": 20, "pagina": 1}` | Búsqueda full-text |
| `/rpc/articulo` | `{"art_id": 123}` | Artículo con referencias cruzadas |
| `/rpc/articulo_por_ley` | `{"p_ley": "CFF", "p_numero": "14"}` | Artículo por código de ley |
| `/rpc/estructura_ley` | `{"ley_codigo": "CFF"}` | Estructura jerárquica |
| `/rpc/division_info` | `{"div_id": 5}` | Info de división (capítulo) |
| `/rpc/articulos_division` | `{"div_id": 5}` | Artículos de una división |
| `/rpc/navegar` | `{"art_id": 123}` | Navegación anterior/siguiente |
| `/rpc/sugerencias` | `{"prefijo": "fac"}` | Autocompletado |
| `/rpc/stats` | `{}` | Stats por ley |

**Nota:** El campo `referencias_salientes` y `referencias_entrantes` en `/rpc/articulo` contiene las referencias cruzadas extraídas automáticamente.

## Troubleshooting

### Error "column a.ley_id does not exist"

Las funciones SQL deben usar schema explícito (`public.articulos`, no `articulos`) para evitar conflictos con las vistas en el schema `api`.

```bash
# Recargar schema cache de PostgREST
kill -SIGUSR1 $(pgrep postgrest)
```

### Error 401 Unauthorized

Verificar permisos en `003_api_views.sql`:

```sql
GRANT EXECUTE ON FUNCTION api.buscar TO web_anon;
GRANT USAGE, SELECT ON SEQUENCE busquedas_frecuentes_id_seq TO web_anon;
```

## Configuración

**Puerto**: 3010 (configurable en `postgrest.conf`)

```
# postgrest.conf
db-uri = "postgres://authenticator:changeme@localhost:5432/leyesmx"
db-schemas = "api"
db-anon-role = "web_anon"
server-port = 3010
```

## Estructura de Archivos

```
backend/
├── sql/
│   ├── 001_schema.sql      # Tablas, índices, extensiones
│   ├── 002_functions.sql   # Funciones de búsqueda (public.*)
│   └── 003_api_views.sql   # Vistas API y permisos (api.*)
├── scripts/
│   ├── importar_leyes.py   # Importación de leyes desde DOCX
│   └── importar_rmf.py     # Importación de RMF
├── postgrest.conf          # Configuración PostgREST
└── README.md
```

## Datos

| Tabla | Registros | Descripción |
|-------|-----------|-------------|
| leyes | 13 | Leyes, reglamentos y RMF |
| divisiones | ~350 | Títulos, capítulos, secciones |
| articulos | 3,536 | Artículos y reglas RMF |
| referencias_cruzadas | 3,180 | Referencias entre artículos |
