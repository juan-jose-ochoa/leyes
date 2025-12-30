-- ============================================================
-- LeyesMX - Schema leyesmx
-- Estructura normalizada para leyes mexicanas
-- PostgreSQL 15+
-- ============================================================

CREATE SCHEMA IF NOT EXISTS leyesmx;

-- ============================================================
-- Tabla: leyes
-- Catálogo de leyes con metadata de validación
-- ============================================================
CREATE TABLE leyesmx.leyes (
    codigo VARCHAR(20) PRIMARY KEY,           -- 'CFF', 'RMF2025', 'LISR'
    nombre TEXT NOT NULL,
    nombre_corto VARCHAR(50),
    tipo VARCHAR(20) NOT NULL
        CHECK (tipo IN ('codigo', 'ley', 'reglamento', 'resolucion')),

    -- Versionamiento (para leyes anuales como RMF)
    ley_base VARCHAR(20),                     -- NULL para leyes base, 'RMF' para RMF2025/RMF2026
    anio SMALLINT,                            -- NULL para leyes permanentes, 2025/2026 para RMF

    fecha_publicacion DATE,
    ultima_reforma DATE,

    -- Fuentes oficiales
    url_fuente TEXT,
    urls_relacionadas TEXT[],

    -- Metadata de validación
    divisiones_permitidas TEXT[] NOT NULL,
    parrafos_permitidos TEXT[] NOT NULL,
    estructura_esperada JSONB,

    -- Auditoría
    fecha_verificacion DATE,
    checksum_global VARCHAR(64)
);

COMMENT ON TABLE leyesmx.leyes IS 'Catálogo de leyes fiscales mexicanas';

-- ============================================================
-- Tabla: divisiones
-- Estructura jerárquica (título, capítulo, sección, libro)
-- ============================================================
CREATE TABLE leyesmx.divisiones (
    id SERIAL PRIMARY KEY,
    ley VARCHAR(20) NOT NULL,
    padre_id INTEGER,
    tipo VARCHAR(20) NOT NULL,
    numero VARCHAR(20) NOT NULL,
    numero_orden SMALLINT NOT NULL,
    nombre TEXT,

    UNIQUE (id, ley),

    FOREIGN KEY (ley)
        REFERENCES leyesmx.leyes(codigo) ON DELETE CASCADE,

    -- Garantiza que el padre sea de la MISMA ley
    FOREIGN KEY (padre_id, ley)
        REFERENCES leyesmx.divisiones(id, ley) ON DELETE CASCADE
);

CREATE INDEX divisiones_ley_idx ON leyesmx.divisiones(ley);
CREATE INDEX divisiones_padre_idx ON leyesmx.divisiones(padre_id);
CREATE INDEX divisiones_tipo_idx ON leyesmx.divisiones(tipo);

COMMENT ON TABLE leyesmx.divisiones IS 'Estructura jerárquica: títulos, capítulos, secciones';

-- ============================================================
-- Tabla: articulos
-- Metadatos de artículos/reglas
-- ============================================================
CREATE TABLE leyesmx.articulos (
    id SERIAL PRIMARY KEY,
    ley VARCHAR(20) NOT NULL,
    division_id INTEGER NOT NULL,
    numero VARCHAR(20) NOT NULL,
    titulo TEXT,
    tipo VARCHAR(20) NOT NULL DEFAULT 'articulo'
        CHECK (tipo IN ('articulo', 'regla', 'transitorio', 'ficha', 'criterio')),
    decreto_dof TEXT,
    reformas TEXT,
    orden SMALLINT NOT NULL,

    UNIQUE (ley, numero),
    UNIQUE (id, ley),

    FOREIGN KEY (ley)
        REFERENCES leyesmx.leyes(codigo) ON DELETE CASCADE,

    -- Garantiza que la división sea de la MISMA ley
    FOREIGN KEY (division_id, ley)
        REFERENCES leyesmx.divisiones(id, ley) ON DELETE CASCADE
);

CREATE INDEX articulos_ley_idx ON leyesmx.articulos(ley);
CREATE INDEX articulos_division_idx ON leyesmx.articulos(division_id);
CREATE INDEX articulos_tipo_idx ON leyesmx.articulos(tipo);
CREATE INDEX articulos_search_idx ON leyesmx.articulos
    USING GIN(to_tsvector('spanish', numero || ' ' || COALESCE(titulo, '')));

COMMENT ON TABLE leyesmx.articulos IS 'Artículos y reglas de las leyes';

-- ============================================================
-- Tabla: parrafos
-- Contenido legal (fracciones, incisos, numerales, texto)
-- ============================================================
CREATE TABLE leyesmx.parrafos (
    ley VARCHAR(20) NOT NULL,
    articulo_id INTEGER NOT NULL,
    numero SMALLINT NOT NULL,
    padre_numero SMALLINT,
    tipo VARCHAR(20) NOT NULL,
    identificador VARCHAR(20),
    contenido TEXT NOT NULL,

    -- Coordenadas X del PDF (para detección de jerarquía)
    x_id SMALLINT,                            -- X del identificador (o inicio de línea)
    x_texto SMALLINT,                         -- X donde empieza el contenido

    -- Auditoría
    checksum VARCHAR(64) GENERATED ALWAYS AS (
        encode(sha256(contenido::bytea), 'hex')
    ) STORED,
    fecha_importacion TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (ley, articulo_id, numero),

    -- Garantiza que el artículo sea de la MISMA ley
    FOREIGN KEY (articulo_id, ley)
        REFERENCES leyesmx.articulos(id, ley) ON DELETE CASCADE,

    -- Garantiza que el padre sea del MISMO artículo Y MISMA ley
    FOREIGN KEY (ley, articulo_id, padre_numero)
        REFERENCES leyesmx.parrafos(ley, articulo_id, numero) ON DELETE CASCADE
);

