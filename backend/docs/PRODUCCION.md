# LeyesMX - Producción

## Servidor

- **IP:** `54.202.41.70`
- **SSH:** `ssh jochoa@54.202.41.70`
- **Dominio API:** `api.leyesfiscalesmexico.com`
- **Frontend:** `leyes.pages.dev` (Cloudflare Pages)

## Arquitectura

```
                    Internet
                        │
                        ▼
                  ┌───────────┐
                  │Cloudflare │
                  └─────┬─────┘
          ┌─────────────┴─────────────┐
          ▼                           ▼
   leyes.pages.dev            api.leyesfiscalesmexico.com
   (Frontend)                         │
                                      ▼
                              ┌─────────────┐
                              │   Caddy     │ :443
                              │  (54.202.41.70)
                              └──────┬──────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              /leyesmx/*        /pdfs/*          / (health)
                    │                │
                    ▼                ▼
              ┌──────────┐    /var/www/leyesmx/pdfs/
              │PostgREST │
              │  :3000   │
              └────┬─────┘
                   │
                   ▼
              ┌──────────┐
              │PostgreSQL│
              │  :5432   │
              └──────────┘
```

## Estructura en Servidor

```
/var/www/leyesmx/
└── pdfs/
    ├── cff/documento.pdf
    ├── lisr/documento.pdf
    └── ...
```

---

# Despliegue

## Backend (BD + PDFs)

```bash
./deploy-backend.sh
```

El script:
1. Exporta el schema `leyesmx` de la BD local
2. Sube el dump al servidor
3. Restaura la BD en el servidor (pide contraseña sudo)
4. Reinicia PostgREST
5. Sube todos los PDFs al servidor

## Frontend

Cloudflare Pages despliega automáticamente desde el repositorio:

```bash
git push origin main
```

---

# Configuración Inicial (solo primera vez)

## Caddy - Agregar ruta de PDFs

```bash
ssh jochoa@54.202.41.70
sudo nano /etc/caddy/Caddyfile
```

Contenido completo:
```caddyfile
api.leyesfiscalesmexico.com {
    tls /etc/caddy/certs/leyesfiscalesmexico.pem /etc/caddy/certs/leyesfiscalesmexico-key.pem

    # API
    handle /leyesmx/* {
        uri strip_prefix /leyesmx
        reverse_proxy localhost:3000
    }

    # PDFs
    handle /pdfs/* {
        root * /var/www/leyesmx
        file_server
        header Cache-Control "public, max-age=604800"
    }

    handle {
        respond "OK" 200
    }
}
```

```bash
sudo systemctl reload caddy
exit
```

---

# Verificación

```bash
# API
curl -s https://api.leyesfiscalesmexico.com/leyesmx/v_leyes | head

# PDF (debe retornar 200)
curl -I https://api.leyesfiscalesmexico.com/pdfs/cff/documento.pdf

# Frontend
curl -s https://leyes.pages.dev | head
```

## Verificar Servicios

```bash
ssh jochoa@54.202.41.70 "systemctl status postgresql postgrest caddy"
```

---

# Instalación Inicial del Servidor

Ver: [docs/production-server.md](../../docs/production-server.md) para instalación desde cero de PostgreSQL, PostgREST, Caddy y certificados SSL.
