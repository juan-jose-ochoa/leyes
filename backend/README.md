# LeyesMX Backend

API REST para búsqueda de leyes fiscales y laborales mexicanas.

## Stack

- **PostgreSQL 16** - Base de datos con FTS y pgvector
- **PostgREST** - API REST automática desde PostgreSQL
- **Nginx** - Reverse proxy y SSL (producción)

## Instalación

### 1. Requisitos

```bash
# Ubuntu 24.04
sudo apt update
sudo apt install postgresql-16 postgresql-16-pgvector

# PostgREST (descargar binario)
# https://github.com/PostgREST/postgrest/releases
wget https://github.com/PostgREST/postgrest/releases/download/v12.2.3/postgrest-v12.2.3-linux-static-x64.tar.xz
tar -xf postgrest-v12.2.3-linux-static-x64.tar.xz
sudo mv postgrest /usr/local/bin/

# Python (para migración)
pip install psycopg2-binary
```

### 2. Crear Base de Datos

```bash
# Crear base de datos
sudo -u postgres createdb leyesmx

# Ejecutar scripts SQL en orden
sudo -u postgres psql leyesmx < sql/001_schema.sql
sudo -u postgres psql leyesmx < sql/002_functions.sql
sudo -u postgres psql leyesmx < sql/003_api_views.sql

# Cambiar password del rol authenticator
sudo -u postgres psql leyesmx -c "ALTER ROLE authenticator PASSWORD 'tu_password_seguro';"
```

### 3. Migrar Datos

```bash
# Asegúrate de tener los archivos .db generados
cd /home/jochoa/Java/workspace/leyes
python scripts/convertir_ley.py

# Ejecutar migración
python backend/scripts/migrate_sqlite.py
```

### 4. Iniciar PostgREST

```bash
# Editar postgrest.conf con tu password
# db-uri = "postgres://authenticator:tu_password_seguro@localhost:5432/leyesmx"

# Iniciar
postgrest backend/postgrest.conf
```

### 5. Probar API

```bash
# Lista de leyes
curl http://localhost:3000/leyes

# Buscar artículos
curl -X POST http://localhost:3000/rpc/buscar \
  -H "Content-Type: application/json" \
  -d '{"q": "factura electrónica"}'

# Artículo específico
curl "http://localhost:3000/articulos?id=eq.1"

# Filtrar por ley
curl "http://localhost:3000/articulos?ley=eq.CFF&limit=10"
```

## Endpoints API

### Vistas (GET)

| Endpoint | Descripción |
|----------|-------------|
| `/leyes` | Lista de leyes y reglamentos |
| `/articulos` | Todos los artículos (paginado) |
| `/articulos?ley=eq.CFF` | Artículos del CFF |
| `/articulos?id=eq.123` | Artículo por ID |
| `/referencias` | Referencias cruzadas |
| `/estadisticas` | Stats generales |

### Funciones RPC (POST)

| Endpoint | Body | Descripción |
|----------|------|-------------|
| `/rpc/buscar` | `{"q": "...", "leyes": "CFF,LISR", "limite": 20, "pagina": 1}` | Búsqueda full-text |
| `/rpc/articulo` | `{"art_id": 123}` | Artículo con referencias |
| `/rpc/sugerencias` | `{"prefijo": "fac"}` | Autocompletado |
| `/rpc/stats` | `{}` | Stats por ley |

## Configuración Nginx (Producción)

```nginx
server {
    listen 443 ssl http2;
    server_name api.leyesmx.com;

    ssl_certificate /etc/letsencrypt/live/api.leyesmx.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.leyesmx.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # CORS
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
        add_header Access-Control-Allow-Headers "Content-Type, Authorization";

        if ($request_method = OPTIONS) {
            return 204;
        }
    }
}
```

## Systemd Service

```ini
# /etc/systemd/system/postgrest.service
[Unit]
Description=PostgREST API Server
After=postgresql.service

[Service]
Type=simple
User=www-data
ExecStart=/usr/local/bin/postgrest /opt/leyesmx/backend/postgrest.conf
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable postgrest
sudo systemctl start postgrest
```

## Estructura de Archivos

```
backend/
├── sql/
│   ├── 001_schema.sql      # Tablas e índices
│   ├── 002_functions.sql   # Funciones de búsqueda
│   └── 003_api_views.sql   # Vistas y permisos API
├── scripts/
│   └── migrate_sqlite.py   # Migración desde SQLite
├── postgrest.conf          # Configuración PostgREST
└── README.md
```
