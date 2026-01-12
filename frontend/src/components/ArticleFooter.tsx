import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface ArticleFooterProps {
  ley: string
  rutaTipo: string
  etiquetaTipo: string
  numeroActual: string
  anteriorNumero?: string
  siguienteNumero?: string
  totalArticulos?: number
  posicionActual?: number
}

export default function ArticleFooter({
  ley,
  rutaTipo,
  etiquetaTipo,
  numeroActual,
  anteriorNumero,
  siguienteNumero,
  totalArticulos,
  posicionActual,
}: ArticleFooterProps) {
  return (
    <footer className="fixed bottom-0 left-0 right-0 z-50 h-14 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm border-t border-gray-200 dark:border-gray-700">
      <div className="h-full max-w-7xl mx-auto px-4 flex items-center justify-between">
        {/* Anterior */}
        {anteriorNumero ? (
          <Link
            to={`/${ley}/${rutaTipo}/${anteriorNumero}`}
            className="flex items-center gap-2 px-3 py-2 -ml-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors group"
          >
            <ChevronLeft className="h-5 w-5 text-gray-400 group-hover:text-primary-500" />
            <div className="text-left">
              <span className="block text-xs text-gray-500 leading-tight">Anterior</span>
              <span className="block text-sm font-medium text-gray-900 dark:text-white group-hover:text-primary-600 dark:group-hover:text-primary-400 leading-tight">
                {etiquetaTipo} {anteriorNumero}
              </span>
            </div>
          </Link>
        ) : (
          <div className="w-24" />
        )}

        {/* Indicador de posición */}
        <div className="text-center">
          <span className="text-sm font-medium text-gray-900 dark:text-white">
            {numeroActual}
          </span>
          {totalArticulos && posicionActual && (
            <span className="text-xs text-gray-500 ml-2">
              / {totalArticulos}
            </span>
          )}
        </div>

        {/* Siguiente */}
        {siguienteNumero ? (
          <Link
            to={`/${ley}/${rutaTipo}/${siguienteNumero}`}
            className="flex items-center gap-2 px-3 py-2 -mr-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors group"
          >
            <div className="text-right">
              <span className="block text-xs text-gray-500 leading-tight">Siguiente</span>
              <span className="block text-sm font-medium text-gray-900 dark:text-white group-hover:text-primary-600 dark:group-hover:text-primary-400 leading-tight">
                {etiquetaTipo} {siguienteNumero}
              </span>
            </div>
            <ChevronRight className="h-5 w-5 text-gray-400 group-hover:text-primary-500" />
          </Link>
        ) : (
          <div className="w-24" />
        )}
      </div>
    </footer>
  )
}
