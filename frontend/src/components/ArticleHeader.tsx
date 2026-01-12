import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import clsx from 'clsx'
import ViewModeToggle from './ViewModeToggle'
import ThemeToggle from './ThemeToggle'
import type { ViewMode } from '@/hooks/useViewMode'
import { useIsDesktop } from '@/hooks/useIsDesktop'

interface Division {
  id: number
  tipo: string
  numero: string | null
  nombre: string | null
}

interface ArticleHeaderProps {
  ley: string
  leyTipo?: string
  numeroRaw: string
  etiquetaTipo: string
  divisiones?: Division[]
  viewMode: ViewMode
  onViewModeChange: (mode: ViewMode) => void
  hasPdf?: boolean
}

export default function ArticleHeader({
  ley,
  leyTipo,
  numeroRaw,
  etiquetaTipo,
  divisiones,
  viewMode,
  onViewModeChange,
  hasPdf = true,
}: ArticleHeaderProps) {
  const isDesktop = useIsDesktop()

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-14 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm border-b border-gray-200 dark:border-gray-700">
      <div className="h-full max-w-7xl mx-auto px-4 flex items-center justify-between gap-4">
        {/* Logo + Breadcrumb */}
        <div className="flex items-center gap-3 min-w-0 flex-1">
          {/* Logo */}
          <Link to="/" className="shrink-0 flex items-center gap-2 text-primary-600 dark:text-primary-400">
            <svg className="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" fill="none" />
            </svg>
            <span className="font-bold text-lg hidden sm:inline">LeyesMX</span>
          </Link>

          {/* Breadcrumb - Desktop */}
          <nav className="hidden md:flex items-center gap-1 text-sm min-w-0 overflow-hidden">
            <ChevronRight className="h-4 w-4 text-gray-400 shrink-0" />

            {/* Ley */}
            <Link
              to={`/${ley}`}
              className={clsx(
                'shrink-0 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium hover:opacity-80 transition-opacity',
                leyTipo === 'resolucion'
                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'
                  : leyTipo === 'ley'
                    ? 'bg-primary-100 text-primary-800 dark:bg-primary-900 dark:text-primary-200'
                    : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
              )}
            >
              {ley}
            </Link>

            {/* Divisiones */}
            {divisiones?.map((div, idx) => {
              const pathParts = divisiones.slice(0, idx + 1).map(d => `${d.tipo}/${d.numero}`)
              const divPath = `/${ley}/${pathParts.join('/')}`
              return (
                <span key={div.id} className="flex items-center gap-1 shrink-0">
                  <ChevronRight className="h-4 w-4 text-gray-400" />
                  <Link
                    to={divPath}
                    className="text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 whitespace-nowrap transition-colors"
                  >
                    {div.tipo.charAt(0).toUpperCase() + div.tipo.slice(1)} {div.numero || ''}
                  </Link>
                </span>
              )
            })}

            {/* Artículo actual */}
            <span className="flex items-center gap-1 shrink-0">
              <ChevronRight className="h-4 w-4 text-gray-400" />
              <span className="font-medium text-gray-900 dark:text-white whitespace-nowrap">
                {etiquetaTipo} {numeroRaw}
              </span>
            </span>
          </nav>

          {/* Breadcrumb - Móvil (compacto) */}
          <div className="flex md:hidden items-center gap-2 text-sm min-w-0">
            <Link
              to={`/${ley}`}
              className={clsx(
                'shrink-0 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                leyTipo === 'resolucion'
                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'
                  : leyTipo === 'ley'
                    ? 'bg-primary-100 text-primary-800 dark:bg-primary-900 dark:text-primary-200'
                    : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
              )}
            >
              {ley}
            </Link>
            <span className="font-medium text-gray-900 dark:text-white truncate">
              {etiquetaTipo} {numeroRaw}
            </span>
          </div>
        </div>

        {/* Controles */}
        <div className="flex items-center gap-2 shrink-0">
          {/* View Mode Toggle - solo desktop (móviles táctiles no sincronizan PDF) */}
          {hasPdf && isDesktop && (
            <ViewModeToggle mode={viewMode} onModeChange={onViewModeChange} />
          )}

          {/* Theme Toggle */}
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
