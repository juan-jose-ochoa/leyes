-- ============================================================
-- LeyesMX - Integridad de Divisiones
-- Constraints y triggers para garantizar jerarquía correcta
-- ============================================================

-- ============================================================
-- 1. TRIGGER: Calcular path_ids, path_texto, nivel automáticamente
-- ============================================================

CREATE OR REPLACE FUNCTION calcular_paths_division()
RETURNS TRIGGER AS $$
DECLARE
    padre RECORD;
    tipo_display VARCHAR(20);
BEGIN
    -- Mapeo de tipo a texto para display
    tipo_display := CASE NEW.tipo
        WHEN 'libro' THEN 'Libro'
        WHEN 'titulo' THEN 'Título'
        WHEN 'capitulo' THEN 'Capítulo'
        WHEN 'seccion' THEN 'Sección'
        WHEN 'subseccion' THEN 'Subsección'
        ELSE NEW.tipo
    END;

    IF NEW.padre_id IS NULL THEN
        -- Es raíz (libro o título)
        NEW.path_ids := ARRAY[NEW.id];
        NEW.path_texto := tipo_display || ' ' || COALESCE(NEW.numero, '');
        NEW.nivel := 0;
    ELSE
        -- Tiene padre, heredar su path
        SELECT path_ids, path_texto, nivel
        INTO padre
        FROM divisiones
        WHERE id = NEW.padre_id;

        IF padre IS NULL THEN
            RAISE EXCEPTION 'padre_id % no existe', NEW.padre_id;
        END IF;

        NEW.path_ids := padre.path_ids || NEW.id;
        NEW.path_texto := padre.path_texto || ' > ' || tipo_display || ' ' || COALESCE(NEW.numero, '');
        NEW.nivel := padre.nivel + 1;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger BEFORE INSERT para calcular paths (necesita el ID)
-- Usamos un enfoque de dos pasos: INSERT sin path_ids, luego UPDATE

CREATE OR REPLACE FUNCTION calcular_paths_division_after()
RETURNS TRIGGER AS $$
DECLARE
    padre RECORD;
    tipo_display VARCHAR(20);
    nuevo_path_texto TEXT;
    nuevo_nivel INT;
BEGIN
    -- Mapeo de tipo a texto para display
    tipo_display := CASE NEW.tipo
        WHEN 'libro' THEN 'Libro'
        WHEN 'titulo' THEN 'Título'
        WHEN 'capitulo' THEN 'Capítulo'
        WHEN 'seccion' THEN 'Sección'
        WHEN 'subseccion' THEN 'Subsección'
        ELSE NEW.tipo
    END;

    IF NEW.padre_id IS NULL THEN
        -- Es raíz (libro o título)
        UPDATE divisiones SET
            path_ids = ARRAY[NEW.id],
            path_texto = tipo_display || ' ' || COALESCE(NEW.numero, ''),
            nivel = 0
        WHERE id = NEW.id;
    ELSE
        -- Tiene padre, heredar su path
        SELECT path_ids, path_texto, nivel
        INTO padre
        FROM divisiones
        WHERE id = NEW.padre_id;

        IF padre IS NULL THEN
            RAISE EXCEPTION 'padre_id % no existe', NEW.padre_id;
        END IF;

        nuevo_path_texto := padre.path_texto || ' > ' || tipo_display || ' ' || COALESCE(NEW.numero, '');
        nuevo_nivel := padre.nivel + 1;

        UPDATE divisiones SET
            path_ids = padre.path_ids || NEW.id,
            path_texto = nuevo_path_texto,
            nivel = nuevo_nivel
        WHERE id = NEW.id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_divisiones_paths ON divisiones;
CREATE TRIGGER trg_divisiones_paths
    AFTER INSERT ON divisiones
    FOR EACH ROW
    EXECUTE FUNCTION calcular_paths_division_after();

-- ============================================================
-- 2. TRIGGER: Validar jerarquía correcta
-- ============================================================

CREATE OR REPLACE FUNCTION validar_jerarquia_division()
RETURNS TRIGGER AS $$
DECLARE
    padre_tipo VARCHAR(20);
