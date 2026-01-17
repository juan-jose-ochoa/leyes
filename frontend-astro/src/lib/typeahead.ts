/**
 * Typeahead para acceso rápido a artículos
 * Detecta patrones como "LISR 96" y ofrece navegación directa
 */

// Types
export interface QuickAccessIndex {
  leyes: Record<string, LeyMeta>;
  aliases: Record<string, string>;
  articulos: Record<string, ArticuloMeta[]>;
}

export interface LeyMeta {
  codigo: string;
  nombre_corto: string;
  categoria: string;
  total: number;
}

export interface ArticuloMeta {
  n: string;      // Número canónico
  s: string;      // Número normalizado (search)
  a?: string[];   // Aliases/variantes
  e?: string;     // Epígrafe SAT (preferido)
  t?: string;     // Título sección (fallback)
}

export interface ArticuloMatch extends ArticuloMeta {
  score: number;
  matchType: 'exact' | 'prefix' | 'contains';
  url: string;
}

export interface ParsedReference {
  type: 'direct' | 'partial-ley' | 'search';
  ley?: string;
  leyMeta?: LeyMeta;
  articulo?: string;
  confidence: number;
}

export interface TypeaheadResult {
  parsed: ParsedReference;
  matches: ArticuloMatch[];
  leyMatches?: LeyMeta[];  // Cuando solo se está escribiendo la ley
}

// Estado del índice
let quickAccessIndex: QuickAccessIndex | null = null;
let loadingPromise: Promise<QuickAccessIndex> | null = null;

/**
 * Carga el índice de acceso rápido
 */
export async function loadQuickAccessIndex(): Promise<QuickAccessIndex> {
  if (quickAccessIndex) return quickAccessIndex;
  if (loadingPromise) return loadingPromise;

  loadingPromise = fetch('/quick-access-index.json')
    .then(res => res.json())
    .then(data => {
      quickAccessIndex = data;
      return data;
    })
    .catch(err => {
      console.error('[QuickAccess] Error cargando índice:', err);
      loadingPromise = null;
      throw err;
    });

  return loadingPromise;
}

/**
 * Normaliza un número de artículo para comparación
 */
export function normalizeArticuloNum(input: string): string {
  return input
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/[áéíóú]/g, m => ({ á: 'a', é: 'e', í: 'i', ó: 'o', ú: 'u' })[m] || m)
    .replace(/[º°]/g, 'o')
    .trim();
}

/**
 * Resuelve un código de ley (incluyendo aliases)
 */
function resolveLey(input: string, index: QuickAccessIndex): string | null {
  const normalized = input.toUpperCase();

  // Buscar directamente
  if (index.leyes[normalized]) {
    return normalized;
  }

  // Buscar en aliases
  const fromAlias = index.aliases[input.toLowerCase()];
  if (fromAlias && index.leyes[fromAlias]) {
    return fromAlias;
  }

  return null;
}

/**
 * Busca leyes que coincidan parcialmente con el input
 */
function findLeyMatches(input: string, index: QuickAccessIndex): LeyMeta[] {
  const normalized = input.toLowerCase();
  const matches: LeyMeta[] = [];

  // Buscar en códigos de ley
  for (const [codigo, meta] of Object.entries(index.leyes)) {
    if (codigo.toLowerCase().startsWith(normalized)) {
      matches.push(meta);
    }
  }

  // Buscar en aliases
  for (const [alias, codigo] of Object.entries(index.aliases)) {
    if (alias.startsWith(normalized) && index.leyes[codigo]) {
      const meta = index.leyes[codigo];
      if (!matches.find(m => m.codigo === meta.codigo)) {
        matches.push(meta);
      }
    }
  }

  return matches.slice(0, 5);  // Limitar a 5
}

/**
 * Parsea el query para detectar referencias directas
 */
