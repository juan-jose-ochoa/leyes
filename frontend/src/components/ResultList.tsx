import { Link } from 'react-router-dom'
import { FileText, ChevronRight } from 'lucide-react'
import DOMPurify from 'dompurify'
import type { SearchResult } from '@/lib/api'
import clsx from 'clsx'

// Sanitizar snippets: solo permitir <mark> para highlighting
const sanitizeSnippet = (html: string): string => {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['mark'],
    ALLOWED_ATTR: []
  })
}

interface ResultListProps {
  results: SearchResult[]
  isLoading?: boolean
}

export default function ResultList({ results, isLoading }: ResultListProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="card animate-pulse">
            <div className="flex gap-4">
              <div className="h-10 w-10 rounded-lg bg-gray-200 dark:bg-gray-700" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-1/4 rounded bg-gray-200 dark:bg-gray-700" />
                <div className="h-3 w-1/2 rounded bg-gray-200 dark:bg-gray-700" />
                <div className="h-3 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <div className="py-12 text-center">
        <FileText className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
        <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-gray-100">
          No se encontraron resultados
        </h3>
        <p className="mt-2 text-gray-500">
          Intenta con otros terminos o ajusta los filtros
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500">
        {results.length} resultado{results.length !== 1 ? 's' : ''} encontrado{results.length !== 1 ? 's' : ''}
      </p>
      {results.map((result) => (
        <ResultCard key={result.id} result={result} />
      ))}
    </div>
  )
}

function ResultCard({ result }: { result: SearchResult }) {
  const esRegla = result.tipo === 'regla'
  const etiquetaTipo = esRegla ? 'Regla' : 'Articulo'
  const rutaTipo = esRegla ? 'regla' : 'articulo'

  return (
    <Link
      to={`/${result.ley}/${rutaTipo}/${result.numero_raw}`}
      className="card group block transition-shadow hover:shadow-md"
    >
      <div className="flex items-start gap-4">
        <div
          className={clsx(
            'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-sm font-bold text-white',
            result.ley_tipo === 'resolucion'
              ? 'bg-amber-600'
              : result.ley_tipo === 'ley'
                ? 'bg-primary-600'
                : 'bg-blue-600'
          )}
        >
          {result.ley}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900 group-hover:text-primary-600 dark:text-gray-100 dark:group-hover:text-primary-400">
              {etiquetaTipo} {result.numero_raw}
            </h3>
            <span
              className={clsx(
                'badge',
                result.ley_tipo === 'resolucion'
                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'
                  : result.ley_tipo === 'ley'
                    ? 'badge-ley'
                    : 'badge-reglamento'
              )}
            >
              {result.ley_tipo === 'resolucion' ? 'RMF' : result.ley_tipo}
            </span>
            {result.es_transitorio && (
              <span className="badge bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                transitorio
              </span>
            )}
          </div>

          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {result.ubicacion || result.ley_nombre}
          </p>

          {/* Snippet con highlighting (sanitizado contra XSS) */}
          <p
            className="mt-2 line-clamp-3 text-sm text-gray-700 dark:text-gray-300"
            dangerouslySetInnerHTML={{ __html: sanitizeSnippet(result.snippet) }}
          />

          <div className="mt-3 flex items-center justify-between">
            <span className="text-xs text-gray-400">
              Relevancia: {(result.relevancia * 100).toFixed(0)}%
            </span>
            <span className="flex items-center gap-1 text-sm font-medium text-primary-600 group-hover:underline dark:text-primary-400">
              Ver {esRegla ? 'regla' : 'articulo'} completo
              <ChevronRight className="h-4 w-4" />
            </span>
          </div>
        </div>
      </div>
    </Link>
  )
}
