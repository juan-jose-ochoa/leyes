-- ============================================================
-- LeyesMX - Esquema API para PostgREST v2
-- Vistas, roles y permisos
-- Adaptado para schema con divisiones jerarquicas
-- ============================================================

-- ============================================================
-- Esquema API
-- ============================================================
CREATE SCHEMA IF NOT EXISTS api;

-- ============================================================
-- Roles de acceso
-- ============================================================

-- Rol anonimo (acceso publico sin autenticacion)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'web_anon') THEN
        CREATE ROLE web_anon NOLOGIN;
    END IF;
END
$$;

-- Rol autenticado (para futuras funciones con login)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'web_user') THEN
        CREATE ROLE web_user NOLOGIN;
    END IF;
END
$$;

-- Rol de servicio para PostgREST
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticator') THEN
        CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD 'changeme';
    END IF;
END
$$;

GRANT web_anon TO authenticator;
GRANT web_user TO authenticator;

-- ============================================================
-- Vista: api.v_leyes
-- Lista de leyes disponibles
-- Prefijo v_ para evitar ambiguedad con tablas public.*
-- ============================================================
CREATE OR REPLACE VIEW api.v_leyes AS
SELECT
    id,
    codigo,
    nombre,
    nombre_corto,
    tipo,
    url_fuente,
    fecha_publicacion,
    ultima_reforma,
    fecha_descarga,
    (SELECT COUNT(*) FROM divisiones d WHERE d.ley_id = l.id) as total_divisiones,
    (SELECT COUNT(*) FROM articulos a WHERE a.ley_id = l.id) as total_articulos
FROM public.leyes l
ORDER BY tipo, codigo;

COMMENT ON VIEW api.v_leyes IS 'Lista de leyes y reglamentos disponibles';

-- ============================================================
-- Vista: api.v_divisiones
-- Estructura jerarquica de las leyes
-- ============================================================
CREATE OR REPLACE VIEW api.v_divisiones AS
SELECT
    d.id,
    l.codigo AS ley,
    d.tipo,
    d.numero,
    d.nombre,
    d.path_texto,
    d.nivel,
    d.orden_global,
    (SELECT COUNT(*) FROM articulos a WHERE a.division_id = d.id) as total_articulos
FROM public.divisiones d
JOIN public.leyes l ON d.ley_id = l.id
ORDER BY d.ley_id, d.orden_global;

COMMENT ON VIEW api.v_divisiones IS 'Estructura jerarquica: titulos, capitulos, secciones';

-- ============================================================
-- Vista: api.v_articulos
-- Articulos con informacion de ley y ubicacion
-- ============================================================
CREATE OR REPLACE VIEW api.v_articulos AS
SELECT
    a.id,
    l.codigo AS ley,
    l.nombre AS ley_nombre,
    l.tipo AS ley_tipo,
    a.numero_raw,
    a.numero_base,
    a.sufijo,
    COALESCE(d.path_texto, '') AS ubicacion,
    a.contenido,
    a.es_transitorio,
    a.decreto_dof,
    a.reformas,
    a.orden_global,
    COALESCE(a.tipo, 'articulo') AS tipo,  -- 'articulo' o 'regla'
    a.referencias                           -- referencias RMF
FROM public.articulos a
JOIN public.leyes l ON a.ley_id = l.id
LEFT JOIN public.divisiones d ON a.division_id = d.id
ORDER BY a.ley_id, a.orden_global;

COMMENT ON VIEW api.v_articulos IS 'Articulos individuales con informacion de ley y ubicacion';

-- ============================================================
-- Vista: api.v_referencias
-- Referencias cruzadas entre articulos
-- ============================================================
CREATE OR REPLACE VIEW api.v_referencias AS
SELECT
    rc.id,
    -- Articulo origen
    ao.id AS origen_id,
    lo.codigo AS origen_ley,
    ao.numero_raw AS origen_articulo,
    -- Articulo destino
    ad.id AS destino_id,
    ld.codigo AS destino_ley,
    ad.numero_raw AS destino_articulo,
    -- Tipo de referencia
    rc.tipo,
    rc.contexto
