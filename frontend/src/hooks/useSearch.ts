import { useQuery } from '@tanstack/react-query'
import { buscar, getSugerencias, type SearchResult, type Sugerencia } from '@/lib/api'

export function useSearch(query: string, leyes?: string[], enabled = true) {
  return useQuery<SearchResult[]>({
    queryKey: ['search', query, leyes],
    queryFn: () => buscar(query, leyes),
    enabled: enabled && query.length >= 2,
    staleTime: 1000 * 60 * 5, // 5 minutos
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
