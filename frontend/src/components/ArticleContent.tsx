import { useFraccionesArticulo } from '@/hooks/useArticle'
import FraccionesView from './FraccionesView'

interface ArticleContentProps {
  articuloId: number
  contenido: string
  ley?: string
}

/**
 * Displays article content: intro paragraphs followed by fracciones if available.
 */
export default function ArticleContent({ articuloId, contenido, ley }: ArticleContentProps) {
  const { data: fracciones, isLoading } = useFraccionesArticulo(articuloId, ley)

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

  return (
    <>
      {/* Contenido introductorio (siempre mostrar si existe) */}
      {contenido && contenido.trim() && (
        contenido.split('\n\n').filter(p => p.trim()).map((paragraph, i) => (
          <p key={`intro-${i}`} className="mb-4 leading-relaxed text-gray-700 dark:text-gray-300">
            {paragraph}
          </p>
        ))
      )}

      {/* Fracciones (si existen) */}
      {fracciones && fracciones.length > 0 && (
        <FraccionesView fracciones={fracciones} />
      )}
    </>
  )
}