FROM public.referencias_cruzadas rc
JOIN public.articulos ao ON rc.articulo_origen_id = ao.id
JOIN public.leyes lo ON ao.ley_id = lo.id
JOIN public.articulos ad ON rc.articulo_destino_id = ad.id
JOIN public.leyes ld ON ad.ley_id = ld.id;

COMMENT ON VIEW api.v_referencias IS 'Referencias cruzadas entre articulos';

-- ============================================================
-- Vista: api.v_estadisticas
-- Estadisticas generales del sistema
-- ============================================================
CREATE OR REPLACE VIEW api.v_estadisticas AS
SELECT
    (SELECT COUNT(*) FROM public.leyes WHERE tipo = 'ley') AS total_leyes,
    (SELECT COUNT(*) FROM public.leyes WHERE tipo = 'reglamento') AS total_reglamentos,
    (SELECT COUNT(*) FROM public.divisiones) AS total_divisiones,
    (SELECT COUNT(*) FROM public.articulos) AS total_articulos,
    (SELECT COUNT(*) FROM public.articulos WHERE es_transitorio = TRUE) AS total_transitorios,
    (SELECT COUNT(*) FROM public.referencias_cruzadas) AS total_referencias;

COMMENT ON VIEW api.v_estadisticas IS 'Estadisticas generales del sistema';

-- ============================================================
-- Funciones RPC expuestas via API
-- ============================================================

-- Wrapper para buscar_articulos expuesto en API
CREATE OR REPLACE FUNCTION api.buscar(
    q TEXT,
    leyes TEXT DEFAULT NULL,
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
    tipo VARCHAR  -- 'articulo' o 'regla'
) AS $$
DECLARE
    leyes_arr TEXT[];
    offset_calc INT;
BEGIN
    -- Validar query
    IF q IS NULL OR TRIM(q) = '' THEN
        RAISE EXCEPTION 'El termino de busqueda no puede estar vacio'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    -- Convertir string de leyes a array (ej: "CFF,LISR" -> {"CFF","LISR"})
    IF leyes IS NOT NULL AND leyes != '' THEN
        leyes_arr := string_to_array(UPPER(leyes), ',');
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
    FROM public.buscar_articulos(q, leyes_arr, solo_transitorios, limite, offset_calc) ba;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION api.buscar IS 'Busqueda full-text de articulos. Parametros: q (query), leyes (filtro), solo_transitorios, limite, pagina';

-- Wrapper para obtener_articulo expuesto en API
CREATE OR REPLACE FUNCTION api.articulo(art_id INT)
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
    referencias_entrantes JSON,
    tipo VARCHAR,
    referencias_legales TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM public.obtener_articulo(art_id);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION api.articulo IS 'Obtiene un articulo por ID con su ubicacion y referencias cruzadas';

