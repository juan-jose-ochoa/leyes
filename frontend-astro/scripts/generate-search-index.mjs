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

// Leer epígrafes SAT y crear mapa para lookup rápido
const epigrafesSat = JSON.parse(readFileSync(join(dataDir, 'epigrafes-sat.json'), 'utf-8'));
const epigrafeMap = new Map();
for (const ep of epigrafesSat.epigrafes) {
  epigrafeMap.set(`${ep.ley}-${ep.articulo}`, ep.epigrafe);
}

// Construir mapa artículo → sección desde estructura.json
// Devuelve objeto con texto y campos separados para búsqueda
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

        // Extraer campos individuales por tipo de división
        const titulo = currentBreadcrumb.find(b => b.tipo === 'titulo');
        const capitulo = currentBreadcrumb.find(b => b.tipo === 'capitulo');
        const seccion = currentBreadcrumb.find(b => b.tipo === 'seccion');

        const seccionData = {
          seccionTexto,
          tituloNumero: titulo?.numero || '',
          tituloNombre: titulo?.nombre || '',
          capituloNumero: capitulo?.numero || '',
          capituloNombre: capitulo?.nombre || '',
          seccionNumero: seccion?.numero || '',
          seccionNombre: seccion?.nombre || ''
        };

        for (const artNum of div.articulos) {
          map.set(artNum, seccionData);
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

// Capitalizar tipo
function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

// Generar etiqueta simple para un párrafo
function getSimpleLabel(parrafo) {
  if (parrafo.identificador) {
    return `${capitalize(parrafo.tipo)} ${parrafo.identificador}`;
  }
  return `Párrafo ${parrafo.numero}`;
}

// Construir breadcrumb jerárquico para un párrafo
function buildParrafoBreadcrumb(parrafo, parrafosMap) {
  const path = [];
  let current = parrafo;

  while (current) {
    // Solo agregar si tiene identificador (fracción, inciso, numeral, etc.)
    if (current.identificador) {
      path.unshift(`${capitalize(current.tipo)} ${current.identificador}`);
    } else if (current === parrafo) {
      // Solo para el párrafo actual sin identificador
      path.unshift(`Párrafo ${current.numero}`);
    }
    current = current.padre_numero ? parrafosMap.get(current.padre_numero) : null;
  }

  return path.length > 0 ? path.join(' › ') : `Párrafo ${parrafo.numero}`;
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

    const seccionData = seccionMap.get(art.numero) || { seccionTexto: '' };
    const url = `/${leyCode}/articulo/${art.numero}/`;
    const parrafos = art.parrafos || [];

    // Buscar epígrafe del SAT para este artículo
    const epigrafe = epigrafeMap.get(`${leyInfo.codigo}-${art.numero}`) || '';

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
        seccion: seccionData.seccionTexto || '',
        contenido: art.contenido,
        url: url,
        // Nuevos campos para búsqueda enriquecida
        epigrafe,
        tituloNombre: seccionData.tituloNombre || '',
        capituloNombre: seccionData.capituloNombre || '',
        seccionNombre: seccionData.seccionNombre || ''
      });
      artCount++;
      parrafoCount++;
      continue;
    }

    // Construir mapa de párrafos por numero para lookup de padres
    const parrafosMap = new Map();
    for (const p of parrafos) {
      parrafosMap.set(p.numero, p);
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
        parrafoLabel: buildParrafoBreadcrumb(parrafo, parrafosMap),
        parrafoTipo: parrafo.tipo,
        parrafoId: parrafo.identificador || null,
        seccion: seccionData.seccionTexto || '',
        contenido: parrafo.contenido,
        url: `${url}#${anclaId}`,
        // Position for sorting (article position, not paragraph)
        pagina: art.pagina || 0,
        posY: art.y || 0,
        // Campos enriquecidos para búsqueda
        epigrafe,
        tituloNombre: seccionData.tituloNombre || '',
        capituloNombre: seccionData.capituloNombre || '',
        seccionNombre: seccionData.seccionNombre || ''
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
  fields: [
    'contenido',
    'articuloTitulo',
    'articuloNumero',
    'epigrafe',        // Búsqueda por epígrafe SAT
    'tituloNombre',    // Búsqueda por nombre de título
    'capituloNombre',  // Búsqueda por nombre de capítulo
    'seccionNombre'    // Búsqueda por nombre de sección
  ],
  storeFields: [
    'ley', 'tipo', 'categoria',
    'articuloNumero', 'articuloTitulo',
    'parrafoLabel', 'parrafoTipo',
    'seccion', 'url',
    'pagina', 'posY',
    'epigrafe'  // Para mostrar en resultados
  ],
  searchOptions: {
    boost: {
      articuloTitulo: 2,
      articuloNumero: 1.5,
      epigrafe: 3,       // Alto boost - búsqueda por concepto
      tituloNombre: 1.2,
      capituloNombre: 1.2,
      seccionNombre: 1.2
    },
    fuzzy: 0.2,
    prefix: true
  }
});

// Indexar documentos
miniSearch.addAll(documents);

// Exportar índice serializado
const indexJson = JSON.stringify(miniSearch.toJSON());
writeFileSync(join(outputDir, 'search-index.json'), indexJson);

// Guardar contenido para excerpts (full content for better term matching)
const excerptData = documents.map(d => ({
  id: d.id,
  contenido: d.contenido
}));
writeFileSync(join(outputDir, 'search-excerpts.json'), JSON.stringify(excerptData));

const indexSizeKB = (indexJson.length / 1024).toFixed(1);
const excerptSizeKB = (JSON.stringify(excerptData).length / 1024).toFixed(1);

console.log(`\nÍndice generado:`);
console.log(`  search-index.json: ${indexSizeKB} KB`);
console.log(`  search-excerpts.json: ${excerptSizeKB} KB`);
console.log(`  Total: ${(parseFloat(indexSizeKB) + parseFloat(excerptSizeKB)).toFixed(1)} KB`);
