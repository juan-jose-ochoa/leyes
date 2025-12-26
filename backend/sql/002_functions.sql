-- ============================================================
-- LeyesMX - Funciones de Busqueda v2
-- Full-text search y busqueda semantica
-- Adaptado para schema con divisiones jerarquicas
-- ============================================================

-- ============================================================
-- Funcion: buscar_articulos
-- Busqueda full-text con ranking y highlighting
-- ============================================================
CREATE OR REPLACE FUNCTION buscar_articulos(
    query TEXT,
    leyes_filter TEXT[] DEFAULT NULL,
    solo_transitorios BOOLEAN DEFAULT FALSE,
    limite INT DEFAULT 20,
    offset_num INT DEFAULT 0
)
RETURNS TABLE(
    id INT,
    ley_id INT,
    ley_codigo VARCHAR,
    ley_nombre VARCHAR,
    ley_tipo VARCHAR,
    numero_raw VARCHAR,
    numero_base INT,
    sufijo VARCHAR,
    ubicacion TEXT,
    contenido TEXT,
    es_transitorio BOOLEAN,
    reformas TEXT,
    relevancia REAL,
    snippet TEXT
) AS $$
DECLARE
    tsquery_parsed tsquery;
BEGIN
    -- Parsear query con websearch (soporta "frases exactas", -exclusiones, OR)
    tsquery_parsed := websearch_to_tsquery('spanish_unaccent', query);

    RETURN QUERY
    SELECT
        a.id,
        a.ley_id,
        l.codigo,
        l.nombre,
        l.tipo,
        a.numero_raw,
        a.numero_base,
        a.sufijo,
        COALESCE(d.path_texto, '') as ubicacion,
        a.contenido,
        a.es_transitorio,
        a.reformas,
        ts_rank_cd(a.search_vector, tsquery_parsed, 32) as relevancia,
        ts_headline(
            'spanish_unaccent',
            a.contenido,
            tsquery_parsed,
            'MaxWords=50, MinWords=20, StartSel=<mark>, StopSel=</mark>, MaxFragments=2'
        ) as snippet
    FROM articulos a
    JOIN leyes l ON a.ley_id = l.id
    LEFT JOIN divisiones d ON a.division_id = d.id
    WHERE a.search_vector @@ tsquery_parsed
      AND (leyes_filter IS NULL OR l.codigo = ANY(leyes_filter))
      AND (solo_transitorios = FALSE OR a.es_transitorio = TRUE)
    ORDER BY relevancia DESC
    LIMIT limite
    OFFSET offset_num;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Funcion: buscar_fuzzy
