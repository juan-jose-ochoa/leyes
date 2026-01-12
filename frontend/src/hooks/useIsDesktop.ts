import { useState, useEffect } from 'react'

/**
 * Detecta si es un dispositivo de escritorio (tiene mouse/hover).
 * Móviles táctiles retornan false incluso en pantalla grande.
 */
export function useIsDesktop(): boolean {
  const [isDesktop, setIsDesktop] = useState(() => {
    if (typeof window === 'undefined') return true
    return window.matchMedia('(hover: hover) and (pointer: fine)').matches
  })

  useEffect(() => {
    const mediaQuery = window.matchMedia('(hover: hover) and (pointer: fine)')
    const handler = (e: MediaQueryListEvent) => setIsDesktop(e.matches)

    mediaQuery.addEventListener('change', handler)
    return () => mediaQuery.removeEventListener('change', handler)
  }, [])

  return isDesktop
}
