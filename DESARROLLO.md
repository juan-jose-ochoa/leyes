# LeyesMX - Flujo de Desarrollo

## Pipeline de Conversión

```
PDF (fuente oficial)
    │
    ▼ pdfplumber (coordenadas X)
JSON (estructura jerárquica)
    │
    ▼ importar.py
PostgreSQL (normalizado)
```

## Flujo de Importación (5 etapas)

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  1. MAPA     │ -> │ 2. APROBAR   │ -> │ 3. EXTRAER   │ -> │ 4. VALIDAR   │ -> │ 5. IMPORTAR  │
│  (outline)   │    │  (manual)    │    │  (contenido) │    │  (vs BD)     │    │  (a BD)      │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

---

### Etapa 1: Extraer Mapa

```bash
python scripts/leyesmx/extraer_mapa.py CFF
```

Genera: `doc/leyes/cff/mapa_estructura.json`

---

### Etapa 2: Aprobar (MANUAL)

```bash
cat doc/leyes/cff/mapa_estructura.json
# Comparar con outline en Okular/Evince

cp doc/leyes/cff/mapa_estructura.json doc/leyes/cff/estructura_esperada.json
```

---

### Etapa 3: Extraer Contenido

```bash
python scripts/leyesmx/extraer.py CFF
```

El extractor usa **coordenadas X** del PDF:
- X~85: Fracción (I., II.)
- X~114: Inciso (a), b))
- X~142: Numeral (1., 2.)

---

### Etapa 4: Validar

```bash
python scripts/leyesmx/validar.py CFF
```

---

### Etapa 5: Importar

```bash
python scripts/leyesmx/importar.py CFF
```

---

## Verificación Post-Importación

```bash
python scripts/leyesmx/verificar_bd.py CFF
```

Confirma:
- Cada artículo tiene `division_id` correcto
- Conteo por capítulo coincide
- No hay artículos huérfanos

---

## Verificación de Regresiones (Checksums)

Para detectar cambios en artículos después de modificar el algoritmo de extracción:

```bash
# 1. Guardar checksums actuales como referencia (antes de modificar)
python scripts/leyesmx/checksums.py CFF --guardar

# 2. [Modificar algoritmo y reimportar]

# 3. Comparar contra referencia
python scripts/leyesmx/checksums.py CFF --comparar

# 4. Ver contenido de artículo específico
python scripts/leyesmx/checksums.py CFF --diff 66

# 5. Si los cambios son correctos, actualizar referencia
python scripts/leyesmx/checksums.py CFF --guardar
```

Los checksums se guardan en `doc/leyes/<ley>/checksums_verificados.json` (versionado con git).

---

## Comandos de Administración

### Refrescar Vista Materializada

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY jerarquia_completa;
```

### Verificar Datos

```sql
SELECT * FROM leyesmx.stats();
SELECT * FROM api.buscar('deduccion', NULL, NULL, 5, 1);
```

### Recargar Schema de PostgREST

```bash
kill -SIGUSR1 $(pgrep postgrest)
```

---

## Normalización de Artículos

| Outline PDF | Normalizado |
|-------------|-------------|
| `Artículo_1o` | `1o` |
| `Artículo_4o_A` | `4o-A` |
| `Artículo_29_Bis` | `29 Bis` |

- Letras sueltas → guión: `4o-A`
- Sufijos (Bis, Ter) → espacio: `29 Bis`
