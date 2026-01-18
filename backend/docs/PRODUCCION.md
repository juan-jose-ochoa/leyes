# LeyesMX - Producción

## Arquitectura

```
                    Internet
                        │
                        ▼
                  ┌───────────┐
                  │Cloudflare │
                  │  Pages    │
                  └─────┬─────┘
                        │
                        ▼
              leyes.pages.dev
              (Astro SSG)
```

El sitio es completamente estático (SSG). No hay backend ni base de datos en producción.

## Despliegue

### Frontend (Cloudflare Pages)

Cloudflare Pages despliega automáticamente desde el repositorio:

```bash
git push origin main
```

Build settings en Cloudflare:
- **Build command:** `npm run build`
- **Build output directory:** `dist`
- **Root directory:** `frontend-astro`

## Flujo de Actualización de Contenido

Cuando se actualiza una ley:

```bash
# 1. Extraer estructura y contenido
python backend/etl/extraer_mapa.py LISR
python backend/etl/extraer.py LISR

# 2. Generar datos para Astro
python backend/scripts/generar-datos-astro.py

# 3. Commit y push
git add .
git commit -m "Update LISR content"
git push origin main

# 4. Cloudflare Pages rebuilds automáticamente
```

## Verificación

```bash
# Frontend
curl -s https://leyes.pages.dev | head
```

## Dominio

- **URL:** `leyes.pages.dev` (Cloudflare Pages)
- **Custom domain:** Configurar en Cloudflare Pages dashboard si se requiere
