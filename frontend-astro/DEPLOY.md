# Deploy a Cloudflare Pages

## Requisitos Previos

- Cuenta en Cloudflare (gratis)
- Repositorio en GitHub/GitLab conectado
- Dominio configurado en Cloudflare (opcional)

## Configuración en Cloudflare

### 1. Crear Proyecto

1. Ir a [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Seleccionar **Pages** en el menú lateral
3. Click en **Create a project** → **Connect to Git**
4. Autorizar acceso al repositorio
5. Seleccionar el repositorio `leyes`

### 2. Build Settings

| Campo | Valor |
|-------|-------|
| Production branch | `main` (o tu branch de producción) |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | `frontend-astro` |

### 3. Variables de Entorno

No se requieren variables de entorno para el build.

### 4. Deploy

Click en **Save and Deploy**. El primer build toma ~2 minutos.

## Dominio Personalizado

### Opción A: Subdominio de Cloudflare
El proyecto estará disponible en `proyecto.pages.dev` automáticamente.

### Opción B: Dominio Propio

1. En el proyecto de Pages, ir a **Custom domains**
2. Click **Set up a custom domain**
3. Ingresar `leyesmx.com`
4. Si el dominio ya está en Cloudflare, los DNS se configuran automáticamente
5. Esperar propagación DNS (minutos a horas)

## Headers y Cache

Los headers de cache están configurados en `public/_headers`:

- Assets (`/_astro/*`): Cache inmutable 1 año
- Pagefind: Cache 1 día
- Fuentes: Cache inmutable 1 año
- HTML: Sin cache (siempre fresco)

## Verificación Post-Deploy

```bash
# Verificar sitemap
curl https://leyesmx.com/sitemap.xml | head -20

# Verificar robots.txt
curl https://leyesmx.com/robots.txt

# Verificar headers de cache
curl -I https://leyesmx.com/_astro/some-file.css

# Lighthouse
npx lighthouse https://leyesmx.com --view
```

## Métricas Esperadas

| Métrica | Valor |
|---------|-------|
| Build time | ~2 min |
| Páginas | 5,815 |
| Tamaño dist | 108 MB |
| Lighthouse Performance | 95+ |
| Lighthouse SEO | 95+ |

## Rollback

Cloudflare Pages mantiene historial de deploys. Para rollback:

1. Ir a **Deployments** en el proyecto
2. Encontrar el deploy anterior funcionando
3. Click en **...** → **Rollback to this deploy**

## CI/CD Automático

Cada push a la branch de producción triggerea un nuevo deploy automáticamente.
