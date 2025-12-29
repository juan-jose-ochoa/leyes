# Extractor Híbrido RMF

Arquitectura multi-fuente para extracción de la Resolución Miscelánea Fiscal (RMF).

## Problema

La extracción de texto desde PDFs es propensa a errores debido a:
- Diferentes herramientas producen resultados distintos
- El PDF no tiene estructura semántica (todo es texto plano con posiciones)
- Los títulos, contenido y referencias están entremezclados
- Las notas de reforma añaden ruido

**Solución**: Usar múltiples fuentes independientes y combinar sus fortalezas.

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTRACTOR HÍBRIDO                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│  │   DOCX      │  │  PyMuPDF    │  │  pdftotext  │                │
│  │   (Word)    │  │   (PDF)     │  │  (poppler)  │                │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │
│         │                │                │                        │
│         ▼                ▼                ▼                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│  │  Títulos    │  │  Contenido  │  │ Validación  │                │
│  │  limpios    │  │  + fraccs   │  │  cruzada    │                │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │
│         │                │                │                        │
│         └────────────────┼────────────────┘                        │
│                          ▼                                         │
│                   ┌─────────────┐                                  │
│                   │   MERGER    │                                  │
│                   │  (combina)  │                                  │
│                   └──────┬──────┘                                  │
│                          │                                         │
│                          ▼                                         │
│                   ┌─────────────┐                                  │
│                   │  Resultado  │                                  │
│                   │   Final     │                                  │
│                   └─────────────┘                                  │
└─────────────────────────────────────────────────────────────────────┘
```

## Fuentes y sus Fortalezas

| Fuente | Herramienta | Fortaleza | Uso |
|--------|-------------|-----------|-----|
| DOCX | zipfile + xml.etree | Títulos perfectamente separados | Títulos de reglas reformadas |
| PDF | PyMuPDF (fitz) | Estructura de párrafos, páginas | Contenido y fracciones |
| PDF | pdftotext (poppler) | Contenido inline con números | Validación cruzada |

### Por qué cada fuente

**DOCX (Word)**: El documento Word convertido tiene una estructura donde el título aparece claramente separado:
```
Regla X.Y.Z. - Reformada... DOF el DD de MMMM de YYYY. TÍTULO X.Y.Z. Contenido...
```
Esto permite extraer títulos limpios de reglas reformadas (86 de 921).

**PyMuPDF**: Extrae texto manteniendo saltos de línea, lo que permite:
- Identificar números de regla standalone (`X.Y.Z.` en su propia línea)
- Parsear fracciones (I., II., a), b))
- Detectar fin de contenido por patrones
- Títulos de reglas no reformadas (788 de 921)

**pdftotext**: Produce contenido "inline" donde el número de regla está en la misma línea que el contenido:
```
2.1.1.    Para los efectos del artículo 29, primer...
```
Esto permite validar que el contenido extraído por PyMuPDF sea correcto.

## Prioridades del Merger

1. **Títulos**: DOCX > PyMuPDF > generado
2. **Contenido**: PyMuPDF (validado contra pdftotext)
3. **Fracciones**: PyMuPDF
4. **Estructura**: PyMuPDF

## Uso

```bash
# Ejecutar extracción híbrida
python scripts/rmf/extractor_hibrido.py

# Archivos requeridos:
#   doc/rmf/rmf_2025_compilada.pdf
#   doc/rmf/rmf_2025_full_converted.docx

# Salida:
#   doc/rmf/rmf_hibrido.json
```

## Salida JSON

```json
{
  "estructura": {
    "titulos": [...],
    "capitulos": [...],
    "secciones": [...]
  },
  "reglas": [
    {
      "numero": "2.1.1",
      "titulo": "Acuse de recibo de promociones",
      "contenido": "Para los efectos...",
      "pagina": 45,
      "fracciones": [...],
      "referencias": "CFF 17-D, 19, 29...",
      "metadata": {
        "titulo_fuente": "docx",
        "contenido_validado": true
      }
    }
  ],
  "estadisticas": {
    "total_reglas": 921,
    "titulos": {
      "docx": 86,
      "pymupdf": 788,
      "generados": 47
    },
    "contenido_validado": 685
  }
}
```

## Resultados

| Métrica | Valor |
|---------|-------|
| Total reglas | 921 |
| Títulos DOCX (reformadas) | 86 |
| Títulos PyMuPDF | 788 |
| Títulos generados | 47 |
| Contenido validado | 685 (74%) |

## Archivos Relacionados

- `extractor_hibrido.py` - Extractor principal
- `validar_fuentes.py` - Comparación entre fuentes (debugging)
- `pdf_extractor_v2.py` - Extractor PyMuPDF original

## Mantenimiento

Para añadir nuevas fuentes de validación:

1. Crear clase extractora en `extractor_hibrido.py`
2. Implementar método de extracción específico
3. Añadir al `MergerHibrido` con prioridad adecuada
4. Actualizar estadísticas en `ResultadoExtraccion`
