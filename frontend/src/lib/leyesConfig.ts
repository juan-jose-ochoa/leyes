/**
 * Configuración de categorización y display de leyes.
 *
 * Este archivo centraliza los mapeos para:
 * - Orden de prioridad para mostrar en UI (por frecuencia de uso)
 * - Vincular reglamentos a sus leyes base
 * - Categorizar leyes como fiscales, laborales, etc.
 * - Definir nombres cortos para mostrar en UI
 */

// Orden de leyes por frecuencia de consulta (UX priority)
export const ORDEN_LEYES: string[] = [
  // Fiscales - uso diario
  'CFF',      // Base del sistema fiscal
  'LISR',     // ISR, el más consultado
  'LIVA',     // IVA, operaciones diarias
  'RMF',      // Reglas actuales, consulta constante
  'LIF',      // Tasas y estímulos del año
  'LIEPS',    // Impuestos especiales
  'LA',       // Comercio exterior
  'LFDC',     // Derechos del contribuyente
  // Laborales / Seguridad Social
  'LFT',      // Relaciones laborales
  'LSS',      // Cuotas IMSS
  'LINFONAVIT', // Créditos vivienda
  'LISSSTE',  // Sector público
  // Constitucional
  'CPEUM',    // Referencia
]

// Orden de reglamentos (siguen a su ley base)
export const ORDEN_REGLAMENTOS: string[] = [
  'RCFF',
  'RLISR',
  'RLIVA',
  'RLIEPS',
  'RLFT',
  'RACERF',
  'RLSS',
]

// Mapeo de reglamento → ley base
export const LEY_BASE: Record<string, string> = {
  'RCFF': 'CFF',
  'RLISR': 'LISR',
  'RLIVA': 'LIVA',
  'RLIEPS': 'LIEPS',
  'RLFT': 'LFT',
  'RACERF': 'LSS',
  'RLSS': 'LSS',
}

export type Categoria = 'fiscal' | 'laboral' | 'constitucional'

// Mapeo de ley → categoría
export const CATEGORIA: Record<string, Categoria> = {
  // Fiscal
  'CFF': 'fiscal',
  'LISR': 'fiscal',
  'LIVA': 'fiscal',
  'RMF': 'fiscal',
  'LIF': 'fiscal',
  'LIEPS': 'fiscal',
  'LA': 'fiscal',
  'LFDC': 'fiscal',
  // Laboral
  'LFT': 'laboral',
  'LSS': 'laboral',
  'LINFONAVIT': 'laboral',
  'LISSSTE': 'laboral',
  // Constitucional
  'CPEUM': 'constitucional',
}

// Nombres cortos para mostrar (override de nombre_corto de BD si es necesario)
export const NOMBRE_DISPLAY: Record<string, string> = {
  // Fiscales
  'CFF': 'Código Fiscal',
  'LISR': 'Ley del ISR',
  'LIVA': 'Ley del IVA',
  'RMF': 'Miscelánea Fiscal 2026',
  'LIF': 'Ley de Ingresos 2026',
  'LIEPS': 'Ley del IEPS',
  'LA': 'Ley Aduanera',
  'LFDC': 'Derechos del Contribuyente',
  // Laborales
  'LFT': 'Ley Federal del Trabajo',
  'LSS': 'Ley del Seguro Social',
  'LINFONAVIT': 'Ley del INFONAVIT',
  'LISSSTE': 'Ley del ISSSTE',
  // Constitucional
  'CPEUM': 'Constitución',
  // Reglamentos
  'RCFF': 'Reglamento CFF',
  'RLISR': 'Reglamento ISR',
  'RLIVA': 'Reglamento IVA',
  'RLIEPS': 'Reglamento IEPS',
  'RLFT': 'Reglamento LFT',
  'RACERF': 'Reglamento Afiliación SS',
  'RLSS': 'Reglamento Reservas SS',
}

// Información de cada categoría para UI
export const CATEGORIA_INFO: Record<Categoria, { nombre: string; color: string; bgLight: string }> = {
  fiscal: {
    nombre: 'Leyes Fiscales',
    color: 'bg-emerald-600',
    bgLight: 'bg-emerald-50 dark:bg-emerald-900/20'
  },
  laboral: {
    nombre: 'Leyes Laborales',
    color: 'bg-blue-600',
    bgLight: 'bg-blue-50 dark:bg-blue-900/20'
  },
  constitucional: {
    nombre: 'Marco Constitucional',
    color: 'bg-amber-600',
    bgLight: 'bg-amber-50 dark:bg-amber-900/20'
  },
}
