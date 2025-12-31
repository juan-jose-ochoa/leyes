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
    -- Solo párrafos introductorios (texto a nivel artículo, sin padre)
    (SELECT string_agg(p.contenido, E'\n\n' ORDER BY p.numero)
     FROM leyesmx.parrafos p
     WHERE p.ley = a.ley
       AND p.articulo_id = a.id
       AND p.padre_numero IS NULL
       AND p.tipo = 'texto') as contenido,
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
-- Vista: v_articulos_completos
-- Base común para funciones de artículos (DRY)
-- ============================================================
CREATE OR REPLACE VIEW leyesmx.v_articulos_completos AS
SELECT
    a.id,
    a.ley,
    l.nombre AS ley_nombre,
    l.tipo AS ley_tipo,
    a.numero AS numero_raw,
    COALESCE((regexp_match(a.numero, '^(\d+)'))[1]::integer, 0) AS numero_base,
    a.tipo,
    a.titulo,
    d.tipo || ' ' || d.numero AS ubicacion,
    (SELECT string_agg(p.contenido, E'\n\n' ORDER BY p.numero)
     FROM leyesmx.parrafos p WHERE p.ley = a.ley AND p.articulo_id = a.id) AS contenido,
    a.tipo = 'transitorio' AS es_transitorio,
    a.reformas,
    a.referencias AS referencias_legales,
    NULL::JSONB AS referencias_salientes,
    NULL::JSONB AS referencias_entrantes
FROM leyesmx.articulos a
JOIN leyesmx.leyes l ON l.codigo = a.ley
LEFT JOIN leyesmx.divisiones d ON d.id = a.division_id AND d.ley = a.ley;

GRANT SELECT ON leyesmx.v_articulos_completos TO web_anon;

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
    referencias_legales TEXT,
    referencias_salientes JSONB,
    referencias_entrantes JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT v.id, v.ley, v.ley_nombre, v.ley_tipo, v.numero_raw, v.numero_base,
           v.tipo, v.titulo, v.ubicacion, v.contenido, v.es_transitorio,
           v.reformas, v.referencias_legales, v.referencias_salientes, v.referencias_entrantes
    FROM leyesmx.v_articulos_completos v
    WHERE v.id = art_id;
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
    referencias_legales TEXT,
    referencias_salientes JSONB,
    referencias_entrantes JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT v.id, v.ley, v.ley_nombre, v.ley_tipo, v.numero_raw, v.numero_base,
           v.tipo, v.titulo, v.ubicacion, v.contenido, v.es_transitorio,
           v.reformas, v.referencias_legales, v.referencias_salientes, v.referencias_entrantes
    FROM leyesmx.v_articulos_completos v
    WHERE v.ley = p_ley AND v.numero_raw = p_numero;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.articulo_por_ley TO web_anon;

-- ============================================================
-- Función: estructura_ley
-- ============================================================
DROP FUNCTION IF EXISTS leyesmx.estructura_ley(VARCHAR);
CREATE OR REPLACE FUNCTION leyesmx.estructura_ley(ley_codigo VARCHAR)
RETURNS TABLE (
    id INTEGER,
    tipo VARCHAR,
    numero VARCHAR,
    nombre TEXT,
    path_texto TEXT,
    nivel SMALLINT,
    total_articulos BIGINT,
    primer_articulo VARCHAR,
    ultimo_articulo VARCHAR,
    padre_id INTEGER
) AS $$
BEGIN
    -- Usa CTE recursivo para contar artículos en toda la jerarquía descendiente
    -- Funciona para cualquier profundidad: libro->titulo->capitulo->seccion->etc
    RETURN QUERY
    WITH RECURSIVE descendientes AS (
        -- Caso base: la división misma
        SELECT d.id as raiz_id, d.id as hijo_id, d.ley
        FROM leyesmx.divisiones d
        WHERE d.ley = ley_codigo

        UNION ALL

        -- Recursión: hijos de cada división
        SELECT anc.raiz_id, child.id, child.ley
        FROM descendientes anc
        JOIN leyesmx.divisiones child ON child.padre_id = anc.hijo_id AND child.ley = anc.ley
    ),
    conteos AS (
        -- Contar artículos de todas las divisiones descendientes
        SELECT
            anc.raiz_id,
            COUNT(a.id) as total
        FROM descendientes anc
        JOIN leyesmx.articulos a ON a.division_id = anc.hijo_id AND a.ley = anc.ley
        GROUP BY anc.raiz_id
    )
    SELECT
        d.id,
        d.tipo,
        d.numero,
        d.nombre,
        d.tipo || ' ' || d.numero || COALESCE(' - ' || d.nombre, ''),
        CASE d.tipo
            WHEN 'libro' THEN 0::SMALLINT
            WHEN 'titulo' THEN 1::SMALLINT
            WHEN 'capitulo' THEN 2::SMALLINT
            WHEN 'seccion' THEN 3::SMALLINT
            ELSE 4::SMALLINT
        END,
        COALESCE(c.total, 0)::BIGINT,
        (SELECT MIN(a.numero)::VARCHAR
         FROM leyesmx.articulos a
         WHERE a.division_id = d.id AND a.ley = d.ley),
        (SELECT MAX(a.numero)::VARCHAR
         FROM leyesmx.articulos a
         WHERE a.division_id = d.id AND a.ley = d.ley),
        d.padre_id
    FROM leyesmx.divisiones d
    LEFT JOIN conteos c ON c.raiz_id = d.id
    WHERE d.ley = ley_codigo
    ORDER BY d.numero_orden;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.estructura_ley TO web_anon;

