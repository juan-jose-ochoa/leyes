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

  // Calcular indentación basada en nivel
  const indentClass = clsx({
    'ml-0': nivel === 0,
    'ml-6': nivel === 1,
    'ml-12': nivel === 2,
    'ml-16': nivel >= 3,
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
          <span className="font-semibold text-gray-700 dark:text-gray-300">
            {numero})
          </span>
        )
      case 'numeral':
        return (
          <span className="font-medium text-gray-600 dark:text-gray-400">
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
    <div className={clsx('leading-relaxed', indentClass)}>
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
