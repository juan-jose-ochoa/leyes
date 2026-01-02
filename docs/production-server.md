# Configuración del Servidor de Producción

Servidor: AWS EC2 Ubuntu
IP: `54.202.41.70`

## 1. Usuario jochoa (sudoer)

### LOCAL: Conectar al servidor como ubuntu
```bash
ssh -i enogales_production.pem ubuntu@54.202.41.70
```

### SERVIDOR: Crear usuario jochoa
```bash
sudo adduser jochoa
sudo usermod -aG sudo jochoa
```

### LOCAL: Copiar tus SSH keys al servidor
```bash
cat ~/.ssh/id_ed25519.pub ~/.ssh/id_ed25519_sk.pub | ssh -i enogales_production.pem ubuntu@54.202.41.70 "sudo mkdir -p /home/jochoa/.ssh && sudo tee /home/jochoa/.ssh/authorized_keys && sudo chown -R jochoa:jochoa /home/jochoa/.ssh && sudo chmod 700 /home/jochoa/.ssh && sudo chmod 600 /home/jochoa/.ssh/authorized_keys"
```

### LOCAL: Probar conexión como jochoa (sin .pem)
```bash
ssh jochoa@54.202.41.70
```

## 2. PostgreSQL 18

### SERVIDOR: Agregar repositorio oficial PostgreSQL
```bash
# Instalar dependencias
sudo apt update
sudo apt install -y curl ca-certificates

# Crear directorio para keyrings
sudo install -d /usr/share/postgresql-common/pgdg

# Descargar y verificar clave GPG
sudo curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc

# Agregar repositorio
sudo sh -c 'echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
```

### SERVIDOR: Instalar PostgreSQL 18
```bash
sudo apt update
sudo apt install -y postgresql-18 postgresql-contrib-18

# Verificar version
psql --version
# psql (PostgreSQL) 18.1

sudo systemctl status postgresql
```

### SERVIDOR: Crear usuario y base de datos
```bash
sudo -u postgres psql <<EOF
CREATE USER leyesmx WITH PASSWORD 'CAMBIAR_PASSWORD';
CREATE DATABASE digiapps OWNER leyesmx;
\c digiapps
CREATE SCHEMA leyesmx AUTHORIZATION leyesmx;
EOF
```

## 3. PostgREST

### SERVIDOR: Instalar PostgREST
```bash
POSTGREST_VERSION=v14.2

# Detectar arquitectura
if [ "$(uname -m)" = "aarch64" ]; then
  POSTGREST_FILE=postgrest-$POSTGREST_VERSION-ubuntu-aarch64.tar.xz
else
  POSTGREST_FILE=postgrest-$POSTGREST_VERSION-linux-static-x86-64.tar.xz
fi

wget https://github.com/PostgREST/postgrest/releases/download/$POSTGREST_VERSION/$POSTGREST_FILE
tar xJf $POSTGREST_FILE
sudo mv postgrest /usr/local/bin/
rm $POSTGREST_FILE

postgrest --version
```

### Configuración PostgREST

```bash
sudo mkdir -p /etc/postgrest
sudo nano /etc/postgrest/config
```

Contenido de `/etc/postgrest/config`:
```ini
db-uri = "postgres://leyesmx:CAMBIAR_PASSWORD@localhost:5432/digiapps"
db-schemas = "leyesmx"
db-anon-role = "web_anon"
server-port = 3000
```

### Crear rol anónimo

```bash
sudo -u postgres psql -d digiapps <<EOF
CREATE ROLE web_anon NOLOGIN;
GRANT web_anon TO leyesmx;
GRANT USAGE ON SCHEMA leyesmx TO web_anon;
GRANT SELECT ON ALL TABLES IN SCHEMA leyesmx TO web_anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA leyesmx GRANT SELECT ON TABLES TO web_anon;
EOF
```

### Servicio systemd

```bash
sudo nano /etc/systemd/system/postgrest.service
```

Contenido:
```ini
[Unit]
Description=PostgREST API
After=postgresql.service

[Service]
ExecStart=/usr/local/bin/postgrest /etc/postgrest/config
Restart=always
User=nobody

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable postgrest
sudo systemctl start postgrest
sudo systemctl status postgrest
```

## 4. Caddy (Reverse Proxy)

### SERVIDOR: Instalar Caddy
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy

# Verificar
caddy version
```

### Configuración Caddy

```bash
sudo nano /etc/caddy/Caddyfile
```

#### Opción A: Con Cloudflare Proxy (recomendado)

DNS en Cloudflare con proxy activado (nube naranja). Cloudflare maneja HTTPS.

```caddy
:80 {
    handle /leyesmx/* {
        uri strip_prefix /leyesmx
        reverse_proxy localhost:3000

        header Access-Control-Allow-Origin "https://leyes.pages.dev"
        header Access-Control-Allow-Methods "GET, POST, OPTIONS"
        header Access-Control-Allow-Headers "Content-Type"
    }

    handle {
        respond "OK" 200
    }
}
```

Beneficios: DDoS protection, IP oculta, caché edge, analytics.

#### Opción B: Sin Cloudflare Proxy (Let's Encrypt)

DNS apuntando directamente a la IP (sin proxy). Caddy genera HTTPS automáticamente.

```caddy
api.leyesfiscalesmexico.com {
    handle /leyesmx/* {
        uri strip_prefix /leyesmx
        reverse_proxy localhost:3000

        header Access-Control-Allow-Origin "https://leyes.pages.dev"
        header Access-Control-Allow-Methods "GET, POST, OPTIONS"
        header Access-Control-Allow-Headers "Content-Type"
    }

    handle {
        respond "OK" 200
    }
}
```

Beneficios: Menos latencia, sin dependencia de terceros.

---

```bash
sudo systemctl reload caddy
sudo systemctl status caddy
```

## 5. Importar datos

### LOCAL: Exportar y copiar al servidor
```bash
sudo -u postgres pg_dump -d digiapps -n leyesmx > backup.sql
scp backup.sql jochoa@54.202.41.70:~
rm backup.sql
```

### SERVIDOR: Importar datos
```bash
sudo -u postgres psql -d digiapps < ~/backup.sql
rm ~/backup.sql
```

## 6. Verificar

### SERVIDOR: Probar PostgreSQL y PostgREST
```bash
psql -h localhost -U leyesmx -d digiapps -c "SELECT COUNT(*) FROM leyesmx.leyes;"
curl http://localhost:3000/leyes
```

### LOCAL: Probar acceso externo vía Caddy
```bash
curl http://54.202.41.70/leyesmx/v_leyes
```

## Puertos requeridos (Security Group AWS)

| Puerto | Protocolo | Uso |
|--------|-----------|-----|
| 22 | TCP | SSH |
| 80 | TCP | HTTP (Caddy) |
| 443 | TCP | HTTPS (Caddy) |
