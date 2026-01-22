/**
 * Genera imagen OG para compartir en redes sociales
 * Tamaño: 1200x630px (estándar Open Graph)
 */

import sharp from 'sharp';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Colores del proyecto (de tailwind.config.mjs)
const PRIMARY_600 = '#16a34a';  // Verde mexicano
const PRIMARY_800 = '#166534';
const WHITE = '#ffffff';

// Dimensiones estándar OG
const WIDTH = 1200;
const HEIGHT = 630;

// SVG de la imagen
const svg = `
<svg width="${WIDTH}" height="${HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:${PRIMARY_600}"/>
      <stop offset="100%" style="stop-color:${PRIMARY_800}"/>
    </linearGradient>
  </defs>

  <!-- Fondo con gradiente -->
  <rect width="100%" height="100%" fill="url(#bg)"/>

  <!-- Patrón decorativo sutil -->
  <g opacity="0.1">
    <rect x="50" y="50" width="100" height="100" rx="10" fill="${WHITE}"/>
    <rect x="1050" y="480" width="100" height="100" rx="10" fill="${WHITE}"/>
  </g>

  <!-- Logo/Texto principal -->
  <text x="600" y="280"
        font-family="system-ui, -apple-system, sans-serif"
        font-size="120"
        font-weight="700"
        fill="${WHITE}"
        text-anchor="middle">
    LeyesMX
  </text>

  <!-- Tagline -->
  <text x="600" y="380"
        font-family="system-ui, -apple-system, sans-serif"
        font-size="36"
        font-weight="400"
        fill="${WHITE}"
        text-anchor="middle"
        opacity="0.9">
    Leyes Fiscales y Laborales de México
  </text>

  <!-- URL -->
  <text x="600" y="550"
        font-family="system-ui, -apple-system, sans-serif"
        font-size="28"
        font-weight="300"
        fill="${WHITE}"
        text-anchor="middle"
        opacity="0.7">
    leyesmx.com
  </text>
</svg>
`;

async function generateOgImage() {
  const outputPath = join(__dirname, '..', 'public', 'og-default.png');

  await sharp(Buffer.from(svg))
    .png()
    .toFile(outputPath);

  console.log(`✓ Imagen OG generada: ${outputPath}`);
  console.log(`  Tamaño: ${WIDTH}x${HEIGHT}px`);
}

generateOgImage().catch(console.error);
