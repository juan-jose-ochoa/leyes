import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { BookOpen, ChevronRight, ChevronDown, FileText, Home } from 'lucide-react'
import { useEstructuraLey, useLeyes } from '@/hooks/useArticle'
import type { Division } from '@/lib/api'
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

export default function LeyIndex() {
  const { ley } = useParams<{ ley: string }>()
  const { data: estructura, isLoading, error } = useEstructuraLey(ley ?? null)
  const { data: leyes } = useLeyes()

  const leyInfo = leyes?.find(l => l.codigo === ley)

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
        <div className="flex items-center gap-3 mb-2">
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

      {/* Estructura agrupada por títulos */}
      <div className="space-y-4">
        {grupos.map((grupo, idx) => (
          <GrupoTituloItem
            key={grupo.titulo?.id ?? `grupo-${idx}`}
            grupo={grupo}
            ley={ley!}
            tipoContenido={tipoContenido}
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
}

function GrupoTituloItem({ grupo, ley, tipoContenido }: GrupoTituloItemProps) {
  const [expandido, setExpandido] = useState(true)
  const { titulo, hijos } = grupo

  // Si no hay título, mostrar los hijos directamente
  if (!titulo) {
    return (
      <div className="space-y-2">
        {hijos.map((div) => (
          <DivisionItem key={div.id} division={div} ley={ley} tipoContenido={tipoContenido} />
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
            <DivisionItem key={div.id} division={div} ley={ley} tipoContenido={tipoContenido} isNested />
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
}

function DivisionItem({ division, ley, tipoContenido, isNested }: DivisionItemProps) {
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
        </div>
        <h3 className="font-medium text-gray-900 dark:text-white truncate">
          {division.nombre || `${tipoLabel} ${division.numero}`}
        </h3>
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
