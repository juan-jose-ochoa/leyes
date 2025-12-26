-- ============================================================
-- LeyesMX - Esquema de Base de Datos v2
-- Estructura jerárquica normalizada para leyes mexicanas
-- PostgreSQL 16 + pgvector
-- ============================================================

-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- Trigrams para busqueda fuzzy
CREATE EXTENSION IF NOT EXISTS unaccent;      -- Ignorar acentos en busquedas

-- pgvector para embeddings IA (requiere superuser - ejecutar como postgres si falla)
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION WHEN insufficient_privilege THEN
    RAISE NOTICE 'Extension vector no instalada - ejecutar como superuser para busqueda semantica';
END $$;

-- ============================================================
-- Configuracion de busqueda en espanol
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'spanish_unaccent') THEN
        CREATE TEXT SEARCH CONFIGURATION spanish_unaccent (COPY = spanish);
        ALTER TEXT SEARCH CONFIGURATION spanish_unaccent
            ALTER MAPPING FOR hword, hword_part, word
            WITH unaccent, spanish_stem;
    END IF;
END $$;

-- ============================================================
-- Tabla: leyes
-- Catálogo de leyes y reglamentos
-- ============================================================
CREATE TABLE leyes (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL,      -- CFF, LFT, LISR, etc.
    nombre VARCHAR(300) NOT NULL,            -- Nombre completo
    nombre_corto VARCHAR(100),               -- Nombre abreviado
    tipo VARCHAR(20) NOT NULL                -- 'ley' o 'reglamento'
        CHECK (tipo IN ('ley', 'reglamento')),

    -- Metadatos de origen
    url_fuente TEXT,                         -- URL original de descarga
    sha256 VARCHAR(64),                      -- Hash del PDF original
    fecha_publicacion DATE,                  -- Fecha DOF original
    ultima_reforma DATE,                     -- Última reforma DOF
    fecha_descarga TIMESTAMPTZ,              -- Cuándo se descargó

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE leyes IS 'Catálogo de leyes y reglamentos fiscales/laborales mexicanos';

-- ============================================================
-- Tabla: divisiones
-- Estructura jerárquica: Libros, Títulos, Capítulos, Secciones
-- ============================================================
CREATE TABLE divisiones (
    id SERIAL PRIMARY KEY,
    ley_id INTEGER NOT NULL REFERENCES leyes(id) ON DELETE CASCADE,
    padre_id INTEGER REFERENCES divisiones(id) ON DELETE CASCADE,

    tipo VARCHAR(20) NOT NULL               -- 'libro', 'titulo', 'capitulo', 'seccion'
        CHECK (tipo IN ('libro', 'titulo', 'capitulo', 'seccion')),

    numero VARCHAR(30),                      -- 'PRIMERO', 'I', 'UNICA', '1', etc.
    numero_orden INTEGER,                    -- Orden numérico para sorting (1, 2, 3...)
    nombre TEXT,                             -- Nombre/descripción de la división

    -- Para reconstruir jerarquía completa eficientemente
    path_ids INTEGER[],                      -- Array de IDs de ancestros [abuelo, padre, self]
    path_texto TEXT,                         -- "TITULO I > CAPITULO II > SECCION I"
    nivel INTEGER DEFAULT 0,                 -- Profundidad en el árbol (0=raíz)

    orden_global INTEGER,                    -- Orden absoluto en el documento

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_divisiones_ley ON divisiones(ley_id);
CREATE INDEX idx_divisiones_padre ON divisiones(padre_id);
CREATE INDEX idx_divisiones_tipo ON divisiones(tipo);
CREATE INDEX idx_divisiones_path ON divisiones USING GIN(path_ids);
CREATE INDEX idx_divisiones_orden ON divisiones(ley_id, orden_global);

COMMENT ON TABLE divisiones IS 'Estructura jerárquica de las leyes: libros, títulos, capítulos, secciones';

-- ============================================================
-- Tabla: articulos
-- Artículos individuales
-- ============================================================
CREATE TABLE articulos (
    id SERIAL PRIMARY KEY,
    ley_id INTEGER NOT NULL REFERENCES leyes(id) ON DELETE CASCADE,
    division_id INTEGER REFERENCES divisiones(id) ON DELETE SET NULL,

    -- Identificación del artículo
    numero_raw VARCHAR(30) NOT NULL,         -- Texto original: "1o", "2-Bis", "84-E"
    numero_base INTEGER,                     -- Número base: 1, 2, 84
    sufijo VARCHAR(20),                      -- Sufijo: NULL, "Bis", "Ter", "A", "E"
    ordinal VARCHAR(5),                      -- "o", "a" (para 1o, 2a, etc.)

    -- Contenido
    contenido TEXT NOT NULL,

    -- Metadatos
    es_transitorio BOOLEAN DEFAULT FALSE,
    decreto_dof VARCHAR(100),                -- "DOF 12-11-2021" para transitorios
    decreto_descripcion TEXT,                -- Descripción del decreto de reforma

    -- Referencias DOF de reformas a este artículo
    reformas TEXT,                           -- "Artículo reformado DOF 01-01-2020..."

    -- Orden para navegación
    orden_global INTEGER,                    -- Orden absoluto en el documento

    -- Full-text search
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('spanish_unaccent', coalesce(numero_raw, '')), 'A') ||
        setweight(to_tsvector('spanish_unaccent', coalesce(contenido, '')), 'B')
    ) STORED,

    -- Vector embedding para busqueda semantica (agregar columna cuando extension vector este disponible)
    -- embedding vector(1536),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_articulos_ley ON articulos(ley_id);
CREATE INDEX idx_articulos_division ON articulos(division_id);
CREATE INDEX idx_articulos_numero ON articulos(ley_id, numero_base, sufijo);
CREATE INDEX idx_articulos_ley_numero_raw ON articulos(ley_id, numero_raw);
CREATE INDEX idx_articulos_transitorio ON articulos(ley_id, es_transitorio);
CREATE INDEX idx_articulos_orden ON articulos(ley_id, orden_global);
CREATE INDEX idx_articulos_search ON articulos USING GIN(search_vector);
CREATE INDEX idx_articulos_contenido_trgm ON articulos USING GIN(contenido gin_trgm_ops);

COMMENT ON TABLE articulos IS 'Artículos de las leyes con estructura de numeración detallada';
COMMENT ON COLUMN articulos.numero_raw IS 'Número del artículo tal como aparece: 1o, 2-Bis, 84-E';
COMMENT ON COLUMN articulos.numero_base IS 'Número base para ordenamiento: 1, 2, 84';
COMMENT ON COLUMN articulos.sufijo IS 'Sufijo del artículo: Bis, Ter, A, B, E, etc.';

-- ============================================================
-- Tabla: fracciones
-- Subdivisiones de artículos: fracciones, incisos, párrafos
-- ============================================================
CREATE TABLE fracciones (
    id SERIAL PRIMARY KEY,
    articulo_id INTEGER NOT NULL REFERENCES articulos(id) ON DELETE CASCADE,
    padre_id INTEGER REFERENCES fracciones(id) ON DELETE CASCADE,

    tipo VARCHAR(20) NOT NULL               -- 'fraccion', 'inciso', 'parrafo', 'numeral'
        CHECK (tipo IN ('fraccion', 'inciso', 'parrafo', 'numeral', 'apartado')),

    numero VARCHAR(20),                      -- 'I', 'II', 'a)', '1.', 'A'
    numero_orden INTEGER,                    -- Orden numérico

    contenido TEXT NOT NULL,

    orden INTEGER,                           -- Orden dentro del artículo

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fracciones_articulo ON fracciones(articulo_id);
CREATE INDEX idx_fracciones_padre ON fracciones(padre_id);
CREATE INDEX idx_fracciones_orden ON fracciones(articulo_id, orden);

COMMENT ON TABLE fracciones IS 'Subdivisiones de artículos: fracciones (I, II), incisos (a, b), párrafos';

-- ============================================================
-- Tabla: referencias_cruzadas
-- Relaciones entre artículos
-- ============================================================
CREATE TABLE referencias_cruzadas (
    id SERIAL PRIMARY KEY,
    articulo_origen_id INTEGER NOT NULL REFERENCES articulos(id) ON DELETE CASCADE,
    articulo_destino_id INTEGER NOT NULL REFERENCES articulos(id) ON DELETE CASCADE,

    tipo VARCHAR(30) NOT NULL               -- 'cita', 'remision', 'excepcion', 'complemento'
        CHECK (tipo IN ('cita', 'remision', 'excepcion', 'complemento', 'definicion')),

    contexto TEXT,                          -- Fragmento donde se menciona

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(articulo_origen_id, articulo_destino_id, tipo)
);

CREATE INDEX idx_referencias_origen ON referencias_cruzadas(articulo_origen_id);
CREATE INDEX idx_referencias_destino ON referencias_cruzadas(articulo_destino_id);

COMMENT ON TABLE referencias_cruzadas IS 'Referencias entre artículos detectadas automáticamente';

-- ============================================================
-- Tabla: busquedas_frecuentes
-- Cache de términos más buscados
-- ============================================================
CREATE TABLE busquedas_frecuentes (
    id SERIAL PRIMARY KEY,
    termino VARCHAR(200) NOT NULL UNIQUE,
    contador INTEGER DEFAULT 1,
    ultima_busqueda TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_busquedas_contador ON busquedas_frecuentes(contador DESC);

-- ============================================================
-- Vista materializada: jerarquia_completa
-- Para navegación eficiente de la estructura
-- ============================================================
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
    a.orden_global
FROM articulos a
JOIN leyes l ON a.ley_id = l.id
LEFT JOIN divisiones d ON a.division_id = d.id
ORDER BY a.ley_id, a.orden_global;

CREATE UNIQUE INDEX idx_jerarquia_articulo ON jerarquia_completa(articulo_id);
CREATE INDEX idx_jerarquia_ley ON jerarquia_completa(ley_id);
CREATE INDEX idx_jerarquia_codigo ON jerarquia_completa(ley_codigo);

COMMENT ON MATERIALIZED VIEW jerarquia_completa IS 'Vista desnormalizada para consultas rápidas de navegación';

-- ============================================================
-- Triggers
-- ============================================================

-- Actualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_leyes_updated_at
    BEFORE UPDATE ON leyes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_articulos_updated_at
    BEFORE UPDATE ON articulos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Refrescar vista materializada después de cambios
CREATE OR REPLACE FUNCTION refresh_jerarquia()
RETURNS TRIGGER AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY jerarquia_completa;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Nota: En producción, refrescar con un job programado en lugar de trigger
-- CREATE TRIGGER trg_refresh_jerarquia
--     AFTER INSERT OR UPDATE OR DELETE ON articulos
--     FOR EACH STATEMENT EXECUTE FUNCTION refresh_jerarquia();

-- ============================================================
-- Función helper: Parsear número de artículo
-- ============================================================
CREATE OR REPLACE FUNCTION parsear_numero_articulo(numero TEXT)
RETURNS TABLE(numero_base INTEGER, sufijo TEXT, ordinal TEXT) AS $$
DECLARE
    match_result TEXT[];
BEGIN
    -- Extraer partes: "84-E" -> base=84, sufijo=E
    -- "1o" -> base=1, ordinal=o
    -- "2 Bis" -> base=2, sufijo=Bis

    SELECT regexp_matches(
        numero,
        '^(\d+)\s*([oa])?\s*[-\s]*(Bis|Ter|Qu[áa]ter|Quinquies|Sexies|[A-Z])?$',
        'i'
    ) INTO match_result;

    IF match_result IS NOT NULL THEN
        RETURN QUERY SELECT
            match_result[1]::INTEGER,
            NULLIF(UPPER(match_result[3]), ''),
            NULLIF(LOWER(match_result[2]), '');
    ELSE
        -- Fallback: intentar extraer solo el número
        RETURN QUERY SELECT
            (regexp_replace(numero, '[^0-9]', '', 'g'))::INTEGER,
            NULL::TEXT,
            NULL::TEXT;
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION parsear_numero_articulo IS 'Extrae número base, sufijo y ordinal de un número de artículo';
