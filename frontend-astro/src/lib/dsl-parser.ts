/**
 * LeyesMX DSL Parser v1.0
 *
 * Parsea referencias a legislación mexicana en formato DSL.
 * Especificación completa en /DSL.md
 *
 * Sintaxis: ley:articulo[/apartado][/fraccion][/inciso][/numeral]
 *
 * Ejemplos:
 *   cpeum:123/A/IX/e     → CPEUM Art. 123, Apartado A, Fracción IX, Inciso e
 *   lisr:28/XXX          → LISR Art. 28, Fracción XXX
 *   rmf:2.1.36/I         → RMF Regla 2.1.36, Fracción I
 *   cpeum:94,97,116/III  → CPEUM Arts. 94, 97, 116 Fracc. III
 */

// Leyes soportadas
export const LEYES_VALIDAS = new Set([
  'cpeum', 'cff', 'lisr', 'liva', 'lieps', 'lft', 'lss', 'la',
  'linfonavit', 'lissste', 'lfdc', 'lif', 'rmf',
  'rcff', 'rlisr', 'rliva', 'rlieps', 'rlft', 'rlss', 'racerf'
]);

// Expresiones regulares
const ROMANO_REGEX = /^[IVXLCDM]+$/;
const NUM_LEY_REGEX = /^\d+[oº]?(-[A-Z]+)?$/;
const NUM_RMF_REGEX = /^\d+\.\d+\.\d+(\.\d+)?$/;
const APARTADO_REGEX = /^[A-Z]$/;
const INCISO_REGEX = /^[a-z]$/;
const NUMERAL_REGEX = /^\d+$/;

/**
 * Referencia a un artículo específico
 */
export interface RefArticulo {
  ley: string;
  articulo: string;
  apartado?: string;
  fraccion?: string;
  inciso?: string;
  numeral?: string;
}

/**
 * Resultado del parseo
 */
export interface ParseResult {
  success: boolean;
  referencias: RefArticulo[];
  error?: string;
  errorPos?: number;
}

/**
 * Parsea una query DSL completa
 *
 * @param query - Query DSL (ej: "cpeum:123/A/IX+lisr:28/XXX")
 * @returns Resultado con lista de referencias o error
 */
export function parseDSL(query: string): ParseResult {
  if (!query || !query.trim()) {
    return { success: false, referencias: [], error: 'Query vacía' };
  }

  const referencias: RefArticulo[] = [];
  const leyRefs = query.trim().split('+');

  for (const leyRef of leyRefs) {
    const result = parseLeyRefs(leyRef.trim());
    if (!result.success) {
      return result;
    }
    referencias.push(...result.referencias);
  }

  return { success: true, referencias };
}

/**
 * Parsea referencias de una sola ley
 *
 * @param leyRef - Referencia con formato "ley:arts" (ej: "cpeum:94,97,116/III")
 */
function parseLeyRefs(leyRef: string): ParseResult {
  const colonIdx = leyRef.indexOf(':');
  if (colonIdx === -1) {
    return {
      success: false,
      referencias: [],
      error: `Falta separador ':' en "${leyRef}"`,
    };
  }

  const ley = leyRef.substring(0, colonIdx).toLowerCase();
  const artsPart = leyRef.substring(colonIdx + 1);

  // Validar ley
  if (!LEYES_VALIDAS.has(ley)) {
    return {
      success: false,
      referencias: [],
      error: `Ley desconocida: "${ley}"`,
    };
  }

  if (!artsPart) {
    return {
      success: false,
      referencias: [],
      error: `Falta artículo después de "${ley}:"`,
    };
  }

  // Parsear lista de artículos
  const referencias: RefArticulo[] = [];
  const artRefs = splitArticulos(artsPart);

  for (const artRef of artRefs) {
    // Verificar si es rango
    if (artRef.includes('..')) {
      const rangeResult = parseRango(ley, artRef);
      if (!rangeResult.success) {
        return rangeResult;
      }
      referencias.push(...rangeResult.referencias);
    } else {
      const ref = parseArtRef(ley, artRef);
      if (!ref) {
        return {
          success: false,
          referencias: [],
          error: `Referencia inválida: "${artRef}"`,
        };
      }
      referencias.push(ref);
    }
  }

  return { success: true, referencias };
}

/**
 * Divide la parte de artículos respetando los modificadores
 *
 * "94,97,116/III" → ["94", "97", "116/III"]
 */
function splitArticulos(artsPart: string): string[] {
  const result: string[] = [];
  let current = '';

  for (let i = 0; i < artsPart.length; i++) {
    const char = artsPart[i];
    if (char === ',') {
      if (current) {
        result.push(current);
        current = '';
      }
    } else {
      current += char;
    }
  }

  if (current) {
    result.push(current);
  }

  return result;
}

/**
 * Parsea una referencia a artículo individual con modificadores
 *
 * @param ley - Código de ley
 * @param artRef - Referencia (ej: "123/A/IX/e")
 */
