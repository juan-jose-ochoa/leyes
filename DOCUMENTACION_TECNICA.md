# LeyesMX - Documentación Técnica

## Sistema de Búsqueda de Leyes Fiscales y Laborales Mexicanas

**Versión**: 2.0
**Fecha**: Diciembre 2025
**Autor**: Sistema automatizado con Claude Code

---

## 0. Quick Start (Setup Rápido)

### Prerrequisitos

```bash
# PostgreSQL 17
sudo apt install postgresql-17 postgresql-contrib-17

# Node.js 20+
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs

# Python 3.12+
sudo apt install python3.12 python3.12-venv

# PostgREST (v12.0.2+)
wget https://github.com/PostgREST/postgrest/releases/download/v12.0.2/postgrest-v12.0.2-linux-static-x64.tar.xz
tar xJf postgrest-v12.0.2-linux-static-x64.tar.xz
mv postgrest ~/.local/bin/  # Asegúrate de que ~/.local/bin esté en tu PATH
```

### Configurar Base de Datos

```bash
# Crear usuario y base de datos
sudo -u postgres psql << 'EOF'
CREATE USER leyesmx WITH PASSWORD 'leyesmx';
CREATE DATABASE leyesmx OWNER leyesmx;
\c leyesmx
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
-- CREATE EXTENSION IF NOT EXISTS vector;  -- Opcional, requiere superuser
EOF

# Ejecutar schema
PGPASSWORD=leyesmx psql -h localhost -U leyesmx -d leyesmx -f backend/sql/001_schema.sql
PGPASSWORD=leyesmx psql -h localhost -U leyesmx -d leyesmx -f backend/sql/002_functions.sql
PGPASSWORD=leyesmx psql -h localhost -U leyesmx -d leyesmx -f backend/sql/003_api_views.sql
```

### Importar Datos

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install python-docx psycopg2-binary
python backend/scripts/importar_leyes.py
```

### Iniciar Servicios

```bash
./start.sh          # Backend + Frontend
./start.sh backend  # Solo API (puerto 3010)
./start.sh frontend # Solo Frontend (puerto 5173)
./start.sh status   # Ver estado de servicios
```

**URLs:**
- Frontend: http://localhost:5173
- API: http://localhost:3010

---

## 0.1 Troubleshooting

### PostgREST no encontrado

```bash
# Si ~/.local/bin no está en PATH, agregar a ~/.bashrc:
export PATH="$HOME/.local/bin:$PATH"
source ~/.bashrc
```

### Error "column a.ley_id does not exist"

Este error ocurre cuando las funciones SQL referencian tablas sin schema explícito y PostgREST resuelve `articulos` a la VIEW `api.articulos` en lugar de la TABLE `public.articulos`.

**Solución:** Las funciones en `002_functions.sql` deben usar `public.articulos`, `public.leyes`, etc. Si actualizaste el código, recargar schema:

```bash
# Recargar PostgREST schema cache
kill -SIGUSR1 $(pgrep postgrest)

# O reiniciar PostgREST
./start.sh stop && ./start.sh backend
```

### Error 401 en /rpc/buscar

Falta permiso para el rol `web_anon`. Verificar en `003_api_views.sql`:

```sql
GRANT EXECUTE ON FUNCTION api.buscar TO web_anon;
GRANT USAGE, SELECT ON SEQUENCE busquedas_frecuentes_id_seq TO web_anon;
```

### Puerto 3010 ocupado

```bash
# Ver qué proceso usa el puerto
lsof -i :3010

# Matar proceso
./start.sh stop
```

### Base de datos vacía después de importar

Verificar que `doc/manifest.json` existe y tiene documentos. Si no:

```bash
source .venv/bin/activate
python scripts/descargar_leyes_mx.py
python scripts/convertir_ley.py
python backend/scripts/importar_leyes.py
```

---

## 1. Resumen del Sistema

LeyesMX es una aplicación web para búsqueda de conceptos en leyes fiscales y laborales mexicanas. El sistema permite a contadores y despachos buscar artículos específicos mediante búsqueda full-text en español.

### 1.1 Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│                   React + TypeScript                         │
│              (Vite, Tailwind, TanStack Query)               │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTPS
┌─────────────────────▼───────────────────────────────────────┐
│                      PostgREST                               │
│            API REST automática desde PostgreSQL              │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                     POSTGRESQL 17                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   leyes     │  │ divisiones  │  │     articulos       │  │
│  │  (12 docs)  │  │ (301 divs)  │  │  (3,090 arts)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                                                              │
│  Extensiones: pg_trgm, unaccent, (vector opcional)          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Proceso de Creación de Documentos

### 2.1 Pipeline de Conversión

El proceso de conversión sigue estos pasos:

```
PDF (fuente oficial)
    │
    ▼ pdf2docx
