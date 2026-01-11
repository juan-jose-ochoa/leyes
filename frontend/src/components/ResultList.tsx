import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, ChevronRight, ChevronDown, BookOpen, FolderOpen } from 'lucide-react'
import DOMPurify from 'dompurify'
import type {
  HybridSearchResult,
  ArticuloSearchResult,
  DivisionSearchResult,
  LeyTipo,
} from '@/lib/api'
import { isDivisionResult } from '@/lib/api'
import clsx from 'clsx'

// Sanitizar snippets: solo permitir <mark> para highlighting
const sanitizeSnippet = (html: string): string => {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['mark'],
    ALLOWED_ATTR: []
  })
}

// Extraer título descriptivo del contenido (primera oración significativa)
const extraerTitulo = (contenido: string, maxLength = 80): string => {
  if (!contenido) return ''

  // Limpiar y obtener primera oración
  const limpio = contenido.replace(/\s+/g, ' ').trim()
  const match = limpio.match(/^(.+?[.;:])/)

  if (match && match[1].length <= maxLength) {
    return match[1]
  }

  // Si no hay puntuación o es muy largo, cortar en maxLength
  if (limpio.length <= maxLength) return limpio

  const cortado = limpio.substring(0, maxLength)
  const ultimoEspacio = cortado.lastIndexOf(' ')
  return cortado.substring(0, ultimoEspacio) + '...'
}

// Agrupar resultados por ley
interface GrupoLey {
  ley: string
  ley_nombre: string
  ley_tipo: LeyTipo
  divisiones: DivisionSearchResult[]
  articulos: ArticuloSearchResult[]
}

const agruparPorLey = (results: HybridSearchResult[]): GrupoLey[] => {
  const grupos: Record<string, GrupoLey> = {}

  for (const result of results) {
    if (!grupos[result.ley]) {
      grupos[result.ley] = {
        ley: result.ley,
        ley_nombre: result.ley_nombre,
        ley_tipo: result.ley_tipo,
        divisiones: [],
        articulos: [],
      }
    }
    if (isDivisionResult(result)) {
      grupos[result.ley].divisiones.push(result)
    } else {
      grupos[result.ley].articulos.push(result)
    }
  }

  // Ordenar por total de resultados (divisiones + artículos)
  return Object.values(grupos).sort(
    (a, b) => (b.divisiones.length + b.articulos.length) - (a.divisiones.length + a.articulos.length)
  )
}

interface ResultListProps {
  results: HybridSearchResult[]
  isLoading?: boolean
  selectedId?: number | null
  selectedType?: 'articulo' | 'division' | null
  onSelect?: (result: HybridSearchResult) => void
}

