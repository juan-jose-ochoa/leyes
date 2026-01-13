# Proyecto: Preguntas SEO por Artículo

> **Estado:** EN DISEÑO - No implementado
> **Prioridad:** Pausado hasta corregir validación de contenido vacío
> **Fecha:** 2026-01-12

## Objetivo

Aumentar tráfico orgánico presentando cada artículo como respuesta a preguntas que los usuarios realmente buscan en Google.

## Concepto

Cada artículo de ley responde al menos a una pregunta concreta. Al enmarcar el artículo como respuesta, el sitio captura búsquedas informativas ("¿Qué es el trabajo digno?") en lugar de solo navegacionales ("artículo 2 LFT").

## Arquitectura de Datos

```
src/data/lft/
├── articulos.json        # GENERADO por extractor (no tocar)
├── preguntas.json        # CURADO manualmente
└── debates/
    ├── art-1o.json       # Log de debate por artículo
    └── ...
```

**Principio:** Separar datos extraídos (PDF → JSON) de datos curados (preguntas).

## Panel de Expertos Virtuales

Cada pregunta debe pasar por validación de 5 perspectivas:

| Experto | Enfoque | Valida que... |
|---------|---------|---------------|
| Abogado Laboralista | Precisión jurídica | La pregunta no distorsione el alcance |
| Trabajador promedio | Lenguaje accesible | Se entienda sin conocimiento legal |
| Patrón/RRHH | Perspectiva empresarial | Aplique desde el lado del empleador |
| Especialista SEO | Búsquedas reales | La gente busca esto en Google |
| Lingüista | Gramática/claridad | Estructura correcta y natural |

## Reglas de Forma

```yaml
pregunta:
  longitud_max: 80 caracteres
  estructura: interrogativa directa (¿Qué/Quién/Cuándo/Cómo/Puede?)
  prohibido:
    - jerga legal sin explicación
    - referencias a números de artículo
    - preguntas compuestas (y/o)
  requerido:
    - sujeto claro (trabajador, patrón, empresa)
    - verbo conjugado
    - contexto implícito México/laboral
```

## Reglas de Cantidad

| Nivel | Preguntas | Criterio |
|-------|-----------|----------|
| Principal | 1 obligatoria | Captura la esencia del artículo completo |
| Secundarias | 0-3 | Una por cada tema distinguible |
| Por párrafo | 0-1 opcional | Solo si tiene contenido autónomo buscable |

## Checklist de Validación

- [ ] La pregunta se responde SOLO con el texto del artículo
- [ ] No requiere leer otros artículos para entender
- [ ] Un usuario sin conocimiento legal entendería la pregunta
- [ ] La búsqueda en Google debería mostrar este artículo
- [ ] No induce a respuesta diferente a lo que dice la ley
- [ ] Aplica al menos a un punto de vista (trabajador/patrón)

## Formato de Datos

### preguntas.json
```json
{
  "version": "1.0",
  "ley": "lft",
  "articulos": [
    {
      "numero": "2o",
      "preguntas": [
        {
          "texto": "¿Qué es el trabajo digno en México?",
          "tipo": "principal",
          "variantes": ["¿Qué significa trabajo decente?"],
          "perspectiva": ["trabajador", "patron"],
          "validado": true
        }
      ]
    }
  ]
}
```

### debates/art-2o.json
```json
{
  "articulo": "2o",
  "contenido_resumen": "Define trabajo digno, no discriminación, igualdad sustantiva",
  "debate": {
    "fecha": "2026-01-12",
    "rondas": [
      {
        "propuesta": "¿Qué es el trabajo digno?",
        "opiniones": {
          "abogado": { "aprueba": true, "nota": "..." },
          "trabajador": { "aprueba": true },
          "patron": { "aprueba": false, "nota": "Falta 'en México'" },
          "seo": { "aprueba": true },
          "linguista": { "aprueba": true }
        },
        "resultado": "ajustar",
        "objeciones": ["Agregar 'en México'"]
      },
      {
        "propuesta": "¿Qué es el trabajo digno en México?",
        "opiniones": { "...": "todos aprueban" },
        "resultado": "aprobado"
      }
    ],
    "conclusion": {
      "pregunta_final": "¿Qué es el trabajo digno en México?",
      "confianza": "alta",
      "votos": "5/5"
    }
  }
}
```

## Implementación Técnica (Pendiente)

1. Crear `preguntas.json` para LFT (primeros 10 artículos como piloto)
2. Modificar página de artículo para mostrar pregunta como `<h2>`
3. Agregar Schema.org FAQPage para rich snippets
4. Usar preguntas en meta description

## Dependencias Bloqueantes

- **CRÍTICO:** Validador de extracción debe detectar artículos con contenido vacío
- Artículos 3o Bis y 3o Ter de LFT tienen `parrafos: []` (error de extracción)
- Sin datos completos, no se pueden generar preguntas confiables

## Próximos Pasos

1. ~~Documentar proyecto~~ ✓
2. **Arreglar validación de contenido vacío** ← SIGUIENTE
3. Re-extraer LFT con extractor corregido
4. Validar extracción completa
5. Continuar con generación de preguntas
