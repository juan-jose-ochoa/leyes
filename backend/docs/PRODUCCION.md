# LeyesMX - Despliegue en Producción

## Arquitectura

```
                    Internet
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Caddy Server                             │
│              (HTTPS, CORS, Rate Limiting)                   │
│                                                             │
│  leyesmx.tudominio.com     → /frontend/dist (static)        │
│  leyesmx.tudominio.com/api → localhost:3010 (PostgREST)     │
└─────────────────────────────────────────────────────────────┘
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
    ┌──────────┐               ┌────────────┐
    │ PostgREST│               │ PostgreSQL │
    │  :3010   │──────────────►│   :5432    │
    └──────────┘               └────────────┘
```

## Instalación de Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

## Caddyfile

Crear `/etc/caddy/Caddyfile`:

```caddyfile
leyesmx.tudominio.com {
    log {
        output file /var/log/caddy/leyesmx.log
        format json
    }

    # CORS para API
    header /api/* {
        Access-Control-Allow-Origin "https://leyesmx.tudominio.com"
        Access-Control-Allow-Methods "GET, POST, OPTIONS"
        Access-Control-Allow-Headers "Content-Type, Authorization"
    }

    # Preflight CORS
    @options method OPTIONS
    handle @options {
        respond "" 204
    }

    # API: proxy a PostgREST
    handle /api/* {
        uri strip_prefix /api
        reverse_proxy localhost:3010
    }

    # Frontend: archivos estáticos
    handle {
        root * /var/www/leyesmx/dist
        try_files {path} /index.html
        file_server
    }

    # Seguridad
    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        -Server
    }

    encode gzip zstd
}
```

## Despliegue del Frontend

```bash
npm run build
sudo mkdir -p /var/www/leyesmx
sudo cp -r frontend/dist/* /var/www/leyesmx/
sudo chown -R caddy:caddy /var/www/leyesmx
```

## Servicio PostgREST (systemd)

Crear `/etc/systemd/system/postgrest.service`:

```ini
[Unit]
Description=PostgREST API Server
After=postgresql.service

[Service]
User=postgrest
ExecStart=/usr/local/bin/postgrest /etc/postgrest/leyesmx.conf
Restart=always
EnvironmentFile=/etc/postgrest/env

[Install]
WantedBy=multi-user.target
```

```bash
sudo useradd -r -s /bin/false postgrest
sudo mkdir -p /etc/postgrest
sudo cp backend/postgrest.conf /etc/postgrest/leyesmx.conf

# Secretos
sudo tee /etc/postgrest/env << 'EOF'
PGRST_DB_URI=postgres://authenticator:PASSWORD@localhost:5432/digiapps
EOF
sudo chmod 600 /etc/postgrest/env

sudo systemctl daemon-reload
sudo systemctl enable --now postgrest
```

## Verificación

```bash
sudo systemctl status caddy postgrest postgresql

curl -s https://leyesmx.tudominio.com/api/v_leyes | jq
```

## Checklist de Seguridad

- [ ] Cambiar passwords de PostgreSQL
- [ ] Firewall: solo puertos 80, 443
- [ ] PostgREST solo en localhost
- [ ] PostgreSQL solo en localhost
- [ ] Backups automáticos
- [ ] Logs rotativos
