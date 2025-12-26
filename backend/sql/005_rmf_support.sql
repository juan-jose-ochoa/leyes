-- ============================================================
-- LeyesMX - Migración para soporte de RMF
-- Agrega campo 'tipo' a artículos para distinguir reglas
-- ============================================================

-- 1. Agregar campo tipo a articulos
ALTER TABLE articulos
ADD COLUMN IF NOT EXISTS tipo VARCHAR(10) DEFAULT 'articulo'
    CHECK (tipo IN ('articulo', 'regla'));

COMMENT ON COLUMN articulos.tipo IS 'Tipo de contenido: articulo (leyes) o regla (RMF)';

-- 2. Agregar 'resolucion' como tipo válido de ley
ALTER TABLE leyes DROP CONSTRAINT IF EXISTS leyes_tipo_check;
ALTER TABLE leyes ADD CONSTRAINT leyes_tipo_check
    CHECK (tipo IN ('ley', 'reglamento', 'resolucion'));

-- 3. Agregar campo referencias para reglas RMF
ALTER TABLE articulos
ADD COLUMN IF NOT EXISTS referencias TEXT;

COMMENT ON COLUMN articulos.referencias IS 'Referencias legales al final de reglas RMF: CFF 4o., LISR 1o.';

-- 4. Recrear vista materializada con campo tipo
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
    a.contenido,
    a.orden_global,
    a.tipo AS articulo_tipo,  -- 'articulo' o 'regla'
    a.referencias             -- referencias RMF
FROM articulos a
JOIN leyes l ON a.ley_id = l.id
LEFT JOIN divisiones d ON a.division_id = d.id
ORDER BY a.ley_id, a.orden_global;

CREATE UNIQUE INDEX idx_jerarquia_articulo ON jerarquia_completa(articulo_id);
CREATE INDEX idx_jerarquia_ley ON jerarquia_completa(ley_id);
CREATE INDEX idx_jerarquia_codigo ON jerarquia_completa(ley_codigo);
CREATE INDEX idx_jerarquia_tipo ON jerarquia_completa(articulo_tipo);

COMMENT ON MATERIALIZED VIEW jerarquia_completa IS 'Vista desnormalizada para consultas rápidas de navegación';

-- 5. Refrescar vista
REFRESH MATERIALIZED VIEW jerarquia_completa;

-- 6. Mensaje de éxito
DO $$
BEGIN
    RAISE NOTICE 'Migración RMF completada: campo tipo agregado a articulos';
END $$;
