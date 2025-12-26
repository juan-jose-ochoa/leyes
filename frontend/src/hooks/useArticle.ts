import { useQuery } from '@tanstack/react-query'
import { getArticulo, getLeyes, type ArticuloDetalle, type Ley } from '@/lib/api'

export function useArticle(id: number | null) {
  return useQuery<ArticuloDetalle | null>({
    queryKey: ['articulo', id],
    queryFn: async () => {
      if (!id) return null
      const result = await getArticulo(id)
      return result[0] || null
    },
    enabled: id !== null,
    staleTime: 1000 * 60 * 30, // 30 minutos
  })
}

export function useLeyes() {
  return useQuery<Ley[]>({
    queryKey: ['leyes'],
    queryFn: getLeyes,
    staleTime: 1000 * 60 * 60, // 1 hora
  })
}
