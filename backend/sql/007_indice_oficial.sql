-- ============================================================
-- LeyesMX - Índice oficial de RMF (checksum)
-- Permite comparar datos importados vs estructura oficial del PDF
-- Versionado por año para soportar RMF2025, RMF2026, etc.
-- ============================================================

-- Tabla para almacenar el índice oficial extraído del PDF
CREATE TABLE IF NOT EXISTS indice_oficial (
    id SERIAL PRIMARY KEY,
    ley_codigo VARCHAR(20) NOT NULL,  -- RMF2025, RMF2026, etc.
    tipo VARCHAR(20) NOT NULL,         -- titulo, capitulo, seccion, subseccion, regla
    numero VARCHAR(20) NOT NULL,       -- 1, 2.1, 2.1.1, etc.
    nombre TEXT,                       -- Nombre/título del elemento
    pagina INT,                        -- Página en el PDF donde aparece
    fecha_extraccion TIMESTAMP DEFAULT NOW(),

    UNIQUE(ley_codigo, tipo, numero)
);

CREATE INDEX IF NOT EXISTS idx_indice_oficial_ley ON indice_oficial(ley_codigo);
CREATE INDEX IF NOT EXISTS idx_indice_oficial_tipo ON indice_oficial(ley_codigo, tipo);

COMMENT ON TABLE indice_oficial IS 'Índice oficial extraído del PDF de cada RMF, usado como checksum';

-- Función para comparar divisiones importadas vs índice oficial
CREATE OR REPLACE FUNCTION comparar_divisiones_indice(ley_codigo VARCHAR)
RETURNS TABLE(
    tipo VARCHAR,
    numero VARCHAR,
    nombre_oficial TEXT,
    nombre_importado TEXT,
    estado VARCHAR  -- 'ok', 'faltante', 'extra', 'diferente'
) AS $$
BEGIN
    RETURN QUERY
    WITH oficial AS (
        SELECT io.tipo, io.numero, io.nombre
        FROM indice_oficial io
        WHERE io.ley_codigo = comparar_divisiones_indice.ley_codigo
        AND io.tipo IN ('titulo', 'capitulo', 'seccion', 'subseccion')
    ),
    importado AS (
        SELECT DISTINCT ON (d.tipo, d.numero)
            d.tipo::VARCHAR, d.numero::VARCHAR, d.nombre::TEXT
        FROM divisiones d
        JOIN leyes l ON d.ley_id = l.id
        WHERE l.codigo = comparar_divisiones_indice.ley_codigo
        ORDER BY d.tipo, d.numero
    )
    -- Elementos en índice oficial pero no importados (faltantes)
    SELECT
        o.tipo,
        o.numero,
        o.nombre as nombre_oficial,
        NULL::TEXT as nombre_importado,
        'faltante'::VARCHAR as estado
    FROM oficial o
    LEFT JOIN importado i ON o.tipo = i.tipo AND o.numero = i.numero
    WHERE i.numero IS NULL

    UNION ALL

    -- Elementos importados pero no en índice oficial (extras)
    SELECT
        i.tipo,
        i.numero,
        NULL::TEXT as nombre_oficial,
        i.nombre as nombre_importado,
        'extra'::VARCHAR as estado
    FROM importado i
    LEFT JOIN oficial o ON o.tipo = i.tipo AND o.numero = i.numero
    WHERE o.numero IS NULL

    UNION ALL

    -- Elementos que coinciden
    SELECT
        o.tipo,
        o.numero,
        o.nombre as nombre_oficial,
        i.nombre as nombre_importado,
        'ok'::VARCHAR as estado
    FROM oficial o
    JOIN importado i ON o.tipo = i.tipo AND o.numero = i.numero

    ORDER BY tipo, numero;
END;
$$ LANGUAGE plpgsql STABLE;

-- Función para comparar reglas importadas vs índice oficial
CREATE OR REPLACE FUNCTION comparar_reglas_indice(ley_codigo VARCHAR)
RETURNS TABLE(
    numero VARCHAR,
    pagina_pdf INT,
    estado VARCHAR  -- 'ok', 'faltante'
) AS $$
BEGIN
    RETURN QUERY
    WITH oficial AS (
        SELECT io.numero, io.pagina
        FROM indice_oficial io
        WHERE io.ley_codigo = comparar_reglas_indice.ley_codigo
        AND io.tipo = 'regla'
    ),
    importado AS (
        SELECT a.numero_raw::VARCHAR as numero
        FROM articulos a
        JOIN leyes l ON a.ley_id = l.id
        WHERE l.codigo = comparar_reglas_indice.ley_codigo
        AND a.tipo = 'regla'
    )
    SELECT
        o.numero,
        o.pagina as pagina_pdf,
        CASE
            WHEN i.numero IS NOT NULL THEN 'ok'::VARCHAR
            ELSE 'faltante'::VARCHAR
        END as estado
    FROM oficial o
    LEFT JOIN importado i ON o.numero = i.numero
    ORDER BY
        (string_to_array(o.numero, '.'))::int[];