function parseArtRef(ley: string, artRef: string): RefArticulo | null {
  const parts = artRef.split('/');
  if (parts.length === 0 || !parts[0]) {
    return null;
  }

  const articulo = parts[0];

  // Validar formato de artículo
  if (!isValidArticulo(articulo, ley)) {
    return null;
  }

  const ref: RefArticulo = { ley, articulo };

  // Parsear modificadores en orden jerárquico
  let idx = 1;

  // Apartado (letra mayúscula sola)
  if (idx < parts.length && APARTADO_REGEX.test(parts[idx])) {
    ref.apartado = parts[idx];
    idx++;
  }

  // Fracción (romano)
  if (idx < parts.length && ROMANO_REGEX.test(parts[idx])) {
    ref.fraccion = parts[idx];
    idx++;
  }

  // Inciso (letra minúscula sola)
  if (idx < parts.length && INCISO_REGEX.test(parts[idx])) {
    ref.inciso = parts[idx];
    idx++;
  }

  // Numeral (número arábigo)
  if (idx < parts.length && NUMERAL_REGEX.test(parts[idx])) {
    ref.numeral = parts[idx];
    idx++;
  }

  // Si quedan partes sin procesar, es inválido
  if (idx < parts.length) {
    return null;
  }

  return ref;
}

/**
 * Valida el formato del artículo según el tipo de ley
 */
function isValidArticulo(articulo: string, ley: string): boolean {
  if (ley === 'rmf') {
    return NUM_RMF_REGEX.test(articulo);
  }
  return NUM_LEY_REGEX.test(articulo);
}

/**
 * Parsea un rango de artículos
 *
 * @param ley - Código de ley
 * @param rangeRef - Rango (ej: "1..5")
 */
function parseRango(ley: string, rangeRef: string): ParseResult {
  const parts = rangeRef.split('..');
  if (parts.length !== 2) {
    return {
      success: false,
      referencias: [],
      error: `Rango inválido: "${rangeRef}"`,
    };
  }

  const [startStr, endStr] = parts;

  // Solo soportamos rangos numéricos simples por ahora
  const start = parseInt(startStr, 10);
  const end = parseInt(endStr, 10);

  if (isNaN(start) || isNaN(end)) {
    return {
      success: false,
      referencias: [],
      error: `Rango debe ser numérico: "${rangeRef}"`,
    };
  }

  if (start > end) {
    return {
      success: false,
      referencias: [],
      error: `Rango invertido: ${start} > ${end}`,
    };
  }

  if (end - start > 100) {
    return {
      success: false,
      referencias: [],
      error: `Rango demasiado grande: ${end - start + 1} artículos`,
    };
  }

  const referencias: RefArticulo[] = [];
  for (let i = start; i <= end; i++) {
    referencias.push({ ley, articulo: String(i) });
  }

  return { success: true, referencias };
}

/**
 * Convierte una lista de referencias a formato DSL
 *
 * @param refs - Lista de referencias
 * @returns String DSL
 */
export function toDSL(refs: RefArticulo[]): string {
  if (refs.length === 0) return '';

  // Agrupar por ley
  const porLey = new Map<string, RefArticulo[]>();
  for (const ref of refs) {
    const lista = porLey.get(ref.ley) || [];
    lista.push(ref);
    porLey.set(ref.ley, lista);
  }

  const partes: string[] = [];
  for (const [ley, leyRefs] of porLey) {
    const arts = leyRefs.map(refToString).join(',');
    partes.push(`${ley}:${arts}`);
  }

  return partes.join('+');
}

/**
 * Convierte una referencia individual a string (sin ley)
 */
function refToString(ref: RefArticulo): string {
  let s = ref.articulo;
  if (ref.apartado) s += `/${ref.apartado}`;
  if (ref.fraccion) s += `/${ref.fraccion}`;
  if (ref.inciso) s += `/${ref.inciso}`;
  if (ref.numeral) s += `/${ref.numeral}`;
  return s;
}

/**
 * Formatea una referencia para mostrar al usuario
 *
 * @param ref - Referencia
 * @returns String legible (ej: "CPEUM Art. 123, Apartado A, Fracción IX")
 */
export function formatRef(ref: RefArticulo): string {
  const ley = ref.ley.toUpperCase();
  const esRMF = ref.ley === 'rmf';
  const tipoArt = esRMF ? 'Regla' : 'Art.';

  let s = `${ley} ${tipoArt} ${ref.articulo}`;

  if (ref.apartado) s += `, Apartado ${ref.apartado}`;
  if (ref.fraccion) s += `, Fracción ${ref.fraccion}`;
  if (ref.inciso) s += `, Inciso ${ref.inciso}`;
  if (ref.numeral) s += `, Numeral ${ref.numeral}`;

  return s;
}

/**
 * Genera la URL para una referencia
 *
 * @param ref - Referencia
 * @returns URL path (ej: "/cpeum/articulo/123/")
 */
export function refToUrl(ref: RefArticulo): string {
  const base = `/${ref.ley}/articulo/${ref.articulo}/`;

  // Construir hash si hay modificadores
  // Por ahora solo navegamos al artículo, el scroll fino requiere
  // conocer el número de párrafo
  return base;
}

/**
 * Genera URL con query DSL para búsqueda
 *
 * @param query - Query DSL
 * @returns URL completa
 */
export function dslToSearchUrl(query: string): string {
  return `/buscar?q=${encodeURIComponent(query)}`;
}