BEGIN
    -- Si no tiene padre, solo puede ser libro o título
    IF NEW.padre_id IS NULL THEN
        IF NEW.tipo NOT IN ('libro', 'titulo') THEN
            RAISE EXCEPTION '% debe tener padre_id (solo libro/titulo pueden ser raíz)', NEW.tipo;
        END IF;
        RETURN NEW;
    END IF;

    -- Obtener tipo del padre
    SELECT tipo INTO padre_tipo
    FROM divisiones
    WHERE id = NEW.padre_id;

    IF padre_tipo IS NULL THEN
        RAISE EXCEPTION 'padre_id % no existe', NEW.padre_id;
    END IF;

    -- Validar jerarquía según tipo
    CASE NEW.tipo
        WHEN 'titulo' THEN
            IF padre_tipo NOT IN ('libro') THEN
                RAISE EXCEPTION 'titulo debe tener padre libro, no %', padre_tipo;
            END IF;
        WHEN 'capitulo' THEN
            IF padre_tipo NOT IN ('titulo') THEN
                RAISE EXCEPTION 'capitulo debe tener padre titulo, no %', padre_tipo;
            END IF;
        WHEN 'seccion' THEN
            IF padre_tipo NOT IN ('capitulo') THEN
                RAISE EXCEPTION 'seccion debe tener padre capitulo, no %', padre_tipo;
            END IF;
        WHEN 'subseccion' THEN
            IF padre_tipo NOT IN ('seccion') THEN
                RAISE EXCEPTION 'subseccion debe tener padre seccion, no %', padre_tipo;
            END IF;
        ELSE
            -- Otros tipos no tienen restricción específica
            NULL;
    END CASE;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_divisiones_jerarquia ON divisiones;
CREATE TRIGGER trg_divisiones_jerarquia
    BEFORE INSERT OR UPDATE ON divisiones
    FOR EACH ROW
    EXECUTE FUNCTION validar_jerarquia_division();

-- ============================================================
-- 3. CONSTRAINT: padre_id obligatorio excepto títulos/libros
-- (Se activa después de migrar datos existentes)
-- ============================================================

-- Primero eliminar constraint si existe (para poder recrearlo)
ALTER TABLE divisiones DROP CONSTRAINT IF EXISTS divisiones_padre_required;

-- Crear constraint como NOT VALID (no valida datos existentes)
ALTER TABLE divisiones ADD CONSTRAINT divisiones_padre_required
CHECK (
    tipo IN ('libro', 'titulo') OR padre_id IS NOT NULL
) NOT VALID;

-- NOTA: Para activar el constraint sobre datos existentes, ejecutar:
-- ALTER TABLE divisiones VALIDATE CONSTRAINT divisiones_padre_required;

-- ============================================================
-- 4. COMENTARIOS
-- ============================================================

COMMENT ON CONSTRAINT divisiones_padre_required ON divisiones IS
'Garantiza que capítulo, sección y subsección siempre tengan padre';

COMMENT ON FUNCTION validar_jerarquia_division() IS
'Valida que la jerarquía sea correcta: título→capítulo→sección→subsección';

COMMENT ON FUNCTION calcular_paths_division_after() IS
'Calcula automáticamente path_ids, path_texto y nivel basándose en padre_id';

-- ============================================================
-- 5. FUNCIÓN: Buscar división por tipo+numero (URLs estables)
-- ============================================================

