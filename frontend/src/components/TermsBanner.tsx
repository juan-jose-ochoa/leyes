import { useState, useEffect } from 'react'
import { Scale } from 'lucide-react'

const STORAGE_KEY = 'leyesmx-terms-accepted'

export default function TermsBanner() {
  const [accepted, setAccepted] = useState(true) // true inicial para evitar flash

  useEffect(() => {
    setAccepted(localStorage.getItem(STORAGE_KEY) === '1')
  }, [])

  // Agregar padding al body cuando el banner está visible
  useEffect(() => {
    if (!accepted) {
      document.body.style.paddingBottom = '120px'
    } else {
      document.body.style.paddingBottom = ''
    }
    return () => {
      document.body.style.paddingBottom = ''
    }
  }, [accepted])

  const handleAccept = () => {
    localStorage.setItem(STORAGE_KEY, '1')
    setAccepted(true)
  }

  if (accepted) return null

  return (
    <div className="fixed bottom-0 inset-x-0 z-50 p-4 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 shadow-lg">
      <div className="container mx-auto max-w-4xl flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <Scale className="h-6 w-6 flex-shrink-0 text-primary-600 hidden sm:block" />
        <p className="flex-1 text-sm text-gray-600 dark:text-gray-400">
          <strong className="text-gray-900 dark:text-white">Condiciones de uso:</strong>{' '}
          Este sitio es una compilación no oficial de leyes mexicanas con fines de consulta.
          El contenido puede contener errores o estar desactualizado.
          Para efectos legales, siempre consulte las fuentes oficiales.
          Al continuar navegando, acepta que el uso de esta información es bajo su propia responsabilidad.
        </p>
        <button
          onClick={handleAccept}
          className="flex-shrink-0 px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 transition-colors"
        >
          Entendido
        </button>
      </div>
    </div>
  )
}
