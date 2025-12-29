import { type Fraccion } from '@/lib/api'
import clsx from 'clsx'

interface FraccionesViewProps {
  fracciones: Fraccion[]
}

export default function FraccionesView({ fracciones }: FraccionesViewProps) {
  if (!fracciones || fracciones.length === 0) {
    return null
  }

  return (
    <div className="space-y-4">
      {fracciones.map((fraccion) => (
        <FraccionItem key={fraccion.id} fraccion={fraccion} />
      ))}
    </div>
  )
}

function FraccionItem({ fraccion }: { fraccion: Fraccion }) {
  const { tipo, numero, contenido, nivel } = fraccion

  // Los párrafos de continuación (texto con nivel > 0) no se indentan
  // porque son continuación del contenido de su padre, no sub-elementos
  const esContinuacion = tipo === 'texto' && nivel > 0

  // Calcular indentación basada en nivel
  // Continuaciones no se indentan extra
  const indentClass = clsx({
    'ml-0': nivel === 0 || esContinuacion,
    'ml-6': nivel === 1 && !esContinuacion,
    'ml-12': nivel === 2 && !esContinuacion,
    'ml-16': nivel >= 3 && !esContinuacion,
  })

  // Estilos de borde y fondo según tipo
  // Continuaciones tienen estilo sutil
  const borderStyles = clsx({
    'border-l-4 border-primary-500 bg-primary-50 dark:bg-primary-950/30': tipo === 'fraccion',
    'border-l-3 border-emerald-400 bg-emerald-50 dark:bg-emerald-950/30': tipo === 'inciso',
    'border-l-2 border-amber-400 bg-amber-50 dark:bg-amber-950/30': tipo === 'numeral',
    'border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-950/30': tipo === 'apartado',
    'border-l-2 border-gray-200 dark:border-gray-700': esContinuacion,
    'border-l-2 border-gray-300 dark:border-gray-600': (tipo === 'parrafo' || tipo === 'texto') && !esContinuacion,
  })

  // Estilo del identificador según tipo
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
            {numero})
          </span>
        )
      case 'numeral':
        return (
          <span className="font-medium text-amber-700 dark:text-amber-400">
            {numero}.
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
    <div className={clsx('leading-relaxed pl-3 py-1.5 rounded-r', indentClass, borderStyles)}>
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
    </div>
  )
}
