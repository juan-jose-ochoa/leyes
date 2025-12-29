# LeyesMX - Notas para Claude

## Flujo de Extracción e Importación

El proceso sigue **5 etapas con aprobación manual**:

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  1. MAPA     │ -> │ 2. APROBAR   │ -> │ 3. EXTRAER   │ -> │ 4. VALIDAR   │ -> │ 5. IMPORTAR  │
│  (outline)   │    │  (manual)    │    │  (contenido) │    │  (vs BD)     │    │  (a BD)      │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

---

### Etapa 1: Extraer Mapa de Estructura (desde outline PDF)

Extrae la jerarquía directamente del **outline del PDF** (fuente autoritativa):

```bash
python scripts/leyesmx/extraer_mapa.py CFF
```

**Genera:**
- `doc/leyes/cff/mapa_estructura.json` - Mapa jerárquico extraído del outline

**Resultado esperado:**
```
TITULO PRIMERO - Disposiciones Generales
  CAPITULO I: 1o, 2o, 3o ... 17-B (31 arts)
  CAPITULO II - DE LOS MEDIOS ELECTRÓNICOS: 17-C ... 17-L (11 arts)
...
TITULO SEXTO - De la Revelación de Esquemas Reportables
  CAPITULO ÚNICO: 197 ... 263 (67 arts)
TRANSITORIOS: Primero ... Décimo Primero (11 arts)
```

**Principios clave:**
- El outline del PDF es la **fuente autoritativa** de estructura
- Artículos derogados NO se separan, tienen `derogado=true` en su posición natural
- Transitorios se incluyen como artículos con `tipo='transitorio'`

---

### Etapa 2: Aprobar Estructura (MANUAL)

Revisar `mapa_estructura.json` contra el PDF (Okular u otro visor):

```bash
# Ver el mapa generado
cat doc/leyes/cff/mapa_estructura.json

# Comparar visualmente con outline en Okular/Evince
```

**Si es correcto**, crear `estructura_esperada.json` y cargar a BD:

```bash
# Copiar mapa como estructura esperada
cp doc/leyes/cff/mapa_estructura.json doc/leyes/cff/estructura_esperada.json

# Agregar aprobación al JSON
{
  "aprobaciones": [
    {"fecha": "2025-12-28", "usuario": "jochoa", "estado": "aprobado"}
  ]
}
```

**Cargar a base de datos:**
```sql
UPDATE leyesmx.leyes
SET estructura_esperada = '<contenido JSON>',
    fecha_verificacion = CURRENT_DATE
WHERE codigo = 'CFF';
```

---

### Etapa 3: Extraer Contenido

Extrae artículos y párrafos del PDF.

```bash
python scripts/leyesmx/extraer.py CFF
```

**Genera:**
- `doc/leyes/cff/estructura.json` - Divisiones extraídas
- `doc/leyes/cff/contenido.json` - Artículos con párrafos

---

### Etapa 4: Validar (contra BD)

Compara extracción contra estructura esperada **almacenada en BD**.

```bash
python scripts/leyesmx/validar.py CFF
python scripts/leyesmx/validar.py CFF --detalle
```

**Ejemplo de salida:**
```
======================================================================
VALIDADOR LEYESMX: CFF
======================================================================

1. Cargando archivos...
   estructura_esperada (BD)
   contenido.json (extracción)

2. Validando artículos por capítulo...

======================================================================
REPORTE DE VALIDACIÓN
======================================================================

Referencia: leyesmx.leyes.estructura_esperada (BD)
Verificado: 2025-12-28
Versión:    2025-01-01
Fuente:     https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf

----------------------------------------------------------------------
Título     Capítulo   Esperado   Encontrado   Estado
----------------------------------------------------------------------
✓ PRIMERO  I          31         31           OK
✓ PRIMERO  II         11         11           OK
...
✓ SEXTO    ÚNICO      67         67           OK
----------------------------------------------------------------------

RESUMEN:
  Capítulos: 11/11 OK
  Faltantes: 0
  Extras:    0

✓ VALIDACIÓN EXITOSA - Extracción coincide con estructura esperada
```

