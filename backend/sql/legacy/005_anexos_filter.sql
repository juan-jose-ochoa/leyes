-- ============================================================
-- LeyesMX - Migración para soportar filtro por tipo de documento
-- Permite filtrar búsquedas por: ley, reglamento, resolucion, anexo
-- ============================================================

-- Actualizar función buscar_articulos para soportar filtro por tipo
DROP FUNCTION IF EXISTS buscar_articulos(TEXT, TEXT[], BOOLEAN, INT, INT);

CREATE OR REPLACE FUNCTION buscar_articulos(
    query TEXT,
    leyes_filter TEXT[] DEFAULT NULL,
    tipos_filter TEXT[] DEFAULT NULL,  -- NUEVO: filtro por tipo de ley
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
    snippet TEXT,
    tipo VARCHAR  -- 'articulo', 'regla', 'ficha', 'criterio'
) AS $$
DECLARE
    tsquery_parsed tsquery;
BEGIN
    -- Validar parametros
    IF query IS NULL OR TRIM(query) = '' THEN
        RAISE EXCEPTION 'El termino de busqueda no puede estar vacio'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    IF limite < 1 OR limite > 100 THEN
        limite := 20;
    END IF;

    -- Parsear query con websearch
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
        COALESCE(d.path_texto, '')::TEXT as ubicacion,
        a.contenido,
        a.es_transitorio,
        a.reformas,
        ts_rank_cd(a.search_vector, tsquery_parsed, 32) as relevancia,
        ts_headline(
            'spanish_unaccent',
            a.contenido,
            tsquery_parsed,
            'MaxWords=50, MinWords=20, StartSel=<mark>, StopSel=</mark>, MaxFragments=2'
        ) as snippet,
        COALESCE(a.tipo, 'articulo') as tipo
    FROM public.articulos a
    JOIN public.leyes l ON a.ley_id = l.id
    LEFT JOIN public.divisiones d ON a.division_id = d.id
    WHERE a.search_vector @@ tsquery_parsed
      AND (leyes_filter IS NULL OR l.codigo = ANY(leyes_filter))
      AND (tipos_filter IS NULL OR l.tipo = ANY(tipos_filter))
      AND (solo_transitorios = FALSE OR a.es_transitorio = TRUE)
    ORDER BY relevancia DESC
    LIMIT limite
    OFFSET offset_num;

EXCEPTION
    WHEN invalid_parameter_value THEN
        RAISE;
    WHEN syntax_error THEN
        RAISE EXCEPTION 'Sintaxis de busqueda invalida: %', query
            USING ERRCODE = 'invalid_parameter_value';
    WHEN OTHERS THEN
        RAISE WARNING 'Error en buscar_articulos: % - %', SQLSTATE, SQLERRM;
        RETURN;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION buscar_articulos IS 'Busqueda full-text con ranking, filtering por ley y tipo, y snippets';

-- Actualizar wrapper API para soportar filtro por tipo
DROP FUNCTION IF EXISTS api.buscar(TEXT, TEXT, BOOLEAN, INT, INT);

CREATE OR REPLACE FUNCTION api.buscar(
    q TEXT,
    leyes TEXT DEFAULT NULL,
    tipos TEXT DEFAULT NULL,  -- NUEVO: filtro por tipo (ley,reglamento,resolucion,anexo)
    solo_transitorios BOOLEAN DEFAULT FALSE,
    limite INT DEFAULT 20,
    pagina INT DEFAULT 1
)
RETURNS TABLE(
    id INT,
    ley VARCHAR,
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
    snippet TEXT,
    tipo VARCHAR  -- 'articulo', 'regla', 'ficha', 'criterio'
) AS $$
DECLARE
    leyes_arr TEXT[];
    tipos_arr TEXT[];
    offset_calc INT;
BEGIN
    -- Validar query
    IF q IS NULL OR TRIM(q) = '' THEN
        RAISE EXCEPTION 'El termino de busqueda no puede estar vacio'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    -- Convertir string de leyes a array
    IF leyes IS NOT NULL AND leyes != '' THEN
        leyes_arr := string_to_array(UPPER(leyes), ',');
    END IF;

    -- Convertir string de tipos a array
    IF tipos IS NOT NULL AND tipos != '' THEN
        tipos_arr := string_to_array(LOWER(tipos), ',');
    END IF;

    offset_calc := (pagina - 1) * limite;

    -- Registrar busqueda para sugerencias
    PERFORM public.registrar_busqueda(q);

    RETURN QUERY
    SELECT
        ba.id,
        ba.ley_codigo,
        ba.ley_nombre,
        ba.ley_tipo,
        ba.numero_raw,
        ba.numero_base,
        ba.sufijo,
        ba.ubicacion,
        ba.contenido,
        ba.es_transitorio,
        ba.reformas,
        ba.relevancia,
        ba.snippet,
        ba.tipo
    FROM public.buscar_articulos(q, leyes_arr, tipos_arr, solo_transitorios, limite, offset_calc) ba;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION api.buscar IS 'Busqueda full-text. Parametros: q, leyes (CFF,LISR), tipos (ley,reglamento,resolucion,anexo), limite, pagina';

-- Otorgar permisos
GRANT EXECUTE ON FUNCTION api.buscar(TEXT, TEXT, TEXT, BOOLEAN, INT, INT) TO web_anon;
