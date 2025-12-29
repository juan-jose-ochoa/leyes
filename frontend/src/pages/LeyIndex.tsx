import { useState, useMemo, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { BookOpen, ChevronRight, ChevronDown, FileText, Home, CheckCircle, AlertTriangle, XCircle, Activity, Download, ChevronsUpDown, ChevronsDownUp, ToggleLeft, ToggleRight, ExternalLink } from 'lucide-react'
import { useEstructuraLey, useLeyes, useVerificacionLey, useVerificacionIndice, useComparacionReglasIndice, useComparacionDivisionesIndice } from '@/hooks/useArticle'
import type { Division, VerificacionDivision, VerificacionStatus, VerificacionIndice, ComparacionRegla, ComparacionDivision } from '@/lib/api'
import clsx from 'clsx'

// División extendida que puede ser un placeholder (faltante)
interface DivisionConEstado extends Omit<Division, 'id'> {
  id: number | string  // string para placeholders (ej: "placeholder-titulo-6")
  esFaltante?: boolean
}

// Agrupar divisiones por título
interface GrupoTitulo {
  titulo: DivisionConEstado | null
  hijos: DivisionConEstado[]
}

// Función para ordenar numéricamente por número de división (1, 2, 3, ... 10, 11, 12)
function parseNumero(numero: string | null): number[] {
  if (!numero) return [Infinity]
  // Soporta números como "1", "2.1", "2.1.1", etc.
  return numero.split('.').map(n => parseInt(n, 10) || 0)
}

function compararNumeros(a: string | null, b: string | null): number {
  const partsA = parseNumero(a)
  const partsB = parseNumero(b)
  for (let i = 0; i < Math.max(partsA.length, partsB.length); i++) {
    const numA = partsA[i] ?? 0
    const numB = partsB[i] ?? 0
    if (numA !== numB) return numA - numB
  }
  return 0
}

function agruparPorTitulo(
  divisiones: Division[],
  divisionesFaltantes?: ComparacionDivision[],
  reglasFaltantes?: ComparacionRegla[]
): GrupoTitulo[] {
  const grupos: GrupoTitulo[] = []
  let grupoActual: GrupoTitulo | null = null

  // Convertir divisiones existentes a DivisionConEstado
  // Usar id como clave única (no tipo-numero que se repite entre títulos)
  const divsExistentes: DivisionConEstado[] = divisiones
    .filter((div) => div.total_articulos > 0 || div.primer_articulo)
    .map(div => ({ ...div, esFaltante: false }))

  // Crear set de divisiones existentes para evitar duplicados
  const existentesSet = new Set(divsExistentes.map(d => `${d.tipo}-${d.numero}`))

  // Convertir divisiones faltantes a DivisionConEstado (placeholders)
  const divsFaltantes: DivisionConEstado[] = (divisionesFaltantes || [])
    .filter(d => d.estado === 'faltante' && !existentesSet.has(`${d.tipo}-${d.numero}`))
    .map(d => ({
      id: `placeholder-${d.tipo}-${d.numero}`,
      tipo: d.tipo,
      numero: d.numero,
      nombre: d.nombre_oficial,
      path_texto: null,
      nivel: d.tipo === 'titulo' ? 1 : d.tipo === 'capitulo' ? 2 : d.tipo === 'seccion' ? 3 : 4,
      total_articulos: 0,
      primer_articulo: null,
      ultimo_articulo: null,
      esFaltante: true,
    }))

  // Crear placeholders para reglas faltantes de dos niveles (X.Y)
  // Estas son reglas que van directamente bajo un título sin capítulo intermedio
  // Ejemplo: Título 1 tiene reglas 1.1, 1.2... en lugar de capítulos
  // El patrón detecta números como X.Y donde ambos son 1-2 dígitos
  const reglasDosNivelesFaltantes: DivisionConEstado[] = (reglasFaltantes || [])
    .filter(r => r.estado === 'faltante' && /^\d{1,2}\.\d{1,2}$/.test(r.numero))
    .map(r => ({
      id: `placeholder-regla-${r.numero}`,
      tipo: 'regla',
      numero: r.numero,
      nombre: null,  // Las reglas no tienen nombre en el índice
      path_texto: null,
      nivel: 2,
      total_articulos: 0,
      primer_articulo: null,
      ultimo_articulo: null,
      esFaltante: true,
    }))

  // Combinar y ordenar todas las divisiones
  const todasDivisiones = [...divsExistentes, ...divsFaltantes, ...reglasDosNivelesFaltantes]
    .sort((a, b) => compararNumeros(a.numero, b.numero))

  for (const div of todasDivisiones) {
    if (div.tipo === 'titulo') {
      // Nuevo grupo de título
      if (grupoActual) {
        grupos.push(grupoActual)
      }
      grupoActual = { titulo: div, hijos: [] }
    } else {
      // Es capítulo, sección o regla de título 1
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
  // Siempre cargar reglas faltantes para placeholders de Título 1
  const { data: reglasFaltantes } = useComparacionReglasIndice(ley ?? null)
  // Siempre cargar divisiones faltantes para mostrar placeholders
  const { data: divisionesFaltantes } = useComparacionDivisionesIndice(ley ?? null)

  // Estado para controlar expansión de títulos
  const [expandedTitles, setExpandedTitles] = useState<Set<number>>(new Set())
  const [accordionMode, setAccordionMode] = useState(false)

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

  // Agrupar por títulos (memoizado), incluyendo placeholders para faltantes
  const grupos = useMemo(() => {
    if (!estructura) return []
    return agruparPorTitulo(estructura, divisionesFaltantes || undefined, reglasFaltantes || undefined)
  }, [estructura, divisionesFaltantes, reglasFaltantes])

  // Funciones de control de expansión
  const expandAll = useCallback(() => {
    const allIds = new Set(
      grupos
        .map(g => g.titulo?.id)
        .filter((id): id is number => typeof id === 'number')
    )
    setExpandedTitles(allIds)
  }, [grupos])

  const collapseAll = useCallback(() => {
    setExpandedTitles(new Set())
  }, [])

  const toggleTitle = useCallback((titleId: number) => {
    setExpandedTitles(prev => {
      const next = new Set(prev)
      if (next.has(titleId)) {
        next.delete(titleId)
      } else {
        if (accordionMode) {
          // En modo acordeón, solo un título puede estar expandido
          next.clear()
        }
        next.add(titleId)
      }
      return next
    })
  }, [accordionMode])

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
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500">
            <span>{leyInfo.total_articulos} {esResolucion ? 'reglas' : 'artículos'}</span>
            {leyInfo.ultima_reforma && (
              <span>Última reforma: {new Date(leyInfo.ultima_reforma).toLocaleDateString('es-MX')}</span>
            )}
            {leyInfo.url_fuente && (
              <a
                href={leyInfo.url_fuente}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
              >
                Fuente oficial
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>
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

      {/* Controles de expansión */}
      {grupos.length > 1 && (
        <div className="flex items-center justify-end gap-2 mb-4">
          <button
            onClick={expandedTitles.size > 0 ? collapseAll : expandAll}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700 transition-colors"
            title={expandedTitles.size > 0 ? 'Colapsar todos los títulos' : 'Expandir todos los títulos'}
          >
            {expandedTitles.size > 0 ? <ChevronsDownUp className="h-4 w-4" /> : <ChevronsUpDown className="h-4 w-4" />}
            {expandedTitles.size > 0 ? 'Colapsar' : 'Expandir'}
          </button>
          <button
            onClick={() => setAccordionMode(!accordionMode)}
            className={clsx(
              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
              accordionMode
                ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700'
            )}
            title={accordionMode ? 'Modo acordeón activado: solo un título a la vez' : 'Activar modo acordeón'}
          >
            {accordionMode ? <ToggleRight className="h-4 w-4" /> : <ToggleLeft className="h-4 w-4" />}
            Acordeón
          </button>
        </div>
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
            expandido={grupo.titulo && typeof grupo.titulo.id === 'number' ? expandedTitles.has(grupo.titulo.id) : false}
            onToggle={() => grupo.titulo && typeof grupo.titulo.id === 'number' && toggleTitle(grupo.titulo.id)}
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
  expandido: boolean
  onToggle: () => void
}

function GrupoTituloItem({ grupo, ley, tipoContenido, showVerificacion, verificacionMap, expandido, onToggle }: GrupoTituloItemProps) {
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
            verificacion={typeof div.id === 'number' ? verificacionMap.get(div.id) : undefined}
          />
        ))}
      </div>
    )
  }

  // Título placeholder (faltante)
  if (titulo.esFaltante) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 dark:border-gray-600 overflow-hidden opacity-60">
        <div className="w-full flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-800/50">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gray-400 dark:bg-gray-600 text-white">
            <BookOpen className="h-5 w-5" />
          </div>

          <div className="flex-1 text-left">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Título {titulo.numero}
              </span>
              <span className="text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                No importado
              </span>
            </div>
            <h3 className="font-semibold text-gray-500 dark:text-gray-400">
              {titulo.nombre || '(Sin nombre)'}
            </h3>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Header del título */}
      <button
        onClick={onToggle}
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
          <div className="text-sm font-medium text-gray-900 dark:text-white">
            {titulo.total_articulos} {tipoContenido === 'regla' ? 'reglas' : 'arts.'}
          </div>
          {titulo.primer_articulo && titulo.ultimo_articulo && (
            <div className="text-xs text-gray-500">
              {titulo.primer_articulo} – {titulo.ultimo_articulo}
            </div>
          )}
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
              parentPath={`titulo/${titulo.numero}`}
              isNested
              showVerificacion={showVerificacion}
              verificacion={typeof div.id === 'number' ? verificacionMap.get(div.id) : undefined}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface DivisionItemProps {
  division: DivisionConEstado
  ley: string
  tipoContenido: string
  parentPath?: string  // Path jerárquico del padre: "titulo/PRIMERO"
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
  const totalExtras = verificacionIndice.reduce((sum, v) => sum + v.extras, 0)
  const totalVirtuales = verificacionIndice.reduce((sum, v) => sum + (v.virtuales || 0), 0)
  // Solo faltantes y extras reales son problemas, los virtuales son esperados
  const hayProblemas = totalFaltantes > 0 || totalExtras > 0

  // Divisiones extras (en DB pero no en índice oficial) - excluyendo virtuales
  const divisionesExtras = divisionesFaltantes.filter(d => d.estado === 'extra')
  // Divisiones virtuales (capítulos generados para reglas de 2 niveles)
  const divisionesVirtuales = divisionesFaltantes.filter(d => d.estado === 'virtual')

  // Nombres legibles para categorías
  const nombreCategoria: Record<string, string> = {
    titulo: 'Títulos',
    capitulo: 'Capítulos',
    seccion: 'Secciones',
    subseccion: 'Subsecciones',
    regla: 'Reglas',
  }

  const soloExtras = totalExtras > 0 && totalFaltantes === 0

  return (
    <div className={clsx(
      'mb-6 p-4 rounded-lg border',
      totalFaltantes > 0
        ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
        : soloExtras
          ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800'
          : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
    )}>
      <div className="flex items-center justify-between mb-3">
        <h3 className={clsx(
          'text-sm font-semibold',
          totalFaltantes > 0 ? 'text-red-900 dark:text-red-100' :
          soloExtras ? 'text-amber-900 dark:text-amber-100' :
          'text-green-900 dark:text-green-100'
        )}>
          Verificación contra índice oficial (PDF)
        </h3>
        {hayProblemas && (
          <button
            onClick={() => setShowDetails(!showDetails)}
            className={clsx(
              'text-xs font-medium hover:underline',
              totalFaltantes > 0 ? 'text-red-700 dark:text-red-300' : 'text-amber-700 dark:text-amber-300'
            )}
          >
            {showDetails ? 'Ocultar detalles' : 'Ver detalles'}
          </button>
        )}
      </div>

      {/* Resumen por categoría */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-3">
        {verificacionIndice.map((v) => {
          const tieneError = v.faltantes > 0
          const tieneExtras = v.extras > 0
          const tieneVirtuales = (v.virtuales || 0) > 0

          return (
            <div
              key={v.categoria}
              className={clsx(
                'p-2 rounded text-center',
                tieneError ? 'bg-red-100 dark:bg-red-900/30' :
                tieneExtras ? 'bg-amber-100 dark:bg-amber-900/30' :
                'bg-green-100 dark:bg-green-900/30'
              )}
            >
              <div className="text-xs text-gray-600 dark:text-gray-400">
                {nombreCategoria[v.categoria] || v.categoria}
              </div>
              <div className="flex items-center justify-center gap-1 mt-1">
                <span className={clsx(
                  'text-lg font-bold',
                  tieneError ? 'text-red-700 dark:text-red-400' :
                  tieneExtras ? 'text-amber-700 dark:text-amber-400' :
                  'text-green-700 dark:text-green-400'
                )}>
                  {v.total_oficial}
                </span>
                <span className="text-xs text-gray-500">oficiales</span>
              </div>
              {tieneError && (
                <div className="text-xs text-red-600 dark:text-red-400 mt-0.5">
                  -{v.faltantes} faltantes
                </div>
              )}
              {tieneExtras && (
                <div className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                  +{v.extras} extras
                </div>
              )}
              {tieneVirtuales && (
                <div className="text-xs text-blue-600 dark:text-blue-400 mt-0.5">
                  +{v.virtuales} virtuales
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Detalles expandidos */}
      {showDetails && (
        <div className={clsx(
          'border-t pt-3 mt-3 space-y-3',
          totalFaltantes > 0 ? 'border-red-200 dark:border-red-700' : 'border-amber-200 dark:border-amber-700'
        )}>
          {/* Divisiones faltantes */}
          {divisionesFaltantes.filter(d => d.estado === 'faltante').length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-red-800 dark:text-red-300 mb-2">
                Divisiones faltantes:
              </h4>
              <div className="max-h-32 overflow-y-auto space-y-1">
                {divisionesFaltantes.filter(d => d.estado === 'faltante').map((d, idx) => (
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

          {/* Divisiones extras (no están en índice oficial) */}
          {divisionesExtras.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-amber-800 dark:text-amber-300 mb-2">
                Divisiones extras (no en índice oficial): {divisionesExtras.length}
              </h4>
              <div className="max-h-32 overflow-y-auto space-y-1">
                {divisionesExtras.slice(0, 20).map((d, idx) => (
                  <div
                    key={`extra-${d.tipo}-${d.numero}-${idx}`}
                    className="flex items-center gap-2 p-2 bg-amber-100 dark:bg-amber-900/30 rounded text-xs"
                  >
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                    <span className="font-medium text-gray-900 dark:text-white capitalize">
                      {d.tipo} {d.numero}
                    </span>
                    <span className="text-gray-600 dark:text-gray-400 truncate">
                      {d.nombre_importado}
                    </span>
                  </div>
                ))}
                {divisionesExtras.length > 20 && (
                  <div className="text-xs text-amber-600 dark:text-amber-400 py-1">
                    ... y {divisionesExtras.length - 20} más
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Divisiones virtuales (capítulos generados para reglas de 2 niveles) */}
          {divisionesVirtuales.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-blue-800 dark:text-blue-300 mb-2">
                Capítulos virtuales (generados para reglas X.Y): {divisionesVirtuales.length}
              </h4>
              <div className="max-h-32 overflow-y-auto space-y-1">
                {divisionesVirtuales.slice(0, 20).map((d, idx) => (
                  <div
                    key={`virtual-${d.tipo}-${d.numero}-${idx}`}
                    className="flex items-center gap-2 p-2 bg-blue-100 dark:bg-blue-900/30 rounded text-xs"
                  >
                    <FileText className="h-3.5 w-3.5 text-blue-500" />
                    <span className="font-medium text-gray-900 dark:text-white capitalize">
                      {d.tipo} {d.numero}
                    </span>
                    <span className="text-gray-600 dark:text-gray-400 truncate">
                      {d.nombre_importado}
                    </span>
                  </div>
                ))}
                {divisionesVirtuales.length > 20 && (
                  <div className="text-xs text-blue-600 dark:text-blue-400 py-1">
                    ... y {divisionesVirtuales.length - 20} más
                  </div>
                )}
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
          <span>
            Todos los elementos del índice oficial están presentes
            {totalVirtuales > 0 && ` (+${totalVirtuales} capítulos virtuales generados)`}
          </span>
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

function DivisionItem({ division, ley, tipoContenido, parentPath, isNested, showVerificacion, verificacion }: DivisionItemProps) {
  const tipoLabel = division.tipo.charAt(0).toUpperCase() + division.tipo.slice(1)

  // Construir path jerárquico completo
  const divisionPath = parentPath
    ? `${parentPath}/${division.tipo}/${division.numero}`
    : `${division.tipo}/${division.numero}`

  // Placeholder para división faltante
  if (division.esFaltante) {
    return (
      <div
        className={clsx(
          'flex items-center gap-4 p-4 opacity-50',
          !isNested && 'rounded-lg border border-dashed border-gray-300 dark:border-gray-600'
        )}
      >
        {/* Icono */}
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gray-200 text-gray-400 dark:bg-gray-700 dark:text-gray-500">
          <FileText className="h-5 w-5" />
        </div>

        {/* Contenido */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase">
              {tipoLabel} {division.numero}
            </span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
              No importado
            </span>
          </div>
          <h3 className="font-medium text-gray-400 dark:text-gray-500 truncate">
            {division.nombre || `${tipoLabel} ${division.numero}`}
          </h3>
        </div>
      </div>
    )
  }

  return (
    <Link
      to={`/${ley}/${divisionPath}`}
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
          <div className="text-sm font-medium text-gray-900 dark:text-white">
            {division.total_articulos} {tipoContenido === 'regla' ? 'reglas' : 'arts.'}
          </div>
          {division.primer_articulo && division.ultimo_articulo && (
            <div className="text-xs text-gray-500">
              {division.primer_articulo} – {division.ultimo_articulo}
            </div>
          )}
        </div>
      )}

      <ChevronRight className="h-5 w-5 text-gray-300 dark:text-gray-600" />
    </Link>
  )
}
