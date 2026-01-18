import type { APIRoute, GetStaticPaths } from 'astro';
import catalogo from '../data/catalogo.json';

// Importar estructuras
import cffEstructura from '../data/cff/estructura.json';
import cpeumEstructura from '../data/cpeum/estructura.json';
import laEstructura from '../data/la/estructura.json';
import lfdcEstructura from '../data/lfdc/estructura.json';
import lftEstructura from '../data/lft/estructura.json';
import liepsEstructura from '../data/lieps/estructura.json';
import lifEstructura from '../data/lif/estructura.json';
import linfonavitEstructura from '../data/linfonavit/estructura.json';
import lisrEstructura from '../data/lisr/estructura.json';
import lisssteEstructura from '../data/lissste/estructura.json';
import livaEstructura from '../data/liva/estructura.json';
import lssEstructura from '../data/lss/estructura.json';
import racerfEstructura from '../data/racerf/estructura.json';
import rcffEstructura from '../data/rcff/estructura.json';
import rlftEstructura from '../data/rlft/estructura.json';
import rliepsEstructura from '../data/rlieps/estructura.json';
import rlisrEstructura from '../data/rlisr/estructura.json';
import rlivaEstructura from '../data/rliva/estructura.json';
import rlssEstructura from '../data/rlss/estructura.json';
import rmfEstructura from '../data/rmf/estructura.json';

// Importar artículos
import cffArticulos from '../data/cff/articulos.json';
import cpeumArticulos from '../data/cpeum/articulos.json';
import laArticulos from '../data/la/articulos.json';
import lfdcArticulos from '../data/lfdc/articulos.json';
import lftArticulos from '../data/lft/articulos.json';
import liepsArticulos from '../data/lieps/articulos.json';
import lifArticulos from '../data/lif/articulos.json';
import linfonavitArticulos from '../data/linfonavit/articulos.json';
import lisrArticulos from '../data/lisr/articulos.json';
import lisssteArticulos from '../data/lissste/articulos.json';
import livaArticulos from '../data/liva/articulos.json';
import lssArticulos from '../data/lss/articulos.json';
import racerfArticulos from '../data/racerf/articulos.json';
import rcffArticulos from '../data/rcff/articulos.json';
import rlftArticulos from '../data/rlft/articulos.json';
import rliepsArticulos from '../data/rlieps/articulos.json';
import rlisrArticulos from '../data/rlisr/articulos.json';
import rlivaArticulos from '../data/rliva/articulos.json';
import rlssArticulos from '../data/rlss/articulos.json';
import rmfArticulos from '../data/rmf/articulos.json';

const estructurasMap: Record<string, any> = {
  cff: cffEstructura, cpeum: cpeumEstructura, la: laEstructura, lfdc: lfdcEstructura,
  lft: lftEstructura, lieps: liepsEstructura, lif: lifEstructura, linfonavit: linfonavitEstructura,
  lisr: lisrEstructura, lissste: lisssteEstructura, liva: livaEstructura, lss: lssEstructura,
  racerf: racerfEstructura, rcff: rcffEstructura, rlft: rlftEstructura, rlieps: rliepsEstructura,
  rlisr: rlisrEstructura, rliva: rlivaEstructura, rlss: rlssEstructura, rmf: rmfEstructura,
};

const articulosMap: Record<string, any[]> = {
  cff: cffArticulos, cpeum: cpeumArticulos, la: laArticulos, lfdc: lfdcArticulos,
  lft: lftArticulos, lieps: liepsArticulos, lif: lifArticulos, linfonavit: linfonavitArticulos,
  lisr: lisrArticulos, lissste: lisssteArticulos, liva: livaArticulos, lss: lssArticulos,
  racerf: racerfArticulos, rcff: rcffArticulos, rlft: rlftArticulos, rlieps: rliepsArticulos,
  rlisr: rlisrArticulos, rliva: rlivaArticulos, rlss: rlssArticulos, rmf: rmfArticulos,
};

function toSlug(numero: string): string {
  return numero.toLowerCase().replace(/\s+/g, '-');
}

function extractDivisionUrls(divisiones: any[], leyCode: string, parentPath: string[] = []): string[] {
  const urls: string[] = [];
  for (const div of divisiones) {
    const currentPath = [...parentPath, toSlug(div.numero)];
    urls.push(`/${leyCode}/${div.tipo}/${currentPath.join('/')}`);
    if (div.hijos && div.hijos.length > 0) {
      urls.push(...extractDivisionUrls(div.hijos, leyCode, currentPath));
    }
  }
  return urls;
}

export const getStaticPaths: GetStaticPaths = () => {
  return catalogo.leyes.map(ley => ({
    params: { ley: ley.codigo.toLowerCase() }
  }));
};

export const GET: APIRoute = async ({ params, site }) => {
  const leyCode = params.ley as string;
  const baseUrl = site?.toString().replace(/\/$/, '') || 'https://leyesmx.com';

  const urls: Array<{ loc: string; priority: string; changefreq: string }> = [];

  // Índice de ley
  urls.push({ loc: `${baseUrl}/${leyCode}`, priority: '0.9', changefreq: 'monthly' });

  // Lista de artículos
  urls.push({ loc: `${baseUrl}/${leyCode}/articulos`, priority: '0.7', changefreq: 'monthly' });

  // Artículos individuales
  const articulos = articulosMap[leyCode] || [];
  for (const art of articulos) {
    urls.push({
      loc: `${baseUrl}/${leyCode}/articulo/${encodeURIComponent(art.numero)}`,
      priority: '0.8',
      changefreq: 'yearly'
    });
  }

  // Divisiones (títulos, capítulos, secciones)
  const estructura = estructurasMap[leyCode];
  if (estructura?.divisiones) {
    const divisionUrls = extractDivisionUrls(estructura.divisiones, leyCode);
    for (const url of divisionUrls) {
      urls.push({ loc: `${baseUrl}${url}`, priority: '0.6', changefreq: 'monthly' });
    }
  }

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map(u => `  <url>
    <loc>${u.loc}</loc>
    <changefreq>${u.changefreq}</changefreq>
    <priority>${u.priority}</priority>
  </url>`).join('\n')}
</urlset>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml',
      'Cache-Control': 'public, max-age=86400'
    }
  });
};
