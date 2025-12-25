# Scripts de Leyes Mexicanas

Scripts para descargar y convertir leyes fiscales y laborales de México.

## Requisitos

```bash
# Activar entorno virtual
source .venv/bin/activate

# Dependencias (ya instaladas)
pip install requests beautifulsoup4 tenacity unidecode tqdm python-docx pdf2docx playwright
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

## Flujo de trabajo típico

### Primera vez:
```bash
# 1. Descargar todas las leyes
python scripts/descargar_leyes_mx.py

# 2. Convertir a todos los formatos
python scripts/convertir_ley.py
```

### Actualización periódica:
```bash
# 1. Verificar si hay cambios
python scripts/descargar_leyes_mx.py
# El script indicará qué archivos cambiaron

# 2. Si hubo cambios, reconvertir
python scripts/convertir_ley.py
```

---

## Leyes incluidas

| Código | Ley |
|--------|-----|
| CFF | Código Fiscal de la Federación |
| LFT | Ley Federal del Trabajo |
| LISR | Ley del Impuesto Sobre la Renta |
| LIVA | Ley del Impuesto al Valor Agregado |
| LIEPS | Ley del Impuesto Especial sobre Producción y Servicios |
| LSS | Ley del Seguro Social |

## Reglamentos incluidos

| Código | Reglamento |
|--------|------------|
| RCFF | Reglamento del CFF |
| RISR | Reglamento de la Ley del ISR |
| RIVA | Reglamento de la Ley del IVA |
| RLIEPS | Reglamento de la Ley del IEPS |
| RLFT | Reglamento de la LFT |
| RLSS | Reglamento del Seguro Social |
| RACERF | Reglamento de Afiliación del IMSS |

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
