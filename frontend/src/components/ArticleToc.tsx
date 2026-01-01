import { useState, useCallback, useMemo } from 'react'
import { ChevronDown } from 'lucide-react'
import clsx from 'clsx'
import type { Fraccion } from '@/lib/api'
import { buildFraccionAnchors, buildTocEntries } from '@/lib/anchorUtils'

interface ArticleTocProps {
  fracciones: Fraccion[]
  minFractions?: number  // Minimo de fracciones para mostrar TOC (default: 1)
  className?: string
}

export default function ArticleToc({
  fracciones,
  minFractions = 1,
  className
}: ArticleTocProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null)

  // Construir entradas de TOC con memoizacion
  const tocEntries = useMemo(() => {
    if (!fracciones || fracciones.length === 0) return []
    const withAnchors = buildFraccionAnchors(fracciones)
    return buildTocEntries(withAnchors)
  }, [fracciones])

  // No renderizar si no hay suficientes fracciones
  if (tocEntries.length < minFractions) {
    return null
  }

  const handleChipClick = useCallback((anchorId: string) => {
    const element = document.getElementById(anchorId)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' })
      // Actualizar URL hash sin triggear scroll
      history.pushState(null, '', `#${anchorId}`)
    }
  }, [])

  const toggleExpand = useCallback((id: number, e: React.MouseEvent) => {
    e.stopPropagation()
    setExpandedId(prev => prev === id ? null : id)
  }, [])

  return (
    <nav
      className={clsx(
        'p-3 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700',
        className
      )}
      aria-label="Tabla de contenido"
    >
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-3">
        Ir a fraccion
      </p>

      {/* Fila principal de chips - scroll horizontal en movil */}
      <div className="flex flex-wrap gap-2">
        {tocEntries.map((entry) => (
          <div key={entry.id} className="relative">
            {/* Chip de fraccion principal */}
            <button
              onClick={() => handleChipClick(entry.anchorId)}
              className={clsx(
                'inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-semibold',
                'bg-primary-100 text-primary-800 dark:bg-primary-900 dark:text-primary-200',
                'hover:bg-primary-200 dark:hover:bg-primary-800 transition-colors',
                'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800'
              )}
            >
              {entry.label}

              {/* Indicador de expansion para fracciones con incisos */}
              {entry.hasChildren && (
                <span
                  onClick={(e) => toggleExpand(entry.id, e)}
                  className="ml-1 p-0.5 rounded hover:bg-primary-300 dark:hover:bg-primary-700 cursor-pointer"
                  role="button"
                  aria-label={expandedId === entry.id ? 'Colapsar incisos' : 'Expandir incisos'}
                >
                  <ChevronDown
                    className={clsx(
                      'h-3 w-3 transition-transform',
                      expandedId === entry.id && 'rotate-180'
                    )}
                  />
                </span>
              )}
            </button>

            {/* Dropdown de incisos expandido */}
            {entry.hasChildren && expandedId === entry.id && (
              <div className="absolute top-full left-0 mt-1 z-10 p-2 bg-white dark:bg-gray-900 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 min-w-max">
                <div className="flex flex-wrap gap-1.5 max-w-xs">
                  {entry.children.map((child) => (
                    <button
                      key={child.id}
                      onClick={() => {
                        handleChipClick(child.anchorId)
                        setExpandedId(null)
                      }}
                      className={clsx(
                        'inline-flex items-center px-2 py-1 rounded text-xs font-medium',
                        'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200',
                        'hover:bg-emerald-200 dark:hover:bg-emerald-800 transition-colors'
                      )}
                    >
                      {child.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </nav>
  )
}
