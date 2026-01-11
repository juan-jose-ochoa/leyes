import { useQuery } from '@tanstack/react-query'
import {
  buscar,
  buscarHibrido,
  getSugerencias,
  type SearchResult,
  type HybridSearchResult,
  type Sugerencia,
  type LeyTipo,
} from '@/lib/api'

// Búsqueda híbrida: artículos + divisiones
export function useSearch(query: string, leyes?: string[], tipos?: LeyTipo[], enabled = true) {
  return useQuery<HybridSearchResult[]>({
    queryKey: ['search', query, leyes, tipos],
    queryFn: () => buscarHibrido(query, leyes, tipos),
    enabled: enabled && query.length >= 2,
    staleTime: 1000 * 60 * 5, // 5 minutos
  })
}

// Búsqueda solo artículos (legacy)
export function useSearchArticulos(query: string, leyes?: string[], tipos?: LeyTipo[], enabled = true) {
  return useQuery<SearchResult[]>({
    queryKey: ['search-articulos', query, leyes, tipos],
    queryFn: () => buscar(query, leyes, tipos),
    enabled: enabled && query.length >= 2,
    staleTime: 1000 * 60 * 5,
  })
}

export function useSugerencias(prefijo: string) {
  return useQuery<Sugerencia[]>({
    queryKey: ['sugerencias', prefijo],
    queryFn: () => getSugerencias(prefijo),
    enabled: prefijo.length >= 2,
    staleTime: 1000 * 60 * 10, // 10 minutos
  })
}
