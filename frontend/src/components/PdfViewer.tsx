import { useEffect, useRef } from 'react'
import { Viewer, Worker, SpecialZoomLevel, RenderPage, RenderPageProps } from '@react-pdf-viewer/core'
import { defaultLayoutPlugin } from '@react-pdf-viewer/default-layout'
import { AlertCircle, Loader2 } from 'lucide-react'

import '@react-pdf-viewer/core/lib/styles/index.css'
import '@react-pdf-viewer/default-layout/lib/styles/index.css'

interface PdfViewerProps {
  pdfUrl: string
  pagina?: number  // 1-indexed
  y?: number       // Coordenada Y en puntos PDF (0 = arriba)
  pageHeight?: number  // Altura de página en puntos (default 792 para Letter)
  className?: string
}

export default function PdfViewer({
  pdfUrl,
  pagina = 1,
  y = 0,
  pageHeight = 792,
  className = ''
}: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  const defaultLayoutPluginInstance = defaultLayoutPlugin({
    sidebarTabs: () => [],
  })

  // Scroll a la página objetivo cuando carga
  useEffect(() => {
    if (!containerRef.current || pagina < 1) return

    const timer = setTimeout(() => {
      const pageContainer = containerRef.current?.querySelector(
        `[data-page-number="${pagina}"]`
      )
      if (pageContainer) {
        pageContainer.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }, 500)

    return () => clearTimeout(timer)
  }, [pagina, pdfUrl])

  // Render personalizado para agregar highlight en la página objetivo
  const renderPage: RenderPage = (props: RenderPageProps) => {
    const isTargetPage = props.pageIndex === pagina - 1
    const showHighlight = isTargetPage && y > 0

    return (
      <>
        {props.canvasLayer.children}
        {props.textLayer.children}
        {props.annotationLayer.children}

        {/* Highlight layer - barra amarilla en la posición Y */}
        {showHighlight && (
          <div
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              // Convertir Y de puntos PDF a porcentaje de altura
              top: `${(y / pageHeight) * 100}%`,
              height: '24px',
              backgroundColor: 'rgba(250, 204, 21, 0.4)', // yellow-400 con transparencia
              borderTop: '2px solid rgb(234, 179, 8)', // yellow-500
              pointerEvents: 'none',
              zIndex: 10,
              // Animación sutil de pulso
              animation: 'pulse 2s ease-in-out infinite',
            }}
          />
        )}
      </>
    )
  }

  return (
    <div ref={containerRef} className={`h-full ${className}`}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.6; }
          50% { opacity: 1; }
        }
      `}</style>
      <Worker workerUrl="/pdf.worker.min.js">
        <Viewer
          fileUrl={pdfUrl}
          plugins={[defaultLayoutPluginInstance]}
          initialPage={pagina - 1}
          defaultScale={SpecialZoomLevel.PageWidth}
          renderPage={renderPage}
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