export default function ResultList({ results, isLoading, selectedId, selectedType, onSelect }: ResultListProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="card animate-pulse">
            <div className="flex gap-4">
              <div className="h-10 w-10 rounded-lg bg-gray-200 dark:bg-gray-700" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-1/4 rounded bg-gray-200 dark:bg-gray-700" />
                <div className="h-3 w-1/2 rounded bg-gray-200 dark:bg-gray-700" />
                <div className="h-3 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <div className="py-12 text-center">
        <FileText className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
        <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-gray-100">
          No se encontraron resultados
        </h3>
        <p className="mt-2 text-gray-500">
          Intenta con otros términos o ajusta los filtros
        </p>
      </div>
    )
  }

  const grupos = agruparPorLey(results)
  const totalDivisiones = results.filter(isDivisionResult).length
  const totalArticulos = results.length - totalDivisiones

  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-500">
        {results.length} resultado{results.length !== 1 ? 's' : ''} en {grupos.length} {grupos.length !== 1 ? 'documentos' : 'documento'}
        {totalDivisiones > 0 && (
          <span className="ml-2">
            ({totalDivisiones} {totalDivisiones === 1 ? 'capítulo' : 'capítulos'}, {totalArticulos} {totalArticulos === 1 ? 'artículo' : 'artículos'})
          </span>
        )}
      </p>

      {grupos.map((grupo) => (
        <GrupoResultados
          key={grupo.ley}
          grupo={grupo}
          selectedId={selectedId}
          selectedType={selectedType}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}

interface GrupoResultadosProps {
  grupo: GrupoLey
  selectedId?: number | null
  selectedType?: 'articulo' | 'division' | null
  onSelect?: (result: HybridSearchResult) => void
}

function GrupoResultados({ grupo, selectedId, selectedType, onSelect }: GrupoResultadosProps) {
  const [expandido, setExpandido] = useState(true)
  const colorClase = grupo.ley_tipo === 'anexo'
    ? 'bg-orange-600'
    : grupo.ley_tipo === 'resolucion'
      ? 'bg-amber-600'
      : grupo.ley_tipo === 'ley'
        ? 'bg-primary-600'
        : 'bg-blue-600'

  const totalResultados = grupo.divisiones.length + grupo.articulos.length

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Header del grupo */}
      <button
        onClick={() => setExpandido(!expandido)}
        className="w-full flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      >
        <div
          className={clsx(
            'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-sm font-bold text-white',
            colorClase
          )}
        >
          <BookOpen className="h-5 w-5" />
        </div>

        <div className="flex-1 text-left">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-gray-900 dark:text-gray-100">
              {grupo.ley}
            </span>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {grupo.ley_nombre}
            </span>
          </div>
          <p className="text-sm text-gray-500">
            {totalResultados} {totalResultados === 1 ? 'resultado' : 'resultados'}
          </p>
        </div>

        <ChevronDown
          className={clsx(
            'h-5 w-5 text-gray-400 transition-transform',
            expandido && 'rotate-180'
          )}
        />
      </button>

      {/* Resultados del grupo: divisiones primero, luego artículos */}
      {expandido && (
        <div className="divide-y divide-gray-100 dark:divide-gray-800">
          {grupo.divisiones.map((result) => (
            <DivisionCard key={`div-${result.id}`} result={result} />
          ))}
          {grupo.articulos.map((result) => (
            <ResultCard
              key={`art-${result.id}`}
              result={result}
              isSelected={result.id === selectedId && selectedType === 'articulo'}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// Componente para resultados de división (capítulos)
// Las divisiones SIEMPRE navegan a su página (no usan panel lateral)
interface DivisionCardProps {
  result: DivisionSearchResult
}

function DivisionCard({ result }: DivisionCardProps) {
  // URL de navegación: /:ley/:div_path
  const url = `/${result.ley}/${result.div_path}`
  const tipoCapitalizado = result.div_tipo.charAt(0).toUpperCase() + result.div_tipo.slice(1)

  return (
    <Link
      to={url}
      className="block p-4 transition-colors group text-left w-full hover:bg-gray-50 dark:hover:bg-gray-800/50"
    >
      <div className="flex items-start gap-3">
        {/* Icono de división */}
        <div className="shrink-0 w-16 flex justify-end">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-100 dark:bg-indigo-900/30">
            <FolderOpen className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
          </div>
        </div>

        <div className="flex-1 min-w-0">
          {/* Tipo y número */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-indigo-600 dark:text-indigo-400">
              {tipoCapitalizado} {result.div_numero}
            </span>
            {result.total_articulos > 0 && (
              <span className="text-xs text-gray-400">
                ({result.total_articulos} {result.total_articulos === 1 ? 'artículo' : 'artículos'})
              </span>
            )}
          </div>

          {/* Nombre del capítulo */}
          {result.div_nombre && (
            <h4 className="font-medium text-gray-900 dark:text-gray-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400">
              {result.div_nombre}
            </h4>
          )}

          {/* Rango de artículos */}
          {result.rango_articulos && (
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {result.rango_articulos}
            </p>
          )}
        </div>

        {/* Flecha */}
        <ChevronRight className="h-5 w-5 text-gray-300 dark:text-gray-600 group-hover:text-indigo-500 shrink-0 mt-1" />
      </div>
    </Link>
  )
}

// Componente para resultados de artículo
interface ResultCardProps {
  result: ArticuloSearchResult
  isSelected?: boolean
  onSelect?: (result: HybridSearchResult) => void
}

function ResultCard({ result, isSelected, onSelect }: ResultCardProps) {
  const esRegla = result.tipo === 'regla'
  const esFicha = result.tipo === 'ficha'
  const esCriterio = result.tipo === 'criterio'
  const etiquetaTipo = esFicha ? 'Ficha' : esCriterio ? 'Criterio' : esRegla ? 'Regla' : 'Art.'
  const rutaTipo = esFicha ? 'ficha' : esCriterio ? 'criterio' : esRegla ? 'regla' : 'articulo'
  const titulo = extraerTitulo(result.contenido)

  const content = (
    <div className="flex items-start gap-3">
      {/* Número de artículo */}
      <div className="shrink-0 w-16 text-right">
        <span className="font-mono font-semibold text-primary-600 dark:text-primary-400 group-hover:text-primary-700 dark:group-hover:text-primary-300">
          {etiquetaTipo} {result.numero_raw}
        </span>
      </div>

      <div className="flex-1 min-w-0">
        {/* Título descriptivo */}
        <h4 className="font-medium text-gray-900 dark:text-gray-100 group-hover:text-primary-600 dark:group-hover:text-primary-400">
          {titulo}
        </h4>

        {/* Ubicación jerárquica */}
        {result.ubicacion && (
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            {result.ubicacion}
          </p>
        )}

        {/* Snippet con highlighting */}
        <p
          className="mt-2 text-sm text-gray-600 dark:text-gray-300 line-clamp-2"
          dangerouslySetInnerHTML={{ __html: sanitizeSnippet(result.snippet) }}
        />

        {/* Tags */}
        <div className="mt-2 flex items-center gap-2">
          {result.es_transitorio && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
              transitorio
            </span>
          )}
        </div>
      </div>

      {/* Flecha */}
      <ChevronRight className="h-5 w-5 text-gray-300 dark:text-gray-600 group-hover:text-primary-500 shrink-0 mt-1" />
    </div>
  )

  const baseClass = clsx(
    'block p-4 transition-colors group text-left w-full',
    isSelected
      ? 'bg-primary-50 dark:bg-primary-900/20 border-l-4 border-primary-500'
      : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'
  )

  // En desktop con onSelect, usar button. En móvil, usar Link.
  if (onSelect) {
    return (
      <button onClick={() => onSelect(result)} className={baseClass}>
        {content}
      </button>
    )
  }

  return (
    <Link to={`/${result.ley}/${rutaTipo}/${result.numero_raw}`} className={baseClass}>
      {content}
    </Link>
  )
}
