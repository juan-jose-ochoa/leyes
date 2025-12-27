import { useState, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { BookOpen, ChevronRight, ChevronDown, FileText, Home, CheckCircle, AlertTriangle, XCircle, Activity, Download } from 'lucide-react'
import { useEstructuraLey, useLeyes, useVerificacionLey, useVerificacionIndice, useComparacionReglasIndice, useComparacionDivisionesIndice } from '@/hooks/useArticle'
import type { Division, VerificacionDivision, VerificacionStatus, VerificacionIndice, ComparacionRegla, ComparacionDivision } from '@/lib/api'
import clsx from 'clsx'

// Agrupar divisiones por título
interface GrupoTitulo {
  titulo: Division | null
  hijos: Division[]
}

function agruparPorTitulo(divisiones: Division[]): GrupoTitulo[] {
  const grupos: GrupoTitulo[] = []
  let grupoActual: GrupoTitulo | null = null

  // Filtrar y deduplicar
  const divsFiltradas = divisiones
    .filter((div) => div.total_articulos > 0 || div.primer_articulo)
    .reduce((acc, div) => {
      const key = `${div.tipo}-${div.numero}`
      const existing = acc.find(d => `${d.tipo}-${d.numero}` === key)
      if (!existing) {
        acc.push(div)
      } else if (div.total_articulos > existing.total_articulos) {
        const idx = acc.indexOf(existing)
        acc[idx] = div
      }
      return acc
    }, [] as Division[])

  for (const div of divsFiltradas) {
    if (div.tipo === 'titulo') {
      // Nuevo grupo de título
      if (grupoActual) {
        grupos.push(grupoActual)
      }
      grupoActual = { titulo: div, hijos: [] }
    } else {
      // Es capítulo o sección
      if (grupoActual) {
        grupoActual.hijos.push(div)
      } else {
        // No hay título padre, crear grupo sin título
        grupos.push({ titulo: null, hijos: [div] })
      }
    }
  }

  // No olvidar el último grupo
  if (grupoActual) {
    grupos.push(grupoActual)
  }

  return grupos
}

// Función para exportar verificación a CSV
function exportarVerificacionCSV(verificacion: VerificacionDivision[], ley: string) {
  const headers = ['Capítulo', 'Nombre', 'Actual', 'Esperado', 'Faltantes', 'Porcentaje', 'Status', 'Números Faltantes']
  const rows = verificacion
    .filter(v => v.total_actual > 0)
    .map(v => [
      v.numero,
      `"${(v.nombre || '').replace(/"/g, '""')}"`,
      v.total_actual,
      v.total_esperado,
      v.faltantes,
      v.porcentaje_completo?.toFixed(1) || '100',
      v.status,
      v.numeros_faltantes?.join(';') || ''
    ])

  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)

  const a = document.createElement('a')
  a.href = url
  a.download = `verificacion-${ley}-${new Date().toISOString().split('T')[0]}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export default function LeyIndex() {
  const { ley } = useParams<{ ley: string }>()
  const { data: estructura, isLoading, error } = useEstructuraLey(ley ?? null)
  const { data: leyes } = useLeyes()
  const [showVerificacion, setShowVerificacion] = useState(false)
  const { data: verificacion } = useVerificacionLey(showVerificacion ? ley ?? null : null)
  const { data: verificacionIndice } = useVerificacionIndice(showVerificacion ? ley ?? null : null)
  const { data: reglasFaltantes } = useComparacionReglasIndice(showVerificacion ? ley ?? null : null)
  const { data: divisionesFaltantes } = useComparacionDivisionesIndice(showVerificacion ? ley ?? null : null)

  const leyInfo = leyes?.find(l => l.codigo === ley)

  // Crear mapa de verificación por division_id
  const verificacionMap = useMemo(() => {
    if (!verificacion) return new Map<number, VerificacionDivision>()
    return new Map(verificacion.map(v => [v.division_id, v]))
  }, [verificacion])

  // Calcular resumen de verificación
  const resumenVerificacion = useMemo(() => {
    if (!verificacion) return null
    const conArticulos = verificacion.filter(v => v.total_actual > 0)
    return {
      total: conArticulos.length,
      ok: conArticulos.filter(v => v.status === 'ok').length,
      warning: conArticulos.filter(v => v.status === 'warning').length,
      error: conArticulos.filter(v => v.status === 'error').length,
      faltantes: conArticulos.reduce((sum, v) => sum + (v.faltantes || 0), 0),
    }
  }, [verificacion])

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl animate-pulse space-y-4">
        <div className="h-8 w-64 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="h-4 w-96 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="mt-8 space-y-3">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-16 rounded-lg bg-gray-200 dark:bg-gray-700" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !estructura) {
    return (
      <div className="py-12 text-center">
        <BookOpen className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
        <h2 className="mt-4 text-2xl font-bold text-gray-900 dark:text-white">
          Ley no encontrada
        </h2>
        <p className="mt-2 text-gray-500">
          No se encontró la ley "{ley}".
        </p>
        <Link to="/" className="btn-primary mt-4 inline-flex">
          Volver al inicio
        </Link>
      </div>
    )
  }

  // Determinar tipo de contenido (articulo o regla)
  const esResolucion = leyInfo?.tipo === 'resolucion'
  const tipoContenido = esResolucion ? 'regla' : 'articulo'

  // Agrupar por títulos
  const grupos = agruparPorTitulo(estructura)

  return (
    <div className="mx-auto max-w-4xl">
      {/* Breadcrumbs */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm">
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
            <span className="font-medium text-gray-900 dark:text-white">{ley}</span>
          </li>
        </ol>
      </nav>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between gap-3 mb-2">
          <span
            className={clsx(
              'inline-flex items-center px-3 py-1 rounded-lg text-sm font-bold text-white',
              leyInfo?.tipo === 'resolucion'
                ? 'bg-amber-600'
                : leyInfo?.tipo === 'anexo'
                  ? 'bg-orange-600'
                  : leyInfo?.tipo === 'ley'
                    ? 'bg-primary-600'
                    : 'bg-blue-600'
            )}
          >
            {ley}
          </span>
          {/* Toggle de verificación - solo para resoluciones (RMF) */}
          {esResolucion && (
            <button
              onClick={() => setShowVerificacion(!showVerificacion)}
              className={clsx(
                'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                showVerificacion
                  ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700'
              )}
            >
              <Activity className="h-4 w-4" />
              Verificar integridad
            </button>
          )}
        </div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          {leyInfo?.nombre || ley}
        </h1>
        {leyInfo && (
          <p className="mt-2 text-gray-500">
            {leyInfo.total_articulos} {esResolucion ? 'reglas' : 'artículos'}
          </p>
        )}
      </div>

      {/* Panel de resumen de verificación */}
      {showVerificacion && resumenVerificacion && verificacion && (
        <div className="mb-6 p-4 rounded-lg bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-purple-900 dark:text-purple-100">
              Verificación de integridad
            </h3>
            <button
              onClick={() => exportarVerificacionCSV(verificacion, ley!)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-purple-200 text-purple-800 hover:bg-purple-300 dark:bg-purple-800 dark:text-purple-200 dark:hover:bg-purple-700 transition-colors"
            >
              <Download className="h-3.5 w-3.5" />
              Exportar CSV
            </button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <div>
                <div className="text-lg font-bold text-green-700 dark:text-green-400">{resumenVerificacion.ok}</div>
                <div className="text-xs text-gray-500">Completos</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              <div>
                <div className="text-lg font-bold text-amber-700 dark:text-amber-400">{resumenVerificacion.warning}</div>
                <div className="text-xs text-gray-500">Advertencias</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-red-500" />
              <div>
                <div className="text-lg font-bold text-red-700 dark:text-red-400">{resumenVerificacion.error}</div>
                <div className="text-xs text-gray-500">Con huecos</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-purple-500" />
              <div>
                <div className="text-lg font-bold text-purple-700 dark:text-purple-400">{resumenVerificacion.faltantes}</div>
                <div className="text-xs text-gray-500">Reglas faltantes</div>
              </div>
            </div>
          </div>

          {/* Lista detallada de capítulos con problemas */}
          {(resumenVerificacion.warning > 0 || resumenVerificacion.error > 0) && (
            <div className="border-t border-purple-200 dark:border-purple-700 pt-3 mt-3">
              <h4 className="text-xs font-medium text-purple-800 dark:text-purple-300 mb-2">
                Capítulos con huecos detectados:
              </h4>
              <div className="max-h-48 overflow-y-auto space-y-1.5">
                {verificacion
                  .filter(v => v.status === 'error' || v.status === 'warning')
                  .sort((a, b) => (a.faltantes || 0) - (b.faltantes || 0))
                  .reverse()
                  .map(v => (
                    <div
                      key={v.division_id}
                      className={clsx(
                        'flex items-start gap-2 p-2 rounded text-xs',
                        v.status === 'error' ? 'bg-red-100 dark:bg-red-900/30' : 'bg-amber-100 dark:bg-amber-900/30'
                      )}
                    >
                      <StatusIcon status={v.status} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-900 dark:text-white">
                            Cap. {v.numero}
                          </span>
                          <span className={clsx(
                            'px-1.5 py-0.5 rounded font-medium',
                            v.status === 'error' ? 'bg-red-200 text-red-800 dark:bg-red-800 dark:text-red-200' : 'bg-amber-200 text-amber-800 dark:bg-amber-800 dark:text-amber-200'
                          )}>
                            {v.porcentaje_completo?.toFixed(0)}%
                          </span>
                          <span className="text-gray-500 dark:text-gray-400">
                            ({v.total_actual}/{v.total_esperado} reglas)
                          </span>
                        </div>
                        {v.numeros_faltantes && v.numeros_faltantes.length > 0 && (
                          <p className="text-gray-600 dark:text-gray-400 mt-0.5 truncate">
                            Faltan: {v.numeros_faltantes.slice(0, 10).join(', ')}
                            {v.numeros_faltantes.length > 10 && ` (+${v.numeros_faltantes.length - 10} más)`}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Panel de verificación contra índice oficial del PDF */}
      {showVerificacion && verificacionIndice && verificacionIndice.length > 0 && (
        <VerificacionIndicePanel
          verificacionIndice={verificacionIndice}
          reglasFaltantes={reglasFaltantes?.filter(r => r.estado === 'faltante') || []}
          divisionesFaltantes={divisionesFaltantes?.filter(d => d.estado === 'faltante') || []}
        />
      )}

      {/* Estructura agrupada por títulos */}
      <div className="space-y-4">
        {grupos.map((grupo, idx) => (
          <GrupoTituloItem
            key={grupo.titulo?.id ?? `grupo-${idx}`}
            grupo={grupo}
            ley={ley!}
            tipoContenido={tipoContenido}
            showVerificacion={showVerificacion}
            verificacionMap={verificacionMap}
          />
        ))}
      </div>
    </div>
  )
}

interface GrupoTituloItemProps {
  grupo: GrupoTitulo
  ley: string
  tipoContenido: string
  showVerificacion: boolean
  verificacionMap: Map<number, VerificacionDivision>
}

function GrupoTituloItem({ grupo, ley, tipoContenido, showVerificacion, verificacionMap }: GrupoTituloItemProps) {
  const [expandido, setExpandido] = useState(true)
  const { titulo, hijos } = grupo

  // Si no hay título, mostrar los hijos directamente
  if (!titulo) {
    return (
      <div className="space-y-2">
        {hijos.map((div) => (
          <DivisionItem
            key={div.id}
            division={div}
            ley={ley}
            tipoContenido={tipoContenido}
            showVerificacion={showVerificacion}
            verificacion={verificacionMap.get(div.id)}
          />
        ))}
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Header del título */}
      <button
        onClick={() => setExpandido(!expandido)}
        className="w-full flex items-center gap-3 p-4 bg-primary-50 dark:bg-primary-900/20 hover:bg-primary-100 dark:hover:bg-primary-900/30 transition-colors"
      >
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary-600 text-white">
          <BookOpen className="h-5 w-5" />
        </div>

        <div className="flex-1 text-left">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-primary-600 dark:text-primary-400 uppercase">
              Título {titulo.numero}
            </span>
          </div>
          <h3 className="font-semibold text-gray-900 dark:text-white">
            {titulo.nombre}
          </h3>
        </div>

        <div className="text-right shrink-0 mr-2">
          <span className="text-sm font-medium text-gray-900 dark:text-white">
            {titulo.total_articulos}
          </span>
          <span className="text-xs text-gray-500 ml-1">
            {tipoContenido === 'regla' ? 'reglas' : 'arts.'}
          </span>
        </div>

        <ChevronDown
          className={clsx(
            'h-5 w-5 text-gray-400 transition-transform',
            expandido && 'rotate-180'
          )}
        />
      </button>

      {/* Capítulos dentro del título */}
      {expandido && hijos.length > 0 && (
        <div className="divide-y divide-gray-100 dark:divide-gray-800">
          {hijos.map((div) => (
            <DivisionItem
              key={div.id}
              division={div}
              ley={ley}
              tipoContenido={tipoContenido}
              isNested
              showVerificacion={showVerificacion}
              verificacion={verificacionMap.get(div.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface DivisionItemProps {
  division: Division
  ley: string
  tipoContenido: string
  isNested?: boolean
  showVerificacion?: boolean
  verificacion?: VerificacionDivision
}

// Panel de verificación contra índice oficial del PDF
interface VerificacionIndicePanelProps {
  verificacionIndice: VerificacionIndice[]
  reglasFaltantes: ComparacionRegla[]
  divisionesFaltantes: ComparacionDivision[]
}

function VerificacionIndicePanel({ verificacionIndice, reglasFaltantes, divisionesFaltantes }: VerificacionIndicePanelProps) {
  const [showDetails, setShowDetails] = useState(false)

  // Calcular totales
  const totalFaltantes = verificacionIndice.reduce((sum, v) => sum + v.faltantes, 0)
  const hayProblemas = totalFaltantes > 0

  // Nombres legibles para categorías
  const nombreCategoria: Record<string, string> = {
    titulo: 'Títulos',
    capitulo: 'Capítulos',
    seccion: 'Secciones',
    subseccion: 'Subsecciones',
    regla: 'Reglas',
  }

  return (
    <div className={clsx(
      'mb-6 p-4 rounded-lg border',
      hayProblemas
        ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
        : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
    )}>
      <div className="flex items-center justify-between mb-3">
        <h3 className={clsx(
          'text-sm font-semibold',
          hayProblemas ? 'text-red-900 dark:text-red-100' : 'text-green-900 dark:text-green-100'
        )}>
          Verificación contra índice oficial (PDF)
        </h3>
        {hayProblemas && (
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="text-xs font-medium text-red-700 dark:text-red-300 hover:underline"
          >
            {showDetails ? 'Ocultar detalles' : 'Ver detalles'}
          </button>
        )}
      </div>

      {/* Resumen por categoría */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-3">
        {verificacionIndice.map((v) => (
          <div
            key={v.categoria}
            className={clsx(
              'p-2 rounded text-center',
              v.faltantes > 0
                ? 'bg-red-100 dark:bg-red-900/30'
                : 'bg-green-100 dark:bg-green-900/30'
            )}
          >
            <div className="text-xs text-gray-600 dark:text-gray-400">
              {nombreCategoria[v.categoria] || v.categoria}
            </div>
            <div className="flex items-center justify-center gap-1 mt-1">
              <span className={clsx(
                'text-lg font-bold',
                v.faltantes > 0
                  ? 'text-red-700 dark:text-red-400'
                  : 'text-green-700 dark:text-green-400'
              )}>
                {v.total_importado}
              </span>
              <span className="text-xs text-gray-500">/{v.total_oficial}</span>
            </div>
            {v.faltantes > 0 && (
              <div className="text-xs text-red-600 dark:text-red-400 mt-0.5">
                -{v.faltantes} faltantes
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Detalles expandidos */}
      {showDetails && (
        <div className="border-t border-red-200 dark:border-red-700 pt-3 mt-3 space-y-3">
          {/* Títulos/Divisiones faltantes */}
          {divisionesFaltantes.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-red-800 dark:text-red-300 mb-2">
                Divisiones faltantes:
              </h4>
              <div className="max-h-32 overflow-y-auto space-y-1">
                {divisionesFaltantes.map((d, idx) => (
                  <div
                    key={`${d.tipo}-${d.numero}-${idx}`}
                    className="flex items-center gap-2 p-2 bg-red-100 dark:bg-red-900/30 rounded text-xs"
                  >
                    <XCircle className="h-3.5 w-3.5 text-red-500" />
                    <span className="font-medium text-gray-900 dark:text-white capitalize">
                      {d.tipo} {d.numero}
                    </span>
                    <span className="text-gray-600 dark:text-gray-400 truncate">
                      {d.nombre_oficial}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Reglas faltantes */}
          {reglasFaltantes.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-red-800 dark:text-red-300 mb-2">
                Reglas faltantes ({reglasFaltantes.length}):
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {reglasFaltantes.map((r) => (
                  <span
                    key={r.numero}
                    className="px-2 py-0.5 bg-red-200 text-red-800 dark:bg-red-800 dark:text-red-200 rounded text-xs font-medium"
                    title={r.pagina_pdf ? `Página ${r.pagina_pdf} del PDF` : undefined}
                  >
                    {r.numero}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Mensaje de éxito */}
      {!hayProblemas && (
        <div className="flex items-center gap-2 text-sm text-green-700 dark:text-green-400">
          <CheckCircle className="h-4 w-4" />
          <span>Todos los elementos del índice oficial están presentes</span>
        </div>
      )}
    </div>
  )
}

// Componente de indicador de estado
function StatusIcon({ status }: { status: VerificacionStatus }) {
  switch (status) {
    case 'ok':
      return <CheckCircle className="h-4 w-4 text-green-500" />
    case 'warning':
      return <AlertTriangle className="h-4 w-4 text-amber-500" />
    case 'error':
      return <XCircle className="h-4 w-4 text-red-500" />
    default:
      return null
  }
}

function DivisionItem({ division, ley, tipoContenido, isNested, showVerificacion, verificacion }: DivisionItemProps) {
  const tipoLabel = division.tipo.charAt(0).toUpperCase() + division.tipo.slice(1)

  return (
    <Link
      to={`/${ley}/division/${division.id}`}
      className={clsx(
        'flex items-center gap-4 p-4 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50',
        !isNested && 'rounded-lg border border-gray-200 dark:border-gray-700'
      )}
    >
      {/* Icono */}
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400">
        <FileText className="h-5 w-5" />
      </div>

      {/* Contenido */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
            {tipoLabel} {division.numero}
          </span>
          {/* Indicador de verificación */}
          {showVerificacion && verificacion && verificacion.status !== 'empty' && (
            <span
              className={clsx(
                'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium',
                verificacion.status === 'ok' && 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
                verificacion.status === 'warning' && 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
                verificacion.status === 'error' && 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
              )}
              title={verificacion.faltantes > 0 ? `Faltan ${verificacion.faltantes} reglas` : 'Completo'}
            >
              <StatusIcon status={verificacion.status} />
              {verificacion.porcentaje_completo?.toFixed(0)}%
            </span>
          )}
        </div>
        <h3 className="font-medium text-gray-900 dark:text-white truncate">
          {division.nombre || `${tipoLabel} ${division.numero}`}
        </h3>
        {/* Detalle de verificación */}
        {showVerificacion && verificacion && verificacion.faltantes > 0 && (
          <p className="text-xs text-red-600 dark:text-red-400 mt-0.5">
            {verificacion.total_actual}/{verificacion.total_esperado} reglas (faltan {verificacion.faltantes})
          </p>
        )}
      </div>

      {/* Contador de artículos */}
      {division.total_articulos > 0 && (
        <div className="text-right shrink-0">
          <span className="text-sm font-medium text-gray-900 dark:text-white">
            {division.total_articulos}
          </span>
          <span className="text-xs text-gray-500 ml-1">
            {tipoContenido === 'regla' ? 'reglas' : 'arts.'}
          </span>
        </div>
      )}

      <ChevronRight className="h-5 w-5 text-gray-300 dark:text-gray-600" />
    </Link>
  )
}
