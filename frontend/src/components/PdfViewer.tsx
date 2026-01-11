import { useRef, useEffect } from 'react'
import { Viewer, Worker, SpecialZoomLevel } from '@react-pdf-viewer/core'
import { defaultLayoutPlugin } from '@react-pdf-viewer/default-layout'
import { AlertCircle, Loader2 } from 'lucide-react'

import '@react-pdf-viewer/core/lib/styles/index.css'
import '@react-pdf-viewer/default-layout/lib/styles/index.css'

interface PdfViewerProps {
  pdfUrl: string
  pagina?: number  // 1-indexed
  y?: number       // Coordenada Y en puntos PDF (0 = arriba)
  className?: string
}

export default function PdfViewer({ pdfUrl, pagina = 1, y = 0, className = '' }: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  const defaultLayoutPluginInstance = defaultLayoutPlugin({
    sidebarTabs: () => [],  // Sin sidebar
  })

  // Scroll a la posición Y después de que la página se renderice
  useEffect(() => {
    if (!containerRef.current || pagina < 1 || y <= 0) return

    // Dar tiempo a que el PDF renderice la página
    const timer = setTimeout(() => {
      const pageContainer = containerRef.current?.querySelector(
        `[data-page-number="${pagina}"]`
      )
      if (pageContainer) {
        const pageHeight = pageContainer.clientHeight
        // Convertir Y de coordenadas PDF a pixels del viewport
        // Asumiendo página Letter 792 puntos de alto
        const scrollRatio = y / 792
        const scrollY = pageHeight * scrollRatio

        pageContainer.scrollIntoView({ behavior: 'smooth' })
        // Ajuste fino después del scroll a la página
        setTimeout(() => {
          containerRef.current?.scrollBy({ top: scrollY - 50, behavior: 'smooth' })
        }, 100)
      }
    }, 500)

    return () => clearTimeout(timer)
  }, [pagina, y, pdfUrl])

  return (
    <div ref={containerRef} className={`h-full ${className}`}>
      <Worker workerUrl="/pdf.worker.min.js">
        <Viewer
          fileUrl={pdfUrl}
          plugins={[defaultLayoutPluginInstance]}
          initialPage={pagina - 1}  // 0-indexed
          defaultScale={SpecialZoomLevel.PageWidth}
          renderLoader={(percentages: number) => (
            <div className="flex flex-col items-center justify-center h-full gap-3">
              <Loader2 className="h-8 w-8 text-primary-600 animate-spin" />
              <span className="text-sm text-gray-500">
                Cargando PDF... {Math.round(percentages)}%
              </span>
            </div>
          )}
          renderError={() => (
            <div className="flex flex-col items-center justify-center h-full gap-3 p-6 text-center">
              <AlertCircle className="h-12 w-12 text-red-500" />
              <div>
                <p className="font-medium text-gray-900 dark:text-white">
                  Error al cargar el PDF
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  El archivo no está disponible o el formato no es válido.
                </p>
              </div>
            </div>
          )}
        />
      </Worker>
    </div>
  )
}
