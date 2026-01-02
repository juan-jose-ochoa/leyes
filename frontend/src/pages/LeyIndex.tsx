import { useState, useMemo, useCallback } from 'react'
import { useParams, useLocation, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { BookOpen, ChevronRight, ChevronDown, FileText, Home, ChevronsUpDown, ChevronsDownUp, ToggleLeft, ToggleRight, ExternalLink } from 'lucide-react'
import { useEstructuraLey, useLeyes } from '@/hooks/useArticle'
import type { Division } from '@/lib/api'
import clsx from 'clsx'

// División extendida con secciones hijas
interface DivisionConEstado extends Division {
  secciones?: DivisionConEstado[]  // Secciones hijas (solo para capítulos)
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

function agruparPorTitulo(divisiones: Division[]): GrupoTitulo[] {
  const grupos: GrupoTitulo[] = []
  let grupoActual: GrupoTitulo | null = null

  // Filtrar divisiones con contenido
  const todasDivisiones: DivisionConEstado[] = divisiones
    .filter((div) => div.total_articulos > 0 || div.primer_articulo)
    .sort((a, b) => compararNumeros(a.numero, b.numero))

  // Crear mapa de divisiones por id para encontrar padres
  const divisionesById = new Map<number, DivisionConEstado>()
  for (const div of todasDivisiones) {
    if (typeof div.id === 'number') {
      divisionesById.set(div.id, div)
    }
  }

  // Separar secciones de otras divisiones
  const secciones = todasDivisiones.filter(d => d.tipo === 'seccion')
  const noSecciones = todasDivisiones.filter(d => d.tipo !== 'seccion')

  // Asignar secciones a sus capítulos padre
  for (const seccion of secciones) {
    if (seccion.padre_id && typeof seccion.padre_id === 'number') {
      const capitulo = divisionesById.get(seccion.padre_id)
      if (capitulo && capitulo.tipo === 'capitulo') {
        if (!capitulo.secciones) capitulo.secciones = []
        capitulo.secciones.push(seccion)
      }
    }
  }

  for (const div of noSecciones) {
    if (div.tipo === 'titulo') {
      // Nuevo grupo de título
      if (grupoActual) {
        grupos.push(grupoActual)
      }
      grupoActual = { titulo: div, hijos: [] }
    } else {
      // Es capítulo o regla de título 1 (secciones ya están anidadas)
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

export default function LeyIndex() {
  const { ley } = useParams<{ ley: string }>()
  const location = useLocation()
  const { data: estructura, isLoading, error } = useEstructuraLey(ley ?? null)
  const { data: leyes } = useLeyes()

  // Estado para controlar expansión de títulos
  const [expandedTitles, setExpandedTitles] = useState<Set<number>>(new Set())
  const [accordionMode, setAccordionMode] = useState(false)

  const leyInfo = leyes?.find(l => l.codigo === ley)

  // Agrupar por títulos (memoizado)
  const grupos = useMemo(() => {
    if (!estructura) return []
    return agruparPorTitulo(estructura)
  }, [estructura])

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

  // SEO
  const seoTitle = leyInfo
    ? `${ley} - ${leyInfo.nombre} | LeyesMX`
    : `${ley} | LeyesMX`
  const seoDescription = leyInfo
    ? `Índice completo de ${leyInfo.nombre}. Consulta todos los artículos, títulos y capítulos.`
    : `Índice de ${ley}. Consulta la estructura completa de la ley.`

  return (
    <div className="mx-auto max-w-4xl">
      <Helmet>
        <title>{seoTitle}</title>
        <link rel="canonical" href={`https://leyesfiscalesmexico.com${location.pathname}`} />
        <meta name="description" content={seoDescription} />
        <meta property="og:title" content={seoTitle} />
        <meta property="og:description" content={seoDescription} />
      </Helmet>

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
        <span
          className={clsx(
            'inline-flex items-center px-3 py-1 rounded-lg text-sm font-bold text-white mb-2',
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
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          {leyInfo?.nombre || ley}
        </h1>
        {leyInfo && (
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500">
            <span>{leyInfo.total_articulos} {esResolucion ? 'reglas' : 'artículos'}</span>
            {leyInfo.ultima_reforma_dof && (
              <span>Última reforma: {leyInfo.ultima_reforma_dof.split('-').reverse().join('/')}</span>
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
  expandido: boolean
  onToggle: () => void
}

function GrupoTituloItem({ grupo, ley, tipoContenido, expandido, onToggle }: GrupoTituloItemProps) {
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
          />
        ))}
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
}

function DivisionItem({ division, ley, tipoContenido, parentPath, isNested }: DivisionItemProps) {
  const tipoLabel = division.tipo.charAt(0).toUpperCase() + division.tipo.slice(1)
  const esSeccion = division.tipo === 'seccion'

  // Construir path jerárquico completo
  const divisionPath = parentPath
    ? `${parentPath}/${division.tipo}/${division.numero}`
    : `${division.tipo}/${division.numero}`

  // Contenido del item (usado tanto para capítulos como secciones)
  const itemContent = (
    <Link
      to={`/${ley}/${divisionPath}`}
      className={clsx(
        'flex items-center gap-4 p-4 transition-colors',
        esSeccion
          ? 'hover:bg-indigo-50 dark:hover:bg-indigo-900/20'
          : 'hover:bg-gray-50 dark:hover:bg-gray-800/50',
        !isNested && !esSeccion && 'rounded-lg border border-gray-200 dark:border-gray-700'
      )}
    >
      {/* Icono */}
      <div className={clsx(
        'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
        esSeccion
          ? 'bg-indigo-100 text-indigo-600 dark:bg-indigo-900/50 dark:text-indigo-400'
          : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
      )}>
        <FileText className="h-5 w-5" />
      </div>

      {/* Contenido */}
      <div className="flex-1 min-w-0">
        <span className={clsx(
          'text-xs font-medium uppercase',
          esSeccion ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-500 dark:text-gray-400'
        )}>
          {tipoLabel} {division.numero}
        </span>
        <h3 className="font-medium text-gray-900 dark:text-white truncate">
          {division.nombre || `${tipoLabel} ${division.numero}`}
        </h3>
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

      <ChevronRight className={clsx(
        'h-5 w-5',
        esSeccion ? 'text-indigo-300 dark:text-indigo-700' : 'text-gray-300 dark:text-gray-600'
      )} />
    </Link>
  )

  // Si es un capítulo con secciones, renderizar las secciones anidadas
  if (division.secciones && division.secciones.length > 0) {
    return (
      <div>
        {itemContent}
        {/* Secciones anidadas con indentación */}
        <div className="ml-6 border-l-2 border-indigo-200 dark:border-indigo-800">
          {division.secciones.map((seccion) => (
            <DivisionItem
              key={seccion.id}
              division={seccion}
              ley={ley}
              tipoContenido={tipoContenido}
              parentPath={divisionPath}
              isNested={true}
            />
          ))}
        </div>
      </div>
    )
  }

  return itemContent
}