DOCX (preserva estructura)
    │
    ▼ parsear_ley.py
JSON (estructura jerárquica)
    │
    ▼ importar_leyes.py
PostgreSQL (normalizado)
```

### 2.2 Descarga de Leyes

**Script**: `scripts/descargar_leyes_mx.py`

Descarga automáticamente los PDFs desde la Cámara de Diputados:

| Documento | URL Fuente |
|-----------|------------|
| CFF | diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf |
| LFT | diputados.gob.mx/LeyesBiblio/pdf/LFT.pdf |
| LISR | diputados.gob.mx/LeyesBiblio/pdf/LISR.pdf |
| LIVA | diputados.gob.mx/LeyesBiblio/pdf/LIVA.pdf |
| LIEPS | diputados.gob.mx/LeyesBiblio/pdf/LIEPS.pdf |
| LSS | diputados.gob.mx/LeyesBiblio/pdf/LSS.pdf |

Genera `doc/manifest.json` con metadatos: SHA256, fecha de descarga, URLs.

### 2.3 Conversión PDF a DOCX

**Script**: `scripts/convertir_ley.py`

Usa `pdf2docx` para preservar la estructura del documento:
- Mantiene párrafos separados
- Preserva formato de títulos y capítulos
- Elimina números de página

### 2.4 Parser de Estructura Jerárquica

**Script**: `scripts/parsear_ley.py`

Extrae la estructura completa de las leyes mexicanas:

#### Patrones de División Reconocidos:

```python
PATRON_TITULO = r'^T[ÍI]TULO\s+(\w+)(?:\s*[-–]\s*|\s+)(.*)?$'
PATRON_CAPITULO = r'^CAP[ÍI]TULO\s+(\w+)(?:\s*[-–]\s*|\s+)(.*)?$'
PATRON_SECCION = r'^SECCI[ÓO]N\s+(\\w+)(?:\s*[-–]\s*|\s+)(.*)?$'
```

#### Patrón de Artículos:

Maneja todos los formatos de numeración:
- Simples: `Artículo 1o.`, `Artículo 2.`
- Con letra: `Artículo 32-A.`, `Artículo 84-E.`
- Con sufijo latino: `Artículo 2 Bis.`, `Artículo 32-B Ter.`
- Compuestos: `Artículo 32-B Bis.`, `Artículo 4o.-A.`

```python
PATRON_ARTICULO = re.compile(
    r'^Art[íi]culo\s+'           # Inicio (mayúscula)
    r'(\d+)'                     # Número base: 84
    r'([oa])?'                   # Ordinal: o, a
    r'[.\s]*[-–]?[.\s]*'         # Separador
    r'([A-Z])?'                  # Letra sufijo: A, B, E
    r'[.\s]*[-–]?[.\s]*'         # Separador
    r'(Bis|Ter|Quáter|...)?'     # Sufijo latino
    r'[.\s\-–]*'                 # Puntuación final
    r'(.*)'                      # Contenido
)
```

### 2.5 Importación a PostgreSQL

**Script**: `backend/scripts/importar_leyes.py`

1. Lee `manifest.json` para metadatos
2. Para cada documento:
   - Lee el DOCX
   - Parsea con `parsear_ley.py`
   - Inserta ley, divisiones y artículos
3. Construye jerarquía de path_ids
4. Refresca vista materializada

---

## 3. Esquema de Base de Datos

### 3.1 Diagrama Entidad-Relación

```
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│    leyes    │       │  divisiones  │       │  articulos  │
├─────────────┤       ├──────────────┤       ├─────────────┤
│ id (PK)     │◄──────│ ley_id (FK)  │       │ id (PK)     │
│ codigo      │       │ padre_id(FK) │◄──┐   │ ley_id (FK) │
│ nombre      │       │ tipo         │   │   │ division_id │
│ tipo        │       │ numero       │   │   │ numero_raw  │
│ url_fuente  │       │ nombre       │   │   │ numero_base │
│ sha256      │       │ path_texto   │   │   │ sufijo      │
└─────────────┘       │ path_ids[]   │   │   │ contenido   │
                      │ nivel        │   │   │ es_transit. │
                      └──────────────┘   │   │ search_vec  │
                           ▲             │   └─────────────┘
                           │             │         │
                           └─────────────┘         │
                           (auto-referencia)       │
                                                   ▼
                                          ┌───────────────┐
                                          │  fracciones   │
                                          │ (futuro)      │
                                          └───────────────┘
