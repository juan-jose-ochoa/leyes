# TODOs - Extracción de Estructura (extraer_mapa.py)

## Problemas detectados (pre-existentes, no regresiones)

### 1. ~~Subsecciones no soportadas~~ ✅ RESUELTO
**Leyes afectadas**: ~~LA~~, ~~LISR~~

Las leyes tienen subdivisiones dentro de secciones/capítulos que no se detectan como marcadores:
- ~~LA: "I", "II" dentro de secciones~~ ✅ RESUELTO (2024-01-18)
- ~~LISR: "DISPOSICIONES GENERALES" capturado como parte del nombre del título~~ ✅ RESUELTO (2024-01-18)

**Artículos ejemplo**:
- ~~LA: Artículo 104 (página 70-71)~~ ✅ RESUELTO
- ~~LISR: Artículo 9 (página 13)~~ ✅ RESUELTO

**Solución LA**: Agregado `detectar_subsecciones: True` en config de LA. Detecta romanos sueltos (I, II, III) como subsecciones.

**Solución LISR**: Agregado `capitulos_implicitos` en config de LISR. Crea capítulo virtual "0" para "DISPOSICIONES GENERALES" en Títulos II y IV.

### 2. ~~Artículos sin capítulo explícito~~ ✅ RESUELTO
**Leyes afectadas**: ~~LISR~~

~~Artículos 9-15 de LISR están bajo "DISPOSICIONES GENERALES" sin capítulo. Se asignan incorrectamente al Título/Capítulo anterior.~~

**Solución**: Configuración `capitulos_implicitos` permite definir capítulos virtuales ("0") para secciones sin marcador explícito.

### 3. ~~Patrón de sección con ordinales~~ ✅ RESUELTO
**Leyes afectadas**: ~~LSS, LFT, CFF~~

~~LSS usa "SECCION PRIMERA", "SECCION SEGUNDA" (ordinales) en lugar de "SECCION I", "SECCION II" (romanos).~~

**Solución**: Agregado soporte para ordinales en patrón de sección default (2024-01-17).
- LSS: 0 → 37 secciones
- LFT: 0 → 17 secciones

## Cambios realizados (2024-01-18) - Capítulos implícitos LISR

1. Agregado `capitulos_implicitos` config para LISR (Títulos II y IV)
2. Modificado `extraer_estructura()` para detectar y separar capítulos implícitos del nombre del título
3. Modificado `asignar_articulos_a_capitulos()` para manejar capítulos "0"
4. LISR ahora tiene 39 capítulos (antes 37, +2 implícitos)
5. Título II: nombre "DE LAS PERSONAS MORALES", capítulo 0 con arts 9-15
6. Título IV: nombre "DE LAS PERSONAS FÍSICAS", capítulo 0 con arts 90-93

## Cambios realizados (2024-01-18) - Subsecciones LA

1. Agregado soporte para subsecciones en LA (`detectar_subsecciones: True`)
2. Agregado `SubseccionRef` dataclass para representar subsecciones
3. Modificado `generar_json` para incluir subsecciones en el JSON
4. LA ahora tiene 6 subsecciones correctamente detectadas

## Cambios realizados (2024-01-17)

1. Agregado filtro header/footer usando `config["filtro_y"]` en `extraer_estructura()`
2. Agregado filtro de líneas vacías al construir `lineas_layout`
3. Agregada configuración `requiere_centrado` (default: True, LFT usa False)
4. Corregido patrón de capítulo en LA para aceptar "Unico" sin acento

## Mejoras logradas

- Nombres de títulos/capítulos que cruzan páginas ahora se capturan completos
- LFT: Capítulos no centrados ahora se detectan correctamente
- Múltiples leyes: Nombres truncados ahora aparecen completos
