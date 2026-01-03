/**
 * Configuración de categorización y display de leyes.
 *
 * Este archivo centraliza los mapeos para:
 * - Vincular reglamentos a sus leyes base
 * - Categorizar leyes como fiscales, laborales, etc.
 * - Definir nombres cortos para mostrar en UI
 */

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
  'LIEPS': 'fiscal',
  'LA': 'fiscal',
  'RMF': 'fiscal',
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
  'CFF': 'Código Fiscal',
  'LISR': 'Ley del ISR',
  'LIVA': 'Ley del IVA',
  'LIEPS': 'Ley del IEPS',
  'LA': 'Ley Aduanera',
  'LFT': 'Ley del Trabajo',
  'LSS': 'Ley del Seguro Social',
  'LINFONAVIT': 'Ley del INFONAVIT',
  'LISSSTE': 'Ley del ISSSTE',
  'CPEUM': 'Constitución',
  'RMF': 'Miscelánea Fiscal',
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
