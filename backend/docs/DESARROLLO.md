# LeyesMX - Flujo de Desarrollo

## Arquitectura

```
PDF (fuente oficial)
    │
    ▼ extraer_mapa.py (PyMuPDF - outline)
backend/etl/data/{ley}/mapa_estructura.json
    │
    ▼ extraer.py (PyMuPDF - coordenadas X, bold)
backend/etl/data/{ley}/contenido.json
    │
    ▼ generar-datos-astro.py
frontend-astro/src/data/{ley}/*.json
    │
    ▼ astro build
Cloudflare Pages (SSG)
```

**Fuentes de verdad:**
- `mapa_estructura.json` - Estructura jerárquica (títulos, capítulos, secciones)
- `contenido.json` - Contenido de artículos y párrafos

**No se permiten cambios manuales** en los JSON. Todo debe emanar de los scripts de extracción.

---

## Pipeline Completo (5 etapas)

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  1. MAPA     │ -> │ 2. APROBAR   │ -> │ 3. EXTRAER   │ -> │ 4. VALIDAR   │ -> │ 5. GENERAR   │
│  (estructura)│    │  (manual)    │    │  (contenido) │    │  (integridad)│    │  (astro)     │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

---

### Etapa 1: Extraer Mapa de Estructura

```bash
python backend/etl/extraer_mapa.py CFF
```

**Genera:** `backend/etl/data/cff/mapa_estructura.json`

Extrae del outline del PDF:
- Títulos, capítulos, secciones, subsecciones
- Asignación de artículos a cada división
- Páginas de cada elemento

---

### Etapa 2: Aprobar Estructura (MANUAL)

```bash
# Revisar el mapa generado
cat backend/etl/data/cff/mapa_estructura.json

# Comparar con el PDF en Okular/Evince
# Verificar que títulos/capítulos coinciden
```

---

### Etapa 3: Extraer Contenido

```bash
python backend/etl/extraer.py CFF
```

**Genera:** `backend/etl/data/cff/contenido.json`

Extrae del texto del PDF usando **coordenadas X** para jerarquía:
- X~85: Fracción (I., II.)
- X~114: Inciso (a), b))
- X~142: Numeral (1., 2.)

**Nota:** La estructura (títulos/capítulos) viene de `mapa_estructura.json`, no se extrae aquí.

---

### Etapa 4: Validar

```bash
python backend/etl/validar.py CFF
```

Verifica integridad de los datos extraídos.

---

### Etapa 5: Generar Datos para Astro

```bash
python backend/scripts/generar-datos-astro.py
```

**Genera en `frontend-astro/src/data/`:**

| Archivo | Contenido |
|---------|-----------|
| `catalogo.json` | Lista de todas las leyes con metadatos |
| `{ley}/articulos.json` | Artículos con párrafos |
| `{ley}/estructura.json` | Divisiones jerárquicas para navegación |
| `{ley}/referencias.json` | Referencias cruzadas entre artículos |
| `{ley}/tooltips.json` | Tooltips para referencias estructurales |

**IMPORTANTE:** Este paso es necesario después de cualquier cambio en `mapa_estructura.json` o `contenido.json`.

---

## Flujo Rápido (una ley)

```bash
# Extraer estructura y contenido
python backend/etl/extraer_mapa.py LISR
python backend/etl/extraer.py LISR

# Generar datos para Astro
python backend/scripts/generar-datos-astro.py

# Verificar en desarrollo
cd frontend-astro && npm run dev
```

---

## Verificación de Regresiones

Antes de hacer commit de cambios en extractores:

```bash
# 1. Ejecutar extracción en TODAS las leyes
for ley in CFF CPEUM LISR LIVA LA LIEPS LFT LSS; do
    python backend/etl/extraer_mapa.py $ley
    python backend/etl/extraer.py $ley
done

# 2. Regenerar datos de Astro
python backend/scripts/generar-datos-astro.py

# 3. Verificar cambios
git diff --stat backend/etl/data/*/mapa_estructura.json
git diff --stat frontend-astro/src/data/*/estructura.json

# 4. Solo hacer commit si los cambios son esperados
```

---

## Checksums (detección de cambios)

```bash
# Guardar checksums como referencia
python backend/etl/checksums.py CFF --guardar

# Comparar después de modificaciones
python backend/etl/checksums.py CFF --comparar

# Ver diff de artículo específico
python backend/etl/checksums.py CFF --diff 66
```

---

## Normalización de Artículos

| Outline PDF | Normalizado |
|-------------|-------------|
| `Artículo_1o` | `1o` |
| `Artículo_4o_A` | `4o-A` |
| `Artículo_29_Bis` | `29 Bis` |

---

## Configuración por Ley

Ver `backend/etl/config.py` para:
- Patrones de detección (títulos, capítulos, artículos)
- Filtros de coordenadas Y (header/footer)
- Opciones especiales (`detectar_subsecciones`, `capitulos_implicitos`)
