import { useFraccionesArticulo } from '@/hooks/useArticle'
import FraccionesView from './FraccionesView'

interface ArticleContentProps {
  articuloId: number
  contenido: string
  ley?: string
  mostrarReferencias?: boolean
}

/**
 * Displays article content: intro paragraphs followed by fracciones if available.
 */
export default function ArticleContent({ articuloId, contenido, ley, mostrarReferencias = false }: ArticleContentProps) {
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

  // Si hay fracciones, mostrar todo a través de FraccionesView (incluye párrafos texto)
  // Si no hay fracciones, mostrar contenido directamente
  const hasFracciones = fracciones && fracciones.length > 0

  return (
    <>
      {hasFracciones ? (
        <FraccionesView fracciones={fracciones} mostrarReferencias={mostrarReferencias} />
      ) : (
        /* Contenido sin fracciones (artículos simples) */
        contenido && contenido.trim() && (
          contenido.split('\n\n').filter(p => p.trim()).map((paragraph, i) => (
            <p key={`intro-${i}`} className="mb-4 leading-relaxed text-gray-700 dark:text-gray-300">
              {paragraph}
            </p>
          ))
        )
      )}
    </>
  )
}
