import { useState, useEffect } from 'react'
import { useParams, Link, useLocation } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { Copy, Check, ExternalLink, BookOpen, ChevronLeft, ChevronRight, Home } from 'lucide-react'
import { useArticle, useArticuloPorLey, useNavegacion, useDivisionesArticulo, useFraccionesArticulo } from '@/hooks/useArticle'
import ArticleContent from '@/components/ArticleContent'
import ArticleToc from '@/components/ArticleToc'
import clsx from 'clsx'

export default function Article() {
  const params = useParams<{ id?: string; ley?: string; '*'?: string }>()
  const { id, ley } = params
  // El numero viene del wildcard (*) para soportar "/" en el valor (ej: "13/LISH")
  const numero = params['*'] || undefined
  const location = useLocation()
  const pathname = location.pathname
  const esRutaRegla = pathname.includes('/regla/')
  const esRutaFicha = pathname.includes('/ficha/')
  const esRutaCriterio = pathname.includes('/criterio/')

  // Usar el hook apropiado según los parámetros
  const porLey = useArticuloPorLey(ley ?? null, numero ?? null)
  const porId = useArticle(id && !ley ? parseInt(id) : null)

  const { data: articulo, isLoading, error } = ley ? porLey : porId
  const { data: navegacion } = useNavegacion(articulo?.id ?? null)
  const { data: divisiones } = useDivisionesArticulo(articulo?.id ?? null)
  const { data: fracciones } = useFraccionesArticulo(articulo?.id ?? null, ley ?? undefined)
  const [copied, setCopied] = useState(false)
  const [mostrarReferencias, setMostrarReferencias] = useState(false)

  // Scroll a hash al cargar la página (después de que carguen las fracciones)
  useEffect(() => {
    if (location.hash && fracciones && fracciones.length > 0) {
      const anchorId = location.hash.slice(1) // Remover '#'
      const element = document.getElementById(anchorId)
      if (element) {
        // Pequeño delay para asegurar que el DOM está listo
        setTimeout(() => {
          element.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }, 100)
      }
    }
  }, [location.hash, fracciones])

  // Determinar el tipo basándose en el tipo del artículo o la ruta
  const esRegla = articulo?.tipo === 'regla' || esRutaRegla
  const esFicha = articulo?.tipo === 'ficha' || esRutaFicha
  const esCriterio = articulo?.tipo === 'criterio' || esRutaCriterio
  const etiquetaTipo = esFicha ? 'Ficha' : esCriterio ? 'Criterio' : esRegla ? 'Regla' : 'Artículo'
  const rutaTipo = esFicha ? 'ficha' : esCriterio ? 'criterio' : esRegla ? 'regla' : 'articulo'

  const handleCopy = async () => {
    if (!articulo) return
    await navigator.clipboard.writeText(
      `${etiquetaTipo} ${articulo.numero_raw}\n\n${articulo.contenido}\n\nFuente: ${articulo.ley_nombre}`
    )
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl animate-pulse space-y-4">
        <div className="h-6 w-48 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="h-10 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="space-y-2 mt-8">
          <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="h-4 w-5/6 rounded bg-gray-200 dark:bg-gray-700" />
        </div>
      </div>
    )
  }

  if (error || !articulo) {
    const tipoTexto = esRutaRegla ? 'regla' : 'artículo'
    return (
      <div className="py-12 text-center">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
          {esRutaRegla ? 'Regla' : 'Artículo'} no encontrado
        </h2>
        <p className="mt-2 text-gray-500">
          El {tipoTexto} que buscas no existe o ha sido eliminado.
        </p>
        <Link to="/" className="btn-primary mt-4 inline-flex">
          Volver al inicio
        </Link>
      </div>
    )
  }

  // SEO: título y descripción dinámicos
  const seoTitle = `${etiquetaTipo} ${articulo.numero_raw} ${articulo.ley} - ${articulo.ley_nombre}`
  const seoDescription = articulo.titulo
    ? `${articulo.titulo}. ${articulo.contenido.slice(0, 150)}...`
    : articulo.contenido.slice(0, 200) + '...'

  return (
    <div className="mx-auto max-w-4xl">
      <Helmet>
        <title>{seoTitle}</title>
        <meta name="description" content={seoDescription} />
        <meta property="og:title" content={seoTitle} />
        <meta property="og:description" content={seoDescription} />
        <meta property="og:type" content="article" />
      </Helmet>

      {/* Breadcrumbs - Sticky en móvil */}
      <nav className="sticky top-0 z-10 -mx-4 px-4 py-3 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm border-b border-gray-200 dark:border-gray-800 mb-6 md:static md:bg-transparent md:dark:bg-transparent md:border-0 md:backdrop-blur-none md:mb-4">
        <ol className="flex items-center gap-1 text-sm overflow-x-auto">
          {/* Home */}
          <li className="shrink-0">
            <Link
              to="/"
              className="flex items-center gap-1 text-gray-500 hover:text-primary-600 dark:hover:text-primary-400"
            >
              <Home className="h-4 w-4" />
              <span className="sr-only md:not-sr-only">Inicio</span>
            </Link>
          </li>

          <ChevronRight className="h-4 w-4 text-gray-400 shrink-0" />

          {/* Ley */}
          <li className="shrink-0">
            <Link
              to={`/${ley || articulo.ley}`}
              className={clsx(
                'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium hover:opacity-80 transition-opacity',
                articulo.ley_tipo === 'resolucion'
                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'
                  : articulo.ley_tipo === 'ley'
                    ? 'bg-primary-100 text-primary-800 dark:bg-primary-900 dark:text-primary-200'
                    : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
              )}
            >
              {articulo.ley}
            </Link>
          </li>

          {/* Divisiones (Título, Capítulo, etc.) */}
          {divisiones?.map((div, idx) => {
            // Construir path jerárquico acumulativo: titulo/PRIMERO/capitulo/I
            const pathParts = divisiones.slice(0, idx + 1).map(d => `${d.tipo}/${d.numero}`)
            const divPath = `/${ley || articulo.ley}/${pathParts.join('/')}`
            return (
              <li key={div.id} className="flex items-center gap-1 shrink-0">
                <ChevronRight className="h-4 w-4 text-gray-400" />
                <Link
                  to={divPath}
                  className="text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 whitespace-nowrap transition-colors"
                >
                  {div.tipo.charAt(0).toUpperCase() + div.tipo.slice(1)} {div.numero}
                </Link>
              </li>
            )
          })}

          {/* Artículo actual */}
          <li className="flex items-center gap-1 shrink-0">
            <ChevronRight className="h-4 w-4 text-gray-400" />
            <span className="font-medium text-gray-900 dark:text-white whitespace-nowrap">
              {etiquetaTipo} {articulo.numero_raw}
            </span>
          </li>
        </ol>
      </nav>

      {/* Header del artículo */}
      <div className="mb-8 prose-legal">
        {/* División padre (Capítulo, Sección, etc.) */}
        {divisiones && divisiones.length > 0 && (
          <Link
            to={`/${ley || articulo.ley}/${divisiones.map(d => `${d.tipo}/${d.numero}`).join('/')}`}
            className="inline-flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 mb-2"
          >
            <span className="uppercase font-medium">
              {divisiones[divisiones.length - 1].tipo} {divisiones[divisiones.length - 1].numero}
            </span>
            <span>-</span>
            <span>{divisiones[divisiones.length - 1].nombre}</span>
          </Link>
        )}

        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          {etiquetaTipo} {articulo.numero_raw}
        </h1>

        {/* Título de la regla (si existe) */}
        {articulo.titulo && (
          <p className="mt-2 text-xl font-semibold text-gray-800 dark:text-gray-200 italic">
            {articulo.titulo}
          </p>
        )}

        <p className="mt-2 text-gray-500 dark:text-gray-400">
          {articulo.ley_nombre}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-3">
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

          {fracciones && fracciones.length > 0 && (
            <button
              onClick={() => setMostrarReferencias(!mostrarReferencias)}
              className={clsx(
                'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                mostrarReferencias
                  ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                  : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
              )}
            >
              {mostrarReferencias ? 'Ocultar referencias' : 'Mostrar referencias'}
            </button>
          )}

          {articulo.es_transitorio && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
              Transitorio
            </span>
          )}
        </div>
      </div>

      {/* Tabla de contenido - Si hay al menos una fracción */}
      {fracciones && fracciones.length >= 1 && (
        <ArticleToc fracciones={fracciones} className="mb-6" />
      )}

      {/* Contenido principal */}
      <div className="card">
        <div className="prose prose-gray prose-legal max-w-none dark:prose-invert">
          <ArticleContent articuloId={articulo.id} contenido={articulo.contenido} ley={ley} mostrarReferencias={mostrarReferencias} />
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
      </div>

      {/* Navegación anterior/siguiente */}
      {navegacion && (navegacion.anterior_numero || navegacion.siguiente_numero) && (
        <div className="mt-8 flex items-center justify-between gap-4">
          {navegacion.anterior_numero ? (
            <Link
              to={`/${ley || articulo.ley}/${rutaTipo}/${navegacion.anterior_numero}`}
              className="flex items-center gap-2 px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors group flex-1 max-w-xs"
            >
              <ChevronLeft className="h-5 w-5 text-gray-400 group-hover:text-primary-500" />
              <div className="text-left">
                <span className="block text-xs text-gray-500">Anterior</span>
                <span className="block font-medium text-gray-900 dark:text-white group-hover:text-primary-600 dark:group-hover:text-primary-400">
                  {etiquetaTipo} {navegacion.anterior_numero}
                </span>
              </div>
            </Link>
          ) : (
            <div />
          )}

          {navegacion.siguiente_numero ? (
            <Link
              to={`/${ley || articulo.ley}/${rutaTipo}/${navegacion.siguiente_numero}`}
              className="flex items-center gap-2 px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors group flex-1 max-w-xs ml-auto"
            >
              <div className="text-right flex-1">
                <span className="block text-xs text-gray-500">Siguiente</span>
                <span className="block font-medium text-gray-900 dark:text-white group-hover:text-primary-600 dark:group-hover:text-primary-400">
                  {etiquetaTipo} {navegacion.siguiente_numero}
                </span>
              </div>
              <ChevronRight className="h-5 w-5 text-gray-400 group-hover:text-primary-500" />
            </Link>
          ) : (
            <div />
          )}
        </div>
      )}

      {/* Referencias cruzadas */}
      {(articulo.referencias_salientes || articulo.referencias_entrantes) && (
        <div className="mt-8 grid gap-6 md:grid-cols-2">
          {articulo.referencias_salientes && articulo.referencias_salientes.length > 0 && (
            <div className="card">
              <h3 className="mb-4 flex items-center gap-2 font-semibold text-gray-900 dark:text-white">
                <BookOpen className="h-5 w-5 text-primary-600" />
                {esRegla ? 'Esta regla cita' : 'Este artículo cita'}
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
