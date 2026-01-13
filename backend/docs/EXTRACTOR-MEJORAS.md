# Mejoras Pendientes del Extractor

> **Estado:** Documentado - No implementado
> **Fecha:** 2026-01-12

## 1. Pre-consolidar por Y exacto antes del scoring

### Problema detectado

PyMuPDF separa texto en "líneas" basándose en bounding boxes. Cuando hay gap horizontal significativo, contenido con **mismo Y** se separa en líneas diferentes:

```
PDF Visual:
a:    Es la densidad del combustible fósil...
^     ^
x=142 x=182  (mismo Y=433)

PyMuPDF output:
LINE y=433: 'a:'                    ← línea 1
LINE y=433: 'Es la densidad...'     ← línea 2 (mismo Y!)
```

### Impacto

El sistema de scoring en `_consolidar_lineas` evalúa si unir líneas. Pero cuando el contenido es de la **misma línea visual** (mismo Y), no debería pasar por scoring - debería consolidarse automáticamente.

Esto causa problemas al agregar nuevos criterios de scoring (ej: terminador `:`):
- "a:" termina en `:` → +1 punto extra
- Puede alcanzar 4 puntos y separar contenido que visualmente está junto

### Solución propuesta

Agregar paso de pre-consolidación ANTES del scoring:

```python
def _preconsolidar_mismo_y(self, lineas: list[dict]) -> list[dict]:
    """Une líneas con exactamente el mismo Y antes del scoring."""
    if not lineas:
        return []

    resultado = []
    buffer = lineas[0].copy()

    for linea in lineas[1:]:
        if linea['y'] == buffer['y']:
            # Mismo Y = misma línea visual → concatenar
            buffer['text'] += ' ' + linea['text']
            buffer['x_end'] = linea['x_end']
        else:
            resultado.append(buffer)
            buffer = linea.copy()

    resultado.append(buffer)
    return resultado
```

Llamar antes de `_consolidar_lineas`:

```python
lineas_preconsolidadas = self._preconsolidar_mismo_y(todas_lineas)
lineas_consolidadas = self._consolidar_lineas(lineas_preconsolidadas, modo)
```

### Casos de uso

1. **Definiciones de variables en fórmulas:**
   - LIEPS Art. 2o-E: `a: Es la densidad...`
   - LISR Art. 5: `D: Dividendo o utilidad...`
   - CFF Art. 20 Ter: `n = Número de días...`

2. **Tablas sin bordes:** Layout de dos columnas donde columna izquierda es etiqueta y derecha es valor.

### Consideraciones

- Verificar que no rompa tablas reales (diferentes conceptos en mismo Y)
- El bold change (+1 punto) ya implementado podría verse afectado
- Probar en todas las leyes antes de implementar

### Relación con otros cambios

Esta mejora habilitaría agregar el terminador `:` como criterio de scoring sin causar regresiones en definiciones de variables.

---

## 2. Terminador `:` como separador de párrafo

### Estado: BLOQUEADO por mejora #1

### Idea original

Agregar `:` como terminador de párrafo además de `.`:

```python
if buffer_texto.rstrip().endswith(('.', ':')):
    puntos += 1
```

### Resultados de prueba (2026-01-12)

| Ley | Resultado | Notas |
|-----|-----------|-------|
| CPEUM | IGNORAR | Solo afecta transitorios |
| CFF | MEJORA | Art. 20 Ter - fórmulas UDI |
| RACERF | MEJORA | Arts. 35-36 - fórmulas |
| LIEPS | REGRESION | Art. 2o-E - fragmenta `a:` de definición |
| LISR | REGRESION | Art. 5 - fragmenta `D:` de definición |
| LFT | (no evaluado) | |

### Conclusión

El `:` funciona bien para frases introductorias ("se utiliza la siguiente fórmula:") pero fragmenta notación de variables ("D: Dividendo...") cuando están en la misma línea PDF.

**Requiere:** Implementar mejora #1 (pre-consolidación por Y) primero.
