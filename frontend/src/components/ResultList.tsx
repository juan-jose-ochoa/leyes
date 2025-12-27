import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, ChevronRight, ChevronDown, BookOpen } from 'lucide-react'
import DOMPurify from 'dompurify'
import type { SearchResult, LeyTipo } from '@/lib/api'
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
  resultados: SearchResult[]
}

const agruparPorLey = (results: SearchResult[]): GrupoLey[] => {
  const grupos: Record<string, GrupoLey> = {}

  for (const result of results) {
    if (!grupos[result.ley]) {
      grupos[result.ley] = {
        ley: result.ley,
        ley_nombre: result.ley_nombre,
        ley_tipo: result.ley_tipo,
        resultados: []
      }
    }
    grupos[result.ley].resultados.push(result)
  }

  // Ordenar por cantidad de resultados (más relevante primero)
  return Object.values(grupos).sort((a, b) => b.resultados.length - a.resultados.length)
}

interface ResultListProps {
  results: SearchResult[]
  isLoading?: boolean
  selectedId?: number | null
  onSelect?: (result: SearchResult) => void
}

export default function ResultList({ results, isLoading, selectedId, onSelect }: ResultListProps) {
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

  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-500">
        {results.length} resultado{results.length !== 1 ? 's' : ''} en {grupos.length} {grupos.length !== 1 ? 'documentos' : 'documento'}
      </p>

      {grupos.map((grupo) => (
        <GrupoResultados key={grupo.ley} grupo={grupo} selectedId={selectedId} onSelect={onSelect} />
      ))}
    </div>
  )
}

interface GrupoResultadosProps {
  grupo: GrupoLey
  selectedId?: number | null
  onSelect?: (result: SearchResult) => void
}

function GrupoResultados({ grupo, selectedId, onSelect }: GrupoResultadosProps) {
  const [expandido, setExpandido] = useState(true)
  const colorClase = grupo.ley_tipo === 'anexo'
    ? 'bg-orange-600'
    : grupo.ley_tipo === 'resolucion'
      ? 'bg-amber-600'
      : grupo.ley_tipo === 'ley'
        ? 'bg-primary-600'
        : 'bg-blue-600'

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
            {grupo.resultados.length} {grupo.resultados.length === 1 ? 'resultado' : 'resultados'}
          </p>
        </div>

        <ChevronDown
          className={clsx(
            'h-5 w-5 text-gray-400 transition-transform',
            expandido && 'rotate-180'
          )}
        />
      </button>

      {/* Resultados del grupo */}
      {expandido && (
        <div className="divide-y divide-gray-100 dark:divide-gray-800">
          {grupo.resultados.map((result) => (
            <ResultCard key={result.id} result={result} isSelected={result.id === selectedId} onSelect={onSelect} />
          ))}
        </div>
      )}
    </div>
  )
}

interface ResultCardProps {
  result: SearchResult
  isSelected?: boolean
  onSelect?: (result: SearchResult) => void
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
