import { useQuery } from '@tanstack/react-query'
import { getArticulo, getArticuloPorLey, getLeyes, getNavegacion, type ArticuloDetalle, type Ley, type NavegacionArticulo } from '@/lib/api'

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

export function useArticuloPorLey(ley: string | null, numero: string | null) {
  return useQuery<ArticuloDetalle | null>({
    queryKey: ['articulo', ley, numero],
    queryFn: async () => {
      if (!ley || !numero) return null
      const result = await getArticuloPorLey(ley, numero)
      return result[0] || null
    },
    enabled: ley !== null && numero !== null,
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

export function useNavegacion(articuloId: number | null) {
  return useQuery<NavegacionArticulo | null>({
    queryKey: ['navegacion', articuloId],
    queryFn: async () => {
      if (!articuloId) return null
      return getNavegacion(articuloId)
    },
    enabled: articuloId !== null,
    staleTime: 1000 * 60 * 30, // 30 minutos
  })
}
