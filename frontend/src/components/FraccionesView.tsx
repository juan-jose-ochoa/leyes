import { useMemo } from 'react'
import { type Fraccion } from '@/lib/api'
import { buildFraccionAnchors, type FraccionWithAnchor } from '@/lib/anchorUtils'
import clsx from 'clsx'

interface FraccionesViewProps {
  fracciones: Fraccion[]
  mostrarReferencias?: boolean
}

export default function FraccionesView({ fracciones, mostrarReferencias = false }: FraccionesViewProps) {
  // Pre-computar IDs de ancla para todas las fracciones
  const fraccionesWithAnchors = useMemo(() => {
    if (!fracciones || fracciones.length === 0) return []
    return buildFraccionAnchors(fracciones)
  }, [fracciones])

  if (fraccionesWithAnchors.length === 0) {
    return null
  }

  return (
    <div className="space-y-4">
      {fraccionesWithAnchors.map((fraccion) => (
        <FraccionItem key={fraccion.id} fraccion={fraccion} mostrarReferencias={mostrarReferencias} />
      ))}
    </div>
  )
}

function FraccionItem({ fraccion, mostrarReferencias }: { fraccion: FraccionWithAnchor; mostrarReferencias: boolean }) {
  const { tipo, numero, contenido, nivel, es_continuacion, referencias, anchorId } = fraccion

  // Indentación: continuaciones usan el nivel del padre
  const nivelVisual = es_continuacion ? nivel - 1 : nivel
  const indentClass = clsx({
    'ml-0': nivelVisual <= 0,
    'ml-6': nivelVisual === 1,
    'ml-12': nivelVisual === 2,
    'ml-16': nivelVisual >= 3,
  })

  // Estilos de borde y fondo según tipo
  // Continuaciones heredan el estilo del padre basado en su nivel
  const tipoVisual = es_continuacion
    ? (nivel === 1 ? 'fraccion' : nivel === 2 ? 'inciso' : nivel === 3 ? 'numeral' : tipo)
    : tipo

  const borderStyles = clsx({
    'border-l-4 border-primary-500 bg-primary-50 dark:bg-primary-950/30': tipoVisual === 'fraccion',
    'border-l-3 border-emerald-400 bg-emerald-50 dark:bg-emerald-950/30': tipoVisual === 'inciso',
    'border-l-2 border-amber-400 bg-amber-50 dark:bg-amber-950/30': tipoVisual === 'numeral',
    'border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-950/30': tipoVisual === 'apartado',
    'border-l-2 border-gray-300 dark:border-gray-600': (tipoVisual === 'parrafo' || tipoVisual === 'texto'),
  })

  // Estilo del identificador según tipo
  // numero ya incluye puntuación para inciso (a)) y numeral (1.)
  // pero NO para fraccion (I, II) ni apartado (A, B)
  const getIdentifier = () => {
    switch (tipo) {
      case 'fraccion':
        return (
          <span className="font-bold text-primary-700 dark:text-primary-400">
            {numero}.
          </span>
        )
      case 'inciso':
        return (
          <span className="font-semibold text-emerald-700 dark:text-emerald-400">
            {numero}
          </span>
        )
      case 'numeral':
        return (
          <span className="font-medium text-amber-700 dark:text-amber-400">
            {numero}
          </span>
        )
      case 'apartado':
        return (
          <span className="font-bold text-blue-700 dark:text-blue-400">
            {numero}.
          </span>
        )
      case 'parrafo':
      default:
        return null
    }
  }

  const identifier = getIdentifier()

  return (
    <div
      id={anchorId}
      className={clsx('leading-relaxed pl-3 py-1.5 rounded-r scroll-mt-24', indentClass, borderStyles)}
    >
      {identifier ? (
        <p className="text-gray-700 dark:text-gray-300">
          {identifier}{' '}
          <span>{contenido}</span>
        </p>
      ) : (
        <p className="text-gray-700 dark:text-gray-300">
          {contenido}
        </p>
      )}
      {mostrarReferencias && referencias && referencias.length > 0 && (
        <div className="text-right mt-1">
          {referencias.map((ref, i) => (
            <p key={i} className="text-xs italic text-blue-600 dark:text-blue-400">
              {ref}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
