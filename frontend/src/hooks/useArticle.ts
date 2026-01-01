import { useQuery } from '@tanstack/react-query'
import { getArticulo, getArticuloPorLey, getLeyes, getNavegacion, getEstructuraLey, getDivisionPorTipoNumero, getDivisionPorPath, getArticulosDivision, getDivisionesHijas, getDivisionesArticulo, getFraccionesArticulo, buscarReferencias, type ArticuloDetalle, type Ley, type NavegacionArticulo, type Division, type DivisionInfo, type DivisionHija, type ArticuloDivision, type DivisionAncestro, type Fraccion, type ReferenciaLegal } from '@/lib/api'

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

export function useEstructuraLey(ley: string | null) {
  return useQuery<Division[]>({
    queryKey: ['estructura', ley],
    queryFn: async () => {
      if (!ley) return []
      return getEstructuraLey(ley)
    },
    enabled: ley !== null,
    staleTime: 1000 * 60 * 60, // 1 hora
  })
}

export function useDivisionPorTipoNumero(ley: string | null, tipo: string | null, numero: string | null) {
  return useQuery<DivisionInfo | null>({
    queryKey: ['division', ley, tipo, numero],
    queryFn: async () => {
      if (!ley || !tipo || !numero) return null
      return getDivisionPorTipoNumero(ley, tipo, numero)
    },
    enabled: ley !== null && tipo !== null && numero !== null,
    staleTime: 1000 * 60 * 60,
  })
}

export function useDivisionPorPath(ley: string | null, path: string | null) {
  return useQuery<DivisionInfo | null>({
    queryKey: ['division-path', ley, path],
    queryFn: async () => {
      if (!ley || !path) return null
      return getDivisionPorPath(ley, path)
    },
    enabled: ley !== null && path !== null,
    staleTime: 1000 * 60 * 60,
  })
}

export function useArticulosDivision(divId: number | null, ley?: string) {
  return useQuery<ArticuloDivision[]>({
    queryKey: ['articulos-division', divId, ley],
    queryFn: async () => {
      if (!divId) return []
      return getArticulosDivision(divId, ley)
    },
    enabled: divId !== null,
    staleTime: 1000 * 60 * 30,
  })
}

export function useDivisionesHijas(divId: number | null) {
  return useQuery<DivisionHija[]>({
    queryKey: ['divisiones-hijas', divId],
    queryFn: async () => {
      if (!divId) return []
      return getDivisionesHijas(divId)
    },
    enabled: divId !== null,
    staleTime: 1000 * 60 * 60,
  })
}

export function useDivisionesArticulo(artId: number | null) {
  return useQuery<DivisionAncestro[]>({
    queryKey: ['divisiones-articulo', artId],
    queryFn: async () => {
      if (!artId) return []
      return getDivisionesArticulo(artId)
    },
    enabled: artId !== null,
    staleTime: 1000 * 60 * 60,
  })
}

export function useFraccionesArticulo(artId: number | null, ley?: string) {
  return useQuery<Fraccion[]>({
    queryKey: ['fracciones-articulo', artId, ley],
    queryFn: async () => {
      if (!artId) return []
      return getFraccionesArticulo(artId, ley)
    },
    enabled: artId !== null,
    staleTime: 1000 * 60 * 30,
  })
}

export function useReferenciasLegales(referencias: string | null) {
  return useQuery<ReferenciaLegal[]>({
    queryKey: ['referencias-legales', referencias],
    queryFn: async () => {
      if (!referencias) return []
      return buscarReferencias(referencias)
    },
    enabled: referencias !== null && referencias.trim() !== '',
    staleTime: 1000 * 60 * 60,
  })
}
