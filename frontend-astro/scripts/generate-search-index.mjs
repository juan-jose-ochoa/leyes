#!/usr/bin/env node
/**
 * Genera el índice de búsqueda para MiniSearch
 * Indexa cada párrafo/inciso/fracción por separado para resultados granulares
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import MiniSearch from 'minisearch';

const __dirname = dirname(fileURLToPath(import.meta.url));
const dataDir = join(__dirname, '../src/data');
const outputDir = join(__dirname, '../public');

// Leer catálogo
const catalogo = JSON.parse(readFileSync(join(dataDir, 'catalogo.json'), 'utf-8'));

// Construir mapa artículo → sección desde estructura.json
function buildSeccionMap(estructura) {
  const map = new Map();

  function traverse(divisiones, breadcrumb = []) {
    for (const div of divisiones) {
      const currentBreadcrumb = [...breadcrumb, {
        tipo: div.tipo,
        numero: div.numero,
        nombre: div.nombre
      }];

      if (div.articulos) {
        const seccionTexto = currentBreadcrumb
          .map(b => `${b.tipo.charAt(0).toUpperCase() + b.tipo.slice(1)} ${b.numero}${b.nombre ? ` - ${b.nombre}` : ''}`)
          .join(' › ');

        for (const artNum of div.articulos) {
          map.set(artNum, seccionTexto);
        }
      }

      if (div.hijos && div.hijos.length > 0) {
        traverse(div.hijos, currentBreadcrumb);
      }
    }
  }

  if (estructura.divisiones) {
    traverse(estructura.divisiones);
  }

  return map;
}

// Generar etiqueta para el tipo de párrafo
function getParrafoLabel(parrafo) {
  const tipo = parrafo.tipo;
  const id = parrafo.identificador;

  if (tipo === 'fraccion' && id) {
    return `Fracción ${id}`;
  } else if (tipo === 'inciso' && id) {
    return `Inciso ${id}`;
  } else if (tipo === 'texto') {
    return `Párrafo ${parrafo.numero}`;
  }
  return `Párrafo ${parrafo.numero}`;
}

// Generar ID de ancla (igual que FraccionesView.astro - usa numero único)
function getAnclaId(parrafo) {
  return `p-${parrafo.numero}`;
}

// Documentos para indexar
const documents = [];
let docId = 0;

console.log('Generando índice de búsqueda (por párrafo)...');

// Procesar cada ley
for (const leyInfo of catalogo.leyes) {
  const leyCode = leyInfo.codigo.toLowerCase();
  const articulosPath = join(dataDir, leyCode, 'articulos.json');
  const estructuraPath = join(dataDir, leyCode, 'estructura.json');

  if (!existsSync(articulosPath)) {
    console.log(`  Saltando ${leyCode}: no existe articulos.json`);
    continue;
  }

  const articulos = JSON.parse(readFileSync(articulosPath, 'utf-8'));

  // Cargar estructura para obtener secciones
  let seccionMap = new Map();
  if (existsSync(estructuraPath)) {
    const estructura = JSON.parse(readFileSync(estructuraPath, 'utf-8'));
    seccionMap = buildSeccionMap(estructura);
  }

  let artCount = 0;
  let parrafoCount = 0;

  for (const art of articulos) {
    // Solo indexar artículos (no transitorios, etc.)
    if (art.tipo !== 'articulo') continue;

    const seccion = seccionMap.get(art.numero) || '';
    const url = `/${leyCode}/articulo/${art.numero}`;
    const parrafos = art.parrafos || [];

    // Si no hay párrafos estructurados, indexar el contenido completo
    if (parrafos.length === 0 && art.contenido) {
      documents.push({
        id: docId++,
        ley: leyInfo.codigo,
        tipo: leyInfo.tipo,
        categoria: leyInfo.categoria,
        articuloNumero: art.numero,
        articuloTitulo: `Artículo ${art.numero}`,
        parrafoLabel: 'Artículo completo',
        parrafoTipo: 'completo',
        seccion: seccion,
        contenido: art.contenido,
        url: url
      });
      artCount++;
      parrafoCount++;
      continue;
    }

    // Indexar cada párrafo por separado
    for (const parrafo of parrafos) {
      if (!parrafo.contenido || !parrafo.contenido.trim()) continue;

      const anclaId = getAnclaId(parrafo);

      documents.push({
        id: docId++,
        ley: leyInfo.codigo,
        tipo: leyInfo.tipo,
        categoria: leyInfo.categoria,
        articuloNumero: art.numero,
        articuloTitulo: `Artículo ${art.numero}`,
        parrafoLabel: getParrafoLabel(parrafo),
        parrafoTipo: parrafo.tipo,
        parrafoId: parrafo.identificador || null,
        seccion: seccion,
        contenido: parrafo.contenido,
        url: `${url}#${anclaId}`
      });
      parrafoCount++;
    }

    artCount++;
  }

  console.log(`  ${leyInfo.codigo}: ${artCount} artículos, ${parrafoCount} párrafos`);
}

console.log(`\nTotal: ${documents.length} documentos (párrafos indexados)`);

// Crear índice MiniSearch
const miniSearch = new MiniSearch({
  fields: ['contenido', 'articuloTitulo', 'articuloNumero'],
  storeFields: [
    'ley', 'tipo', 'categoria',
    'articuloNumero', 'articuloTitulo',
    'parrafoLabel', 'parrafoTipo',
    'seccion', 'url'
  ],
  searchOptions: {
    boost: { articuloTitulo: 2, articuloNumero: 1.5 },
    fuzzy: 0.2,
    prefix: true
  }
});

// Indexar documentos
miniSearch.addAll(documents);

// Exportar índice serializado
const indexJson = JSON.stringify(miniSearch.toJSON());
writeFileSync(join(outputDir, 'search-index.json'), indexJson);

// Guardar contenido para excerpts
const excerptData = documents.map(d => ({
  id: d.id,
  contenido: d.contenido.substring(0, 300)
}));
writeFileSync(join(outputDir, 'search-excerpts.json'), JSON.stringify(excerptData));

const indexSizeKB = (indexJson.length / 1024).toFixed(1);
const excerptSizeKB = (JSON.stringify(excerptData).length / 1024).toFixed(1);

console.log(`\nÍndice generado:`);
console.log(`  search-index.json: ${indexSizeKB} KB`);
console.log(`  search-excerpts.json: ${excerptSizeKB} KB`);
console.log(`  Total: ${(parseFloat(indexSizeKB) + parseFloat(excerptSizeKB)).toFixed(1)} KB`);
