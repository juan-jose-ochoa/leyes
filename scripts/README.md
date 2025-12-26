# Scripts de Leyes Mexicanas

Scripts para descargar, convertir y procesar leyes fiscales y laborales de México.

## Requisitos

```bash
# Activar entorno virtual
source .venv/bin/activate

# Dependencias (ya instaladas)
pip install requests beautifulsoup4 tenacity unidecode tqdm python-docx pdf2docx playwright psycopg2-binary
```

## Scripts disponibles

### 1. `descargar_leyes_mx.py` - Descarga leyes y reglamentos

**Cuándo usarlo:**
- Primera vez que configuras el proyecto
- Periódicamente para detectar actualizaciones (cambios en las leyes)
- Después de que se publiquen reformas en el DOF

**Qué hace:**
- Descarga PDFs de Cámara de Diputados, SAT y DOF
- Solo descarga leyes fiscales/laborales filtradas (CFF, LFT, LISR, LIVA, LIEPS, LSS)
- Detecta cambios comparando SHA256 de archivos
- Genera manifest.json con metadatos

**Cómo usarlo:**
```bash
cd /home/jochoa/Java/workspace/leyes
source .venv/bin/activate
python scripts/descargar_leyes_mx.py
```

**Salida:**
```
doc/
├── leyes/{codigo}/          # PDFs de leyes
├── reglamentos/{codigo}/    # PDFs de reglamentos
└── manifest.json            # Metadatos y hashes
```

---

### 2. `convertir_ley.py` - Convierte PDFs a múltiples formatos

**Cuándo usarlo:**
- Después de descargar nuevas leyes o actualizaciones
- Para regenerar formatos si se modifica el parser

**Qué hace:**
- Convierte PDF → DOCX → Markdown, JSON, SQLite
- Extrae estructura: títulos, capítulos, artículos
- Crea base de datos con búsqueda de texto completo (FTS5)

**Cómo usarlo:**
```bash
cd /home/jochoa/Java/workspace/leyes
source .venv/bin/activate
python scripts/convertir_ley.py
```

**Salida por cada ley:**
```
doc/leyes/{codigo}/
├── {nombre}.pdf      # Original
├── {nombre}.docx     # Convertido de PDF
├── {nombre}.md       # Markdown estructurado
├── {nombre}.json     # JSON con artículos
└── {nombre}.db       # SQLite con FTS5
```

**Ejemplo de consulta SQLite:**
```sql
-- Buscar artículos sobre "factura"
SELECT articulo, substr(contenido, 1, 200)
FROM articulos_fts
WHERE articulos_fts MATCH 'factura';
```

---

### 3. `urls_conocidas.py` - Módulo de configuración

**No ejecutar directamente.** Es un módulo usado por `descargar_leyes_mx.py`.

Contiene:
- URLs conocidas de leyes en Cámara de Diputados
- Patrones para identificar archivos

---

### 4. `descargar_rmf.py` - Descarga Resolución Miscelánea Fiscal

**Cuándo usarlo:**
- Para obtener la RMF del año actual
- Cuando se publique una nueva modificación a la RMF

**Qué hace:**
- Descarga la RMF compilada desde el portal del SAT
- Guarda en `doc/rmf/`

**Cómo usarlo:**
```bash
python scripts/descargar_rmf.py
```

---

### 5. `parsear_rmf.py` - Parser especializado para RMF

**Cuándo usarlo:**
- Después de descargar la RMF
- Si se modifica el parser para mejorar la extracción

**Qué hace:**
- Parsea la estructura de la RMF (Títulos, Capítulos, Secciones, Reglas)
- Extrae el campo "Referencias" al final de cada regla (ej: `CFF 10, LISR 27`)
- Genera JSON estructurado

**Patrones de RMF:**

| Elemento | Patrón | Ejemplo |
|----------|--------|---------|
| Título | `^\d+\.\s+(.+)$` | `2. Código Fiscal de la Federación` |
| Capítulo | `^Capítulo\s+(\d+\.\d+)` | `Capítulo 2.1. Disposiciones generales` |
| Regla | `^(\d+\.\d+\.\d+)\.\s*` | `2.1.1. Cobro de créditos fiscales...` |

**Cómo usarlo:**
```bash
python scripts/parsear_rmf.py
```

---

### 6. `extraer_fracciones.py` - Extracción de estructura interna de artículos

**Cuándo usarlo:**
- Después de importar todas las leyes a PostgreSQL
- Si se agregan nuevas leyes o se modifica el parser

