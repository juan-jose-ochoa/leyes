import { useState, useCallback, useEffect, useMemo } from 'react'
import { useSearchParams, useLocation, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { Scale, ChevronRight } from 'lucide-react'
import clsx from 'clsx'
import SearchBar from '@/components/SearchBar'
import ResultList from '@/components/ResultList'
import ArticlePanel from '@/components/ArticlePanel'
import { useSearch } from '@/hooks/useSearch'
import { useLeyes } from '@/hooks/useArticle'
import type { SearchResult, LeyTipo, Ley } from '@/lib/api'
import { LEY_BASE, CATEGORIA, NOMBRE_DISPLAY, CATEGORIA_INFO, type Categoria } from '@/lib/leyesConfig'

// Ley con reglamentos anidados y nombre para mostrar
interface LeyConReglamentos extends Ley {
  reglamentos: Ley[]
  displayName: string
}

// Grupo de leyes por categoría
interface GrupoCategoria {
  categoria: Categoria
  leyes: LeyConReglamentos[]
}

// Agrupa leyes por categoría con reglamentos anidados
function agruparLeyes(leyes: Ley[]): GrupoCategoria[] {
  // 1. Separar leyes principales de reglamentos
  const reglamentosPorBase = new Map<string, Ley[]>()
  const leyesPrincipales: Ley[] = []

  for (const ley of leyes) {
    const leyBase = LEY_BASE[ley.codigo]
    if (leyBase) {
      const arr = reglamentosPorBase.get(leyBase) || []
      arr.push(ley)
      reglamentosPorBase.set(leyBase, arr)
    } else {
      leyesPrincipales.push(ley)
    }
  }

  // 2. Agrupar por categoría
  const porCategoria = new Map<Categoria, LeyConReglamentos[]>()

  for (const ley of leyesPrincipales) {
    const cat = CATEGORIA[ley.codigo] || 'fiscal'
    const leyConRegs: LeyConReglamentos = {
      ...ley,
      reglamentos: reglamentosPorBase.get(ley.codigo) || [],
      displayName: NOMBRE_DISPLAY[ley.codigo] || ley.nombre_corto || ley.codigo,
    }

    const arr = porCategoria.get(cat) || []
    arr.push(leyConRegs)
    porCategoria.set(cat, arr)
  }

  // 3. Ordenar y retornar
  const orden: Categoria[] = ['fiscal', 'laboral', 'constitucional']
  return orden
    .filter(cat => porCategoria.has(cat))
    .map(cat => ({
      categoria: cat,
      leyes: porCategoria.get(cat)!,
    }))
}

export default function Home() {
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const urlQuery = searchParams.get('q') || ''

  const [query, setQuery] = useState(urlQuery)
  const [selectedLeyes, setSelectedLeyes] = useState<string[]>([])
  const [selectedTipos, setSelectedTipos] = useState<LeyTipo[]>([])
  const [selectedArticle, setSelectedArticle] = useState<{ ley: string; numero: string; id: number } | null>(null)
  const { data: leyes } = useLeyes()

  // Sincronizar query con URL al cargar
  useEffect(() => {
    if (urlQuery && urlQuery !== query) {
      setQuery(urlQuery)
    }
  }, [urlQuery])

  const { data: results, isLoading, isFetching } = useSearch(
    urlQuery,
    selectedLeyes.length > 0 ? selectedLeyes : undefined,
    selectedTipos.length > 0 ? selectedTipos : undefined
  )

  const handleSearch = useCallback((q: string) => {
    // Actualizar URL con el query
    if (q) {
      setSearchParams({ q })
    } else {
      setSearchParams({})
    }
    setSelectedArticle(null)
  }, [setSearchParams])

  const handleSelectArticle = useCallback((result: SearchResult) => {
    setSelectedArticle({
      ley: result.ley,
      numero: result.numero_raw,
      id: result.id
    })
  }, [])

  const handleNavigateArticle = useCallback((numero: string) => {
    if (selectedArticle) {
      setSelectedArticle({
        ...selectedArticle,
        numero
      })
    }
  }, [selectedArticle])

  const hasSearched = urlQuery.length > 0

  // SEO dinámico según búsqueda
  const seoTitle = hasSearched
    ? `"${urlQuery}" - Búsqueda en LeyesMX`
    : 'LeyesMX - Leyes Fiscales y Laborales de México'
  const seoDescription = hasSearched
    ? `Resultados de búsqueda para "${urlQuery}" en leyes fiscales y laborales mexicanas.`
    : 'Encuentra cualquier artículo en segundos. Consulta leyes fiscales y laborales mexicanas sin buscar en PDFs.'

  return (
    <div className="space-y-8">
      <Helmet>
        <title>{seoTitle}</title>
        <link rel="canonical" href={`https://leyesfiscalesmexico.com${location.pathname}${location.search}`} />
        <meta name="description" content={seoDescription} />
        <meta property="og:title" content={seoTitle} />
        <meta property="og:description" content={seoDescription} />
      </Helmet>

      {/* Hero section - solo visible antes de buscar */}
      {!hasSearched && (
        <div className="py-12 text-center">
          <div className="mb-6 flex justify-center">
            <div className="rounded-2xl bg-primary-100 p-4 dark:bg-primary-900/30">
              <Scale className="h-16 w-16 text-primary-600 dark:text-primary-400" />
            </div>
          </div>
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white sm:text-5xl">
            Leyes fiscales y laborales
            <span className="block text-primary-600">sin buscar en PDFs</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-gray-600 dark:text-gray-400">
            Encuentra cualquier artículo en segundos. Navega fácilmente por la estructura de cada ley.
          </p>
          {leyes && (
            <p className="mt-4 text-sm text-gray-400">
              {leyes.length} leyes y reglamentos · {leyes.reduce((sum, l) => sum + l.total_articulos, 0).toLocaleString()} artículos
            </p>
          )}
        </div>
      )}

      {/* Barra de busqueda */}
      <SearchBar
        value={query}
        onChange={setQuery}
        onSearch={handleSearch}
        selectedLeyes={selectedLeyes}
        onLeyesChange={setSelectedLeyes}
        selectedTipos={selectedTipos}
        onTiposChange={setSelectedTipos}
        isLoading={isFetching}
      />

      {/* Resultados de busqueda con split panel en desktop */}
      {hasSearched && (
        <div className="mt-8">
          {/* Layout: móvil = solo lista, desktop = split panel */}
          <div className="lg:grid lg:grid-cols-12 lg:gap-6">
            {/* Panel izquierdo: Resultados */}
            <div className={selectedArticle ? 'lg:col-span-5 xl:col-span-4' : 'lg:col-span-12'}>
              {/* En móvil: sin onSelect (usa Link). En desktop: con onSelect */}
              <div className="lg:hidden">
                <ResultList results={results || []} isLoading={isLoading} />
              </div>
              <div className="hidden lg:block lg:max-h-[calc(100vh-200px)] lg:overflow-y-auto lg:pr-2">
                <ResultList
                  results={results || []}
                  isLoading={isLoading}
                  selectedId={selectedArticle?.id}
                  onSelect={handleSelectArticle}
                />
              </div>
            </div>

            {/* Panel derecho: Artículo (solo desktop) */}
            {selectedArticle && (
              <div className="hidden lg:block lg:col-span-7 xl:col-span-8">
                <div className="sticky top-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg max-h-[calc(100vh-200px)] overflow-hidden">
                  <ArticlePanel
                    ley={selectedArticle.ley}
                    numero={selectedArticle.numero}
                    onClose={() => setSelectedArticle(null)}
                    onNavigate={handleNavigateArticle}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Lista de leyes agrupadas por categoría - solo visible antes de buscar */}
      {!hasSearched && leyes && (
        <LeyesPorCategoria leyes={leyes} />
      )}
    </div>
  )
}

// Componente para mostrar leyes agrupadas por categoría
function LeyesPorCategoria({ leyes }: { leyes: Ley[] }) {
  const grupos = useMemo(() => agruparLeyes(leyes), [leyes])

  return (
    <div className="mt-12 space-y-10">
      {grupos.map((grupo) => {
        const info = CATEGORIA_INFO[grupo.categoria]
        return (
          <div key={grupo.categoria}>
            {/* Header de categoría */}
            <div className="mb-4 flex items-center gap-3">
              <div className={clsx('h-1 w-8 rounded-full', info.color)} />
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                {info.nombre}
              </h2>
            </div>

            {/* Grid de leyes */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {grupo.leyes.map((ley) => (
                <LeyCard key={ley.codigo} ley={ley} categoriaColor={info.color} />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// Card individual de ley con reglamentos anidados
function LeyCard({ ley, categoriaColor }: { ley: LeyConReglamentos; categoriaColor: string }) {
  return (
    <div className="card overflow-hidden p-0">
      {/* Ley principal */}
      <Link
        to={`/${ley.codigo}`}
        className="block p-4 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50"
      >
        <div className="flex items-start gap-3">
          <div
            className={clsx(
              'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-sm font-bold text-white',
              categoriaColor
            )}
          >
            {ley.codigo.length > 4 ? ley.codigo.slice(0, 3) : ley.codigo}
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-gray-900 dark:text-white">
              {ley.displayName}
            </h3>
            <p className="mt-0.5 text-xs text-gray-500 line-clamp-2">
              {ley.nombre}
            </p>
            <div className="mt-2 flex items-center gap-3 text-xs text-gray-400">
              <span>{ley.total_articulos} {ley.tipo === 'resolucion' ? 'reglas' : 'arts.'}</span>
              {ley.ultima_reforma_dof && (
                <span>{ley.ultima_reforma_dof.split('-').reverse().join('/')}</span>
              )}
            </div>
          </div>
          <ChevronRight className="h-5 w-5 shrink-0 text-gray-300 dark:text-gray-600" />
        </div>
      </Link>

      {/* Reglamentos anidados */}
      {ley.reglamentos.length > 0 && (
        <div className="border-t border-gray-100 bg-gray-50/50 dark:border-gray-800 dark:bg-gray-800/30">
          {ley.reglamentos.map((reg) => (
            <Link
              key={reg.codigo}
              to={`/${reg.codigo}`}
              className="flex items-center gap-2 px-4 py-2 text-sm transition-colors hover:bg-gray-100 dark:hover:bg-gray-700/50"
            >
              <div className="h-1.5 w-1.5 rounded-full bg-gray-400" />
              <span className="font-medium text-gray-700 dark:text-gray-300">
                {NOMBRE_DISPLAY[reg.codigo] || reg.nombre_corto || reg.codigo}
              </span>
              <span className="text-xs text-gray-400">
                {reg.total_articulos} arts.
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
