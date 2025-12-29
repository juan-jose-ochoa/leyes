# Extractor CFF

Extracción del Código Fiscal de la Federación desde PDF con parsing de fracciones.

## Arquitectura

Siguiendo el patrón del extractor híbrido de RMF:

```
┌─────────────────────────────────────────────────────────────┐
│                      EXTRACTOR CFF                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PDF (PyMuPDF) → Parser → Validador → JSON → Importador     │
│                                                             │
│  El JSON contiene:                                          │
│    - articulos.contenido = solo intro                       │
│    - articulos.fracciones = [{tipo, numero, contenido}]     │
│                                                             │
│  NO se repara en BD - todo se valida antes de importar      │
└─────────────────────────────────────────────────────────────┘
```

## Uso

```bash
# 1. Extraer del PDF y generar JSON validado
python scripts/cff/extractor_cff.py

# 2. Importar a PostgreSQL
python scripts/cff/importar_cff.py --limpiar
```

## Archivos

| Archivo | Descripción |
|---------|-------------|
| `extractor_cff.py` | Extrae artículos y fracciones del PDF |
| `importar_cff.py` | Importa el JSON a PostgreSQL |

## Salida JSON

```json
{
  "codigo": "CFF",
  "estructura": {
    "titulos": [...],
    "capitulos": [...]
  },
  "articulos": [
    {
      "numero_raw": "17-H BIS",
      "numero_base": 17,
      "sufijo": "H BIS",
      "contenido": "Párrafo introductorio...",
      "fracciones": [
        {"tipo": "fraccion", "numero": "I", "contenido": "..."},
        {"tipo": "fraccion", "numero": "II", "contenido": "..."},
        {"tipo": "inciso", "numero": "a", "contenido": "...", "padre": "XIII"},
        {"tipo": "parrafo", "contenido": "Párrafo final..."}
      ],
      "referencias": "CFF 17-D, 19...",
      "pagina": 24
    }
  ],
  "estadisticas": {...}
}
```

## Tipos de fracciones

| Tipo | Patrón | Ejemplo |
|------|--------|---------|
| `fraccion` | `I.`, `II.`, `XIV.` | Fracciones romanas |
| `inciso` | `a)`, `b)` | Incisos bajo una fracción |
| `numeral` | `1.`, `2.` | Numerales |
| `parrafo` | (sin número) | Párrafos después de fracciones |

## Resultados

| Métrica | Valor |
|---------|-------|
| Total artículos | 423 |
| Artículos con fracciones | 164 |
| Total fracciones | 2,751 |
| Fracciones romanas | ~990 |
| Incisos | ~330 |
| Párrafos finales | ~1,400 |

## Diferencia con extracción anterior (DOCX)

La extracción anterior desde DOCX tenía problemas:
- Artículos con sufijos (17-H, 17-H BIS) mal parseados
- Contenido truncado
- Sin fracciones separadas

La nueva extracción desde PDF:
- Parsea correctamente artículos con cualquier sufijo
- Extrae fracciones, incisos y párrafos finales
- Valida antes de importar
- Sigue el patrón establecido con RMF