**Qué hace:**
- Parsea el contenido de cada artículo
- Extrae estructura jerárquica:
  - Fracciones: I., II., III. (números romanos)
  - Incisos: a), b), c) (letras minúsculas)
  - Numerales: 1., 2., 3. (números arábigos)
  - Apartados: A., B., C. (letras mayúsculas)
  - Párrafos: texto sin identificador
- Inserta en tabla `fracciones` con relaciones padre-hijo

**Cómo usarlo:**
```bash
python scripts/extraer_fracciones.py
```

**Salida esperada:**
```
Artículos con estructura: 1,040
Total elementos extraídos: 11,148

Por tipo:
  parrafo: 5,668
  fraccion: 4,022
  inciso: 1,168
  numeral: 269
  apartado: 21
```

---

### 7. `extraer_referencias.py` - Extracción de referencias cruzadas

**Cuándo usarlo:**
- Después de importar todas las leyes a PostgreSQL
- Si se agregan nuevas leyes o se modifica el parser

**Qué hace:**
- Extrae referencias cruzadas entre artículos
- Fuentes de extracción:
  - Campo `referencias` de RMF: `CFF 10, LISR 27, RCFF 13`
  - Contenido de artículos: `artículo 14-B de este Código`
- Ignora referencias a la Constitución (`artículo 21 Constitucional`)
- Inserta en tabla `referencias_cruzadas`

**Cómo usarlo:**
```bash
python scripts/extraer_referencias.py
```

**Salida esperada:**
```
Extrayendo referencias cruzadas...
Construyendo índice de artículos...
  3536 artículos indexados
Extrayendo referencias del contenido...
  5092 referencias encontradas
Resolviendo e insertando...
Total referencias en BD: 3180

Referencias por ley origen:
  RMF2025: 878
  LISR: 582
  CFF: 504
  LFT: 397
  ...
```

---

## Flujo de trabajo típico

### Primera vez (setup completo):
```bash
# 1. Descargar todas las leyes
python scripts/descargar_leyes_mx.py

# 2. Convertir a todos los formatos
python scripts/convertir_ley.py

# 3. Descargar y procesar RMF
python scripts/descargar_rmf.py

# 4. Importar a PostgreSQL
python backend/scripts/importar_leyes.py
python backend/scripts/importar_rmf.py

# 5. Extraer estructura de artículos (fracciones, incisos, numerales)
python scripts/extraer_fracciones.py

# 6. Extraer referencias cruzadas
python scripts/extraer_referencias.py
```

### Actualización periódica:
```bash
# 1. Verificar si hay cambios en leyes
python scripts/descargar_leyes_mx.py
# El script indicará qué archivos cambiaron

# 2. Si hubo cambios, reconvertir
python scripts/convertir_ley.py

# 3. Re-importar y regenerar estructura
python backend/scripts/importar_leyes.py
python scripts/extraer_fracciones.py
python scripts/extraer_referencias.py
```

### Actualización de RMF (cuando SAT publique nueva versión):
```bash
python scripts/descargar_rmf.py
python backend/scripts/importar_rmf.py
python scripts/extraer_referencias.py
```

---

## Documentos incluidos

### Leyes

| Código | Ley |
|--------|-----|
| CFF | Código Fiscal de la Federación |
| LFT | Ley Federal del Trabajo |
| LISR | Ley del Impuesto Sobre la Renta |
| LIVA | Ley del Impuesto al Valor Agregado |
| LIEPS | Ley del Impuesto Especial sobre Producción y Servicios |
| LSS | Ley del Seguro Social |

### Reglamentos

| Código | Reglamento |
|--------|------------|
| RCFF | Reglamento del CFF |
| RISR | Reglamento de la Ley del ISR |
| RIVA | Reglamento de la Ley del IVA |
| RLIEPS | Reglamento de la Ley del IEPS |
| RLFT | Reglamento de la LFT |
| RLSS | Reglamento del Seguro Social |
| RACERF | Reglamento de Afiliación del IMSS |

### Resoluciones

| Código | Resolución |
|--------|------------|
| RMF2025 | Resolución Miscelánea Fiscal 2025 |

---

## Agregar nuevas leyes

Editar `scripts/descargar_leyes_mx.py`:

```python
# Agregar a LEYES_PERMITIDAS
LEYES_PERMITIDAS = {
    "CFF", "LFT", "LIEPS", "LISR", "LIVA", "LSS",
    "NUEVA_LEY",  # Agregar aquí
}
```

Luego editar `scripts/convertir_ley.py`:

```python
DOCUMENTOS = {
    # ...
    BASE_DIR / "doc/leyes/nueva_ley": "Nombre de la Nueva Ley",
}
```
