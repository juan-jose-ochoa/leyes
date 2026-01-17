import type { APIRoute } from 'astro';
import catalogo from '../data/catalogo.json';

/**
 * Sitemap Index - Lista todos los sitemaps individuales
 */
export const GET: APIRoute = async ({ site }) => {
  const baseUrl = site?.toString().replace(/\/$/, '') || 'https://leyesmx.com';
  const today = new Date().toISOString().split('T')[0];

  const sitemaps = [
    { loc: `${baseUrl}/sitemap-main.xml`, lastmod: today },
    ...catalogo.leyes.map(ley => ({
      loc: `${baseUrl}/sitemap-${ley.codigo.toLowerCase()}.xml`,
      lastmod: ley.ultima_reforma_dof || today
    }))
  ];

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${sitemaps.map(s => `  <sitemap>
    <loc>${s.loc}</loc>
    <lastmod>${s.lastmod}</lastmod>
  </sitemap>`).join('\n')}
</sitemapindex>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml',
      'Cache-Control': 'public, max-age=86400'
    }
  });
};
