import { useState, useEffect, useRef, useCallback } from 'react'
import { Search, X, Loader2 } from 'lucide-react'
import { useSugerencias } from '@/hooks/useSearch'
import { useLeyes } from '@/hooks/useArticle'
import clsx from 'clsx'

interface SearchBarProps {
  value: string
  onChange: (value: string) => void
  onSearch: (query: string) => void
  selectedLeyes: string[]
  onLeyesChange: (leyes: string[]) => void
  isLoading?: boolean
}

export default function SearchBar({
  value,
  onChange,
  onSearch,
  selectedLeyes,
  onLeyesChange,
  isLoading,
}: SearchBarProps) {
  const [showSugerencias, setShowSugerencias] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const { data: sugerencias } = useSugerencias(value)
  const { data: leyes } = useLeyes()

  // Keyboard shortcut: "/" para enfocar búsqueda
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault()
        inputRef.current?.focus()
      }
      if (e.key === 'Escape') {
        setShowSugerencias(false)
        inputRef.current?.blur()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      if (value.trim()) {
        onSearch(value.trim())
        setShowSugerencias(false)
      }
    },
    [value, onSearch]
  )

  const handleSugerenciaClick = (termino: string) => {
    onChange(termino)
    onSearch(termino)
    setShowSugerencias(false)
  }

  const toggleLey = (codigo: string) => {
    if (selectedLeyes.includes(codigo)) {
      onLeyesChange(selectedLeyes.filter((l) => l !== codigo))
    } else {
      onLeyesChange([...selectedLeyes, codigo])
    }
  }

  return (
    <div className="relative w-full max-w-3xl mx-auto">
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={(e) => {
              onChange(e.target.value)
              setShowSugerencias(true)
            }}
            onFocus={() => setShowSugerencias(true)}
            placeholder="Buscar en leyes fiscales y laborales..."
            className="w-full rounded-xl border-2 border-gray-200 bg-white py-4 pl-12 pr-24 text-lg placeholder-gray-400 transition-colors focus:border-primary-500 focus:outline-none focus:ring-4 focus:ring-primary-500/20 dark:border-gray-700 dark:bg-gray-800 dark:placeholder-gray-500"
          />
          <div className="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-2">
            {value && (
              <button
                type="button"
                onClick={() => {
                  onChange('')
                  inputRef.current?.focus()
                }}
                className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                <X className="h-4 w-4" />
              </button>
            )}
            <button
              type="submit"
              disabled={!value.trim() || isLoading}
              className="btn-primary px-4 py-2"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                'Buscar'
              )}
            </button>
          </div>
        </div>

        <div className="mt-2 flex items-center gap-2 text-sm text-gray-500">
          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-1 rounded-lg px-2 py-1 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            Filtrar por ley
            {selectedLeyes.length > 0 && (
              <span className="ml-1 rounded-full bg-primary-100 px-2 py-0.5 text-xs font-medium text-primary-700 dark:bg-primary-900 dark:text-primary-300">
                {selectedLeyes.length}
              </span>
            )}
          </button>
          <span className="hidden sm:inline text-gray-400">
            Presiona <kbd className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs dark:bg-gray-700">/</kbd> para buscar
          </span>
        </div>
      </form>

      {/* Filtros por ley */}
      {showFilters && leyes && (
        <div className="mt-2 flex flex-wrap gap-2 rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800">
          {leyes.map((ley) => (
            <button
              key={ley.codigo}
              onClick={() => toggleLey(ley.codigo)}
              className={clsx(
                'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                selectedLeyes.includes(ley.codigo)
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
              )}
              title={ley.nombre}
            >
              {ley.codigo}
            </button>
          ))}
          {selectedLeyes.length > 0 && (
            <button
              onClick={() => onLeyesChange([])}
              className="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            >
              Limpiar filtros
            </button>
          )}
        </div>
      )}

      {/* Sugerencias de autocompletado */}
      {showSugerencias && sugerencias && sugerencias.length > 0 && (
        <div className="absolute z-10 mt-2 w-full rounded-lg border border-gray-200 bg-white py-2 shadow-lg dark:border-gray-700 dark:bg-gray-800">
          {sugerencias.map((s) => (
            <button
              key={s.termino}
              onClick={() => handleSugerenciaClick(s.termino)}
              className="flex w-full items-center justify-between px-4 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              <span>{s.termino}</span>
              <span className="text-xs text-gray-400">{s.frecuencia} busquedas</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