-- ============================================================
-- Función: divisiones_hijas
-- Devuelve las divisiones hijas directas de una división padre
-- ============================================================
DROP FUNCTION IF EXISTS leyesmx.divisiones_hijas(INTEGER);
CREATE OR REPLACE FUNCTION leyesmx.divisiones_hijas(div_id INTEGER)
RETURNS TABLE (
    id INTEGER,
    tipo VARCHAR,
    numero VARCHAR,
    nombre TEXT,
    path_texto TEXT,
    nivel SMALLINT,
    total_articulos BIGINT,
    primer_articulo VARCHAR,
    ultimo_articulo VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE descendientes AS (
        SELECT d.id as raiz_id, d.id as hijo_id, d.ley
        FROM leyesmx.divisiones d
        WHERE d.padre_id = div_id

        UNION ALL

        SELECT anc.raiz_id, child.id, child.ley
        FROM descendientes anc
        JOIN leyesmx.divisiones child ON child.padre_id = anc.hijo_id AND child.ley = anc.ley
    ),
    conteos AS (
        SELECT
            anc.raiz_id,
            COUNT(a.id) as total
        FROM descendientes anc
        JOIN leyesmx.articulos a ON a.division_id = anc.hijo_id AND a.ley = anc.ley
        GROUP BY anc.raiz_id
    )
    SELECT
        d.id,
        d.tipo,
        d.numero,
        d.nombre,
        d.tipo || ' ' || d.numero || COALESCE(' - ' || d.nombre, ''),
        CASE d.tipo
            WHEN 'libro' THEN 0::SMALLINT
            WHEN 'titulo' THEN 1::SMALLINT
            WHEN 'capitulo' THEN 2::SMALLINT
            WHEN 'seccion' THEN 3::SMALLINT
            ELSE 4::SMALLINT
        END,
        COALESCE(c.total, 0)::BIGINT,
        (SELECT MIN(a.numero)::VARCHAR
         FROM leyesmx.articulos a
         WHERE a.division_id = d.id AND a.ley = d.ley),
        (SELECT MAX(a.numero)::VARCHAR
         FROM leyesmx.articulos a
         WHERE a.division_id = d.id AND a.ley = d.ley)
    FROM leyesmx.divisiones d
    LEFT JOIN conteos c ON c.raiz_id = d.id
    WHERE d.padre_id = div_id
    ORDER BY d.numero_orden;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.divisiones_hijas TO web_anon;

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
        -- Solo párrafos introductorios (texto a nivel artículo, sin padre)
        (SELECT string_agg(p.contenido, E'\n\n' ORDER BY p.numero)
         FROM leyesmx.parrafos p
         WHERE p.ley = a.ley
           AND p.articulo_id = a.id
           AND p.padre_numero IS NULL
           AND p.tipo = 'texto'),
        a.tipo = 'transitorio',
        a.reformas,
        a.tipo,
        a.referencias,
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
-- Retorna párrafos con nivel jerárquico calculado recursivamente
-- es_continuacion: true si es párrafo de continuación (texto con nivel > 0)
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.fracciones_articulo(art_id INTEGER, p_ley VARCHAR DEFAULT NULL)
RETURNS TABLE (
    id INTEGER,
    padre_id SMALLINT,
    tipo VARCHAR,
    numero VARCHAR,
    contenido TEXT,
    orden SMALLINT,
    nivel INTEGER,
    es_continuacion BOOLEAN,
    referencias TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE jerarquia AS (
        -- Nivel 0: párrafos sin padre
        SELECT
            p.numero::INTEGER as id,
            p.padre_numero,
            p.tipo,
            p.identificador,
            p.contenido,
            p.numero as orden,
            0 as nivel,
            p.ley,
            p.articulo_id,
            p.referencias
        FROM leyesmx.parrafos p
        WHERE p.articulo_id = art_id
          AND (p_ley IS NULL OR p.ley = p_ley)
          AND p.padre_numero IS NULL

        UNION ALL

        -- Niveles siguientes: hijos de párrafos ya procesados
        SELECT
            p.numero::INTEGER,
            p.padre_numero,
            p.tipo,
            p.identificador,
            p.contenido,
            p.numero,
            j.nivel + 1,
            p.ley,
            p.articulo_id,
            p.referencias
        FROM leyesmx.parrafos p
        JOIN jerarquia j ON p.padre_numero = j.id
                        AND p.ley = j.ley
                        AND p.articulo_id = j.articulo_id
        WHERE p.articulo_id = art_id
          AND (p_ley IS NULL OR p.ley = p_ley)
    )
    SELECT
        j.id,
        j.padre_numero,
        j.tipo,
        j.identificador,
        j.contenido,
        j.orden,
        j.nivel,
        (j.tipo = 'texto' AND j.nivel > 0)::BOOLEAN,
        j.referencias
    FROM jerarquia j
    ORDER BY j.orden;
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
    SELECT a.division_id, a.ley INTO v_division_id, v_ley
    FROM leyesmx.articulos a WHERE a.id = art_id;

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

-- ============================================================
-- Función: division_por_path
-- Resuelve división por path jerárquico: titulo/PRIMERO/capitulo/I
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.division_por_path(
    p_ley VARCHAR,
    p_path TEXT
)
RETURNS TABLE (
    id INTEGER,
    ley_codigo VARCHAR,
    ley_nombre TEXT,
    ley_tipo VARCHAR,
    div_tipo VARCHAR,
    numero VARCHAR,
    nombre TEXT,
    path_texto TEXT,
    total_articulos BIGINT
) AS $$
DECLARE
    v_parts TEXT[];
    v_current_id INTEGER := NULL;
    v_tipo TEXT;
    v_numero TEXT;
    v_i INTEGER;
BEGIN
    -- Parsear path: "titulo/PRIMERO/capitulo/I" -> ['titulo','PRIMERO','capitulo','I']
    v_parts := string_to_array(p_path, '/');

    -- Validar que tengamos pares tipo/numero
    IF array_length(v_parts, 1) IS NULL OR array_length(v_parts, 1) % 2 != 0 THEN
        RETURN;
    END IF;

    -- Recorrer en pares (tipo, numero)
    FOR v_i IN 1..array_length(v_parts, 1) BY 2 LOOP
        v_tipo := v_parts[v_i];
        v_numero := v_parts[v_i + 1];

        -- Buscar división que coincida con tipo, numero y padre
        SELECT d.id INTO v_current_id
        FROM leyesmx.divisiones d
        WHERE d.ley = p_ley
          AND LOWER(d.tipo) = LOWER(v_tipo)
          AND UPPER(d.numero) = UPPER(v_numero)
          AND (
              (v_current_id IS NULL AND d.padre_id IS NULL)
              OR d.padre_id = v_current_id
          );

        -- Si no encontramos, retornar vacío
        IF v_current_id IS NULL THEN
            RETURN;
        END IF;
    END LOOP;

    -- Retornar la división encontrada con su info completa
    RETURN QUERY
    WITH RECURSIVE ancestros AS (
        SELECT d.id, d.padre_id, d.tipo, d.numero, d.nombre, 1 as nivel
        FROM leyesmx.divisiones d
        WHERE d.id = v_current_id AND d.ley = p_ley

        UNION ALL

        SELECT d.id, d.padre_id, d.tipo, d.numero, d.nombre, a.nivel + 1
        FROM leyesmx.divisiones d
        JOIN ancestros a ON d.id = a.padre_id
        WHERE d.ley = p_ley
    ),
    path_completo AS (
        SELECT string_agg(
            a.tipo || ' ' || a.numero || COALESCE(' - ' || a.nombre, ''),
            ' > ' ORDER BY a.nivel DESC
        ) as path_texto
        FROM ancestros a
    ),
    conteo AS (
        SELECT COUNT(a.id) as total
        FROM leyesmx.articulos a
        WHERE a.division_id = v_current_id AND a.ley = p_ley
    )
    SELECT
        d.id,
        d.ley,
        l.nombre,
        l.tipo,
        d.tipo,
        d.numero,
        d.nombre,
        pc.path_texto,
        c.total
    FROM leyesmx.divisiones d
    JOIN leyesmx.leyes l ON l.codigo = d.ley
    CROSS JOIN path_completo pc
    CROSS JOIN conteo c
    WHERE d.id = v_current_id AND d.ley = p_ley;
END;
$$ LANGUAGE plpgsql STABLE;

GRANT EXECUTE ON FUNCTION leyesmx.division_por_path TO web_anon;
