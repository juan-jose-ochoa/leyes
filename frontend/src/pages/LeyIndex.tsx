import { useParams, Link } from 'react-router-dom'
import { BookOpen, ChevronRight, FileText, Home } from 'lucide-react'
import { useEstructuraLey, useLeyes } from '@/hooks/useArticle'
import clsx from 'clsx'

export default function LeyIndex() {
  const { ley } = useParams<{ ley: string }>()
  const { data: estructura, isLoading, error } = useEstructuraLey(ley ?? null)
  const { data: leyes } = useLeyes()

  const leyInfo = leyes?.find(l => l.codigo === ley)

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl animate-pulse space-y-4">
        <div className="h-8 w-64 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="h-4 w-96 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="mt-8 space-y-3">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-16 rounded-lg bg-gray-200 dark:bg-gray-700" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !estructura) {
    return (
      <div className="py-12 text-center">
        <BookOpen className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
        <h2 className="mt-4 text-2xl font-bold text-gray-900 dark:text-white">
          Ley no encontrada
        </h2>
        <p className="mt-2 text-gray-500">
          No se encontró la ley "{ley}".
        </p>
        <Link to="/" className="btn-primary mt-4 inline-flex">
          Volver al inicio
        </Link>
      </div>
    )
  }

  // Determinar tipo de contenido (articulo o regla)
  const esResolucion = leyInfo?.tipo === 'resolucion'
  const tipoContenido = esResolucion ? 'regla' : 'articulo'

  return (
    <div className="mx-auto max-w-4xl">
      {/* Breadcrumbs */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm">
          <li>
            <Link
              to="/"
              className="flex items-center gap-1 text-gray-500 hover:text-primary-600 dark:hover:text-primary-400"
            >
              <Home className="h-4 w-4" />
              <span>Inicio</span>
            </Link>
          </li>
          <ChevronRight className="h-4 w-4 text-gray-400" />
          <li>
            <span className="font-medium text-gray-900 dark:text-white">{ley}</span>
          </li>
        </ol>
      </nav>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <span
            className={clsx(
              'inline-flex items-center px-3 py-1 rounded-lg text-sm font-bold text-white',
              leyInfo?.tipo === 'resolucion'
                ? 'bg-amber-600'
                : leyInfo?.tipo === 'ley'
                  ? 'bg-primary-600'
                  : 'bg-blue-600'
            )}
          >
            {ley}
          </span>
        </div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          {leyInfo?.nombre || ley}
        </h1>
        {leyInfo && (
          <p className="mt-2 text-gray-500">
            {leyInfo.total_articulos} {esResolucion ? 'reglas' : 'artículos'}
          </p>
        )}
      </div>

      {/* Estructura jerárquica */}
      <div className="space-y-2">
        {estructura.map((div) => (
          <DivisionItem
            key={div.id}
            division={div}
            ley={ley!}
            tipoContenido={tipoContenido}
          />
        ))}
      </div>
    </div>
  )
}

interface DivisionItemProps {
  division: {
    id: number
    tipo: string
    numero: string | null
    nombre: string | null
    nivel: number
    total_articulos: number
    primer_articulo: string | null
  }
  ley: string
  tipoContenido: string
}

function DivisionItem({ division, ley, tipoContenido }: DivisionItemProps) {
  const tipoLabel = division.tipo.charAt(0).toUpperCase() + division.tipo.slice(1)
  const hasArticles = division.total_articulos > 0 && division.primer_articulo

  const content = (
    <div
      className={clsx(
        'flex items-center gap-4 p-4 rounded-lg border transition-colors',
        hasArticles
          ? 'border-gray-200 dark:border-gray-700 hover:border-primary-300 dark:hover:border-primary-700 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer'
          : 'border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30'
      )}
      style={{ marginLeft: `${division.nivel * 1.5}rem` }}
    >
      {/* Icono */}
      <div
        className={clsx(
          'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
          division.nivel === 0
            ? 'bg-primary-100 text-primary-600 dark:bg-primary-900/30 dark:text-primary-400'
            : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
        )}
      >
        {hasArticles ? (
          <FileText className="h-5 w-5" />
        ) : (
          <BookOpen className="h-5 w-5" />
        )}
      </div>

      {/* Contenido */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
            {tipoLabel} {division.numero}
          </span>
        </div>
        <h3 className="font-medium text-gray-900 dark:text-white truncate">
          {division.nombre || `${tipoLabel} ${division.numero}`}
        </h3>
      </div>

      {/* Contador de artículos */}
      {division.total_articulos > 0 && (
        <div className="text-right shrink-0">
          <span className="text-sm font-medium text-gray-900 dark:text-white">
            {division.total_articulos}
          </span>
          <span className="text-xs text-gray-500 ml-1">
            {tipoContenido === 'regla' ? 'reglas' : 'arts.'}
          </span>
        </div>
      )}

      {/* Flecha si tiene artículos */}
      {hasArticles && (
        <ChevronRight className="h-5 w-5 text-gray-300 dark:text-gray-600" />
      )}
    </div>
  )

  // Siempre enlazar a la vista de división si tiene artículos
  if (hasArticles) {
    return (
      <Link to={`/${ley}/division/${division.id}`}>
        {content}
      </Link>
    )
  }

  return content
}