END;
$$ LANGUAGE plpgsql STABLE;

-- Función resumen de verificación contra índice
CREATE OR REPLACE FUNCTION verificar_indice(ley_codigo VARCHAR)
RETURNS TABLE(
    categoria VARCHAR,
    total_oficial INT,
    total_importado INT,
    faltantes INT,
    extras INT,
    porcentaje_completo NUMERIC
) AS $$
BEGIN
    RETURN QUERY

    -- Títulos
    SELECT
        'titulo'::VARCHAR as categoria,
        (SELECT COUNT(*)::INT FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'titulo'),
        (SELECT COUNT(DISTINCT numero)::INT FROM divisiones d JOIN leyes l ON d.ley_id = l.id WHERE l.codigo = verificar_indice.ley_codigo AND d.tipo = 'titulo'),
        (SELECT COUNT(*)::INT FROM comparar_divisiones_indice(verificar_indice.ley_codigo) WHERE tipo = 'titulo' AND estado = 'faltante'),
        (SELECT COUNT(*)::INT FROM comparar_divisiones_indice(verificar_indice.ley_codigo) WHERE tipo = 'titulo' AND estado = 'extra'),
        CASE
            WHEN (SELECT COUNT(*) FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'titulo') = 0 THEN 100
            ELSE ROUND(
                (SELECT COUNT(*)::NUMERIC FROM comparar_divisiones_indice(verificar_indice.ley_codigo) WHERE tipo = 'titulo' AND estado = 'ok') /
                (SELECT COUNT(*)::NUMERIC FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'titulo') * 100, 1
            )
        END

    UNION ALL

    -- Capítulos
    SELECT
        'capitulo'::VARCHAR,
        (SELECT COUNT(*)::INT FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'capitulo'),
        (SELECT COUNT(DISTINCT numero)::INT FROM divisiones d JOIN leyes l ON d.ley_id = l.id WHERE l.codigo = verificar_indice.ley_codigo AND d.tipo = 'capitulo'),
        (SELECT COUNT(*)::INT FROM comparar_divisiones_indice(verificar_indice.ley_codigo) WHERE tipo = 'capitulo' AND estado = 'faltante'),
        (SELECT COUNT(*)::INT FROM comparar_divisiones_indice(verificar_indice.ley_codigo) WHERE tipo = 'capitulo' AND estado = 'extra'),
        CASE
            WHEN (SELECT COUNT(*) FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'capitulo') = 0 THEN 100
            ELSE ROUND(
                (SELECT COUNT(*)::NUMERIC FROM comparar_divisiones_indice(verificar_indice.ley_codigo) WHERE tipo = 'capitulo' AND estado = 'ok') /
                (SELECT COUNT(*)::NUMERIC FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'capitulo') * 100, 1
            )
        END

    UNION ALL

    -- Secciones
    SELECT
        'seccion'::VARCHAR,
        (SELECT COUNT(*)::INT FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'seccion'),
        (SELECT COUNT(DISTINCT numero)::INT FROM divisiones d JOIN leyes l ON d.ley_id = l.id WHERE l.codigo = verificar_indice.ley_codigo AND d.tipo = 'seccion'),
        (SELECT COUNT(*)::INT FROM comparar_divisiones_indice(verificar_indice.ley_codigo) WHERE tipo = 'seccion' AND estado = 'faltante'),
        (SELECT COUNT(*)::INT FROM comparar_divisiones_indice(verificar_indice.ley_codigo) WHERE tipo = 'seccion' AND estado = 'extra'),
        CASE
            WHEN (SELECT COUNT(*) FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'seccion') = 0 THEN 100
            ELSE ROUND(
                (SELECT COUNT(*)::NUMERIC FROM comparar_divisiones_indice(verificar_indice.ley_codigo) WHERE tipo = 'seccion' AND estado = 'ok') /
                (SELECT COUNT(*)::NUMERIC FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'seccion') * 100, 1
            )
        END

    UNION ALL

    -- Subsecciones
    SELECT
        'subseccion'::VARCHAR,
        (SELECT COUNT(*)::INT FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'subseccion'),
        (SELECT COUNT(DISTINCT numero)::INT FROM divisiones d JOIN leyes l ON d.ley_id = l.id WHERE l.codigo = verificar_indice.ley_codigo AND d.tipo = 'subseccion'),
        (SELECT COUNT(*)::INT FROM comparar_divisiones_indice(verificar_indice.ley_codigo) WHERE tipo = 'subseccion' AND estado = 'faltante'),
        (SELECT COUNT(*)::INT FROM comparar_divisiones_indice(verificar_indice.ley_codigo) WHERE tipo = 'subseccion' AND estado = 'extra'),
        CASE
            WHEN (SELECT COUNT(*) FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'subseccion') = 0 THEN 100
            ELSE ROUND(
                (SELECT COUNT(*)::NUMERIC FROM comparar_divisiones_indice(verificar_indice.ley_codigo) WHERE tipo = 'subseccion' AND estado = 'ok') /
                (SELECT COUNT(*)::NUMERIC FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'subseccion') * 100, 1
            )
        END

    UNION ALL

    -- Reglas
    SELECT
        'regla'::VARCHAR,
        (SELECT COUNT(*)::INT FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'regla'),
        (SELECT COUNT(*)::INT FROM articulos a JOIN leyes l ON a.ley_id = l.id WHERE l.codigo = verificar_indice.ley_codigo AND a.tipo = 'regla'),
        (SELECT COUNT(*)::INT FROM comparar_reglas_indice(verificar_indice.ley_codigo) WHERE estado = 'faltante'),
        0::INT,  -- No puede haber reglas "extra" (el parser no inventa)
        CASE
            WHEN (SELECT COUNT(*) FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'regla') = 0 THEN 100
            ELSE ROUND(
                (SELECT COUNT(*)::NUMERIC FROM comparar_reglas_indice(verificar_indice.ley_codigo) WHERE estado = 'ok') /
                (SELECT COUNT(*)::NUMERIC FROM indice_oficial WHERE indice_oficial.ley_codigo = verificar_indice.ley_codigo AND tipo = 'regla') * 100, 1
            )
        END;
