import { useState, useMemo } from 'react'
import { useParams, Link, useLocation } from 'react-router-dom'
import { Home, ChevronRight, BookOpen, ExternalLink, AlertTriangle, CheckCircle, XCircle, Filter, Eye, EyeOff, FileQuestion } from 'lucide-react'
import { useDivisionPorTipoNumero, useArticulosDivision, useVerificacionDivision } from '@/hooks/useArticle'
import ArticleContent from '@/components/ArticleContent'
import ReferenciasList from '@/components/ReferenciasList'
import type { RegistroCalidad, ArticuloDivision, VerificacionDivisionSimple } from '@/lib/api'
import clsx from 'clsx'

// Componente para mostrar el estatus de calidad de importación
function CalidadBadge({ calidad }: { calidad: RegistroCalidad }) {
  const config = {
    ok: { icon: CheckCircle, bg: 'bg-green-100 dark:bg-green-900', text: 'text-green-700 dark:text-green-300', label: 'OK' },
    corregida: { icon: AlertTriangle, bg: 'bg-yellow-100 dark:bg-yellow-900', text: 'text-yellow-700 dark:text-yellow-300', label: 'Corregida' },
    con_error: { icon: XCircle, bg: 'bg-red-100 dark:bg-red-900', text: 'text-red-700 dark:text-red-300', label: 'Con errores' },
  }[calidad.estatus]

  const Icon = config.icon

  return (
    <div className={clsx('mt-4 p-3 rounded-lg', config.bg)}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={clsx('h-4 w-4', config.text)} />
        <span className={clsx('text-sm font-medium', config.text)}>
          Calidad de importación: {config.label}
        </span>
      </div>
      <ul className="space-y-1">
        {calidad.issues.map((issue, idx) => (
          <li key={idx} className="text-xs text-gray-600 dark:text-gray-400">
            <span className={clsx(
              'font-medium',
              issue.severidad === 'error' ? 'text-red-600 dark:text-red-400' : 'text-yellow-600 dark:text-yellow-400'
            )}>
              [{issue.severidad}]
            </span>{' '}
            {issue.descripcion}
            {issue.accion && (
              <span className="text-gray-500 dark:text-gray-500"> → {issue.accion}</span>
            )}
            {issue.resuelto && (
              <CheckCircle className="inline h-3 w-3 ml-1 text-green-500" />
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

// Panel de resumen de calidad con links directos
function ResumenCalidad({
  articulos,
  soloIssues,
  onToggle
}: {
  articulos: ArticuloDivision[]
  soloIssues: boolean
  onToggle: () => void
}) {
  const stats = useMemo(() => {
    const conError = articulos.filter(a => a.calidad?.estatus === 'con_error')
    const corregidas = articulos.filter(a => a.calidad?.estatus === 'corregida')
    const ok = articulos.filter(a => !a.calidad)
    return { conError, corregidas, ok, total: articulos.length }
  }, [articulos])

  // Si no hay issues, no mostrar el panel
  if (stats.conError.length === 0 && stats.corregidas.length === 0) {
    return null
  }

  return (
    <div className="mb-8 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-2">
          <Filter className="h-4 w-4" />
          Resumen de Calidad de Importación
        </h3>
        <button
          onClick={onToggle}
          className={clsx(
            'flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
            soloIssues
              ? 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'
              : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-400 hover:bg-gray-300 dark:hover:bg-gray-600'
          )}
        >
          {soloIssues ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
          {soloIssues ? 'Mostrando solo issues' : 'Mostrar solo issues'}
        </button>
      </div>

      {/* Contadores */}
      <div className="flex gap-4 mb-4 text-sm">
        <span className="text-green-600 dark:text-green-400">
          <CheckCircle className="inline h-4 w-4 mr-1" />
          {stats.ok.length} OK
        </span>
        <span className="text-yellow-600 dark:text-yellow-400">
          <AlertTriangle className="inline h-4 w-4 mr-1" />
          {stats.corregidas.length} corregidas
        </span>
        <span className="text-red-600 dark:text-red-400">
          <XCircle className="inline h-4 w-4 mr-1" />
          {stats.conError.length} con errores
        </span>
      </div>

      {/* Links directos a reglas con errores */}
      {stats.conError.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-red-600 dark:text-red-400 mb-2">
            Reglas con errores pendientes:
          </p>
          <div className="flex flex-wrap gap-2">
            {stats.conError.map(art => (
              <a
                key={art.id}
                href={`#art-${art.numero_raw}`}
                className="inline-flex items-center px-2 py-1 text-xs bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300 rounded hover:bg-red-200 dark:hover:bg-red-800 transition-colors"
              >
                {art.numero_raw}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Links a reglas corregidas */}
      {stats.corregidas.length > 0 && (
        <div>
          <p className="text-xs font-medium text-yellow-600 dark:text-yellow-400 mb-2">
            Reglas corregidas en segunda pasada:
          </p>
          <div className="flex flex-wrap gap-2">
            {stats.corregidas.map(art => (
              <a
                key={art.id}
                href={`#art-${art.numero_raw}`}
                className="inline-flex items-center px-2 py-1 text-xs bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300 rounded hover:bg-yellow-200 dark:hover:bg-yellow-800 transition-colors"
              >
                {art.numero_raw}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Panel de verificación de integridad (reglas faltantes)
function VerificacionPanel({
  verificacion,
  capitulo
}: {
  verificacion: VerificacionDivisionSimple
  capitulo: string
}) {
  if (!verificacion.faltantes || verificacion.faltantes === 0) {
    return null
  }

  const porcentaje = verificacion.porcentaje_completo ?? 100
  const isWarning = porcentaje >= 80 && porcentaje < 100
  const isError = porcentaje < 80

  return (
    <div className={clsx(
      'mb-8 p-4 rounded-lg border',
      isError
        ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
        : isWarning
          ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800'
          : 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700'
    )}>
      <div className="flex items-center justify-between mb-3">
        <h3 className={clsx(
          'text-sm font-semibold flex items-center gap-2',
          isError
            ? 'text-red-700 dark:text-red-300'
            : isWarning
              ? 'text-amber-700 dark:text-amber-300'
              : 'text-gray-700 dark:text-gray-300'
        )}>
          <FileQuestion className="h-4 w-4" />
          Verificación de Integridad
        </h3>
        <span className={clsx(
          'text-sm font-medium px-2 py-0.5 rounded',
          isError
            ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
            : isWarning
              ? 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300'
              : 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
        )}>
          {porcentaje}%
        </span>
      </div>

      <div className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        {verificacion.total_actual} de {verificacion.total_esperado} reglas
        {verificacion.faltantes > 0 && (
          <span className="text-red-600 dark:text-red-400 font-medium ml-1">
            ({verificacion.faltantes} faltantes)
          </span>
        )}
      </div>

      {verificacion.numeros_faltantes && verificacion.numeros_faltantes.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
            Reglas no encontradas en el documento:
          </p>
          <div className="flex flex-wrap gap-2">
            {verificacion.numeros_faltantes.map(num => (
              <span
                key={num}
                className="inline-flex items-center px-2 py-1 text-xs bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300 rounded"
              >
                {capitulo}.{num}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function DivisionView() {
  const { ley, numero } = useParams<{ ley: string; numero: string }>()
  const location = useLocation()
  const [soloIssues, setSoloIssues] = useState(false)

  // Extraer tipo de la URL: /RMF2025/capitulo/1.9 → capitulo
  const tipo = useMemo(() => {
    const parts = location.pathname.split('/')
    // parts = ['', 'RMF2025', 'capitulo', '1.9']
    return parts[2] || null
  }, [location.pathname])

  // Buscar división por tipo+numero (estable, no depende de IDs)
  const { data: info, isLoading: loadingInfo } = useDivisionPorTipoNumero(ley || null, tipo, numero || null)
  const divId = info?.id || null
  const { data: articulos, isLoading: loadingArticulos } = useArticulosDivision(divId)
  const { data: verificacion } = useVerificacionDivision(divId)

  const isLoading = loadingInfo || loadingArticulos
  const esRegla = info?.ley_tipo === 'resolucion'
  const tipoContenido = esRegla ? 'regla' : 'articulo'

  // Filtrar artículos según el toggle
  const articulosFiltrados = useMemo(() => {
    if (!articulos) return []
    if (!soloIssues) return articulos
    return articulos.filter(a => a.calidad)
  }, [articulos, soloIssues])

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl animate-pulse space-y-4">
        <div className="h-6 w-48 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="h-10 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="mt-8 space-y-6">
          {[1, 2, 3].map(i => (
            <div key={i} className="space-y-2">
              <div className="h-6 w-32 rounded bg-gray-200 dark:bg-gray-700" />
              <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
              <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
              <div className="h-4 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!info || !articulos) {
    return (
      <div className="py-12 text-center">
        <BookOpen className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
        <h2 className="mt-4 text-2xl font-bold text-gray-900 dark:text-white">
          División no encontrada
        </h2>
        <Link to="/" className="btn-primary mt-4 inline-flex">
          Volver al inicio
        </Link>
      </div>
    )
  }

  // Parsear path_texto para breadcrumbs
  const partes = info.path_texto?.split(' > ') || []

  return (
    <div className="mx-auto max-w-4xl prose-legal">
      {/* Breadcrumbs */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm flex-wrap">
          <li>
            <Link
              to="/"
              className="flex items-center gap-1 text-gray-500 hover:text-primary-600 dark:hover:text-primary-400"
            >
              <Home className="h-4 w-4" />
              <span>Inicio</span>
            </Link>
          </li>
          <ChevronRight className="h-4 w-4 text-gray-400" />
          <li>
            <Link
              to={`/${info.ley_codigo}`}
              className={clsx(
                'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium hover:opacity-80',
                info.ley_tipo === 'resolucion'
                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'
                  : info.ley_tipo === 'ley'
                    ? 'bg-primary-100 text-primary-800 dark:bg-primary-900 dark:text-primary-200'
                    : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
              )}
            >
              {info.ley_codigo}
            </Link>
          </li>
          {partes.map((parte, idx) => (
            <li key={idx} className="flex items-center gap-2">
              <ChevronRight className="h-4 w-4 text-gray-400" />
              <span className={idx === partes.length - 1 ? 'font-medium text-gray-900 dark:text-white' : 'text-gray-500'}>
                {parte}
              </span>
            </li>
          ))}
        </ol>
      </nav>

      {/* Header */}
      <div className="mb-8">
        <p className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">
          {info.div_tipo} {info.numero}
        </p>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          {info.nombre || `${info.div_tipo} ${info.numero}`}
        </h1>
        <p className="mt-2 text-gray-500">
          {info.total_articulos} {esRegla ? 'reglas' : 'artículos'}
        </p>
      </div>

      {/* Panel de verificación de integridad (reglas faltantes) */}
      {verificacion && info.numero && (
        <VerificacionPanel
          verificacion={verificacion}
          capitulo={info.numero}
        />
      )}

      {/* Panel de resumen de calidad (solo para RMF) */}
      {esRegla && articulos && (
        <ResumenCalidad
          articulos={articulos}
          soloIssues={soloIssues}
          onToggle={() => setSoloIssues(!soloIssues)}
        />
      )}

      {/* Artículos */}
      <div className="space-y-8">
        {articulosFiltrados.map((art) => (
          <article
            key={art.id}
            id={`art-${art.numero_raw}`}
            className="scroll-mt-20"
          >
            {/* Header del artículo */}
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                <Link
                  to={`/${ley}/${tipoContenido}/${art.numero_raw}`}
                  className="inline-flex items-center gap-2 group"
                >
                  <h2 className="text-xl font-bold text-primary-600 dark:text-primary-400 group-hover:text-primary-700 dark:group-hover:text-primary-300">
                    {esRegla ? 'Regla' : 'Artículo'} {art.numero_raw}
                  </h2>
                  <ExternalLink className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
                {art.titulo && (
                  <p className="text-lg font-semibold text-gray-800 dark:text-gray-200 mt-1 italic">
                    {art.titulo}
                  </p>
                )}
                {art.es_transitorio && (
                  <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                    Transitorio
                  </span>
                )}
              </div>
            </div>

            {/* Contenido */}
            <div className="prose prose-gray prose-legal max-w-none dark:prose-invert">
              <ArticleContent articuloId={art.id} contenido={art.contenido} />
            </div>

            {/* Reformas */}
            {art.reformas && (
              <div className="mt-4 text-sm text-gray-500 dark:text-gray-400 italic">
                Reformas: {art.reformas}
              </div>
            )}

            {/* Referencias legales expandibles (RMF) */}
            {art.referencias && (
              <ReferenciasList referencias={art.referencias} />
            )}

            {/* Calidad de importación (solo si hay issues) */}
            {art.calidad && <CalidadBadge calidad={art.calidad} />}

            {/* Separador */}
            <hr className="mt-8 border-gray-200 dark:border-gray-700" />
          </article>
        ))}
      </div>

      {/* Navegación al final */}
      <div className="mt-12 flex justify-center">
        <Link
          to={`/${info.ley_codigo}`}
          className="btn-secondary"
        >
          Volver al índice de {info.ley_codigo}
        </Link>
      </div>
    </div>
  )
}
