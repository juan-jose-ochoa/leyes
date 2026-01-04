/**
 * Configuración de categorización y display de leyes.
 *
 * Este archivo centraliza los mapeos para:
 * - Catálogo de leyes conocidas (importadas y no importadas)
 * - Orden de prioridad para mostrar en UI (por frecuencia de uso)
 * - Vincular reglamentos a sus leyes base
 * - Categorizar leyes como fiscales, laborales, etc.
 */

export type Categoria = 'fiscal' | 'laboral' | 'constitucional'

// Información de una ley en el catálogo
export interface InfoLey {
  nombre: string           // Nombre completo
  nombreCorto?: string     // Para UI compacta
  categoria?: Categoria    // Categoría si aplica
}

// Catálogo unificado de leyes conocidas (importadas y no importadas)
export const CATALOGO_LEYES: Record<string, InfoLey> = {
  // === LEYES FISCALES (importadas) ===
  'CFF': { nombre: 'Código Fiscal de la Federación', nombreCorto: 'Código Fiscal', categoria: 'fiscal' },
  'LISR': { nombre: 'Ley del Impuesto Sobre la Renta', nombreCorto: 'Ley del ISR', categoria: 'fiscal' },
  'LIVA': { nombre: 'Ley del Impuesto al Valor Agregado', nombreCorto: 'Ley del IVA', categoria: 'fiscal' },
  'LIEPS': { nombre: 'Ley del Impuesto Especial sobre Producción y Servicios', nombreCorto: 'Ley del IEPS', categoria: 'fiscal' },
  'RMF': { nombre: 'Resolución Miscelánea Fiscal 2026', nombreCorto: 'Miscelánea Fiscal 2026', categoria: 'fiscal' },
  'LIF': { nombre: 'Ley de Ingresos de la Federación 2026', nombreCorto: 'Ley de Ingresos 2026', categoria: 'fiscal' },
  'LA': { nombre: 'Ley Aduanera', nombreCorto: 'Ley Aduanera', categoria: 'fiscal' },
  'LFDC': { nombre: 'Ley Federal de los Derechos del Contribuyente', nombreCorto: 'Derechos del Contribuyente', categoria: 'fiscal' },

  // === LEYES LABORALES (importadas) ===
  'LFT': { nombre: 'Ley Federal del Trabajo', nombreCorto: 'Ley Federal del Trabajo', categoria: 'laboral' },
  'LSS': { nombre: 'Ley del Seguro Social', nombreCorto: 'Ley del Seguro Social', categoria: 'laboral' },
  'LINFONAVIT': { nombre: 'Ley del Instituto del Fondo Nacional de la Vivienda para los Trabajadores', nombreCorto: 'Ley del INFONAVIT', categoria: 'laboral' },
  'LISSSTE': { nombre: 'Ley del Instituto de Seguridad y Servicios Sociales de los Trabajadores del Estado', nombreCorto: 'Ley del ISSSTE', categoria: 'laboral' },

  // === CONSTITUCIONAL (importada) ===
  'CPEUM': { nombre: 'Constitución Política de los Estados Unidos Mexicanos', nombreCorto: 'Constitución', categoria: 'constitucional' },

  // === REGLAMENTOS (importados) ===
  'RCFF': { nombre: 'Reglamento del Código Fiscal de la Federación', nombreCorto: 'Reglamento CFF', categoria: 'fiscal' },
  'RLISR': { nombre: 'Reglamento de la Ley del Impuesto Sobre la Renta', nombreCorto: 'Reglamento ISR', categoria: 'fiscal' },
  'RLIVA': { nombre: 'Reglamento de la Ley del Impuesto al Valor Agregado', nombreCorto: 'Reglamento IVA', categoria: 'fiscal' },
  'RLIEPS': { nombre: 'Reglamento de la Ley del Impuesto Especial sobre Producción y Servicios', nombreCorto: 'Reglamento IEPS', categoria: 'fiscal' },
  'RLFT': { nombre: 'Reglamento de la Ley Federal del Trabajo', nombreCorto: 'Reglamento LFT', categoria: 'laboral' },
  'RACERF': { nombre: 'Reglamento de la Ley del Seguro Social en Materia de Afiliación, Clasificación de Empresas, Recaudación y Fiscalización', nombreCorto: 'Reglamento Afiliación SS', categoria: 'laboral' },
  'RLSS': { nombre: 'Reglamento de la Ley del Seguro Social en Materia de Reservas', nombreCorto: 'Reglamento Reservas SS', categoria: 'laboral' },

  // === LEYES NO IMPORTADAS (referenciadas en RMF y otras) ===
  'LCF': { nombre: 'Ley de Coordinación Fiscal', categoria: 'fiscal' },
  'LFPIORPI': { nombre: 'Ley Federal para la Prevención e Identificación de Operaciones con Recursos de Procedencia Ilícita', categoria: 'fiscal' },
  'LGSM': { nombre: 'Ley General de Sociedades Mercantiles' },
  'LGTOC': { nombre: 'Ley General de Títulos y Operaciones de Crédito' },
  'LIC': { nombre: 'Ley de Instituciones de Crédito' },
  'LMV': { nombre: 'Ley del Mercado de Valores' },
  'CNBV': { nombre: 'Comisión Nacional Bancaria y de Valores' },
  'LFPCA': { nombre: 'Ley Federal de Procedimiento Contencioso Administrativo' },
  'CFPC': { nombre: 'Código Federal de Procedimientos Civiles' },
  'CC': { nombre: 'Código Civil Federal' },
  'CCom': { nombre: 'Código de Comercio' },
}

// Helper para obtener nombre de ley
export function getNombreLey(codigo: string, corto = false): string {
  const info = CATALOGO_LEYES[codigo]
  if (!info) return codigo
  return corto && info.nombreCorto ? info.nombreCorto : info.nombre
}

// Helper para obtener categoría
export function getCategoria(codigo: string): Categoria | undefined {
  return CATALOGO_LEYES[codigo]?.categoria
}

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

// === DEPRECADO: usar CATALOGO_LEYES y getNombreLey() ===
// Mantenido temporalmente para compatibilidad
export const NOMBRE_DISPLAY: Record<string, string> = Object.fromEntries(
  Object.entries(CATALOGO_LEYES).map(([codigo, info]) => [codigo, info.nombreCorto || info.nombre])
)

export const CATEGORIA: Record<string, Categoria> = Object.fromEntries(
  Object.entries(CATALOGO_LEYES)
    .filter(([, info]) => info.categoria)
    .map(([codigo, info]) => [codigo, info.categoria!])
)