-- Busqueda tolerante a errores tipograficos
-- ============================================================
CREATE OR REPLACE FUNCTION buscar_fuzzy(
    query TEXT,
    limite INT DEFAULT 10
)
RETURNS TABLE(
    id INT,
    ley_codigo VARCHAR,
    numero_raw VARCHAR,
    ubicacion TEXT,
    similitud REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id,
        l.codigo,
        a.numero_raw,
        COALESCE(d.path_texto, '') as ubicacion,
        similarity(a.contenido, query) as similitud
    FROM articulos a
    JOIN leyes l ON a.ley_id = l.id
    LEFT JOIN divisiones d ON a.division_id = d.id
    WHERE a.contenido % query  -- Operador de similitud de pg_trgm
    ORDER BY similitud DESC
    LIMIT limite;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Funcion: buscar_semantico
-- Busqueda por similitud de vectores (requiere extension vector y columna embedding)
-- Esta funcion se crea como placeholder - actualizar cuando vector este disponible
-- ============================================================
-- CREATE OR REPLACE FUNCTION buscar_semantico(
--     query_embedding vector(1536),
--     limite INT DEFAULT 10,
--     umbral_similitud REAL DEFAULT 0.7
-- )
-- RETURNS TABLE(...) AS $$ ... $$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Funcion: obtener_articulo
-- Obtiene un articulo con su jerarquia y referencias
-- ============================================================
CREATE OR REPLACE FUNCTION obtener_articulo(articulo_id INT)
RETURNS TABLE(
    id INT,
    ley_codigo VARCHAR,
    ley_nombre VARCHAR,
    ley_tipo VARCHAR,
    numero_raw VARCHAR,
    numero_base INT,
    sufijo VARCHAR,
    ubicacion TEXT,
    division_tipo VARCHAR,
    contenido TEXT,
    es_transitorio BOOLEAN,
    decreto_dof VARCHAR,
    reformas TEXT,
    orden_global INT,
    referencias_salientes JSON,
    referencias_entrantes JSON
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id,
        l.codigo,
        l.nombre,
        l.tipo,
        a.numero_raw,
        a.numero_base,
        a.sufijo,
        COALESCE(d.path_texto, '') as ubicacion,
        d.tipo as division_tipo,
        a.contenido,
        a.es_transitorio,
        a.decreto_dof,
        a.reformas,
        a.orden_global,
        -- Referencias que hace este articulo
        (
            SELECT json_agg(json_build_object(
                'id', a2.id,
                'ley', l2.codigo,
                'numero_raw', a2.numero_raw,
                'tipo', rc.tipo
            ))
            FROM referencias_cruzadas rc
            JOIN articulos a2 ON rc.articulo_destino_id = a2.id
            JOIN leyes l2 ON a2.ley_id = l2.id
            WHERE rc.articulo_origen_id = a.id
        ) as referencias_salientes,
        -- Articulos que referencian a este
        (
            SELECT json_agg(json_build_object(
                'id', a2.id,
                'ley', l2.codigo,
                'numero_raw', a2.numero_raw,
                'tipo', rc.tipo
            ))
            FROM referencias_cruzadas rc
            JOIN articulos a2 ON rc.articulo_origen_id = a2.id
            JOIN leyes l2 ON a2.ley_id = l2.id
            WHERE rc.articulo_destino_id = a.id
        ) as referencias_entrantes
    FROM articulos a
    JOIN leyes l ON a.ley_id = l.id
    LEFT JOIN divisiones d ON a.division_id = d.id
    WHERE a.id = articulo_id;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Funcion: articulos_por_ley
-- Lista articulos de una ley con navegacion jerarquica
-- ============================================================
CREATE OR REPLACE FUNCTION articulos_por_ley(
    ley_codigo VARCHAR,
    limite INT DEFAULT 100,
    offset_num INT DEFAULT 0
)
RETURNS TABLE(
    id INT,
    numero_raw VARCHAR,
    numero_base INT,
    sufijo VARCHAR,
    ubicacion TEXT,
    contenido_preview TEXT,
    es_transitorio BOOLEAN,
    orden_global INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id,
        a.numero_raw,
        a.numero_base,
        a.sufijo,
        COALESCE(d.path_texto, '') as ubicacion,
        LEFT(a.contenido, 300) as contenido_preview,
        a.es_transitorio,
        a.orden_global
    FROM articulos a
    JOIN leyes l ON a.ley_id = l.id
    LEFT JOIN divisiones d ON a.division_id = d.id
    WHERE l.codigo = ley_codigo
    ORDER BY a.orden_global
    LIMIT limite
    OFFSET offset_num;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Funcion: estructura_ley
-- Obtiene la estructura jerarquica completa de una ley
-- ============================================================
CREATE OR REPLACE FUNCTION estructura_ley(ley_codigo VARCHAR)
RETURNS TABLE(
    id INT,
    tipo VARCHAR,
    numero VARCHAR,
    nombre TEXT,
    path_texto TEXT,
    nivel INT,
    total_articulos BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.tipo,
        d.numero,
        d.nombre,
        d.path_texto,
        d.nivel,
        (SELECT COUNT(*) FROM articulos a WHERE a.division_id = d.id) as total_articulos
    FROM divisiones d
    JOIN leyes l ON d.ley_id = l.id
    WHERE l.codigo = ley_codigo
    ORDER BY d.orden_global;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Funcion: articulos_por_division
-- Obtiene articulos de una division especifica
-- ============================================================
CREATE OR REPLACE FUNCTION articulos_por_division(division_id_param INT)
RETURNS TABLE(
    id INT,
    numero_raw VARCHAR,
    numero_base INT,
    sufijo VARCHAR,
    contenido TEXT,
    es_transitorio BOOLEAN,
    orden_global INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id,
        a.numero_raw,
        a.numero_base,
        a.sufijo,
        a.contenido,
        a.es_transitorio,
        a.orden_global
    FROM articulos a
    WHERE a.division_id = division_id_param
    ORDER BY a.orden_global;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Funcion: navegar_articulo
-- Obtiene el articulo anterior y siguiente para navegacion
-- ============================================================
CREATE OR REPLACE FUNCTION navegar_articulo(articulo_id INT)
RETURNS TABLE(
    anterior_id INT,
    anterior_numero VARCHAR,
    siguiente_id INT,
    siguiente_numero VARCHAR
) AS $$
DECLARE
    current_ley_id INT;
    current_orden INT;
BEGIN
    -- Obtener ley y orden del articulo actual
    SELECT a.ley_id, a.orden_global
    INTO current_ley_id, current_orden
    FROM articulos a
    WHERE a.id = articulo_id;

    RETURN QUERY
    SELECT
        (SELECT a.id FROM articulos a
         WHERE a.ley_id = current_ley_id AND a.orden_global < current_orden
         ORDER BY a.orden_global DESC LIMIT 1) as anterior_id,
        (SELECT a.numero_raw FROM articulos a
         WHERE a.ley_id = current_ley_id AND a.orden_global < current_orden
         ORDER BY a.orden_global DESC LIMIT 1) as anterior_numero,
        (SELECT a.id FROM articulos a
         WHERE a.ley_id = current_ley_id AND a.orden_global > current_orden
         ORDER BY a.orden_global ASC LIMIT 1) as siguiente_id,
        (SELECT a.numero_raw FROM articulos a
         WHERE a.ley_id = current_ley_id AND a.orden_global > current_orden
         ORDER BY a.orden_global ASC LIMIT 1) as siguiente_numero;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Funcion: registrar_busqueda
-- Registra terminos de busqueda para sugerencias
-- ============================================================
CREATE OR REPLACE FUNCTION registrar_busqueda(termino_busqueda TEXT)
RETURNS VOID AS $$
BEGIN
    INSERT INTO busquedas_frecuentes (termino, contador, ultima_busqueda)
    VALUES (LOWER(TRIM(termino_busqueda)), 1, NOW())
    ON CONFLICT (termino)
    DO UPDATE SET
        contador = busquedas_frecuentes.contador + 1,
        ultima_busqueda = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Funcion: sugerir_busquedas
-- Autocompletado basado en busquedas frecuentes
-- ============================================================
CREATE OR REPLACE FUNCTION sugerir_busquedas(
    prefijo TEXT,
    limite INT DEFAULT 5
)
RETURNS TABLE(
    termino VARCHAR,
    frecuencia INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT bf.termino, bf.contador
    FROM busquedas_frecuentes bf
    WHERE bf.termino ILIKE prefijo || '%'
    ORDER BY bf.contador DESC, bf.ultima_busqueda DESC
    LIMIT limite;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Funcion: estadisticas_leyes
-- Resumen de contenido por ley
-- ============================================================
CREATE OR REPLACE FUNCTION estadisticas_leyes()
RETURNS TABLE(
    codigo VARCHAR,
    nombre VARCHAR,
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
        (SELECT COUNT(*) FROM divisiones d WHERE d.ley_id = l.id) as total_divisiones,
        (SELECT COUNT(*) FROM articulos a WHERE a.ley_id = l.id) as total_articulos,
        (SELECT COUNT(*) FROM articulos a WHERE a.ley_id = l.id AND a.es_transitorio = TRUE) as articulos_transitorios
    FROM leyes l
    ORDER BY l.tipo, l.codigo;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- Comentarios de documentacion
-- ============================================================
COMMENT ON FUNCTION buscar_articulos IS 'Busqueda full-text con ranking, filtering y snippets';
COMMENT ON FUNCTION buscar_fuzzy IS 'Busqueda tolerante a errores tipograficos usando trigrams';
-- COMMENT ON FUNCTION buscar_semantico IS 'Busqueda por similitud de vectores (IA)';
COMMENT ON FUNCTION obtener_articulo IS 'Obtiene articulo completo con referencias cruzadas';
COMMENT ON FUNCTION articulos_por_ley IS 'Lista articulos de una ley con paginacion';
COMMENT ON FUNCTION estructura_ley IS 'Obtiene estructura jerarquica de una ley (titulos, capitulos, secciones)';
COMMENT ON FUNCTION articulos_por_division IS 'Obtiene articulos de una division especifica';
COMMENT ON FUNCTION navegar_articulo IS 'Obtiene articulo anterior y siguiente para navegacion';
COMMENT ON FUNCTION registrar_busqueda IS 'Registra terminos para sugerencias de autocompletado';
COMMENT ON FUNCTION sugerir_busquedas IS 'Autocompletado basado en busquedas frecuentes';
COMMENT ON FUNCTION estadisticas_leyes IS 'Resumen estadistico de contenido por ley';
