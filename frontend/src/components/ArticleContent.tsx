import { useFraccionesArticulo } from '@/hooks/useArticle'
import FraccionesView from './FraccionesView'

interface ArticleContentProps {
  articuloId: number
  contenido: string
}

/**
 * Displays article content with styled fracciones if available.
 * Falls back to plain text paragraphs if no fracciones exist.
 */
export default function ArticleContent({ articuloId, contenido }: ArticleContentProps) {
  const { data: fracciones, isLoading } = useFraccionesArticulo(articuloId)

  // Show loading skeleton briefly
  if (isLoading) {
    return (
      <div className="animate-pulse space-y-2">
        <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="h-4 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="h-4 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
      </div>
    )
  }

  // If fracciones exist, use styled view
  if (fracciones && fracciones.length > 0) {
    return <FraccionesView fracciones={fracciones} />
  }

  // Fallback to plain paragraphs
  return (
    <>
      {contenido.split('\n\n').filter(p => p.trim()).map((paragraph, i) => (
        <p key={i} className="mb-4 leading-relaxed text-gray-700 dark:text-gray-300">
          {paragraph}
        </p>
      ))}
    </>
  )
}
