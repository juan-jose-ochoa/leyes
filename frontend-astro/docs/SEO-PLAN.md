# Plan SEO - LeyesMX

> **Estado:** En progreso
> **Fecha:** 2026-01-22

## Estado Actual

| Prioridad | Iniciativa | Estado | Impacto | Complejidad |
|-----------|-----------|--------|---------|-------------|
| **P1** | og:image para compartir | ✅ Hecho | Alto | Trivial |
| **P2** | Botones compartir + Web Share API + UTM | ✅ Hecho | Alto | Baja |
| **P3** | Schema BreadcrumbList | ✅ Hecho | Medio | Baja |
| **P4** | Schema WebSite + SearchAction | ❌ Pendiente | Medio | Baja |

---

## ✅ P2: Botones de Compartir (Completado)

**Commit:** `e854529` - Add social share buttons to article pages

- Componente `ShareButtons.astro` con dropdown
- Redes: WhatsApp, X, Facebook, LinkedIn, Telegram
- Web Share API para móviles
- UTM tracking por red social
- Copiar enlace con feedback visual

---

## P1: og:image para Compartir

### Decisión
Opción A: Imagen única para todo el sitio (simplicidad)

### Implementación
1. Crear imagen `public/og-default.png` (1200x630px)
2. Agregar meta tags en `BaseLayout.astro`:
   - `og:image`, `og:image:width`, `og:image:height`
   - `twitter:card`, `twitter:image`
3. Verificar `site` en `astro.config.mjs`

### Escalabilidad futura
- Opción B: Una imagen por ley (~20 imágenes)
- Opción C: Una imagen por artículo (~5,000+ con Sharp)

---

## ✅ P3: Schema BreadcrumbList (Completado)

JSON-LD en páginas de artículos con jerarquía completa:
```json
{
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "name": "LISR", "item": "https://leyesmx.com/lisr/" },
    { "name": "Titulo IV", "item": "https://leyesmx.com/lisr/titulo/iv/" },
    { "name": "Capitulo I", "item": "https://leyesmx.com/lisr/capitulo/iv/i/" },
    { "name": "Artículo 96" }
  ]
}
```

Google mostrará en SERP: `leyesmx.com › LISR › Titulo IV › Capitulo I`

---

## P4: Schema WebSite + SearchAction (Pendiente)

En homepage, agregar:
```json
{
  "@type": "WebSite",
  "name": "LeyesMX",
  "url": "https://leyesmx.com",
  "potentialAction": {
    "@type": "SearchAction",
    "target": "https://leyesmx.com/buscar/?q={search_term_string}",
    "query-input": "required name=search_term_string"
  }
}
```

---

## Lo que ya está bien

- URLs semánticas y limpias
- Sitemap completo (index + 18 sitemaps por ley)
- Canonical URLs dinámicas
- Open Graph básico (title, description, url)
- Schema LegalDocument en artículos
- H1 descriptiva por página