```

### 3.2 Tabla: leyes

Catálogo de leyes y reglamentos.

```sql
CREATE TABLE leyes (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL,    -- CFF, LFT, LISR
    nombre VARCHAR(300) NOT NULL,          -- Nombre completo
    nombre_corto VARCHAR(100),             -- Abreviatura
    tipo VARCHAR(20) NOT NULL              -- 'ley' o 'reglamento'
        CHECK (tipo IN ('ley', 'reglamento')),
    url_fuente TEXT,                       -- URL de descarga
    sha256 VARCHAR(64),                    -- Hash del PDF
    fecha_publicacion DATE,
    ultima_reforma DATE,
    fecha_descarga TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.3 Tabla: divisiones

Estructura jerárquica con auto-referencia.

```sql
CREATE TABLE divisiones (
    id SERIAL PRIMARY KEY,
    ley_id INTEGER NOT NULL REFERENCES leyes(id),
    padre_id INTEGER REFERENCES divisiones(id),  -- Auto-referencia
    tipo VARCHAR(20) NOT NULL
        CHECK (tipo IN ('libro', 'titulo', 'capitulo', 'seccion')),
    numero VARCHAR(30),           -- 'PRIMERO', 'I', 'UNICA'
    numero_orden INTEGER,         -- Para ordenamiento
    nombre TEXT,
    path_ids INTEGER[],           -- [abuelo_id, padre_id, self_id]
    path_texto TEXT,              -- "TITULO I > CAPITULO II"
    nivel INTEGER DEFAULT 0,
    orden_global INTEGER
);
```

### 3.4 Tabla: articulos

Artículos con búsqueda full-text.

```sql
CREATE TABLE articulos (
    id SERIAL PRIMARY KEY,
    ley_id INTEGER NOT NULL REFERENCES leyes(id),
    division_id INTEGER REFERENCES divisiones(id),

    -- Numeración desglosada
    numero_raw VARCHAR(30) NOT NULL,   -- "84-E", "32-B BIS"
    numero_base INTEGER,               -- 84, 32
    sufijo VARCHAR(20),                -- "E", "B BIS"
    ordinal VARCHAR(5),                -- "o", "a"

    contenido TEXT NOT NULL,
    es_transitorio BOOLEAN DEFAULT FALSE,
    decreto_dof VARCHAR(100),
    reformas TEXT,
    orden_global INTEGER,

    -- Full-text search
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('spanish_unaccent',
            coalesce(numero_raw, '')), 'A') ||
        setweight(to_tsvector('spanish_unaccent',
            coalesce(contenido, '')), 'B')
    ) STORED
);
```

### 3.5 Vista Materializada

Para consultas rápidas de navegación:

```sql
CREATE MATERIALIZED VIEW jerarquia_completa AS
SELECT
    a.id AS articulo_id,
    a.ley_id,
    l.codigo AS ley_codigo,
    l.nombre AS ley_nombre,
    d.path_texto AS ubicacion,
    a.numero_raw AS articulo,
    a.contenido,
    a.orden_global
FROM articulos a
JOIN leyes l ON a.ley_id = l.id
LEFT JOIN divisiones d ON a.division_id = d.id;
```

---

## 4. Análisis de Tamaños

### 4.1 Resumen de Base de Datos

| Métrica | Valor |
|---------|-------|
| **Tamaño total BD** | ~35 MB |
| **Documentos** | 13 (6 leyes + 6 reglamentos + 1 RMF) |
| **Divisiones** | ~350 |
| **Artículos/Reglas** | 3,536 |
| **Referencias cruzadas** | 3,180 |

### 4.2 Tamaño por Tabla

| Tabla | Total | Datos | Índices |
|-------|-------|-------|---------|
| articulos | ~20 MB | ~4 MB | ~16 MB |
| jerarquia_completa | ~4 MB | - | - |
| referencias_cruzadas | ~500 KB | ~200 KB | ~300 KB |
| divisiones | ~400 KB | ~120 KB | ~280 KB |
| leyes | ~50 KB | ~10 KB | ~40 KB |

### 4.3 Desglose de Índices

| Índice | Tamaño | Tipo |
|--------|--------|------|
| idx_articulos_contenido_trgm | 6.6 MB | GIN (trigrams) |
| idx_articulos_search | 5.2 MB | GIN (tsvector) |
| idx_articulos_numero | 112 KB | B-tree |
| articulos_pkey | 88 KB | B-tree |
| idx_articulos_orden | 88 KB | B-tree |
| idx_jerarquia_articulo | 88 KB | B-tree |
| idx_divisiones_path | 56 KB | GIN (array) |
| idx_articulos_ley | 48 KB | B-tree |
| idx_articulos_transitorio | 48 KB | B-tree |
| idx_articulos_division | 48 KB | B-tree |

**Observaciones:**
- El 83% del espacio de índices está en los índices de búsqueda (FTS + trigrams)
- El índice de trigrams es más grande que el de tsvector por la granularidad
- Los índices B-tree son muy compactos (< 100 KB cada uno)

### 4.4 Contenido por Documento

| Código | Tipo | Arts/Reglas | Prom. Caracteres | Prom. Palabras |
|--------|------|-------------|------------------|----------------|
| LISR | ley | 235 | 4,012 | 802 |
| CFF | ley | 420 | 1,966 | 393 |
| LIVA | ley | 80 | 1,886 | 377 |
| LIEPS | ley | 69 | 1,852 | 370 |
| RMF2025 | resolución | 446 | ~1,500 | ~300 |
| RACERF | reglamento | 196 | 1,269 | 254 |
| RCFF | reglamento | 113 | 1,052 | 210 |
| RISR | reglamento | 313 | 972 | 194 |
| LFT | ley | 1,170 | 835 | 167 |
| LSS | ley | 385 | 805 | 161 |
| RLSS | reglamento | 18 | 736 | 147 |
| RIVA | reglamento | 72 | 532 | 106 |
| RLIEPS | reglamento | 19 | 492 | 98 |

**Observaciones:**
- La LISR tiene los artículos más extensos (800 palabras promedio)
- RMF2025 incluye campo "referencias" con citas a otras leyes

### 4.5 Estructura Jerárquica por Documento

| Código | Tipo | Títulos | Capítulos | Secciones |
|--------|------|---------|-----------|-----------|
| LFT | ley | 12 | 45 | 4 |
| LSS | ley | 5 | 18 | 32 |
| LISR | ley | 7 | 27 | 7 |
| CFF | ley | 5 | 6 | 6 |
| RACERF | reglamento | 7 | 29 | 0 |
| RISR | reglamento | 7 | 19 | 4 |
| RCFF | reglamento | 5 | 15 | 6 |
| LIVA | ley | 0 | 9 | 0 |
| LIEPS | ley | 1 | 6 | 0 |
| RLSS | reglamento | 0 | 6 | 0 |
| RIVA | reglamento | 0 | 6 | 3 |
| RLIEPS | reglamento | 0 | 4 | 0 |

---

## 5. Funciones de Búsqueda

### 5.1 Búsqueda Full-Text

```sql
SELECT * FROM buscar_articulos(
    'factura electronica',  -- query
    ARRAY['CFF', 'LISR'],   -- filtro de leyes
    FALSE,                   -- solo transitorios
    20,                      -- límite
    0                        -- offset
);
```

Retorna: id, ley, número, ubicación, contenido, relevancia, snippet con highlighting.

### 5.2 Búsqueda Fuzzy (tolerante a errores)

```sql
SELECT * FROM buscar_fuzzy('contribullente', 10);
-- Encuentra "contribuyente" a pesar del error
```

### 5.3 Navegación Jerárquica

```sql
-- Estructura de una ley
SELECT * FROM estructura_ley('CFF');

-- Artículos de una división específica
SELECT * FROM articulos_por_division(5);

-- Navegación anterior/siguiente
SELECT * FROM navegar_articulo(123);
```

---

## 6. API REST (PostgREST)

### 6.1 Endpoints de Vistas

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/leyes` | Lista de leyes |
| GET | `/leyes?codigo=eq.CFF` | Ley específica |
| GET | `/divisiones?ley=eq.CFF` | Estructura de ley |
| GET | `/articulos?ley=eq.LISR` | Artículos de una ley |
| GET | `/articulos?es_transitorio=eq.true` | Transitorios |
| GET | `/estadisticas` | Stats generales |

### 6.2 Endpoints RPC (Funciones)

| Método | Endpoint | Body |
|--------|----------|------|
| POST | `/rpc/buscar` | `{"q": "impuesto", "leyes": "CFF,LISR"}` |
| POST | `/rpc/articulo` | `{"art_id": 123}` |
| POST | `/rpc/estructura` | `{"ley_codigo": "CFF"}` |
| POST | `/rpc/navegar` | `{"art_id": 123}` |
| POST | `/rpc/sugerencias` | `{"prefijo": "fac"}` |

---

## 7. Comandos de Administración

### 7.1 Recrear Schema

```bash
# Conectar como superuser para extensiones
sudo -u postgres psql -d leyesmx -c 'CREATE EXTENSION IF NOT EXISTS vector;'

# Ejecutar schema
PGPASSWORD=leyesmx psql -h localhost -U leyesmx -d leyesmx \
    -f backend/sql/001_schema.sql

# Funciones y vistas
PGPASSWORD=leyesmx psql -h localhost -U leyesmx -d leyesmx \
    -f backend/sql/002_functions.sql
PGPASSWORD=leyesmx psql -h localhost -U leyesmx -d leyesmx \
    -f backend/sql/003_api_views.sql
```

### 7.2 Importar Datos

```bash
source .venv/bin/activate
python backend/scripts/importar_leyes.py
```

### 7.3 Refrescar Vista Materializada

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY jerarquia_completa;
```

### 7.4 Verificar Datos

```sql
-- Estadísticas por ley
SELECT * FROM estadisticas_leyes();

-- Probar búsqueda
SELECT * FROM buscar_articulos('deduccion', NULL, FALSE, 5, 0);

-- Ver estructura
SELECT * FROM estructura_ley('CFF');
```

---

## 8. Estructura de Archivos

```
leyes/
├── doc/
│   ├── manifest.json              # Metadatos de documentos
│   ├── leyes/                     # PDF, DOCX, JSON por ley
│   │   ├── cff/, lft/, lisr/, liva/, lieps/, lss/
│   ├── reglamentos/
│   │   ├── rcff/, risr/, riva/, rlieps/, rlft/, rlss/, racerf/
│   └── rmf/                       # Resolución Miscelánea Fiscal
│       └── rmf_2025_compilada.docx
├── scripts/
│   ├── descargar_leyes_mx.py      # Descarga PDFs de leyes
│   ├── convertir_ley.py           # PDF → DOCX → JSON
│   ├── parsear_ley.py             # Parser v2 jerárquico
│   ├── descargar_rmf.py           # Descarga RMF del SAT
│   ├── parsear_rmf.py             # Parser especializado RMF
│   └── extraer_referencias.py     # Extrae referencias cruzadas
├── backend/
│   ├── sql/
│   │   ├── 001_schema.sql         # Tablas e índices
│   │   ├── 002_functions.sql      # Funciones de búsqueda
│   │   └── 003_api_views.sql      # Vistas API PostgREST
│   ├── scripts/
│   │   ├── importar_leyes.py      # Importa leyes a PostgreSQL
│   │   └── importar_rmf.py        # Importa RMF a PostgreSQL
│   └── postgrest.conf
├── frontend/
│   ├── src/
│   │   ├── components/            # ArticlePanel, ResultList, etc.
│   │   ├── hooks/                 # useArticle, useSearch, etc.
│   │   ├── pages/                 # Home, Article, LeyIndex, DivisionView
│   │   └── lib/                   # API client
│   └── package.json
├── DOCUMENTACION_TECNICA.md       # Este documento
└── start.sh                       # Script de inicio
```

---

## 9. Despliegue en Produccion (Caddy)

### 9.1 Arquitectura de Produccion

```
                    Internet
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Caddy Server                             │
│              (HTTPS, CORS, Rate Limiting)                   │
│                                                             │
│  leyesmx.tudominio.com  ──►  /frontend/dist (static)        │
│  leyesmx.tudominio.com/api/* ──► localhost:3010 (PostgREST) │
└─────────────────────────────────────────────────────────────┘
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
    ┌──────────┐               ┌────────────┐
    │ PostgREST│               │ PostgreSQL │
    │  :3010   │──────────────►│   :5432    │
    └──────────┘               └────────────┘
```

### 9.2 Instalacion de Caddy

```bash
# Debian/Ubuntu
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

### 9.3 Caddyfile

Crear `/etc/caddy/Caddyfile`:

```caddyfile
leyesmx.tudominio.com {
    # Logs
    log {
        output file /var/log/caddy/leyesmx.log
        format json
    }

    # Rate limiting (requiere caddy-rate-limit plugin o usar limit_req)
    # Para rate limiting basico, usar el modulo interno:
    @api path /api/*

    # CORS headers para la API
    header /api/* {
        Access-Control-Allow-Origin "https://leyesmx.tudominio.com"
        Access-Control-Allow-Methods "GET, POST, OPTIONS"
        Access-Control-Allow-Headers "Content-Type, Authorization"
        Access-Control-Max-Age "86400"
    }

    # Responder OPTIONS para preflight CORS
    @options method OPTIONS
    handle @options {
        header Access-Control-Allow-Origin "https://leyesmx.tudominio.com"
        header Access-Control-Allow-Methods "GET, POST, OPTIONS"
        header Access-Control-Allow-Headers "Content-Type, Authorization"
        respond "" 204
    }

    # API: proxy a PostgREST
    handle /api/* {
        uri strip_prefix /api
        reverse_proxy localhost:3010 {
            header_up Host {host}
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
        }
    }

    # Frontend: archivos estaticos
    handle {
        root * /var/www/leyesmx/dist
        try_files {path} /index.html
        file_server
    }

    # Seguridad headers
    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        X-XSS-Protection "1; mode=block"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }

    # Compresion
    encode gzip zstd
}
```

### 9.4 Rate Limiting con Caddy

Para rate limiting mas avanzado, usar el plugin `caddy-rate-limit`:

```bash
# Instalar Caddy con el plugin
xcaddy build --with github.com/mholt/caddy-ratelimit
```

Luego en el Caddyfile:

```caddyfile
leyesmx.tudominio.com {
    # Rate limit: 100 requests por minuto por IP
    rate_limit {
        zone api {
            match {
                path /api/*
            }
            key {remote_host}
            window 1m
            events 100
        }
    }

    # ... resto de la configuracion
}
```

### 9.5 Despliegue del Frontend

```bash
# Construir frontend
npm run build

# Copiar a directorio de produccion
sudo mkdir -p /var/www/leyesmx
sudo cp -r frontend/dist/* /var/www/leyesmx/
sudo chown -R caddy:caddy /var/www/leyesmx
```

### 9.6 Servicio PostgREST (systemd)

Crear `/etc/systemd/system/postgrest.service`:

```ini
[Unit]
Description=PostgREST API Server
After=postgresql.service
Requires=postgresql.service

[Service]
User=postgrest
Group=postgrest
ExecStart=/usr/local/bin/postgrest /etc/postgrest/leyesmx.conf
Restart=always
RestartSec=5
Environment=PGRST_DB_URI=postgres://authenticator:PASSWORD@localhost:5432/leyesmx

[Install]
WantedBy=multi-user.target
```

```bash
# Crear usuario sin shell
sudo useradd -r -s /bin/false postgrest

# Crear directorio de config
sudo mkdir -p /etc/postgrest
sudo cp backend/postgrest.conf /etc/postgrest/leyesmx.conf

# Editar para usar variable de entorno
sudo sed -i 's|db-uri = .*|db-uri = "$(PGRST_DB_URI)"|' /etc/postgrest/leyesmx.conf

# Habilitar servicio
sudo systemctl daemon-reload
sudo systemctl enable postgrest
sudo systemctl start postgrest
```

### 9.7 Variables de Entorno en Produccion

Usar archivo de entorno para systemd:

```bash
# Crear archivo de secretos (solo root puede leer)
sudo tee /etc/postgrest/env << 'EOF'
PGRST_DB_URI=postgres://authenticator:TU_PASSWORD_SEGURO@localhost:5432/leyesmx
EOF
sudo chmod 600 /etc/postgrest/env
```

Modificar el servicio:

```ini
[Service]
EnvironmentFile=/etc/postgrest/env
```

### 9.8 Verificacion

```bash
# Verificar servicios
sudo systemctl status caddy
sudo systemctl status postgrest
sudo systemctl status postgresql

# Probar API
curl -s https://leyesmx.tudominio.com/api/leyes | jq

# Probar busqueda
curl -s -X POST https://leyesmx.tudominio.com/api/rpc/buscar \
  -H "Content-Type: application/json" \
  -d '{"q": "factura"}' | jq

# Ver logs
sudo journalctl -u postgrest -f
sudo tail -f /var/log/caddy/leyesmx.log
```

### 9.9 Checklist de Seguridad Produccion

- [ ] Cambiar password de PostgreSQL (`PG_PASS`)
- [ ] Crear usuario `authenticator` con permisos minimos
- [ ] Firewall: solo puertos 80, 443 abiertos
- [ ] PostgREST escucha solo en localhost (127.0.0.1)
- [ ] PostgreSQL escucha solo en localhost
- [ ] Backups automaticos de PostgreSQL
- [ ] Monitoreo con Prometheus/Grafana (opcional)
- [ ] Logs rotativos configurados

---

## 10. Estado de Funcionalidades

### Completado

1. **Referencias Cruzadas** ✅
   - Script `scripts/extraer_referencias.py` extrae referencias del contenido
   - Soporta campo `referencias` de RMF (ej: `CFF 10, LISR 27`)
   - Parsea patrones como `artículo 14-B de este Código`
   - Ignora referencias a la Constitución
   - 3,180 referencias cruzadas en la base de datos
   - Frontend muestra "Este artículo cita" y "Citado por"

2. **Soporte RMF** ✅
   - Scripts `descargar_rmf.py` y `parsear_rmf.py`
   - Importador `backend/scripts/importar_rmf.py`
   - 446 reglas de RMF 2025 importadas
   - Campo `tipo='regla'` para distinguir de artículos
   - Frontend muestra "Regla X.X.X" en lugar de "Artículo"

3. **Frontend Completo** ✅
   - React + TypeScript + TanStack Query
   - Búsqueda full-text con snippets y highlighting
   - Vista de artículo con navegación anterior/siguiente
   - Índice de ley con estructura jerárquica
   - Vista de división (capítulo completo)
   - Panel dividido en desktop (resultados + artículo)
   - Fuente Atkinson Hyperlegible para lectura
   - Tema claro/oscuro

4. **Extracción de Fracciones** ✅
   - Script `scripts/extraer_fracciones.py`
   - Extrae fracciones (I, II), incisos (a, b), numerales (1, 2)
   - 11,148 elementos en 1,040 artículos
   - Visualización jerárquica con indentación en frontend
   - Función SQL `api.fracciones_articulo`

### Pendiente

1. **Búsqueda Semántica con IA**
   - Instalar extensión `vector` como superuser
   - Generar embeddings con OpenAI ada-002
   - Habilitar función `buscar_semantico`

2. **PWA y Modo Offline**
   - Service Worker para cache
   - Sincronización de búsquedas recientes

---

## 10. Notas Técnicas

### Configuración de Búsqueda en Español

```sql
CREATE TEXT SEARCH CONFIGURATION spanish_unaccent (COPY = spanish);
ALTER TEXT SEARCH CONFIGURATION spanish_unaccent
    ALTER MAPPING FOR hword, hword_part, word
    WITH unaccent, spanish_stem;
```

Esto permite buscar "artículo" encontrando "articulo" y viceversa.

### Índice de Trigrams

El índice `idx_articulos_contenido_trgm` permite búsqueda fuzzy:
- Encuentra "contribuyente" buscando "contribullente"
- Usa el operador `%` de similaridad
- Configurable con `pg_trgm.similarity_threshold`

### Columna Generada para tsvector

La columna `search_vector` se genera automáticamente:
- Peso A para número de artículo (mayor relevancia)
- Peso B para contenido
- Se actualiza automáticamente con triggers

---

*Documento generado automáticamente - LeyesMX v2.0*
