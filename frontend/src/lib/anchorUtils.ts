import type { Fraccion } from './api'

export interface FraccionWithAnchor extends Fraccion {
  anchorId: string
}

/**
 * Construye IDs de ancla jerárquicos para todas las fracciones.
 *
 * Ejemplos:
 * - Fraccion I (nivel 0, padre_id null) -> "fraccion-I"
 * - Inciso a) bajo I -> "fraccion-I-inciso-a"
 * - Numeral 1. bajo a) -> "fraccion-I-inciso-a-numeral-1"
 */
export function buildFraccionAnchors(fracciones: Fraccion[]): FraccionWithAnchor[] {
  // Mapa por id para búsqueda rápida
  const byId = new Map<number, Fraccion>()
  fracciones.forEach(f => byId.set(f.id, f))

  // Construir cadena de padres para cada fracción
  function getParentChain(f: Fraccion): string[] {
    const chain: string[] = []
    let current: Fraccion | undefined = f

    while (current) {
      // Solo incluir elementos que tienen numero (excluir texto/parrafo sin identificador)
      if (current.numero && current.tipo !== 'texto' && current.tipo !== 'parrafo') {
        // Limpiar numero: "a)" -> "a", "1." -> "1", "I" -> "I"
        const cleanNumero = current.numero.replace(/[).]/g, '').trim()
        // Incluir tipo para SEO: "fraccion-I", "inciso-a", "numeral-1"
        chain.unshift(`${current.tipo}-${cleanNumero}`)
      }
      current = current.padre_id ? byId.get(current.padre_id) : undefined
    }

    return chain
  }

  return fracciones.map(f => {
    const parentPath = getParentChain(f)
    // Fallback para elementos sin identificador
    const anchorId = parentPath.length > 0 ? parentPath.join('-') : `p-${f.id}`

    return {
      ...f,
      anchorId
    }
  })
}

/**
 * Entrada de TOC para navegación
 */
export interface TocEntry {
  id: number
  anchorId: string
  label: string           // "I", "II", etc.
  tipo: Fraccion['tipo']
  children: TocEntry[]    // incisos bajo esta fracción
  hasChildren: boolean
}

/**
 * Construye estructura de TOC desde fracciones (solo fracciones de nivel superior con hijos expandibles)
 */
export function buildTocEntries(fracciones: FraccionWithAnchor[]): TocEntry[] {
  // Filtrar a fracciones principales (nivel 0 o tipo='fraccion' sin padre)
  const topLevel = fracciones.filter(f =>
    f.tipo === 'fraccion' &&
    f.padre_id === null &&
    f.numero
  )

  return topLevel.map(frac => {
    // Encontrar hijos directos (incisos)
    const children = fracciones
      .filter(f => f.padre_id === frac.id && f.tipo === 'inciso' && f.numero)
      .map(child => ({
        id: child.id,
        anchorId: child.anchorId,
        label: child.numero!.replace(/[)]/g, '').trim(),
        tipo: child.tipo,
        children: [] as TocEntry[],
        hasChildren: fracciones.some(f => f.padre_id === child.id && f.numero)
      }))

    return {
      id: frac.id,
      anchorId: frac.anchorId,
      label: frac.numero!,
      tipo: frac.tipo,
      children,
      hasChildren: children.length > 0
    }
  })
}
