import { useState, useEffect } from 'react'
import { useParams, Link, useLocation } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { Copy, Check, ExternalLink, BookOpen } from 'lucide-react'
import clsx from 'clsx'
import ReferenciasList from '@/components/ReferenciasList'
import { useArticle, useArticuloPorLey, useNavegacion, useDivisionesArticulo, useFraccionesArticulo, useArticuloPdf } from '@/hooks/useArticle'
import ArticleContent from '@/components/ArticleContent'
import ArticleToc from '@/components/ArticleToc'
import PdfViewer from '@/components/PdfViewer'
import ArticleHeader from '@/components/ArticleHeader'
import ArticleFooter from '@/components/ArticleFooter'
import { useViewMode } from '@/hooks/useViewMode'
import { PDF_BASE } from '@/lib/api'

export default function Article() {
  const params = useParams<{ id?: string; ley?: string; '*'?: string }>()
  const { id, ley } = params
  const numero = params['*'] || undefined
  const location = useLocation()
  const pathname = location.pathname
  const esRutaRegla = pathname.includes('/regla/')
  const esRutaFicha = pathname.includes('/ficha/')
  const esRutaCriterio = pathname.includes('/criterio/')

  // Hooks de datos
  const porLey = useArticuloPorLey(ley ?? null, numero ?? null)
  const porId = useArticle(id && !ley ? parseInt(id) : null)
  const { data: articulo, isLoading, error } = ley ? porLey : porId
  const { data: navegacion } = useNavegacion(articulo?.id ?? null)
  const { data: divisiones } = useDivisionesArticulo(articulo?.id ?? null)
  const { data: fracciones } = useFraccionesArticulo(articulo?.id ?? null, ley ?? undefined)
  const { data: coordenadasPdf } = useArticuloPdf(articulo?.id ?? null)

  // Estados locales
  const [copied, setCopied] = useState(false)
  const [mostrarReferencias, setMostrarReferencias] = useState(false)
  const { mode: viewMode, setMode: setViewMode } = useViewMode('text')

  // Scroll a hash al cargar
  useEffect(() => {
    if (location.hash && fracciones && fracciones.length > 0) {
      const anchorId = location.hash.slice(1)
      const element = document.getElementById(anchorId)
      if (element) {
        setTimeout(() => {
          element.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }, 100)
      }
    }
  }, [location.hash, fracciones])

  // Determinar tipo
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

  // Loading
  if (isLoading) {
    return (
      <div className="min-h-screen pt-14 pb-14">
        <div className="mx-auto max-w-4xl px-4 py-8 animate-pulse space-y-4">
          <div className="h-6 w-48 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="h-10 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="space-y-2 mt-8">
            <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
            <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
            <div className="h-4 w-5/6 rounded bg-gray-200 dark:bg-gray-700" />
          </div>
        </div>
      </div>
    )
  }

  // Error
  if (error || !articulo) {
    const tipoTexto = esRutaRegla ? 'regla' : 'artículo'
    return (
      <div className="min-h-screen pt-14 pb-14">
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
      </div>
    )
  }

  // SEO
  const seoTitle = `${etiquetaTipo} ${articulo.numero_raw} ${articulo.ley} - ${articulo.ley_nombre}`
  const seoDescription = articulo.titulo
    ? `${articulo.titulo}. ${articulo.contenido.slice(0, 150)}...`
    : articulo.contenido.slice(0, 200) + '...'

  // PDF URL
  const pdfUrl = `${PDF_BASE}/${articulo.ley.toLowerCase()}/documento.pdf`
  const hasPdf = !!coordenadasPdf

  // Determinar qué mostrar según modo
  // Texto: siempre visible en móvil, oculto en lg+ solo si modo PDF
  const showPdf = (viewMode === 'pdf' || viewMode === 'split') && hasPdf

  return (
    <>
      <Helmet>
        <title>{seoTitle}</title>
        <link rel="canonical" href={`https://leyesfiscalesmexico.com${location.pathname}`} />
        <meta name="description" content={seoDescription} />
        <meta property="og:title" content={seoTitle} />
        <meta property="og:description" content={seoDescription} />
        <meta property="og:type" content="article" />
      </Helmet>

      {/* Header fijo - siempre visible */}
      <ArticleHeader
        ley={ley || articulo.ley}
        leyTipo={articulo.ley_tipo}
        numeroRaw={articulo.numero_raw}
        etiquetaTipo={etiquetaTipo}
        divisiones={divisiones}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        hasPdf={hasPdf}
      />

      {/* Contenido principal */}
      <main className="min-h-screen pt-14 pb-14">
        <div className={clsx(
          'h-[calc(100vh-7rem)]',
          viewMode === 'split' && 'lg:grid lg:grid-cols-2',
        )}>
          {/* Panel de texto - oculto en modo PDF */}
          {viewMode !== 'pdf' && (
            <div className={clsx(
              'overflow-y-auto',
              viewMode === 'split' && 'lg:border-r border-gray-200 dark:border-gray-700'
            )}>
            <div className={clsx(
              'px-4 pt-6 pb-16',
              viewMode !== 'split' && 'max-w-4xl mx-auto'
            )}>
                {/* Header del artículo */}
                <div className="mb-8 prose-legal">
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

                {/* TOC */}
                {fracciones && fracciones.length >= 1 && (
                  <ArticleToc fracciones={fracciones} className="mb-6" />
                )}

                {/* Contenido */}
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
                    <ReferenciasList referencias={articulo.referencias_legales} />
                  )}
                </div>

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
          </div>
          )}

          {/* Panel PDF */}
          {showPdf && coordenadasPdf && (
            <div className={clsx(
              'h-full overflow-hidden bg-gray-100 dark:bg-gray-800',
              viewMode === 'split' && 'hidden lg:block'
            )}>
              <PdfViewer
                key={`${pdfUrl}-${coordenadasPdf.pagina}-${coordenadasPdf.y}`}
                pdfUrl={pdfUrl}
                pagina={coordenadasPdf.pagina}
                y={coordenadasPdf.y}
                className="h-full"
              />
            </div>
          )}
        </div>
      </main>

      {/* Footer fijo - siempre visible */}
      <ArticleFooter
        ley={ley || articulo.ley}
        rutaTipo={rutaTipo}
        etiquetaTipo={etiquetaTipo}
        numeroActual={articulo.numero_raw}
        anteriorNumero={navegacion?.anterior_numero ?? undefined}
        siguienteNumero={navegacion?.siguiente_numero ?? undefined}
      />
    </>
  )
}
