import { useState, useCallback, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Scale, BookOpen, Search as SearchIcon, Zap } from 'lucide-react'
import SearchBar from '@/components/SearchBar'
import ResultList from '@/components/ResultList'
import ArticlePanel from '@/components/ArticlePanel'
import { useSearch } from '@/hooks/useSearch'
import { useLeyes } from '@/hooks/useArticle'
import type { SearchResult } from '@/lib/api'

export default function Home() {
  const [searchParams, setSearchParams] = useSearchParams()
  const urlQuery = searchParams.get('q') || ''

  const [query, setQuery] = useState(urlQuery)
  const [selectedLeyes, setSelectedLeyes] = useState<string[]>([])
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
    selectedLeyes.length > 0 ? selectedLeyes : undefined
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

  return (
    <div className="space-y-8">
      {/* Hero section - solo visible antes de buscar */}
      {!hasSearched && (
        <div className="py-12 text-center">
          <div className="mb-6 flex justify-center">
            <div className="rounded-2xl bg-primary-100 p-4 dark:bg-primary-900/30">
              <Scale className="h-16 w-16 text-primary-600 dark:text-primary-400" />
            </div>
          </div>
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white sm:text-5xl">
            Busca en las leyes
            <span className="block text-primary-600">fiscales y laborales</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-gray-600 dark:text-gray-400">
            Encuentra rapidamente articulos del CFF, LISR, LIVA, LFT y mas.
            Busqueda inteligente con referencias cruzadas.
          </p>
        </div>
      )}

      {/* Barra de busqueda */}
      <SearchBar
        value={query}
        onChange={setQuery}
        onSearch={handleSearch}
        selectedLeyes={selectedLeyes}
        onLeyesChange={setSelectedLeyes}
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

      {/* Stats y features - solo visible antes de buscar */}
      {!hasSearched && leyes && (
        <div className="mt-16">
          {/* Stats */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={<BookOpen className="h-6 w-6" />}
              label="Leyes"
              value={leyes.filter((l) => l.tipo === 'ley').length}
            />
            <StatCard
              icon={<BookOpen className="h-6 w-6" />}
              label="Reglamentos"
              value={leyes.filter((l) => l.tipo === 'reglamento').length}
            />
            <StatCard
              icon={<SearchIcon className="h-6 w-6" />}
              label="Articulos"
              value={leyes.reduce((sum, l) => sum + l.total_articulos, 0)}
            />
            <StatCard
              icon={<Zap className="h-6 w-6" />}
              label="Busqueda FTS"
              value="Activa"
            />
          </div>

          {/* Lista de leyes disponibles */}
          <div className="mt-12">
            <h2 className="mb-6 text-center text-2xl font-bold text-gray-900 dark:text-white">
              Leyes disponibles
            </h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {leyes.map((ley) => (
                <button
                  key={ley.codigo}
                  onClick={() => {
                    setSelectedLeyes([ley.codigo])
                    setQuery('')
                    setSearchParams({})
                  }}
                  className="card text-left transition-all hover:border-primary-300 hover:shadow-md dark:hover:border-primary-700"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-lg text-sm font-bold text-white ${
                        ley.tipo === 'ley' ? 'bg-primary-600' : 'bg-blue-600'
                      }`}
                    >
                      {ley.codigo}
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="truncate font-medium text-gray-900 dark:text-white">
                        {ley.nombre}
                      </h3>
                      <p className="text-sm text-gray-500">
                        {ley.total_articulos} articulos
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string | number
}) {
  return (
    <div className="card flex items-center gap-4">
      <div className="rounded-lg bg-primary-100 p-2 text-primary-600 dark:bg-primary-900/30 dark:text-primary-400">
        {icon}
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  )
}
