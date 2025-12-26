// API Client for LeyesMX Backend

const API_BASE = '/api'

export interface Ley {
  id: number
  codigo: string
  nombre: string
  tipo: 'ley' | 'reglamento' | 'resolucion'
  total_articulos: number
  fecha_descarga: string
}

export interface Articulo {
  id: number
  ley: string
  ley_nombre: string
  ley_tipo: 'ley' | 'reglamento' | 'resolucion'
  numero_raw: string
  numero_base: number
  sufijo: string | null
  ubicacion: string
  contenido: string
  es_transitorio: boolean
  reformas: string | null
  tipo?: 'articulo' | 'regla'  // Tipo de contenido: articulo (leyes) o regla (RMF)
}

export interface SearchResult extends Articulo {
  relevancia: number
  snippet: string
}

export interface ArticuloDetalle extends Articulo {
  referencias_salientes: Referencia[] | null
  referencias_entrantes: Referencia[] | null
  referencias_legales?: string | null  // Referencias legales RMF (CFF, LISR, etc.)
}

export interface Referencia {
  id: number
  ley: string
  numero_raw: string
  tipo: string
}

export interface Sugerencia {
  termino: string
  frecuencia: number
}

export interface Stats {
  codigo: string
  nombre: string
  tipo: string
  total_divisiones: number
  total_articulos: number
  articulos_transitorios: number
}

// Fetch wrapper con manejo de errores
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`

  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    })

    if (!response.ok) {
      const errorText = await response.text()
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`

      try {
        const errorJson = JSON.parse(errorText)
        errorMessage = errorJson.message || errorJson.error || errorText
        console.error(`[API Error] ${url}:`, errorJson)
      } catch {
        console.error(`[API Error] ${url}:`, errorText)
      }

      throw new Error(errorMessage)
    }

    return response.json()
  } catch (error) {
    console.error(`[API Error] ${url}:`, error)
    throw error
  }
}

// API Functions

export async function getLeyes(): Promise<Ley[]> {
  return fetchAPI<Ley[]>('/v_leyes')
}

export async function buscar(
  query: string,
  leyes?: string[],
  limite = 20,
  pagina = 1
): Promise<SearchResult[]> {
  return fetchAPI<SearchResult[]>('/rpc/buscar', {
    method: 'POST',
    body: JSON.stringify({
      q: query,
      leyes: leyes?.join(',') || null,
      limite,
      pagina,
    }),
  })
}

export async function getArticulo(id: number): Promise<ArticuloDetalle[]> {
  return fetchAPI<ArticuloDetalle[]>('/rpc/articulo', {
    method: 'POST',
    body: JSON.stringify({ art_id: id }),
  })
}

export async function getArticuloPorLey(ley: string, numero: string): Promise<ArticuloDetalle[]> {
  return fetchAPI<ArticuloDetalle[]>('/rpc/articulo_por_ley', {
    method: 'POST',
    body: JSON.stringify({ p_ley: ley, p_numero: numero }),
  })
}

export async function getArticulos(
  ley?: string,
  limite = 50,
  offset = 0
): Promise<Articulo[]> {
  const params = new URLSearchParams()
  if (ley) params.set('ley', `eq.${ley}`)
  params.set('limit', String(limite))
  params.set('offset', String(offset))

  return fetchAPI<Articulo[]>(`/v_articulos?${params}`)
}

export async function getSugerencias(prefijo: string): Promise<Sugerencia[]> {
  if (prefijo.length < 2) return []

  return fetchAPI<Sugerencia[]>('/rpc/sugerencias', {
    method: 'POST',
    body: JSON.stringify({ prefijo }),
  })
}

export async function getStats(): Promise<Stats[]> {
  return fetchAPI<Stats[]>('/rpc/stats', {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export interface NavegacionArticulo {
  anterior_id: number | null
  anterior_numero: string | null
  siguiente_id: number | null
  siguiente_numero: string | null
}

export async function getNavegacion(articuloId: number): Promise<NavegacionArticulo | null> {
  const result = await fetchAPI<NavegacionArticulo[]>('/rpc/navegar', {
    method: 'POST',
    body: JSON.stringify({ art_id: articuloId }),
  })
  return result[0] || null
}

export interface Division {
  id: number
  tipo: string
  numero: string | null
  nombre: string | null
  path_texto: string | null
  nivel: number
  total_articulos: number
  primer_articulo: string | null
}

export async function getEstructuraLey(ley: string): Promise<Division[]> {
  return fetchAPI<Division[]>('/rpc/estructura_ley', {
    method: 'POST',
    body: JSON.stringify({ ley_codigo: ley }),
  })
}

export interface DivisionInfo {
  id: number
  ley_codigo: string
  ley_nombre: string
  ley_tipo: string
  div_tipo: string
  numero: string | null
  nombre: string | null
  path_texto: string | null
  total_articulos: number
}

export interface ArticuloDivision {
  id: number
  numero_raw: string
  contenido: string
  es_transitorio: boolean
  reformas: string | null
  tipo: string | null
  referencias: string | null
}

export async function getDivisionInfo(divId: number): Promise<DivisionInfo | null> {
  const result = await fetchAPI<DivisionInfo[]>('/rpc/division_info', {
    method: 'POST',
    body: JSON.stringify({ div_id: divId }),
  })
  return result[0] || null
}

export async function getArticulosDivision(divId: number): Promise<ArticuloDivision[]> {
  return fetchAPI<ArticuloDivision[]>('/rpc/articulos_division', {
    method: 'POST',
    body: JSON.stringify({ div_id: divId }),
  })
}

export interface DivisionBasica {
  id: number
  tipo: string
  numero: string | null
  nombre: string | null
}

export async function getDivisionPorPath(ley: string, path: string): Promise<DivisionBasica | null> {
  const result = await fetchAPI<DivisionBasica[]>('/rpc/division_por_path', {
    method: 'POST',
    body: JSON.stringify({ p_ley: ley, p_path: path }),
  })
  return result[0] || null
}

export interface DivisionAncestro {
  id: number
  tipo: string
  numero: string | null
  nombre: string | null
  path_texto: string | null
  nivel: number
}

export async function getDivisionesArticulo(artId: number): Promise<DivisionAncestro[]> {
  return fetchAPI<DivisionAncestro[]>('/rpc/divisiones_articulo', {
    method: 'POST',
    body: JSON.stringify({ art_id: artId }),
  })
}

export interface Fraccion {
  id: number
  padre_id: number | null
  tipo: 'fraccion' | 'inciso' | 'numeral' | 'parrafo' | 'apartado'
  numero: string | null
  contenido: string
  orden: number
  nivel: number
}

export async function getFraccionesArticulo(artId: number): Promise<Fraccion[]> {
  return fetchAPI<Fraccion[]>('/rpc/fracciones_articulo', {
    method: 'POST',
    body: JSON.stringify({ art_id: artId }),
  })
}
