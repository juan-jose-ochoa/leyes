import { Copy, Check, ExternalLink, BookOpen, ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useArticuloPorLey, useNavegacion, useFraccionesArticulo } from '@/hooks/useArticle'
import FraccionesView from './FraccionesView'
import clsx from 'clsx'

interface ArticlePanelProps {
  ley: string
  numero: string
  onClose?: () => void
  onNavigate?: (numero: string) => void
}

export default function ArticlePanel({ ley, numero, onClose, onNavigate }: ArticlePanelProps) {
  const { data: articulo, isLoading, error } = useArticuloPorLey(ley, numero)
  const { data: navegacion } = useNavegacion(articulo?.id ?? null)
  const { data: fracciones } = useFraccionesArticulo(articulo?.id ?? null)
  const [copied, setCopied] = useState(false)

  const esRegla = articulo?.tipo === 'regla'
  const etiquetaTipo = esRegla ? 'Regla' : 'Artículo'

  const handleCopy = async () => {
    if (!articulo) return
    await navigator.clipboard.writeText(
      `${etiquetaTipo} ${articulo.numero_raw}\n\n${articulo.contenido}\n\nFuente: ${articulo.ley_nombre}`
    )
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleNavegar = (nuevoNumero: string) => {
    if (onNavigate) {
      onNavigate(nuevoNumero)
    }
  }

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4 p-6">
        <div className="h-6 w-48 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="h-8 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="space-y-2 mt-6">
          <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="h-4 w-5/6 rounded bg-gray-200 dark:bg-gray-700" />
        </div>
      </div>
    )
  }

  if (error || !articulo) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center">
        <BookOpen className="h-12 w-12 text-gray-300 dark:text-gray-600 mb-4" />
        <h3 className="text-lg font-medium text-gray-900 dark:text-white">
          {esRegla ? 'Regla' : 'Artículo'} no encontrado
        </h3>
        <p className="mt-2 text-gray-500">
          El contenido no existe o ha sido eliminado.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header sticky */}
      <div className="sticky top-0 z-10 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1 prose-legal">
            <div className="flex items-center gap-2 mb-1">
              <span
                className={clsx(
                  'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                  articulo.ley_tipo === 'resolucion'
                    ? 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'
                    : articulo.ley_tipo === 'ley'
                      ? 'bg-primary-100 text-primary-800 dark:bg-primary-900 dark:text-primary-200'
                      : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                )}
              >
                {articulo.ley}
              </span>
              {articulo.es_transitorio && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                  Transitorio
                </span>
              )}
            </div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              {etiquetaTipo} {articulo.numero_raw}
            </h2>
            {articulo.ubicacion && (
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 truncate">
                {articulo.ubicacion}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={handleCopy}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              title="Copiar"
            >
              {copied ? (
                <Check className="h-5 w-5 text-green-600" />
              ) : (
                <Copy className="h-5 w-5 text-gray-500" />
              )}
            </button>
            <Link
              to={`/${ley}/${esRegla ? 'regla' : 'articulo'}/${numero}`}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              title="Abrir en página completa"
            >
              <ExternalLink className="h-5 w-5 text-gray-500" />
            </Link>
            {onClose && (
              <button
                onClick={onClose}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                title="Cerrar"
              >
                <X className="h-5 w-5 text-gray-500" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Contenido scrolleable */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="prose prose-gray prose-legal max-w-none dark:prose-invert">
          {fracciones && fracciones.length > 0 ? (
            <FraccionesView fracciones={fracciones} />
          ) : (
            articulo.contenido.split('\n\n').filter(p => p.trim()).map((paragraph, i) => (
              <p key={i} className="mb-4 leading-relaxed">
                {paragraph}
              </p>
            ))
          )}
        </div>

        {articulo.reformas && (
          <div className="mt-6 rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
            <h3 className="mb-2 flex items-center gap-2 font-medium text-gray-900 dark:text-white">
              <ExternalLink className="h-4 w-4" />
              Reformas DOF
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {articulo.reformas}
            </p>
          </div>
        )}

        {articulo.referencias_legales && (
          <div className="mt-6 rounded-lg bg-amber-50 p-4 dark:bg-amber-900/20">
            <h3 className="mb-2 flex items-center gap-2 font-medium text-gray-900 dark:text-white">
              <BookOpen className="h-4 w-4" />
              Referencias Legales
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {articulo.referencias_legales}
            </p>
          </div>
        )}

        {/* Referencias cruzadas */}
        {(articulo.referencias_salientes || articulo.referencias_entrantes) && (
          <div className="mt-6 grid gap-4">
            {articulo.referencias_salientes && articulo.referencias_salientes.length > 0 && (
              <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                <h3 className="mb-3 flex items-center gap-2 font-semibold text-gray-900 dark:text-white text-sm">
                  <BookOpen className="h-4 w-4 text-primary-600" />
                  {esRegla ? 'Esta regla cita' : 'Este artículo cita'}
                </h3>
                <div className="flex flex-wrap gap-2">
                  {articulo.referencias_salientes.map((ref) => (
                    <button
                      key={ref.id}
                      onClick={() => handleNavegar(ref.numero_raw)}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 transition-colors"
                    >
                      <span className="text-primary-600 dark:text-primary-400">{ref.ley}</span>
                      <span className="text-gray-700 dark:text-gray-300">Art. {ref.numero_raw}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {articulo.referencias_entrantes && articulo.referencias_entrantes.length > 0 && (
              <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                <h3 className="mb-3 flex items-center gap-2 font-semibold text-gray-900 dark:text-white text-sm">
                  <BookOpen className="h-4 w-4 text-blue-600" />
                  Citado por
                </h3>
                <div className="flex flex-wrap gap-2">
                  {articulo.referencias_entrantes.map((ref) => (
                    <button
                      key={ref.id}
                      onClick={() => handleNavegar(ref.numero_raw)}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 transition-colors"
                    >
                      <span className="text-blue-600 dark:text-blue-400">{ref.ley}</span>
                      <span className="text-gray-700 dark:text-gray-300">Art. {ref.numero_raw}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Navegación sticky al bottom */}
      {navegacion && (navegacion.anterior_numero || navegacion.siguiente_numero) && (
        <div className="sticky bottom-0 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 px-6 py-3">
          <div className="flex items-center justify-between gap-4">
            {navegacion.anterior_numero ? (
              <button
                onClick={() => handleNavegar(navegacion.anterior_numero!)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors group"
              >
                <ChevronLeft className="h-5 w-5 text-gray-400 group-hover:text-primary-500" />
                <div className="text-left">
                  <span className="block text-xs text-gray-500">Anterior</span>
                  <span className="block text-sm font-medium text-gray-900 dark:text-white group-hover:text-primary-600 dark:group-hover:text-primary-400">
                    {etiquetaTipo} {navegacion.anterior_numero}
                  </span>
                </div>
              </button>
            ) : (
              <div />
            )}

            {navegacion.siguiente_numero ? (
              <button
                onClick={() => handleNavegar(navegacion.siguiente_numero!)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors group"
              >
                <div className="text-right">
                  <span className="block text-xs text-gray-500">Siguiente</span>
                  <span className="block text-sm font-medium text-gray-900 dark:text-white group-hover:text-primary-600 dark:group-hover:text-primary-400">
                    {etiquetaTipo} {navegacion.siguiente_numero}
                  </span>
                </div>
                <ChevronRight className="h-5 w-5 text-gray-400 group-hover:text-primary-500" />
              </button>
            ) : (
              <div />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
