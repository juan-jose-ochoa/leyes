import { memo } from 'react'

interface PdfViewerProps {
  pdfUrl: string
  pagina?: number
  y?: number
  pageHeight?: number
  className?: string
}

function PdfViewerInner({
  pdfUrl,
  pagina = 1,
  y = 0,
  pageHeight = 792,
  className = ''
}: PdfViewerProps) {
  // Convertir Y: nuestra extracción es desde TOP, PDF URL usa desde BOTTOM
  const yFromBottom = pageHeight - y

  // Probar: nameddest o pagemode podría ayudar
  // Formato simple que funciona: page + zoom con page-width
  const pdfUrlWithPosition = y > 0
    ? `${pdfUrl}#page=${pagina}&zoom=page-width,0,${yFromBottom}`
    : `${pdfUrl}#page=${pagina}&zoom=page-width`

  return (
    <iframe
      src={pdfUrlWithPosition}
      className={`w-full h-full border-0 ${className}`}
      title="PDF Document"
    />
  )
}

// Memoizar para evitar re-renders
const PdfViewer = memo(PdfViewerInner, (prev, next) => {
  return (
    prev.pdfUrl === next.pdfUrl &&
    prev.pagina === next.pagina &&
    prev.y === next.y
  )
})

export default PdfViewer
