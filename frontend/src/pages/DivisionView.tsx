import { useParams, Link } from 'react-router-dom'
import { Home, ChevronRight, BookOpen, ExternalLink } from 'lucide-react'
import { useDivisionInfo, useArticulosDivision } from '@/hooks/useArticle'
import clsx from 'clsx'

export default function DivisionView() {
  const { ley, id } = useParams<{ ley: string; id: string }>()
  const divId = id ? parseInt(id) : null

  const { data: info, isLoading: loadingInfo } = useDivisionInfo(divId)
  const { data: articulos, isLoading: loadingArticulos } = useArticulosDivision(divId)

  const isLoading = loadingInfo || loadingArticulos
  const esRegla = info?.ley_tipo === 'resolucion'
  const tipoContenido = esRegla ? 'regla' : 'articulo'

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl animate-pulse space-y-4">
        <div className="h-6 w-48 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="h-10 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="mt-8 space-y-6">
          {[1, 2, 3].map(i => (
            <div key={i} className="space-y-2">
              <div className="h-6 w-32 rounded bg-gray-200 dark:bg-gray-700" />
              <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
              <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
              <div className="h-4 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!info || !articulos) {
    return (
      <div className="py-12 text-center">
        <BookOpen className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
        <h2 className="mt-4 text-2xl font-bold text-gray-900 dark:text-white">
          División no encontrada
        </h2>
        <Link to="/" className="btn-primary mt-4 inline-flex">
          Volver al inicio
        </Link>
      </div>
    )
  }

  // Parsear path_texto para breadcrumbs
  const partes = info.path_texto?.split(' > ') || []

  return (
    <div className="mx-auto max-w-4xl">
      {/* Breadcrumbs */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm flex-wrap">
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
            <Link
              to={`/${info.ley_codigo}`}
              className={clsx(
                'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium hover:opacity-80',
                info.ley_tipo === 'resolucion'
                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'
                  : info.ley_tipo === 'ley'
                    ? 'bg-primary-100 text-primary-800 dark:bg-primary-900 dark:text-primary-200'
                    : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
              )}
            >
              {info.ley_codigo}
            </Link>
          </li>
          {partes.map((parte, idx) => (
            <li key={idx} className="flex items-center gap-2">
              <ChevronRight className="h-4 w-4 text-gray-400" />
              <span className={idx === partes.length - 1 ? 'font-medium text-gray-900 dark:text-white' : 'text-gray-500'}>
                {parte}
              </span>
            </li>
          ))}
        </ol>
      </nav>

      {/* Header */}
      <div className="mb-8 prose-legal">
        <p className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">
          {info.div_tipo} {info.numero}
        </p>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          {info.nombre || `${info.div_tipo} ${info.numero}`}
        </h1>
        <p className="mt-2 text-gray-500">
          {info.total_articulos} {esRegla ? 'reglas' : 'artículos'}
        </p>
      </div>

      {/* Artículos */}
      <div className="space-y-8">
        {articulos.map((art) => (
          <article
            key={art.id}
            id={`art-${art.numero_raw}`}
            className="scroll-mt-20"
          >
            {/* Header del artículo */}
            <div className="flex items-start justify-between gap-4 mb-4 prose-legal">
              <div>
                <Link
                  to={`/${ley}/${tipoContenido}/${art.numero_raw}`}
                  className="inline-flex items-center gap-2 group"
                >
                  <h2 className="text-xl font-bold text-primary-600 dark:text-primary-400 group-hover:text-primary-700 dark:group-hover:text-primary-300">
                    {esRegla ? 'Regla' : 'Artículo'} {art.numero_raw}
                  </h2>
                  <ExternalLink className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
                {art.es_transitorio && (
                  <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                    Transitorio
                  </span>
                )}
              </div>
            </div>

            {/* Contenido */}
            <div className="prose prose-gray prose-legal max-w-none dark:prose-invert">
              {art.contenido.split('\n\n').filter(p => p.trim()).map((paragraph, i) => (
                <p key={i} className="mb-4 leading-relaxed text-gray-700 dark:text-gray-300">
                  {paragraph}
                </p>
              ))}
            </div>

            {/* Reformas */}
            {art.reformas && (
              <div className="mt-4 text-sm text-gray-500 dark:text-gray-400 italic">
                Reformas: {art.reformas}
              </div>
            )}

            {/* Referencias (RMF) */}
            {art.referencias && (
              <div className="mt-4 text-sm text-amber-700 dark:text-amber-400">
                Referencias: {art.referencias}
              </div>
            )}

            {/* Separador */}
            <hr className="mt-8 border-gray-200 dark:border-gray-700" />
          </article>
        ))}
      </div>

      {/* Navegación al final */}
      <div className="mt-12 flex justify-center">
        <Link
          to={`/${info.ley_codigo}`}
          className="btn-secondary"
        >
          Volver al índice de {info.ley_codigo}
        </Link>
      </div>
    </div>
  )
}
