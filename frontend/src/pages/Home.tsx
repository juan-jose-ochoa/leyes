import { useState, useCallback } from 'react'
import { Scale, BookOpen, Search as SearchIcon, Zap } from 'lucide-react'
import SearchBar from '@/components/SearchBar'
import ResultList from '@/components/ResultList'
import { useSearch } from '@/hooks/useSearch'
import { useLeyes } from '@/hooks/useArticle'

export default function Home() {
  const [query, setQuery] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedLeyes, setSelectedLeyes] = useState<string[]>([])
  const { data: leyes } = useLeyes()

  const { data: results, isLoading, isFetching } = useSearch(
    searchQuery,
    selectedLeyes.length > 0 ? selectedLeyes : undefined
  )

  const handleSearch = useCallback((q: string) => {
    setSearchQuery(q)
  }, [])

  const hasSearched = searchQuery.length > 0

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

      {/* Resultados de busqueda */}
      {hasSearched && (
        <div className="mt-8">
          <ResultList results={results || []} isLoading={isLoading} />
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
                    setSearchQuery('')
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
