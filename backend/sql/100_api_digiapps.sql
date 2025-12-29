-- ============================================================
-- Vistas y funciones API en schema leyesmx
-- PostgREST usa db-schemas = "leyesmx"
-- ============================================================

-- Permisos para web_anon
GRANT USAGE ON SCHEMA leyesmx TO web_anon;
GRANT SELECT ON ALL TABLES IN SCHEMA leyesmx TO web_anon;

-- ============================================================
-- Vista: v_leyes
-- ============================================================
CREATE OR REPLACE VIEW leyesmx.v_leyes AS
SELECT
    codigo,
    nombre,
    nombre_corto,
    tipo,
    url_fuente,
    fecha_publicacion,
    ultima_reforma,
    (SELECT COUNT(*) FROM leyesmx.articulos a WHERE a.ley = l.codigo) as total_articulos
FROM leyesmx.leyes l;

GRANT SELECT ON leyesmx.v_leyes TO web_anon;

-- ============================================================
-- Vista: v_articulos
-- ============================================================
CREATE OR REPLACE VIEW leyesmx.v_articulos AS
SELECT
    a.id,
    a.ley,
    l.nombre as ley_nombre,
    l.tipo as ley_tipo,
    a.numero as numero_raw,
    COALESCE(
        (regexp_match(a.numero, '^(\d+)'))[1]::integer,
        0
    ) as numero_base,
    a.tipo,
    a.titulo,
    d.tipo || ' ' || d.numero as ubicacion,
    a.orden,
    (SELECT string_agg(p.contenido, E'\n\n' ORDER BY p.numero)
     FROM leyesmx.parrafos p
     WHERE p.ley = a.ley AND p.articulo_id = a.id) as contenido,
    a.tipo = 'transitorio' as es_transitorio,
    a.reformas
FROM leyesmx.articulos a
JOIN leyesmx.leyes l ON l.codigo = a.ley
LEFT JOIN leyesmx.divisiones d ON d.id = a.division_id AND d.ley = a.ley;

GRANT SELECT ON leyesmx.v_articulos TO web_anon;

-- ============================================================
-- Vista: v_divisiones
-- ============================================================
CREATE OR REPLACE VIEW leyesmx.v_divisiones AS
SELECT
    d.id,
    d.ley,
    d.padre_id,
    d.tipo,
    d.numero,
    d.nombre,
    d.numero_orden,
    (SELECT COUNT(*) FROM leyesmx.articulos a WHERE a.division_id = d.id AND a.ley = d.ley) as total_articulos
FROM leyesmx.divisiones d;

GRANT SELECT ON leyesmx.v_divisiones TO web_anon;

