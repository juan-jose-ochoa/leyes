import { Link } from 'react-router-dom'
import { FileText, ChevronRight } from 'lucide-react'
import type { SearchResult } from '@/lib/api'
import clsx from 'clsx'

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
  return (
    <Link
      to={`/articulo/${result.id}`}
      className="card group block transition-shadow hover:shadow-md"
    >
      <div className="flex items-start gap-4">
        <div
          className={clsx(
            'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-sm font-bold text-white',
            result.ley_tipo === 'ley' ? 'bg-primary-600' : 'bg-blue-600'
          )}
        >
          {result.ley}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900 group-hover:text-primary-600 dark:text-gray-100 dark:group-hover:text-primary-400">
              {result.articulo}
            </h3>
            <span
              className={clsx(
                'badge',
                result.ley_tipo === 'ley' ? 'badge-ley' : 'badge-reglamento'
              )}
            >
              {result.ley_tipo}
            </span>
          </div>

          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {result.titulo}
          </p>

          {/* Snippet con highlighting */}
          <p
            className="mt-2 line-clamp-3 text-sm text-gray-700 dark:text-gray-300"
            dangerouslySetInnerHTML={{ __html: result.snippet }}
          />

          <div className="mt-3 flex items-center justify-between">
            <span className="text-xs text-gray-400">
              Relevancia: {(result.relevancia * 100).toFixed(0)}%
            </span>
            <span className="flex items-center gap-1 text-sm font-medium text-primary-600 group-hover:underline dark:text-primary-400">
              Ver articulo completo
              <ChevronRight className="h-4 w-4" />
            </span>
          </div>
        </div>
      </div>
    </Link>
  )
}
