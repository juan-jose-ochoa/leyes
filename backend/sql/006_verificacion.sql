-- ============================================================
-- LeyesMX - Funciones de verificación de integridad
-- Permite detectar reglas/artículos faltantes en divisiones
-- ============================================================

-- Función auxiliar para extraer el último número de una regla (2.1.49 -> 49)
CREATE OR REPLACE FUNCTION extraer_ultimo_numero(numero_raw VARCHAR)
RETURNS INT AS $$
DECLARE
    partes TEXT[];
BEGIN
    partes := string_to_array(numero_raw, '.');
    IF array_length(partes, 1) >= 1 THEN
        RETURN partes[array_length(partes, 1)]::INT;
    END IF;
    RETURN NULL;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Función para verificar integridad de una división específica
CREATE OR REPLACE FUNCTION verificar_division(div_id INT)
RETURNS TABLE(
    division_id INT,
    capitulo VARCHAR,
    total_actual INT,
    primera_regla TEXT,
    ultima_regla TEXT,
    num_primera INT,
    num_ultima INT,
    total_esperado INT,
    faltantes INT,
    porcentaje_completo NUMERIC,
    numeros_faltantes INT[]
) AS $$
BEGIN
    RETURN QUERY
    WITH reglas AS (
        SELECT
            a.numero_raw::TEXT as numero_raw,
            extraer_ultimo_numero(a.numero_raw) as num
        FROM articulos a
        WHERE a.division_id = div_id
    ),
    stats AS (
        SELECT
            COUNT(*)::INT as total,
            -- Usar ORDER BY num para obtener primera/ultima correctamente (no lexicográfico)
            (SELECT numero_raw FROM reglas WHERE num IS NOT NULL ORDER BY num ASC LIMIT 1) as primera,
            (SELECT numero_raw FROM reglas WHERE num IS NOT NULL ORDER BY num DESC LIMIT 1) as ultima,
            MIN(num) as min_num,
            MAX(num) as max_num,
            array_agg(num ORDER BY num) as nums
        FROM reglas
        WHERE num IS NOT NULL
    )
    SELECT
        div_id,
        d.numero,
        s.total,
        s.primera,
        s.ultima,
        s.min_num,
        s.max_num,
        CASE WHEN s.max_num IS NOT NULL AND s.min_num IS NOT NULL
             THEN (s.max_num - s.min_num + 1)
             ELSE s.total END::INT,
        CASE WHEN s.max_num IS NOT NULL AND s.min_num IS NOT NULL
             THEN (s.max_num - s.min_num + 1) - s.total
             ELSE 0 END::INT,
        CASE WHEN s.max_num IS NOT NULL AND s.min_num IS NOT NULL AND (s.max_num - s.min_num + 1) > 0
             THEN ROUND(s.total::NUMERIC / (s.max_num - s.min_num + 1) * 100, 1)
             ELSE 100 END,
        -- Devolver array de números faltantes
        (
            SELECT array_agg(n ORDER BY n)
            FROM generate_series(s.min_num, s.max_num) n
            WHERE n != ALL(s.nums)
        )
    FROM stats s
    CROSS JOIN divisiones d
    WHERE d.id = div_id;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION verificar_division IS 'Verifica integridad de una división, detectando reglas faltantes';

-- Función para verificar todas las divisiones de una ley
CREATE OR REPLACE FUNCTION verificar_ley(ley_codigo VARCHAR)
RETURNS TABLE(
    division_id INT,
    tipo VARCHAR,
    numero VARCHAR,
    nombre TEXT,
    total_actual INT,
    primera_regla TEXT,
    ultima_regla TEXT,
    num_primera INT,
    num_ultima INT,
    total_esperado INT,
    faltantes INT,
    porcentaje_completo NUMERIC,
    status TEXT,  -- 'ok', 'warning', 'error', 'empty'
    numeros_faltantes INT[]
) AS $$
BEGIN
    RETURN QUERY
    WITH divisiones_ley AS (
        SELECT d.id, d.tipo, d.numero, d.nombre, d.orden_global
        FROM divisiones d
        JOIN leyes l ON d.ley_id = l.id
        WHERE l.codigo = ley_codigo
    ),
    verificaciones AS (
        SELECT dl.*, v.*
        FROM divisiones_ley dl
        CROSS JOIN LATERAL verificar_division(dl.id) v
    )
    SELECT
        v.division_id,
        dl.tipo,
        dl.numero,
        dl.nombre,
        v.total_actual,
        v.primera_regla,
        v.ultima_regla,
        v.num_primera,
        v.num_ultima,
        v.total_esperado,
        v.faltantes,
        v.porcentaje_completo,
        CASE
            WHEN v.total_actual = 0 THEN 'empty'::TEXT
            WHEN v.porcentaje_completo >= 100 THEN 'ok'::TEXT
            WHEN v.porcentaje_completo >= 80 THEN 'warning'::TEXT
            ELSE 'error'::TEXT
        END as status,
        v.numeros_faltantes
    FROM divisiones_ley dl
    LEFT JOIN verificaciones v ON v.division_id = dl.id
    ORDER BY dl.orden_global;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION verificar_ley IS 'Verifica integridad de todas las divisiones de una ley';

-- API wrapper para verificar_ley
DROP FUNCTION IF EXISTS api.verificar_ley(VARCHAR);
CREATE OR REPLACE FUNCTION api.verificar_ley(ley_codigo VARCHAR)
RETURNS TABLE(
    division_id INT,
    tipo VARCHAR,
    numero VARCHAR,
    nombre TEXT,
    total_actual INT,
    primera_regla TEXT,
    ultima_regla TEXT,
    num_primera INT,
    num_ultima INT,
    total_esperado INT,
    faltantes INT,
    porcentaje_completo NUMERIC,
    status TEXT,
    numeros_faltantes INT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM public.verificar_ley(ley_codigo);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION api.verificar_ley IS 'API: Verifica integridad de divisiones, detecta reglas faltantes';

-- Permisos
GRANT EXECUTE ON FUNCTION api.verificar_ley(VARCHAR) TO web_anon;