export function parseQuery(input: string, index: QuickAccessIndex): ParsedReference {
  const trimmed = input.trim();
  if (!trimmed) {
    return { type: 'search', confidence: 0 };
  }

  // Patrón: {CÓDIGO_LEY} {NÚMERO_ARTÍCULO}
  // Ejemplos: "LISR 96", "cff 17-h bis", "CPEUM 123", "lisr96"
  const patterns = [
    // Con espacio: "LISR 96", "CFF 17-H Bis"
    /^([a-záéíóú]{2,12})\s+(\d+(?:o|º|°)?(?:[-\s]?[a-záéíóú]+)?(?:\s+(?:bis|ter|qu[aá]ter|quinquies))?)$/i,
    // Sin espacio pero con número: "LISR96", "CFF32"
    /^([a-záéíóú]{2,12})(\d+(?:o|º|°)?(?:[-]?[a-záéíóú]+)?(?:\s*(?:bis|ter|qu[aá]ter|quinquies))?)$/i,
  ];

  for (const pattern of patterns) {
    const match = trimmed.match(pattern);
    if (match) {
      const [, leyCodigo, artNum] = match;
      const ley = resolveLey(leyCodigo, index);

      if (ley) {
        return {
          type: 'direct',
          ley,
          leyMeta: index.leyes[ley],
          articulo: normalizeArticuloNum(artNum),
          confidence: 1.0
        };
      }
    }
  }

  // Patrón: solo código de ley (parcial o completo)
  const leyOnlyMatch = trimmed.match(/^([a-záéíóú]{2,12})$/i);
  if (leyOnlyMatch) {
    const ley = resolveLey(leyOnlyMatch[1], index);
    if (ley) {
      // Ley completa reconocida
      return {
        type: 'partial-ley',
        ley,
        leyMeta: index.leyes[ley],
        confidence: 0.9
      };
    }

    // Verificar si es prefijo de alguna ley
    const leyMatches = findLeyMatches(leyOnlyMatch[1], index);
    if (leyMatches.length > 0) {
      return {
        type: 'partial-ley',
        confidence: 0.5
      };
    }
  }

  // No es referencia directa
  return { type: 'search', confidence: 0 };
}

/**
 * Comparación natural de números de artículo
 */
function naturalCompare(a: string, b: string): number {
  const numA = parseInt(a.match(/^\d+/)?.[0] || '0');
  const numB = parseInt(b.match(/^\d+/)?.[0] || '0');
  if (numA !== numB) return numA - numB;
  return a.localeCompare(b);
}

/**
 * Busca artículos que coincidan con el query
 */
export function findArticuloMatches(
  ley: string,
  query: string,
  index: QuickAccessIndex,
  limit = 8
): ArticuloMatch[] {
  const articulos = index.articulos[ley] || [];
  if (!query) {
    // Sin query, mostrar primeros artículos
    return articulos.slice(0, limit).map(art => ({
      ...art,
      score: 0.5,
      matchType: 'prefix' as const,
      url: `/${ley.toLowerCase()}/articulo/${encodeURIComponent(art.n)}`
    }));
  }

  const queryNorm = normalizeArticuloNum(query);
  const results: ArticuloMatch[] = [];

  for (const art of articulos) {
    const artNorm = art.s;
    const aliases = art.a || [];
    let score = 0;
    let matchType: 'exact' | 'prefix' | 'contains' = 'contains';

    // Match exacto
    if (artNorm === queryNorm || aliases.includes(queryNorm)) {
      score = 1.0;
      matchType = 'exact';
    }
    // Match por prefijo
    else if (artNorm.startsWith(queryNorm) || aliases.some(a => a.startsWith(queryNorm))) {
      score = 0.9;
      matchType = 'prefix';
    }
    // Match contenido (ej: "96" en "196")
    else if (artNorm.includes(queryNorm)) {
      score = 0.6;
      matchType = 'contains';
    }

    if (score > 0) {
      results.push({
        ...art,
        score,
        matchType,
        url: `/${ley.toLowerCase()}/articulo/${encodeURIComponent(art.n)}`
      });
    }
  }

  // Ordenar: primero por score, luego por número natural
  return results
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return naturalCompare(a.n, b.n);
    })
    .slice(0, limit);
}

/**
 * Ejecuta el typeahead completo
 */
export async function executeTypeahead(query: string): Promise<TypeaheadResult> {
  const index = await loadQuickAccessIndex();
  const parsed = parseQuery(query, index);

  if (parsed.type === 'direct' && parsed.ley && parsed.articulo) {
    // Referencia directa completa: buscar artículos
    const matches = findArticuloMatches(parsed.ley, parsed.articulo, index);
    return { parsed, matches };
  }

  if (parsed.type === 'partial-ley') {
    if (parsed.ley) {
      // Ley reconocida, mostrar primeros artículos
      const matches = findArticuloMatches(parsed.ley, '', index);
      return { parsed, matches };
    } else {
      // Prefijo de ley, mostrar leyes que coinciden
      const leyMatches = findLeyMatches(query.trim(), index);
      return { parsed, matches: [], leyMatches };
    }
  }

  // Búsqueda normal
  return { parsed, matches: [] };
}

/**
 * Obtiene la URL para un artículo
 */
export function getArticuloUrl(ley: string, numero: string): string {
  return `/${ley.toLowerCase()}/articulo/${encodeURIComponent(numero)}`;
}