-- Wrapper para estructura de ley
CREATE OR REPLACE FUNCTION api.estructura(ley_codigo TEXT)
RETURNS TABLE(
    id INT,
    tipo VARCHAR,
    numero VARCHAR,
    nombre TEXT,
    path_texto TEXT,
    nivel INT,
    total_articulos BIGINT,
    primer_articulo VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM public.estructura_ley(ley_codigo);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION api.estructura IS 'Obtiene la estructura jerarquica de una ley (titulos, capitulos, secciones)';

-- Funcion estructura_ley con articulos heredados (usada por frontend)
CREATE OR REPLACE FUNCTION api.estructura_ley(ley_codigo VARCHAR)
RETURNS TABLE(
    id INT,
    tipo VARCHAR,
    numero VARCHAR,
    nombre TEXT,
    path_texto TEXT,
    nivel INT,
    total_articulos BIGINT,
    primer_articulo VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE division_tree AS (
        SELECT d.id, d.id as root_id, d.padre_id
        FROM public.divisiones d
        JOIN public.leyes l ON d.ley_id = l.id
        WHERE l.codigo = ley_codigo

        UNION ALL

        SELECT child.id, dt.root_id, child.padre_id
        FROM public.divisiones child
        JOIN division_tree dt ON child.padre_id = dt.id
    ),
    articulos_por_division AS (
        SELECT
            d.id as division_id,
            COUNT(a.id)::BIGINT as direct_count,
            MIN(a.numero_raw)::VARCHAR as primer_art
        FROM public.divisiones d
        JOIN public.leyes l ON d.ley_id = l.id
        LEFT JOIN public.articulos a ON a.division_id = d.id
        WHERE l.codigo = ley_codigo
        GROUP BY d.id
    ),
    articulos_heredados AS (
        SELECT
            dt.root_id as division_id,
            COALESCE(SUM(apd.direct_count), 0)::BIGINT as total_heredado
        FROM division_tree dt
        JOIN articulos_por_division apd ON apd.division_id = dt.id
        WHERE dt.id != dt.root_id
        GROUP BY dt.root_id
    )
    SELECT
        d.id,
        d.tipo,
        d.numero,
        d.nombre,
        d.path_texto,
        d.nivel,
        (COALESCE(apd.direct_count, 0) + COALESCE(ah.total_heredado, 0))::BIGINT as total_articulos,
        apd.primer_art::VARCHAR as primer_articulo
    FROM public.divisiones d
    JOIN public.leyes l ON d.ley_id = l.id
    LEFT JOIN articulos_por_division apd ON apd.division_id = d.id
    LEFT JOIN articulos_heredados ah ON ah.division_id = d.id
    WHERE l.codigo = ley_codigo
    ORDER BY d.orden_global;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION api.estructura_ley IS 'Obtiene estructura jerarquica con articulos heredados de hijos';

-- Wrapper para articulos por division (ordena por numero de regla para RMF)
CREATE OR REPLACE FUNCTION api.articulos_division(div_id INT)
RETURNS TABLE(
    id INT,
    numero_raw VARCHAR,
    contenido TEXT,
    es_transitorio BOOLEAN,
    reformas TEXT,
    tipo VARCHAR,
    referencias TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id,
        a.numero_raw,
        a.contenido,
        a.es_transitorio,
        a.reformas,
        a.tipo,
        a.referencias
    FROM public.articulos a
    JOIN public.divisiones d ON a.division_id = d.id
    JOIN public.leyes l ON a.ley_id = l.id
    WHERE div_id = ANY(d.path_ids) OR a.division_id = div_id
    ORDER BY
        CASE
            WHEN l.tipo = 'resolucion' THEN extraer_ultimo_numero(a.numero_raw)
            ELSE a.orden_global
        END;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION api.articulos_division IS 'Obtiene articulos de una division, ordenados por numero';

-- Wrapper para navegacion de articulos
CREATE OR REPLACE FUNCTION api.navegar(art_id INT)
RETURNS TABLE(
    anterior_id INT,
    anterior_numero VARCHAR,
    siguiente_id INT,
    siguiente_numero VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM public.navegar_articulo(art_id);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION api.navegar IS 'Obtiene articulo anterior y siguiente para navegacion';

-- Wrapper para sugerencias
CREATE OR REPLACE FUNCTION api.sugerencias(prefijo TEXT)
RETURNS TABLE(
    termino VARCHAR,
    frecuencia INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM public.sugerir_busquedas(prefijo, 5);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION api.sugerencias IS 'Autocompletado de busquedas basado en historial';

-- Wrapper para estadisticas por ley
CREATE OR REPLACE FUNCTION api.stats()
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
    SELECT * FROM public.estadisticas_leyes();
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION api.stats IS 'Estadisticas detalladas por ley';

-- Wrapper para obtener articulo por ley y numero (URLs amigables)
CREATE OR REPLACE FUNCTION api.articulo_por_ley(
    p_ley TEXT,
    p_numero TEXT
)
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
    referencias_entrantes JSON,
    tipo VARCHAR,
    referencias_legales TEXT
) AS $$
DECLARE
    art_id INT;
BEGIN
    -- Buscar el ID del articulo por ley y numero
    SELECT a.id INTO art_id
    FROM public.articulos a
    JOIN public.leyes l ON a.ley_id = l.id
    WHERE UPPER(l.codigo) = UPPER(p_ley)
      AND a.numero_raw = p_numero
    LIMIT 1;

    IF art_id IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT * FROM public.obtener_articulo(art_id);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION api.articulo_por_ley IS 'Obtiene articulo por codigo de ley y numero (ej: LFT, 199)';

-- ============================================================
-- Permisos para rol anonimo
-- ============================================================

-- Acceso al esquema api
GRANT USAGE ON SCHEMA api TO web_anon;

-- Lectura de vistas
GRANT SELECT ON api.v_leyes TO web_anon;
GRANT SELECT ON api.v_divisiones TO web_anon;
GRANT SELECT ON api.v_articulos TO web_anon;
GRANT SELECT ON api.v_referencias TO web_anon;
GRANT SELECT ON api.v_estadisticas TO web_anon;

-- Ejecucion de funciones RPC
GRANT EXECUTE ON FUNCTION api.buscar(TEXT, TEXT, BOOLEAN, INT, INT) TO web_anon;
GRANT EXECUTE ON FUNCTION api.articulo(INT) TO web_anon;
GRANT EXECUTE ON FUNCTION api.estructura(TEXT) TO web_anon;
GRANT EXECUTE ON FUNCTION api.estructura_ley(VARCHAR) TO web_anon;
GRANT EXECUTE ON FUNCTION api.articulos_division(INT) TO web_anon;
GRANT EXECUTE ON FUNCTION api.navegar(INT) TO web_anon;
GRANT EXECUTE ON FUNCTION api.sugerencias(TEXT) TO web_anon;
GRANT EXECUTE ON FUNCTION api.stats() TO web_anon;
GRANT EXECUTE ON FUNCTION api.articulo_por_ley(TEXT, TEXT) TO web_anon;

-- Permisos en esquema publico (necesarios para las funciones)
GRANT USAGE ON SCHEMA public TO web_anon;
GRANT SELECT ON public.leyes TO web_anon;
GRANT SELECT ON public.divisiones TO web_anon;
GRANT SELECT ON public.articulos TO web_anon;
GRANT SELECT ON public.referencias_cruzadas TO web_anon;
GRANT SELECT ON public.busquedas_frecuentes TO web_anon;
GRANT INSERT, UPDATE ON public.busquedas_frecuentes TO web_anon;
GRANT USAGE, SELECT ON SEQUENCE busquedas_frecuentes_id_seq TO web_anon;
GRANT SELECT ON public.jerarquia_completa TO web_anon;

-- ============================================================
-- Documentacion de endpoints resultantes
-- ============================================================
/*
PostgREST expondra automaticamente:

VISTAS (GET) - Prefijo v_ para evitar ambiguedad con tablas:
  GET /v_leyes                           - Lista de leyes
  GET /v_leyes?codigo=eq.CFF             - Filtrar por codigo
  GET /v_divisiones                      - Estructura de todas las leyes
  GET /v_divisiones?ley=eq.CFF           - Estructura de una ley
  GET /v_articulos                       - Todos los articulos (paginado)
  GET /v_articulos?ley=eq.LISR           - Articulos de una ley
  GET /v_articulos?id=eq.123             - Articulo especifico
  GET /v_articulos?es_transitorio=eq.true - Articulos transitorios
  GET /v_referencias                     - Todas las referencias
  GET /v_estadisticas                    - Stats generales

FUNCIONES RPC (POST):
  POST /rpc/buscar                     - Busqueda full-text
    Body: {"q": "factura electronica", "leyes": "CFF,LISR", "limite": 20, "pagina": 1}

  POST /rpc/articulo                   - Obtener articulo con referencias
    Body: {"art_id": 123}

  POST /rpc/estructura                 - Estructura jerarquica de ley
    Body: {"ley_codigo": "CFF"}

  POST /rpc/estructura_ley             - Estructura con articulos heredados
    Body: {"ley_codigo": "RMF2025"}

  POST /rpc/articulos_division         - Articulos de una division
    Body: {"div_id": 5}

  POST /rpc/navegar                    - Navegacion anterior/siguiente
    Body: {"art_id": 123}

  POST /rpc/sugerencias                - Autocompletado
    Body: {"prefijo": "fac"}

  POST /rpc/stats                      - Stats por ley
    Body: {}
*/