-- ============================================================
-- Función: buscar
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.buscar(
    q TEXT,
    leyes TEXT DEFAULT NULL,
    tipos TEXT DEFAULT NULL,
    limite INTEGER DEFAULT 20,
    pagina INTEGER DEFAULT 1
)
RETURNS TABLE (
    id INTEGER,
    ley VARCHAR,
    ley_nombre TEXT,
    ley_tipo VARCHAR,
    numero_raw VARCHAR,
    numero_base INTEGER,
    tipo VARCHAR,
    ubicacion TEXT,
    contenido TEXT,
    es_transitorio BOOLEAN,
    reformas TEXT,
    relevancia REAL,
    snippet TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH contenido_articulos AS (
        SELECT
            a.id,
            a.ley,
            l.nombre as ley_nombre,
            l.tipo as ley_tipo,
            a.numero as numero_raw,
            COALESCE((regexp_match(a.numero, '^(\d+)'))[1]::integer, 0) as numero_base,
            a.tipo,
            d.tipo || ' ' || d.numero as ubicacion,
            string_agg(p.contenido, E'\n\n' ORDER BY p.numero) as contenido,
            a.tipo = 'transitorio' as es_transitorio,
            a.reformas
        FROM leyesmx.articulos a
        JOIN leyesmx.leyes l ON l.codigo = a.ley
        LEFT JOIN leyesmx.divisiones d ON d.id = a.division_id AND d.ley = a.ley
        LEFT JOIN leyesmx.parrafos p ON p.ley = a.ley AND p.articulo_id = a.id
        WHERE (leyes IS NULL OR a.ley = ANY(string_to_array(leyes, ',')))
          AND (tipos IS NULL OR l.tipo = ANY(string_to_array(tipos, ',')))
        GROUP BY a.id, a.ley, l.nombre, l.tipo, a.numero, a.tipo, d.tipo, d.numero, a.reformas
    )
    SELECT
        ca.id,
        ca.ley,
        ca.ley_nombre,
        ca.ley_tipo,
        ca.numero_raw,
        ca.numero_base,
        ca.tipo,
        ca.ubicacion,
        ca.contenido,
        ca.es_transitorio,
        ca.reformas,
        ts_rank(to_tsvector('spanish', ca.contenido), plainto_tsquery('spanish', q)) as relevancia,
        ts_headline('spanish', ca.contenido, plainto_tsquery('spanish', q),
            'StartSel=<mark>, StopSel=</mark>, MaxWords=50, MinWords=20') as snippet
    FROM contenido_articulos ca
    WHERE to_tsvector('spanish', ca.contenido) @@ plainto_tsquery('spanish', q)
       OR ca.numero_raw ILIKE '%' || q || '%'
    ORDER BY relevancia DESC
    LIMIT limite
    OFFSET (pagina - 1) * limite;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.buscar TO web_anon;

-- ============================================================
-- Función: articulo (por ID)
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.articulo(art_id INTEGER)
RETURNS TABLE (
    id INTEGER,
    ley VARCHAR,
    ley_nombre TEXT,
    ley_tipo VARCHAR,
    numero_raw VARCHAR,
    numero_base INTEGER,
    tipo VARCHAR,
    titulo TEXT,
    ubicacion TEXT,
    contenido TEXT,
    es_transitorio BOOLEAN,
    reformas TEXT,
    referencias_salientes JSONB,
    referencias_entrantes JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id,
        a.ley,
        l.nombre,
        l.tipo,
        a.numero,
        COALESCE((regexp_match(a.numero, '^(\d+)'))[1]::integer, 0),
        a.tipo,
        a.titulo,
        d.tipo || ' ' || d.numero,
        (SELECT string_agg(p.contenido, E'\n\n' ORDER BY p.numero)
         FROM leyesmx.parrafos p WHERE p.ley = a.ley AND p.articulo_id = a.id),
        a.tipo = 'transitorio',
        a.reformas,
        NULL::JSONB,
        NULL::JSONB
    FROM leyesmx.articulos a
    JOIN leyesmx.leyes l ON l.codigo = a.ley
    LEFT JOIN leyesmx.divisiones d ON d.id = a.division_id AND d.ley = a.ley
    WHERE a.id = art_id;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.articulo TO web_anon;

-- ============================================================
-- Función: articulo_por_ley
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.articulo_por_ley(p_ley VARCHAR, p_numero VARCHAR)
RETURNS TABLE (
    id INTEGER,
    ley VARCHAR,
    ley_nombre TEXT,
    ley_tipo VARCHAR,
    numero_raw VARCHAR,
    numero_base INTEGER,
    tipo VARCHAR,
    titulo TEXT,
    ubicacion TEXT,
    contenido TEXT,
    es_transitorio BOOLEAN,
    reformas TEXT,
    referencias_salientes JSONB,
    referencias_entrantes JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id,
        a.ley,
        l.nombre,
        l.tipo,
        a.numero,
        COALESCE((regexp_match(a.numero, '^(\d+)'))[1]::integer, 0),
        a.tipo,
        a.titulo,
        d.tipo || ' ' || d.numero,
        (SELECT string_agg(p.contenido, E'\n\n' ORDER BY p.numero)
         FROM leyesmx.parrafos p WHERE p.ley = a.ley AND p.articulo_id = a.id),
        a.tipo = 'transitorio',
        a.reformas,
        NULL::JSONB,
        NULL::JSONB
    FROM leyesmx.articulos a
    JOIN leyesmx.leyes l ON l.codigo = a.ley
    LEFT JOIN leyesmx.divisiones d ON d.id = a.division_id AND d.ley = a.ley
    WHERE a.ley = p_ley AND a.numero = p_numero;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.articulo_por_ley TO web_anon;

-- ============================================================
-- Función: estructura_ley
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.estructura_ley(ley_codigo VARCHAR)
RETURNS TABLE (
    id INTEGER,
    tipo VARCHAR,
    numero VARCHAR,
    nombre TEXT,
    path_texto TEXT,
    nivel SMALLINT,
    total_articulos BIGINT,
    primer_articulo VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.tipo,
        d.numero,
        d.nombre,
        d.tipo || ' ' || d.numero || COALESCE(' - ' || d.nombre, ''),
        CASE d.tipo
            WHEN 'titulo' THEN 1::SMALLINT
            WHEN 'capitulo' THEN 2::SMALLINT
            WHEN 'seccion' THEN 3::SMALLINT
            ELSE 0::SMALLINT
        END,
        (SELECT COUNT(*) FROM leyesmx.articulos a WHERE a.division_id = d.id AND a.ley = d.ley),
        (SELECT MIN(a.numero) FROM leyesmx.articulos a WHERE a.division_id = d.id AND a.ley = d.ley)
    FROM leyesmx.divisiones d
    WHERE d.ley = ley_codigo
    ORDER BY d.numero_orden;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.estructura_ley TO web_anon;

-- ============================================================
-- Función: stats
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.stats()
RETURNS TABLE (
    codigo VARCHAR,
    nombre TEXT,
    tipo VARCHAR,
    total_divisiones BIGINT,
    total_articulos BIGINT,
    articulos_transitorios BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        l.codigo,
        l.nombre,
        l.tipo,
        (SELECT COUNT(*) FROM leyesmx.divisiones d WHERE d.ley = l.codigo),
        (SELECT COUNT(*) FROM leyesmx.articulos a WHERE a.ley = l.codigo),
        (SELECT COUNT(*) FROM leyesmx.articulos a WHERE a.ley = l.codigo AND a.tipo = 'transitorio')
    FROM leyesmx.leyes l;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.stats TO web_anon;

-- ============================================================
-- Función: navegar (anterior/siguiente)
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.navegar(art_id INTEGER)
RETURNS TABLE (
    anterior_id INTEGER,
    anterior_numero VARCHAR,
    siguiente_id INTEGER,
    siguiente_numero VARCHAR
) AS $$
DECLARE
    v_ley VARCHAR;
    v_orden SMALLINT;
BEGIN
    SELECT ley, orden INTO v_ley, v_orden
    FROM leyesmx.articulos WHERE id = art_id;

    RETURN QUERY
    SELECT
        (SELECT a.id FROM leyesmx.articulos a WHERE a.ley = v_ley AND a.orden = v_orden - 1),
        (SELECT a.numero FROM leyesmx.articulos a WHERE a.ley = v_ley AND a.orden = v_orden - 1),
        (SELECT a.id FROM leyesmx.articulos a WHERE a.ley = v_ley AND a.orden = v_orden + 1),
        (SELECT a.numero FROM leyesmx.articulos a WHERE a.ley = v_ley AND a.orden = v_orden + 1);
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.navegar TO web_anon;

-- ============================================================
-- Función: sugerencias
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.sugerencias(prefijo TEXT)
RETURNS TABLE (
    termino TEXT,
    frecuencia INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT a.numero::TEXT, 1
    FROM leyesmx.articulos a
    WHERE a.numero ILIKE prefijo || '%'
    LIMIT 10;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.sugerencias TO web_anon;

-- ============================================================
-- Función: articulos_division
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.articulos_division(div_id INTEGER, p_ley VARCHAR DEFAULT NULL)
RETURNS TABLE (
    id INTEGER,
    numero_raw VARCHAR,
    titulo TEXT,
    contenido TEXT,
    es_transitorio BOOLEAN,
    reformas TEXT,
    tipo VARCHAR,
    referencias TEXT,
    calidad JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id,
        a.numero,
        a.titulo,
        (SELECT string_agg(p.contenido, E'\n\n' ORDER BY p.numero)
         FROM leyesmx.parrafos p WHERE p.ley = a.ley AND p.articulo_id = a.id),
        a.tipo = 'transitorio',
        a.reformas,
        a.tipo,
        NULL::TEXT,
        NULL::JSONB
    FROM leyesmx.articulos a
    WHERE a.division_id = div_id
      AND (p_ley IS NULL OR a.ley = p_ley)
    ORDER BY a.orden;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.articulos_division TO web_anon;

-- ============================================================
-- Función: fracciones_articulo
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.fracciones_articulo(art_id INTEGER, p_ley VARCHAR DEFAULT NULL)
RETURNS TABLE (
    id INTEGER,
    padre_id SMALLINT,
    tipo VARCHAR,
    numero VARCHAR,
    contenido TEXT,
    orden SMALLINT,
    nivel INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.numero::INTEGER as id,
        p.padre_numero,
        p.tipo,
        p.identificador,
        p.contenido,
        p.numero,
        CASE
            WHEN p.padre_numero IS NULL THEN 0
            ELSE 1
        END
    FROM leyesmx.parrafos p
    WHERE p.articulo_id = art_id
      AND (p_ley IS NULL OR p.ley = p_ley)
    ORDER BY p.numero;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.fracciones_articulo TO web_anon;

-- ============================================================
-- Función: divisiones_articulo (breadcrumb)
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.divisiones_articulo(art_id INTEGER)
RETURNS TABLE (
    id INTEGER,
    tipo VARCHAR,
    numero VARCHAR,
    nombre TEXT,
    path_texto TEXT,
    nivel INTEGER
) AS $$
DECLARE
    v_division_id INTEGER;
    v_ley VARCHAR;
BEGIN
    SELECT division_id, ley INTO v_division_id, v_ley
    FROM leyesmx.articulos WHERE id = art_id;

    RETURN QUERY
    WITH RECURSIVE ancestros AS (
        SELECT d.id, d.padre_id, d.tipo, d.numero, d.nombre, 1 as nivel
        FROM leyesmx.divisiones d
        WHERE d.id = v_division_id AND d.ley = v_ley

        UNION ALL

        SELECT d.id, d.padre_id, d.tipo, d.numero, d.nombre, a.nivel + 1
        FROM leyesmx.divisiones d
        JOIN ancestros a ON d.id = a.padre_id
        WHERE d.ley = v_ley
    )
    SELECT
        a.id,
        a.tipo,
        a.numero,
        a.nombre,
        a.tipo || ' ' || a.numero || COALESCE(' - ' || a.nombre, ''),
        a.nivel
    FROM ancestros a
    ORDER BY a.nivel DESC;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.divisiones_articulo TO web_anon;