END;
$$ LANGUAGE plpgsql STABLE;

-- API wrappers
CREATE OR REPLACE FUNCTION api.verificar_indice(ley_codigo VARCHAR)
RETURNS TABLE(
    categoria VARCHAR,
    total_oficial INT,
    total_importado INT,
    faltantes INT,
    extras INT,
    porcentaje_completo NUMERIC
) AS $$
BEGIN
    RETURN QUERY SELECT * FROM public.verificar_indice(ley_codigo);
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION api.comparar_reglas_indice(ley_codigo VARCHAR)
RETURNS TABLE(
    numero VARCHAR,
    pagina_pdf INT,
    estado VARCHAR
) AS $$
BEGIN
    RETURN QUERY SELECT * FROM public.comparar_reglas_indice(ley_codigo);
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION api.comparar_divisiones_indice(ley_codigo VARCHAR)
RETURNS TABLE(
    tipo VARCHAR,
    numero VARCHAR,
    nombre_oficial TEXT,
    nombre_importado TEXT,
    estado VARCHAR
) AS $$
BEGIN
    RETURN QUERY SELECT * FROM public.comparar_divisiones_indice(ley_codigo);
END;
$$ LANGUAGE plpgsql STABLE;

-- Permisos
GRANT SELECT ON indice_oficial TO web_anon;
GRANT EXECUTE ON FUNCTION api.verificar_indice(VARCHAR) TO web_anon;
GRANT EXECUTE ON FUNCTION api.comparar_reglas_indice(VARCHAR) TO web_anon;
GRANT EXECUTE ON FUNCTION api.comparar_divisiones_indice(VARCHAR) TO web_anon;

COMMENT ON FUNCTION api.verificar_indice IS 'Resumen de verificación contra índice oficial del PDF';
COMMENT ON FUNCTION api.comparar_reglas_indice IS 'Lista de reglas con estado (ok/faltante) vs índice oficial';
COMMENT ON FUNCTION api.comparar_divisiones_indice IS 'Lista de divisiones con estado vs índice oficial';
