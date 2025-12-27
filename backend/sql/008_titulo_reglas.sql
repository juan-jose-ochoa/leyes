-- ============================================================
-- LeyesMX - Migración: Agregar título a reglas RMF
-- El título de cada regla se muestra antes del número
-- ============================================================

-- 1. Agregar campo titulo a articulos
ALTER TABLE articulos
ADD COLUMN IF NOT EXISTS titulo TEXT;

COMMENT ON COLUMN articulos.titulo IS 'Título de la regla RMF (ej: "Concepto de operaciones financieras derivadas")';

-- 2. Actualizar vista materializada para incluir título
DROP MATERIALIZED VIEW IF EXISTS jerarquia_completa;

CREATE MATERIALIZED VIEW jerarquia_completa AS
SELECT
    a.id AS articulo_id,
    a.ley_id,
    l.codigo AS ley_codigo,
    l.nombre AS ley_nombre,
    l.tipo AS ley_tipo,
    d.id AS division_id,
    d.path_texto AS ubicacion,
    d.tipo AS division_tipo,
    a.numero_raw AS articulo,
    a.numero_base,
    a.sufijo,
    a.es_transitorio,
    a.decreto_dof,
    a.titulo,          -- Nuevo: título de regla
    a.contenido,
    a.orden_global,
    a.tipo AS articulo_tipo,
    a.referencias
FROM articulos a
JOIN leyes l ON a.ley_id = l.id
LEFT JOIN divisiones d ON a.division_id = d.id
ORDER BY a.ley_id, a.orden_global;

CREATE UNIQUE INDEX idx_jerarquia_articulo ON jerarquia_completa(articulo_id);
CREATE INDEX idx_jerarquia_ley ON jerarquia_completa(ley_id);
CREATE INDEX idx_jerarquia_codigo ON jerarquia_completa(ley_codigo);
CREATE INDEX idx_jerarquia_tipo ON jerarquia_completa(articulo_tipo);

-- 3. Refrescar vista
REFRESH MATERIALIZED VIEW jerarquia_completa;

-- 4. Mensaje de éxito
DO $$
BEGIN
    RAISE NOTICE 'Migración titulo completada: campo titulo agregado a articulos';
END $$;
