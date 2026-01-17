#!/usr/bin/env node
/**
 * Genera el índice de acceso rápido para navegación directa a artículos
 * Formato: "LISR 96" → /lisr/articulo/96
 *
 * Output: public/quick-access-index.json (~15-25KB)
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const dataDir = join(__dirname, '../src/data');
const outputDir = join(__dirname, '../public');

// Leer catálogo
const catalogo = JSON.parse(readFileSync(join(dataDir, 'catalogo.json'), 'utf-8'));

// Leer epígrafes del SAT
const epigrafesPath = join(dataDir, 'epigrafes-sat.json');
let epigrafesMap = new Map();
if (existsSync(epigrafesPath)) {
  const epigrafesData = JSON.parse(readFileSync(epigrafesPath, 'utf-8'));
  for (const e of epigrafesData.epigrafes || []) {
    epigrafesMap.set(`${e.ley}:${e.articulo}`, e.epigrafe);
  }
  console.log(`Epígrafes SAT cargados: ${epigrafesMap.size}`);
}

/**
 * Normaliza un número de artículo para comparación
 * Ejemplos: "1º" → "1o", "17-H Bis" → "17-h bis"
 */
function normalizeArticuloNum(input) {
  return input
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/[áéíóú]/g, m => ({ á: 'a', é: 'e', í: 'i', ó: 'o', ú: 'u' })[m])
    .replace(/[º°]/g, 'o')
    .trim();
}

/**
 * Genera variantes de búsqueda para un número de artículo
 * "17-H Bis" → ["17-h bis", "17-h-bis", "17hbis", "17 h bis"]
 */
function generateSearchVariants(numero) {
  const base = normalizeArticuloNum(numero);
  const variants = new Set([base]);

  // Sin guiones
  variants.add(base.replace(/-/g, ' '));
  variants.add(base.replace(/-/g, ''));

  // Con guiones en lugar de espacios
  variants.add(base.replace(/\s+/g, '-'));

  // Sin espacios
  variants.add(base.replace(/\s+/g, ''));

  return [...variants].filter(v => v !== base);
}

/**
 * Extrae el título/nombre de un artículo desde la estructura
 * Busca el nombre más descriptivo en el breadcrumb (el último que tenga nombre)
 */
function getArticuloTitulo(articulo, seccionMap) {
  const seccion = seccionMap.get(articulo.numero);
  if (seccion) {
    // El breadcrumb viene como "Título VI - Del Trabajo › Capitulo UNICO"
    // Buscamos la parte más descriptiva (que tenga nombre después del guión)
    const parts = seccion.split(' › ');

    // Buscar de atrás hacia adelante la primera parte con nombre descriptivo
    for (let i = parts.length - 1; i >= 0; i--) {
      const part = parts[i];
      // Si tiene " - " significa que tiene nombre descriptivo
      if (part.includes(' - ')) {
        return part;
      }
    }

    // Si ninguna tiene nombre descriptivo, devolver la última
    return parts[parts.length - 1];
  }
  return null;
}

/**
 * Construye mapa artículo → sección desde estructura.json
 */
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

// Construir índice
console.log('Generando índice de acceso rápido...');

const index = {
  _generado: new Date().toISOString(),
  _version: '1.0',
  leyes: {},
  aliases: {},
  articulos: {}
};

// Procesar cada ley
for (const leyInfo of catalogo.leyes) {
  const codigo = leyInfo.codigo;
  const codigoLower = codigo.toLowerCase();
  const articulosPath = join(dataDir, codigoLower, 'articulos.json');
  const estructuraPath = join(dataDir, codigoLower, 'estructura.json');

  if (!existsSync(articulosPath)) {
    console.log(`  Saltando ${codigo}: no existe articulos.json`);
    continue;
  }

  // Metadata de la ley
  index.leyes[codigo] = {
    codigo,
    nombre_corto: leyInfo.nombre_corto,
    categoria: leyInfo.categoria,
    total: leyInfo.total_articulos || 0
  };

  // Aliases para la ley (para búsqueda fuzzy)
  const leyAliases = [
    codigo.toLowerCase(),
    codigo.toUpperCase(),
    // Variantes sin vocales acentuadas ya están normalizadas
  ];
  for (const alias of leyAliases) {
    index.aliases[alias] = codigo;
  }

  // Cargar artículos
  const articulos = JSON.parse(readFileSync(articulosPath, 'utf-8'));

  // Cargar estructura para títulos
  let seccionMap = new Map();
  if (existsSync(estructuraPath)) {
    const estructura = JSON.parse(readFileSync(estructuraPath, 'utf-8'));
    seccionMap = buildSeccionMap(estructura);
  }

  // Procesar artículos
  const articulosMeta = [];
  let epigrafesCount = 0;

  for (const art of articulos) {
    if (art.tipo !== 'articulo') continue;

    const numero = art.numero;
    const normalized = normalizeArticuloNum(numero);
    const variants = generateSearchVariants(numero);

    // Buscar epígrafe del SAT y título de sección
    const epigrafe = epigrafesMap.get(`${codigo}:${numero}`);
    const titulo = getArticuloTitulo(art, seccionMap);

    if (epigrafe) epigrafesCount++;

    const meta = {
      n: numero,  // Número canónico (como aparece en la ley)
      s: normalized  // Número normalizado para búsqueda
    };

    // Solo agregar variantes si hay alguna diferente
    if (variants.length > 0) {
      meta.a = variants;
    }

    // Agregar epígrafe SAT y título de sección (ambos si existen)
    if (epigrafe) {
      meta.e = epigrafe;  // Epígrafe SAT
    }
    if (titulo) {
      meta.t = titulo;  // Título de sección
    }

    articulosMeta.push(meta);
  }

  index.articulos[codigo] = articulosMeta;

  if (epigrafesCount > 0) {
    console.log(`  ${codigo}: ${articulosMeta.length} artículos (${epigrafesCount} con epígrafe SAT)`);
  } else {
    console.log(`  ${codigo}: ${articulosMeta.length} artículos`);
  }
}

// Agregar aliases adicionales comunes
const aliasesAdicionales = {
  'isr': 'LISR',
  'iva': 'LIVA',
  'ieps': 'LIEPS',
  'imss': 'LSS',
  'seguro social': 'LSS',
  'constitucion': 'CPEUM',
  'const': 'CPEUM',
  'trabajo': 'LFT',
  'infonavit': 'LINFONAVIT',
  'issste': 'LISSSTE',
  'aduanera': 'LA',
  'aduana': 'LA',
  'miscelanea': 'RMF',
  'rmf': 'RMF'
};

for (const [alias, codigo] of Object.entries(aliasesAdicionales)) {
  if (index.leyes[codigo]) {
    index.aliases[alias] = codigo;
  }
}

// Guardar índice
const outputPath = join(outputDir, 'quick-access-index.json');
const jsonOutput = JSON.stringify(index);
writeFileSync(outputPath, jsonOutput);

const sizeKB = (jsonOutput.length / 1024).toFixed(1);
const leyCount = Object.keys(index.leyes).length;
const totalArticulos = Object.values(index.articulos).reduce((sum, arts) => sum + arts.length, 0);

console.log(`\nÍndice generado: ${outputPath}`);
console.log(`  Leyes: ${leyCount}`);
console.log(`  Artículos: ${totalArticulos}`);
console.log(`  Tamaño: ${sizeKB} KB`);
