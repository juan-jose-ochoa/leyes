-- ============================================================
-- Migración: Agregar campo calidad para seguimiento de importación
-- ============================================================

-- Agregar columna calidad a la tabla articulos
-- Almacena información sobre issues detectados y acciones correctivas
ALTER TABLE articulos ADD COLUMN IF NOT EXISTS calidad JSONB;

-- Índice para buscar artículos con problemas de calidad
CREATE INDEX IF NOT EXISTS idx_articulos_calidad ON articulos USING GIN(calidad);

-- Índice para filtrar por estatus de calidad
CREATE INDEX IF NOT EXISTS idx_articulos_calidad_estatus
ON articulos ((calidad->>'estatus'))
WHERE calidad IS NOT NULL;

COMMENT ON COLUMN articulos.calidad IS 'Registro de calidad de importación: estatus (ok/corregida/con_error) e issues detectados con acciones correctivas';