CREATE INDEX parrafos_ley_idx ON leyesmx.parrafos(ley);
CREATE INDEX parrafos_articulo_idx ON leyesmx.parrafos(articulo_id);
CREATE INDEX parrafos_tipo_idx ON leyesmx.parrafos(tipo);
CREATE INDEX parrafos_padre_idx ON leyesmx.parrafos(ley, articulo_id, padre_numero);
CREATE INDEX parrafos_search_idx ON leyesmx.parrafos
    USING GIN(to_tsvector('spanish', contenido));

COMMENT ON TABLE leyesmx.parrafos IS 'Párrafos de artículos: texto, fracciones, incisos, numerales';
COMMENT ON COLUMN leyesmx.parrafos.x_id IS 'Coordenada X del identificador en el PDF';
COMMENT ON COLUMN leyesmx.parrafos.x_texto IS 'Coordenada X donde inicia el texto en el PDF';

-- ============================================================
-- Vistas de conveniencia
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
    (SELECT COUNT(*) FROM leyesmx.articulos a WHERE a.ley = l.codigo) AS total_articulos
FROM leyesmx.leyes l;

CREATE OR REPLACE VIEW leyesmx.v_divisiones AS
SELECT
    id,
    ley,
    padre_id,
    tipo,
    numero,
    nombre,
    numero_orden,
    (SELECT COUNT(*) FROM leyesmx.articulos a
     WHERE a.division_id = d.id AND a.ley = d.ley) AS total_articulos
FROM leyesmx.divisiones d;

CREATE OR REPLACE VIEW leyesmx.v_articulos AS
SELECT
    a.id,
    a.ley,
    l.nombre AS ley_nombre,
    l.tipo AS ley_tipo,
    a.numero AS numero_raw,
    COALESCE((regexp_match(a.numero, '^(\d+)'))[1]::INTEGER, 0) AS numero_base,
    a.tipo,
    a.titulo,
    d.tipo || ' ' || d.numero AS ubicacion,
    a.orden,
    (SELECT string_agg(p.contenido, E'\n\n' ORDER BY p.numero)
     FROM leyesmx.parrafos p
     WHERE p.ley = a.ley AND p.articulo_id = a.id
       AND p.padre_numero IS NULL AND p.tipo = 'texto') AS contenido,
    a.tipo = 'transitorio' AS es_transitorio,
    a.reformas
FROM leyesmx.articulos a
JOIN leyesmx.leyes l ON l.codigo = a.ley
LEFT JOIN leyesmx.divisiones d ON d.id = a.division_id AND d.ley = a.ley;

-- ============================================================
-- Función: validar_estructura
-- Verifica que la estructura importada coincida con lo esperado
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.validar_estructura(p_ley VARCHAR(20))
RETURNS TABLE (
    elemento VARCHAR(20),
    esperado INTEGER,
    actual BIGINT,
    ok BOOLEAN
) AS $$
DECLARE
    v_esperado JSONB;
    v_key TEXT;
BEGIN
    SELECT estructura_esperada INTO v_esperado
    FROM leyesmx.leyes WHERE codigo = p_ley;

    IF v_esperado IS NULL THEN
        RETURN;
    END IF;

    -- Validar divisiones
    FOR v_key IN SELECT jsonb_object_keys(v_esperado) LOOP
        IF v_key != 'articulos' AND v_key != 'reglas' THEN
            RETURN QUERY
            SELECT
                v_key::VARCHAR(20),
                (v_esperado->>v_key)::INTEGER,
                COUNT(*)::BIGINT,
                COUNT(*) = (v_esperado->>v_key)::INTEGER
            FROM leyesmx.divisiones d
            WHERE d.ley = p_ley AND d.tipo = rtrim(v_key, 's');
        END IF;
    END LOOP;

    -- Validar artículos
    IF v_esperado ? 'articulos' THEN
        RETURN QUERY
        SELECT
            'articulos'::VARCHAR(20),
            (v_esperado->>'articulos')::INTEGER,
            COUNT(*)::BIGINT,
            COUNT(*) = (v_esperado->>'articulos')::INTEGER
        FROM leyesmx.articulos a
        WHERE a.ley = p_ley;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Función: stats
-- Estadísticas generales del schema
-- ============================================================
CREATE OR REPLACE FUNCTION leyesmx.stats()
RETURNS TABLE (
    ley VARCHAR(20),
    nombre TEXT,
    divisiones BIGINT,
    articulos BIGINT,
    parrafos BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        l.codigo,
        l.nombre,
        (SELECT COUNT(*) FROM leyesmx.divisiones d WHERE d.ley = l.codigo),
        (SELECT COUNT(*) FROM leyesmx.articulos a WHERE a.ley = l.codigo),
        (SELECT COUNT(*) FROM leyesmx.parrafos p WHERE p.ley = l.codigo)
    FROM leyesmx.leyes l
    ORDER BY l.codigo;
END;
$$ LANGUAGE plpgsql;