**Fallback:** Si la BD no está disponible, usa `estructura_esperada.json` local.

---

### Etapa 5: Importar (solo después de validación exitosa)

```bash
python scripts/leyesmx/importar.py CFF --limpiar
```

---

## Scripts

| Script | Función | Modifica BD |
|--------|---------|-------------|
| `extraer_mapa.py` | Extrae jerarquía del outline PDF | No |
| `extraer.py` | Extrae contenido (párrafos) | No |
| `validar.py` | Compara extracción vs estructura en BD | No |
| `importar.py` | Carga a PostgreSQL | **Sí** |

---

## Archivos de Referencia

```
doc/leyes/cff/
├── mapa_estructura.json       # Mapa extraído del outline (regenerable)
├── estructura_esperada.json   # Copia local de estructura aprobada
├── estructura.json            # Divisiones extraídas
└── contenido.json             # Artículos/párrafos extraídos
```

**IMPORTANTE:** La fuente autoritativa de `estructura_esperada` es la **BD**, no el archivo JSON.

---

## Base de Datos

- **Database:** `digiapps`
- **Schema:** `leyesmx`
- **Credenciales:** user=leyesmx, password=leyesmx (o variables de entorno)

### Variables de Entorno

```bash
export LEYESMX_DB_HOST=localhost
export LEYESMX_DB_PORT=5432
export LEYESMX_DB_NAME=digiapps
export LEYESMX_DB_USER=leyesmx
export LEYESMX_DB_PASSWORD=leyesmx
```

### Tablas

| Tabla | Propósito |
|-------|-----------|
| `leyes` | Catálogo de leyes + `estructura_esperada` JSONB |
| `divisiones` | Títulos, capítulos |
| `articulos` | Artículos/reglas/transitorios |
| `parrafos` | Contenido (texto, fracciones, incisos) |

### Estructura Esperada en BD

```sql
SELECT codigo,
       estructura_esperada->>'version' as version,
       fecha_verificacion
FROM leyesmx.leyes;

-- codigo | version    | fecha_verificacion
-- CFF    | 2025-01-01 | 2025-12-28
```

---

## Normalización de Artículos

El outline del PDF usa formato `Artículo_4o_A` que se normaliza a `4o-A`:

| Outline PDF | Normalizado |
|-------------|-------------|
| `Artículo_1o` | `1o` |
| `Artículo_4o_A` | `4o-A` |
| `Artículo_29_Bis` | `29 Bis` |
| `Artículo_32_B_Ter` | `32-B Ter` |

**Reglas:**
- Letras sueltas (A, B, C...) se unen con guión: `4o-A`
- Sufijos (Bis, Ter, Quáter...) se unen con espacio: `29 Bis`

---

## Estado Actual del CFF

- **Estructura esperada:** ✓ Aprobada (2025-12-28) - En BD
- **Método:** Outline del PDF (fuente autoritativa)
- **Artículos:** 421 (incluyendo derogados en su posición)
- **Transitorios:** 11
- **Total:** 432

### Estadísticas por Título

| Título | Capítulos | Artículos |
|--------|-----------|-----------|
| PRIMERO | 2 | 42 |
| SEGUNDO | 1 | 50 |
| TERCERO | 2 | 63 |
| CUARTO | 2 | 62 |
| QUINTO | 3 | 137 |
| SEXTO | 1 | 67 |
| **Total** | **11** | **421** |

---

## Pendiente

- [x] ~~Aprobar estructura esperada del CFF~~
- [x] ~~Cargar estructura a BD~~
- [x] ~~Actualizar validar.py para usar BD~~
- [x] ~~Corregir extracción de 8 artículos faltantes~~
- [ ] Agregar configuración para RMF2025
- [ ] Implementar extracción de transitorios
