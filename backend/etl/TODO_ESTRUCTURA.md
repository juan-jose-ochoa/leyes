# TODOs - Extracción de Estructura (extraer_mapa.py)

## Problemas detectados (pre-existentes, no regresiones)

### 1. Subsecciones no soportadas
**Leyes afectadas**: LA, LISR, LSS

Las leyes tienen subdivisiones dentro de secciones/capítulos que no se detectan como marcadores:
- LA: "I", "II" dentro de secciones (ej: Sección Primera > I Disposiciones generales)
- LISR: "DISPOSICIONES GENERALES" capturado como parte del nombre del título
- LSS: "SECCION PRIMERA GENERALIDADES" capturado como nombre de capítulo

**Artículos ejemplo**:
- LA: Artículo 104 (página 70-71)
- LISR: Artículo 9 (página 13) - se muestra en Título I pero pertenece a Título II
- LSS: Capítulo III del Título II

**Solución propuesta**: Agregar soporte para subsecciones o detectar patrones de subdivisión como marcadores.

### 2. Artículos sin capítulo explícito
**Leyes afectadas**: LISR

Artículos 9-15 de LISR están bajo "DISPOSICIONES GENERALES" sin capítulo. Se asignan incorrectamente al Título/Capítulo anterior.

**Solución propuesta**: Crear capítulo virtual "DISPOSICIONES GENERALES" o similar cuando hay artículos antes del primer capítulo de un título.

### 3. Patrón de sección con ordinales
**Leyes afectadas**: LSS

LSS usa "SECCION PRIMERA", "SECCION SEGUNDA" (ordinales) en lugar de "SECCION I", "SECCION II" (romanos). El patrón default solo detecta romanos.

**Solución propuesta**: Configurar patrón de sección por ley, o agregar ordinales al patrón default.

## Cambios realizados (2024-01-17)

1. Agregado filtro header/footer usando `config["filtro_y"]` en `extraer_estructura()`
2. Agregado filtro de líneas vacías al construir `lineas_layout`
3. Agregada configuración `requiere_centrado` (default: True, LFT usa False)
4. Corregido patrón de capítulo en LA para aceptar "Unico" sin acento

## Mejoras logradas

- Nombres de títulos/capítulos que cruzan páginas ahora se capturan completos
- LFT: Capítulos no centrados ahora se detectan correctamente
- Múltiples leyes: Nombres truncados ahora aparecen completos
