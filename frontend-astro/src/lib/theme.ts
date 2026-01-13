/**
 * Sistema de colores centralizado para LeyesMX
 *
 * Dos dimensiones visuales:
 * 1. Categoría → Color sólido (fill)
 * 2. Tipo de documento → Estilo de borde
 */

// Colores por categoría (fill/background)
export const categoryColors = {
  fiscal: {
    bg: 'bg-emerald-600',
    bgLight: 'bg-emerald-100',
    bgDark: 'dark:bg-emerald-900/30',
    text: 'text-emerald-600',
    textDark: 'dark:text-emerald-400',
    border: 'border-emerald-500',
  },
  laboral: {
    bg: 'bg-blue-600',
    bgLight: 'bg-blue-100',
    bgDark: 'dark:bg-blue-900/30',
    text: 'text-blue-600',
    textDark: 'dark:text-blue-400',
    border: 'border-blue-500',
  },
  constitucional: {
    bg: 'bg-orange-600',
    bgLight: 'bg-orange-100',
    bgDark: 'dark:bg-orange-900/30',
    text: 'text-orange-600',
    textDark: 'dark:text-orange-400',
    border: 'border-orange-500',
  },
} as const;

// Estilos por tipo de documento (simple y limpio)
export const tipoStyles = {
  ley: {
    border: '',
    ring: '',
    label: 'Ley',
    chipColor: 'bg-primary-600',
  },
  codigo: {
    border: '',
    ring: '',
    label: 'Código',
    chipColor: 'bg-yellow-600',
  },
  reglamento: {
    border: '',
    ring: '',
    label: 'Reglamento',
    chipColor: 'bg-purple-600',
  },
  resolucion: {
    border: '',
    ring: '',
    label: 'RMF',
    chipColor: 'bg-amber-600',
  },
} as const;

// Helper para obtener clases de categoría
export function getCategoryClasses(categoria: string) {
  return categoryColors[categoria as keyof typeof categoryColors] || categoryColors.fiscal;
}

// Helper para obtener clases de tipo
export function getTipoClasses(tipo: string) {
  return tipoStyles[tipo as keyof typeof tipoStyles] || tipoStyles.ley;
}

// Helper para obtener todas las clases combinadas para un chip/badge
export function getLeyClasses(categoria: string, tipo: string) {
  const cat = getCategoryClasses(categoria);
  const tip = getTipoClasses(tipo);

  return {
    // Para chips con fill sólido
    solid: `${cat.bg} text-white ${tip.border}`,
    // Para chips con fondo claro
    light: `${cat.bgLight} ${cat.bgDark} ${cat.text} ${cat.textDark} ${tip.border}`,
    // Para badges/iconos
    badge: `${cat.bg} text-white ${tip.ring}`,
  };
}

// Definición de categorías para UI (con color para chips)
export const categoriasDef = [
  { value: 'fiscal', label: 'Fiscal', color: categoryColors.fiscal.bg },
  { value: 'laboral', label: 'Laboral', color: categoryColors.laboral.bg },
  { value: 'constitucional', label: 'Constitucional', color: categoryColors.constitucional.bg },
] as const;

// Definición de tipos para UI
export const tiposDef = [
  { value: 'ley', label: 'Leyes', color: tipoStyles.ley.chipColor },
  { value: 'codigo', label: 'Códigos', color: tipoStyles.codigo.chipColor },
  { value: 'reglamento', label: 'Reglamentos', color: tipoStyles.reglamento.chipColor },
  { value: 'resolucion', label: 'RMF', color: tipoStyles.resolucion.chipColor },
] as const;

export type Categoria = keyof typeof categoryColors;
export type TipoDocumento = keyof typeof tipoStyles;