CREATE OR REPLACE FUNCTION api.division_por_tipo_numero(
    p_ley TEXT,
    p_tipo TEXT,
    p_numero TEXT
)
RETURNS TABLE (
    id INT,
    ley_codigo TEXT,
    ley_nombre TEXT,
    ley_tipo TEXT,
    div_tipo TEXT,
    numero TEXT,
    nombre TEXT,
    path_texto TEXT,
    total_articulos BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        l.codigo::TEXT,
        l.nombre::TEXT,
        l.tipo::TEXT,
        d.tipo::TEXT,
        d.numero::TEXT,
        d.nombre::TEXT,
        d.path_texto::TEXT,
        COUNT(a.id)
    FROM public.divisiones d
    JOIN public.leyes l ON d.ley_id = l.id
    LEFT JOIN public.articulos a ON a.division_id = d.id
    WHERE l.codigo = p_ley
      AND d.tipo = p_tipo
      AND d.numero = p_numero
    GROUP BY d.id, l.codigo, l.nombre, l.tipo, d.tipo, d.numero, d.nombre, d.path_texto;
END;
$$ LANGUAGE plpgsql;

GRANT EXECUTE ON FUNCTION api.division_por_tipo_numero TO web_anon;

COMMENT ON FUNCTION api.division_por_tipo_numero IS
'Busca división por ley, tipo y número para URLs estables (no depende de IDs)';

-- ============================================================
-- 6. FUNCIÓN: Buscar referencias legales (para UI expandible)
-- ============================================================

CREATE OR REPLACE FUNCTION api.buscar_referencias(p_referencias text)
RETURNS TABLE(ley_codigo text, numero text, titulo text, contenido text, encontrado boolean)
LANGUAGE plpgsql
AS $function$
DECLARE
    clean_refs TEXT;
    ref_parts TEXT[];
    current_ley TEXT;
    num TEXT;
    part TEXT;
    ley_real TEXT;
    pos INT;
BEGIN
    -- 1. Encontrar dónde empiezan las referencias reales (primer código de ley)
    pos := position('CFF' in upper(p_referencias));
    IF pos = 0 THEN pos := position('LISR' in upper(p_referencias)); END IF;
    IF pos = 0 THEN pos := position('LIVA' in upper(p_referencias)); END IF;
    IF pos = 0 THEN pos := position('LIEPS' in upper(p_referencias)); END IF;
    IF pos = 0 THEN pos := position('RCFF' in upper(p_referencias)); END IF;
    IF pos = 0 THEN pos := position('RMF' in upper(p_referencias)); END IF;
    IF pos = 0 THEN pos := position('LSS' in upper(p_referencias)); END IF;
    IF pos = 0 THEN pos := position('LFT' in upper(p_referencias)); END IF;
    
    IF pos = 0 THEN RETURN; END IF;
    
    -- Tomar solo desde el primer código de ley
    clean_refs := substring(p_referencias from pos);
    
    -- 2. Dividir por comas o punto y coma
    ref_parts := regexp_split_to_array(clean_refs, '[,;]\s*');
    current_ley := NULL;
    
    FOREACH part IN ARRAY ref_parts LOOP
        part := trim(part);
        IF part = '' THEN CONTINUE; END IF;
        
        -- Detectar si empieza con código de ley
        IF part ~* '^(CFF|LISR|LIVA|LIEPS|LIC|LFD|RCFF|RLISR|RLIVA|RISR|RMF|RISAT|LSS|LFT|CPEUM)\s*' THEN
            current_ley := upper((regexp_matches(part, '^([A-Za-z]+)'))[1]);
            part := regexp_replace(part, '^[A-Za-z]+\s*', '');
        END IF;
        
        IF current_ley IS NULL THEN CONTINUE; END IF;
        
        -- Mapear código a código real en BD (RMF -> RMF2025, etc.)
        ley_real := CASE current_ley
            WHEN 'RMF' THEN 'RMF2025'
            WHEN 'RLISR' THEN 'RISR'
            WHEN 'RLIVA' THEN 'RIVA'
            ELSE current_ley
        END;
        
        -- Procesar números
        FOREACH num IN ARRAY regexp_split_to_array(part, '\s*,\s*|\s+y\s+') LOOP
            num := trim(regexp_replace(regexp_replace(num, '[o°]\.\s*$', ''), '\.\s*$', ''));
            
            IF num = '' OR num ~ '^[a-z]' OR num ~ '^(al|del|de|la|el|los|las|en|por|para)$' THEN 
                CONTINUE; 
            END IF;
            
            -- Buscar con UPPER() para case-insensitive (17-H Bis = 17-H BIS)
            RETURN QUERY
            SELECT
                current_ley::TEXT,
                num::TEXT,
                a.titulo::TEXT,
                LEFT(a.contenido, 500)::TEXT,
                TRUE
            FROM articulos a
            JOIN leyes l ON a.ley_id = l.id
            WHERE l.codigo = ley_real
              AND (UPPER(a.numero_raw) = UPPER(num)
                   OR UPPER(a.numero_raw) = UPPER(num || '.')
                   OR (num ~ '^\d+$' AND a.numero_raw ~* ('^' || num || '[.-]'))
              )
            LIMIT 1;
            
            IF NOT FOUND THEN
                RETURN QUERY SELECT current_ley::TEXT, num::TEXT, NULL::TEXT, NULL::TEXT, FALSE;
            END IF;
        END LOOP;
    END LOOP;
    
    RETURN;
END;
$function$;

GRANT EXECUTE ON FUNCTION api.buscar_referencias TO web_anon;

COMMENT ON FUNCTION api.buscar_referencias IS
'Parsea string de referencias legales (ej: "CFF 29, 31, LISR 86") y retorna artículos encontrados';
