import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Copy, Check, ExternalLink, BookOpen } from 'lucide-react'
import { useState } from 'react'
import { useArticle, useArticuloPorLey } from '@/hooks/useArticle'
import clsx from 'clsx'

export default function Article() {
  const { id, ley, numero } = useParams<{ id?: string; ley?: string; numero?: string }>()

  // Usar el hook apropiado según los parámetros
  const porLey = useArticuloPorLey(ley ?? null, numero ?? null)
  const porId = useArticle(id && !ley ? parseInt(id) : null)

  const { data: articulo, isLoading, error } = ley ? porLey : porId
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    if (!articulo) return
    await navigator.clipboard.writeText(
      `Artículo ${articulo.numero_raw}\n\n${articulo.contenido}\n\nFuente: ${articulo.ley_nombre}`
    )
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 w-32 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="h-12 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="space-y-2">
          <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="h-4 w-5/6 rounded bg-gray-200 dark:bg-gray-700" />
        </div>
      </div>
    )
  }

  if (error || !articulo) {
    return (
      <div className="py-12 text-center">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
          Articulo no encontrado
        </h2>
        <p className="mt-2 text-gray-500">
          El articulo que buscas no existe o ha sido eliminado.
        </p>
        <Link to="/" className="btn-primary mt-4 inline-flex">
          Volver al inicio
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl">
      {/* Navegación */}
      <Link
        to="/"
        className="mb-6 inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
      >
        <ArrowLeft className="h-4 w-4" />
        Volver a la busqueda
      </Link>

      {/* Header del articulo */}
      <div className="mb-8">
        <div className="flex items-center gap-3">
          <span
            className={clsx(
              'badge text-sm',
              articulo.ley_tipo === 'ley' ? 'badge-ley' : 'badge-reglamento'
            )}
          >
            {articulo.ley}
          </span>
          <span className="text-sm text-gray-500">{articulo.ley_nombre}</span>
        </div>

        <h1 className="mt-4 text-3xl font-bold text-gray-900 dark:text-white">
          Artículo {articulo.numero_raw}
        </h1>

        {articulo.ubicacion && (
          <p className="mt-2 text-lg text-gray-600 dark:text-gray-400">
            {articulo.ubicacion}
          </p>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={handleCopy}
            className="btn-secondary inline-flex items-center gap-2"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4" />
                Copiado
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                Copiar
              </>
            )}
          </button>
        </div>
      </div>

      {/* Contenido principal */}
      <div className="card">
        <div className="prose prose-gray max-w-none dark:prose-invert">
          {articulo.contenido.split('\n\n').filter(p => p.trim()).map((paragraph, i) => (
            <p key={i} className="mb-4 leading-relaxed">
              {paragraph}
            </p>
          ))}
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
      </div>

      {/* Referencias cruzadas */}
      {(articulo.referencias_salientes || articulo.referencias_entrantes) && (
        <div className="mt-8 grid gap-6 md:grid-cols-2">
          {articulo.referencias_salientes && articulo.referencias_salientes.length > 0 && (
            <div className="card">
              <h3 className="mb-4 flex items-center gap-2 font-semibold text-gray-900 dark:text-white">
                <BookOpen className="h-5 w-5 text-primary-600" />
                Este articulo cita
              </h3>
              <ul className="space-y-2">
                {articulo.referencias_salientes.map((ref) => (
                  <li key={ref.id}>
                    <Link
                      to={`/${ref.ley}/articulo/${ref.numero_raw}`}
                      className="flex items-center gap-2 rounded-lg p-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700"
                    >
                      <span className="font-medium text-primary-600 dark:text-primary-400">
                        {ref.ley}
                      </span>
                      <span className="text-gray-700 dark:text-gray-300">
                        Art. {ref.numero_raw}
                      </span>
                      <span className="ml-auto text-xs text-gray-400">{ref.tipo}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {articulo.referencias_entrantes && articulo.referencias_entrantes.length > 0 && (
            <div className="card">
              <h3 className="mb-4 flex items-center gap-2 font-semibold text-gray-900 dark:text-white">
                <BookOpen className="h-5 w-5 text-blue-600" />
                Citado por
              </h3>
              <ul className="space-y-2">
                {articulo.referencias_entrantes.map((ref) => (
                  <li key={ref.id}>
                    <Link
                      to={`/${ref.ley}/articulo/${ref.numero_raw}`}
                      className="flex items-center gap-2 rounded-lg p-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700"
                    >
                      <span className="font-medium text-blue-600 dark:text-blue-400">
                        {ref.ley}
                      </span>
                      <span className="text-gray-700 dark:text-gray-300">
                        Art. {ref.numero_raw}
                      </span>
                      <span className="ml-auto text-xs text-gray-400">{ref.tipo}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
