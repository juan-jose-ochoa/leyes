import { useState, useEffect, useCallback } from 'react'

export type ViewMode = 'text' | 'split' | 'pdf'

const STORAGE_KEY = 'leyesmx-view-mode'

export function useViewMode(defaultMode: ViewMode = 'text') {
  const [mode, setModeState] = useState<ViewMode>(() => {
    if (typeof window === 'undefined') return defaultMode
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'text' || stored === 'split' || stored === 'pdf') {
      return stored
    }
    return defaultMode
  })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, mode)
  }, [mode])

  const setMode = useCallback((newMode: ViewMode) => {
    setModeState(newMode)
  }, [])

  // Atajos de teclado
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignorar si está en un input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }

      switch (e.key.toLowerCase()) {
        case 't':
          setMode('text')
          break
        case 's':
          setMode('split')
          break
        case 'p':
          setMode('pdf')
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [setMode])

  return { mode, setMode }
}
