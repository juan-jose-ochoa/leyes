/**
 * Genera imágenes OG para cada ley del catálogo
 * Tamaño: 1200x630px (estándar Open Graph)
 */

import sharp from 'sharp';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Colores del proyecto
const PRIMARY_600 = '#16a34a';
const PRIMARY_800 = '#166534';
const WHITE = '#ffffff';

// Dimensiones estándar OG
const WIDTH = 1200;
const HEIGHT = 630;

/**
 * Determina el tamaño de fuente del código según su longitud
 */
function getCodigoFontSize(codigo) {
  const len = codigo.length;
  if (len <= 3) return 160;
  if (len <= 5) return 140;
  if (len <= 7) return 120;
  return 100;
}

/**
 * Divide el nombre en líneas de máximo maxChars caracteres
 * Respeta palabras completas
 */
function wrapText(text, maxChars = 45) {
  const words = text.split(' ');
  const lines = [];
  let currentLine = '';

  for (const word of words) {
    const testLine = currentLine ? `${currentLine} ${word}` : word;
    if (testLine.length <= maxChars) {
      currentLine = testLine;
    } else {
      if (currentLine) lines.push(currentLine);
      currentLine = word;
    }
  }
  if (currentLine) lines.push(currentLine);

  return lines.slice(0, 3); // Máximo 3 líneas
}

/**
 * Genera el SVG para una ley
 */
function generateSvg(codigo, nombre) {
  const codigoFontSize = getCodigoFontSize(codigo);
  const lines = wrapText(nombre, 40); // Menos chars por línea para fuente más grande
  const lineCount = lines.length;

  // Ajustar posiciones Y según número de líneas
  let codigoY, nombreStartY;
  if (lineCount === 1) {
    codigoY = 320;
    nombreStartY = 440;
  } else if (lineCount === 2) {
    codigoY = 300;
    nombreStartY = 410;
  } else {
    codigoY = 280;
    nombreStartY = 380;
  }

  const lineHeight = 50;

  // Generar elementos de texto para el nombre
  const nombreElements = lines
    .map((line, i) => {
      const y = nombreStartY + i * lineHeight;
      // Escapar caracteres especiales para XML
      const escapedLine = line
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      return `
    <text x="600" y="${y}"
          font-family="system-ui, -apple-system, sans-serif"
          font-size="36"
          font-weight="400"
          fill="${WHITE}"
          text-anchor="middle"
          opacity="0.9">
      ${escapedLine}
    </text>`;
    })
    .join('');

  return `
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

  <!-- Marca LeyesMX -->
  <text x="600" y="160"
        font-family="system-ui, -apple-system, sans-serif"
        font-size="72"
        font-weight="700"
        fill="${WHITE}"
        text-anchor="middle"
        opacity="0.95">
    LeyesMX
  </text>

  <!-- Código de la ley (protagonista) -->
  <text x="600" y="${codigoY}"
        font-family="system-ui, -apple-system, sans-serif"
        font-size="${codigoFontSize}"
        font-weight="700"
        fill="${WHITE}"
        text-anchor="middle">
    ${codigo}
  </text>

  <!-- Nombre completo de la ley -->
  ${nombreElements}

  <!-- URL del sitio -->
  <text x="600" y="580"
        font-family="system-ui, -apple-system, sans-serif"
        font-size="28"
        font-weight="400"
        fill="${WHITE}"
        text-anchor="middle"
        opacity="0.7">
    leyesmx.com
  </text>
</svg>
`;
}

async function generateOgImages() {
  // Leer catálogo
  const catalogoPath = join(__dirname, '..', 'src', 'data', 'catalogo.json');
  const catalogo = JSON.parse(readFileSync(catalogoPath, 'utf-8'));

  const outputDir = join(__dirname, '..', 'public');

  console.log('Generando imágenes OG para cada ley...\n');

  for (const ley of catalogo.leyes) {
    const { codigo, nombre } = ley;
    const svg = generateSvg(codigo, nombre);
    const outputPath = join(outputDir, `og-${codigo.toLowerCase()}.png`);

    await sharp(Buffer.from(svg)).png().toFile(outputPath);

    const lines = wrapText(nombre);
    console.log(`  ${codigo.padEnd(12)} → og-${codigo.toLowerCase()}.png (${lines.length} línea${lines.length > 1 ? 's' : ''})`);
  }

  console.log(`\n${catalogo.leyes.length} imágenes generadas en public/`);
}

generateOgImages().catch(console.error);
