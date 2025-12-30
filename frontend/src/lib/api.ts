// API Client for LeyesMX Backend

const API_BASE = '/api'

export type LeyTipo = 'codigo' | 'ley' | 'reglamento' | 'resolucion' | 'anexo'

export interface Ley {
  id: number
  codigo: string
  nombre: string
  nombre_corto: string | null
  tipo: LeyTipo
  url_fuente: string | null
  fecha_publicacion: string | null
  ultima_reforma: string | null
  total_articulos: number
  fecha_descarga: string | null
}

export type ArticuloTipo = 'articulo' | 'regla' | 'ficha' | 'criterio'

export interface Articulo {
  id: number
  ley: string
  ley_nombre: string
  ley_tipo: LeyTipo
  numero_raw: string
  numero_base: number
  sufijo: string | null
  ubicacion: string
  titulo?: string | null  // Título de regla RMF
  contenido: string
  es_transitorio: boolean
  reformas: string | null
  tipo?: ArticuloTipo  // Tipo de contenido: articulo (leyes), regla (RMF), ficha, criterio
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
  tipos?: LeyTipo[],
  limite = 20,
  pagina = 1
): Promise<SearchResult[]> {
  return fetchAPI<SearchResult[]>('/rpc/buscar', {
    method: 'POST',
    body: JSON.stringify({
      q: query,
      leyes: leyes?.join(',') || null,
      tipos: tipos?.join(',') || null,
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
  ultimo_articulo: string | null
  padre_id: number | null
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

// Registro de calidad de importación
export interface IssueCalidad {
  tipo: string
  descripcion: string
  severidad: 'error' | 'warning'
  accion: string | null
  fuente_correccion: string | null
  resuelto: boolean
}

export interface RegistroCalidad {
  estatus: 'ok' | 'corregida' | 'con_error'
  issues: IssueCalidad[]
}

export interface ArticuloDivision {
  id: number
  numero_raw: string
  titulo: string | null
  contenido: string
  es_transitorio: boolean
  reformas: string | null
  tipo: string | null
  referencias: string | null
  calidad: RegistroCalidad | null
}

export async function getDivisionPorTipoNumero(
  ley: string,
  tipo: string,
  numero: string
): Promise<DivisionInfo | null> {
  const result = await fetchAPI<DivisionInfo[]>('/rpc/division_por_tipo_numero', {
    method: 'POST',
    body: JSON.stringify({ p_ley: ley, p_tipo: tipo, p_numero: numero }),
  })
  return result[0] || null
}

export async function getArticulosDivision(divId: number, ley?: string): Promise<ArticuloDivision[]> {
  return fetchAPI<ArticuloDivision[]>('/rpc/articulos_division', {
    method: 'POST',
    body: JSON.stringify({ div_id: divId, p_ley: ley || null }),
  })
}

export interface DivisionBasica {
  id: number
  tipo: string
  numero: string | null
  nombre: string | null
}

export async function getDivisionPorPath(ley: string, path: string): Promise<DivisionInfo | null> {
  const result = await fetchAPI<DivisionInfo[]>('/rpc/division_por_path', {
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
  tipo: 'fraccion' | 'inciso' | 'numeral' | 'parrafo' | 'apartado' | 'texto'
  numero: string | null
  contenido: string
  orden: number
  nivel: number
  es_continuacion: boolean
  referencias: string[] | null
}

export async function getFraccionesArticulo(artId: number, ley?: string): Promise<Fraccion[]> {
  return fetchAPI<Fraccion[]>('/rpc/fracciones_articulo', {
    method: 'POST',
    body: JSON.stringify({ art_id: artId, p_ley: ley || null }),
  })
}

// Verificación de integridad de divisiones
export type VerificacionStatus = 'ok' | 'warning' | 'error' | 'empty'

export interface VerificacionDivision {
  division_id: number
  tipo: string
  numero: string
  nombre: string | null
  total_actual: number
  primera_regla: string | null
  ultima_regla: string | null
  num_primera: number | null
  num_ultima: number | null
  total_esperado: number
  faltantes: number
  porcentaje_completo: number | null
  status: VerificacionStatus
  numeros_faltantes: number[] | null
}

export async function getVerificacionLey(ley: string): Promise<VerificacionDivision[]> {
  return fetchAPI<VerificacionDivision[]>('/rpc/verificar_ley', {
    method: 'POST',
    body: JSON.stringify({ ley_codigo: ley }),
  })
}

export interface VerificacionDivisionSimple {
  division_id: number
  capitulo: string
  total_actual: number
  primera_regla: string | null
  ultima_regla: string | null
  num_primera: number | null
  num_ultima: number | null
  total_esperado: number
  faltantes: number
  porcentaje_completo: number | null
  numeros_faltantes: number[] | null
}

export async function getVerificacionDivision(divId: number): Promise<VerificacionDivisionSimple | null> {
  const result = await fetchAPI<VerificacionDivisionSimple[]>('/rpc/verificar_division', {
    method: 'POST',
    body: JSON.stringify({ div_id: divId }),
  })
  return result[0] || null
}

// Verificación contra índice oficial del PDF
export interface VerificacionIndice {
  categoria: string
  total_oficial: number
  total_importado: number
  faltantes: number
  extras: number
  virtuales: number  // Capítulos virtuales generados para reglas de 2 niveles
  porcentaje_completo: number
}

export interface ComparacionRegla {
  numero: string
  pagina_pdf: number | null
  estado: 'ok' | 'faltante'
}

export interface ComparacionDivision {
  tipo: string
  numero: string
  nombre_oficial: string | null
  nombre_importado: string | null
  estado: 'ok' | 'faltante' | 'extra' | 'virtual'  // virtual = capítulo generado
}

export async function getVerificacionIndice(ley: string): Promise<VerificacionIndice[]> {
  return fetchAPI<VerificacionIndice[]>('/rpc/verificar_indice', {
    method: 'POST',
    body: JSON.stringify({ ley_codigo: ley }),
  })
}

export async function getComparacionReglasIndice(ley: string): Promise<ComparacionRegla[]> {
  return fetchAPI<ComparacionRegla[]>('/rpc/comparar_reglas_indice', {
    method: 'POST',
    body: JSON.stringify({ ley_codigo: ley }),
  })
}

export async function getComparacionDivisionesIndice(ley: string): Promise<ComparacionDivision[]> {
  return fetchAPI<ComparacionDivision[]>('/rpc/comparar_divisiones_indice', {
    method: 'POST',
    body: JSON.stringify({ ley_codigo: ley }),
  })
}

// Referencias legales
export interface ReferenciaLegal {
  ley_codigo: string
  numero: string
  titulo: string | null
  contenido: string | null
  encontrado: boolean
}

export async function buscarReferencias(referencias: string): Promise<ReferenciaLegal[]> {
  return fetchAPI<ReferenciaLegal[]>('/rpc/buscar_referencias', {
    method: 'POST',
    body: JSON.stringify({ p_referencias: referencias }),
  })
}
