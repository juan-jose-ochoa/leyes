import { useState } from 'react'
import { ChevronDown, ChevronUp, ExternalLink, AlertCircle, BookOpen } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useReferenciasLegales } from '@/hooks/useArticle'
import clsx from 'clsx'

interface ReferenciasListProps {
  referencias: string
}

export default function ReferenciasList({ referencias }: ReferenciasListProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const { data: refsData, isLoading } = useReferenciasLegales(isExpanded ? referencias : null)

  // Separar referencias individuales para mostrar como chips
  const referenciasParsed = referencias.split(',').map(r => r.trim()).filter(Boolean)

  return (
    <div className="mt-4 rounded-lg border border-amber-200 dark:border-amber-800 overflow-hidden">
      {/* Header clickable */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={clsx(
          'w-full flex items-center justify-between px-4 py-3 text-left transition-colors',
          'bg-amber-50 dark:bg-amber-900/30 hover:bg-amber-100 dark:hover:bg-amber-900/50'
        )}
      >
        <div className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400">
          <BookOpen className="h-4 w-4" />
          <span className="font-medium">Referencias legales:</span>
          <span className="text-amber-600 dark:text-amber-300">{referencias}</span>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-5 w-5 text-amber-600 dark:text-amber-400" />
        ) : (
          <ChevronDown className="h-5 w-5 text-amber-600 dark:text-amber-400" />
        )}
      </button>

      {/* Contenido expandido */}
      {isExpanded && (
        <div className="p-4 bg-white dark:bg-gray-800 border-t border-amber-200 dark:border-amber-800">
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="animate-pulse">
                  <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
                  <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded" />
                  <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded mt-1 w-3/4" />
                </div>
              ))}
            </div>
          ) : refsData && refsData.length > 0 ? (
            <div className="space-y-4">
              {refsData.map((ref, idx) => (
                <div
                  key={`${ref.ley_codigo}-${ref.numero}-${idx}`}
                  className={clsx(
                    'rounded-lg p-4',
                    ref.encontrado
                      ? 'bg-gray-50 dark:bg-gray-900'
                      : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
                  )}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary-100 text-primary-800 dark:bg-primary-900 dark:text-primary-200">
                          {ref.ley_codigo}
                        </span>
                        <span className="font-semibold text-gray-900 dark:text-white">
                          Artículo {ref.numero}
                        </span>
                        {!ref.encontrado && (
                          <span className="inline-flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
                            <AlertCircle className="h-3 w-3" />
                            No disponible
                          </span>
                        )}
                      </div>

                      {ref.encontrado ? (
                        <>
                          {ref.titulo && (
                            <p className="text-sm font-medium text-gray-700 dark:text-gray-300 italic mb-2">
                              {ref.titulo}
                            </p>
                          )}
                          <div className="text-sm text-gray-600 dark:text-gray-400 prose-legal line-clamp-4">
                            {ref.contenido}
                          </div>
                        </>
                      ) : (
                        <p className="text-sm text-red-600 dark:text-red-400">
                          Este artículo no se encuentra en la base de datos.
                          La ley {ref.ley_codigo} podría no estar importada.
                        </p>
                      )}
                    </div>

                    {ref.encontrado && (
                      <Link
                        to={`/${ref.ley_codigo}/articulo/${ref.numero}`}
                        className="flex-shrink-0 inline-flex items-center gap-1 text-xs text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300"
                      >
                        Ver completo
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-4 text-gray-500 dark:text-gray-400">
              <AlertCircle className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No se encontraron referencias</p>
            </div>
          )}

          {/* Chips de referencias rápidas */}
          <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
              Referencias individuales:
            </p>
            <div className="flex flex-wrap gap-2">
              {referenciasParsed.map((ref, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center px-2 py-1 text-xs bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300 rounded-full"
                >
                  {ref}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
