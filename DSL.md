# LeyesMX DSL - Especificación v1.0

Sistema de referencias para legislación mexicana. Diseñado para URLs compartibles y detección automática en textos legales.

## Sintaxis

```
<ley>:<artículo>[/<apartado>][/<fracción>][/<inciso>][/<numeral>]
```

### Componentes

| Componente | Descripción | Formato | Ejemplos |
|------------|-------------|---------|----------|
| `ley` | Código de la ley | Minúsculas | `cpeum`, `lisr`, `cff`, `rmf` |
| `artículo` | Número de artículo o regla | Ver abajo | `123`, `5o`, `5-BIS`, `2.1.36` |
| `apartado` | Apartado (opcional) | Letra mayúscula | `A`, `B` |
| `fracción` | Fracción (opcional) | Romano mayúscula | `I`, `IX`, `XXX` |
| `inciso` | Inciso (opcional) | Letra minúscula | `a`, `e` |
| `numeral` | Numeral (opcional) | Número arábigo | `1`, `2`, `3` |

### Formato de artículos

| Tipo | Formato | Ejemplos |
|------|---------|----------|
| Simple | `N` | `1`, `123`, `456` |
| Ordinal | `No` | `1o`, `5o`, `9o` |
| Con sufijo | `N-SUFIJO` | `5-A`, `5-BIS`, `14-B`, `28-A` |
| Regla RMF | `X.Y.Z` | `2.1.36`, `3.21.2.1` |

### Separadores

| Carácter | Uso |
|----------|-----|
| `:` | Separa ley de artículo |
| `-` | Parte del nombre del artículo (sufijos) |
| `/` | Separa modificadores jerárquicos |
| `,` | Lista de artículos de la misma ley |
| `+` | Combina referencias de diferentes leyes |
| `..` | Rango de artículos |

## Ejemplos

### Referencias simples

```
cpeum:123                    → CPEUM, Artículo 123
lisr:28                      → LISR, Artículo 28
cff:5o                       → CFF, Artículo 5o
rmf:2.1.36                   → RMF, Regla 2.1.36
```

### Con modificadores

```
cpeum:123/A                  → CPEUM, Art. 123, Apartado A
cpeum:123/A/IX               → CPEUM, Art. 123, Apartado A, Fracción IX
cpeum:123/A/IX/e             → CPEUM, Art. 123, Apartado A, Fracción IX, Inciso e
lisr:28/XXX                  → LISR, Art. 28, Fracción XXX
cff:9o/II/a/1                → CFF, Art. 9o, Fracción II, Inciso a, Numeral 1
rmf:2.1.36/I                 → RMF, Regla 2.1.36, Fracción I
```

### Artículos con sufijo

```
cff:5-A                      → CFF, Artículo 5-A
cff:5-A/II                   → CFF, Artículo 5-A, Fracción II
cff:14-B/II/a                → CFF, Artículo 14-B, Fracción II, Inciso a
lisr:5o-BIS                  → LISR, Artículo 5o-BIS
```

### Desambiguación artículo vs apartado

```
lisr:5-A                     → Artículo 5-A (guión es parte del nombre)
lisr:5/A                     → Artículo 5, Apartado A
lisr:5-A/B                   → Artículo 5-A, Apartado B
```

### Listas de artículos

```
cpeum:94,97,116              → CPEUM, Arts. 94, 97, 116
cpeum:94,97,116/III          → CPEUM, Arts. 94, 97, y 116 Fracc. III
cpeum:122/A/IV,123/A/IX      → CPEUM, Art. 122 Apartado A Fracc. IV, Art. 123 Apartado A Fracc. IX
```

### Múltiples leyes

```
lisr:28/XXX+cff:33           → LISR Art. 28 Fracc. XXX + CFF Art. 33
cpeum:123/A+lisr:94+lft:132  → Referencias a tres leyes
```

### Rangos

```
cff:1..5                     → CFF, Arts. 1, 2, 3, 4, 5
lisr:90..93                  → LISR, Arts. 90, 91, 92, 93
```

## Jerarquía de elementos

```
Artículo (o Regla)
└── Apartado (A, B, C...)
    └── Fracción (I, II, III... romanos)
        └── Inciso (a, b, c...)
            └── Numeral (1, 2, 3... arábigos)
```

Los modificadores deben seguir este orden jerárquico. No es válido:
- `lisr:28/a/I` (inciso antes de fracción)
- `cpeum:123/IX/A` (fracción antes de apartado)

## URLs

### Formato

```
https://leyesmx.com/buscar?q=<DSL>
```

### Ejemplos de URLs compartibles

```
https://leyesmx.com/buscar?q=cpeum:123/A/IX/e
https://leyesmx.com/buscar?q=lisr:28/XXX,29/I
https://leyesmx.com/buscar?q=rmf:2.1.36
https://leyesmx.com/buscar?q=cpeum:94,97,116/III+lisr:28
```

### Encoding

El carácter `/` en query strings puede requerir encoding como `%2F`:

```
?q=cpeum:123%2FA%2FIX%2Fe
```

Sin embargo, la mayoría de navegadores modernos manejan `/` en query strings sin problemas.

## Leyes soportadas

| Código | Nombre |
|--------|--------|
| `cpeum` | Constitución Política de los Estados Unidos Mexicanos |
| `cff` | Código Fiscal de la Federación |
| `lisr` | Ley del Impuesto Sobre la Renta |
| `liva` | Ley del Impuesto al Valor Agregado |
| `lieps` | Ley del Impuesto Especial sobre Producción y Servicios |
| `lft` | Ley Federal del Trabajo |
| `lss` | Ley del Seguro Social |
| `la` | Ley Aduanera |
| `linfonavit` | Ley del INFONAVIT |
| `lissste` | Ley del ISSSTE |
| `lfdc` | Ley Federal de Derechos del Contribuyente |
| `lif` | Ley de Ingresos de la Federación |
| `rmf` | Resolución Miscelánea Fiscal |
| `rcff` | Reglamento del CFF |
| `rlisr` | Reglamento de la LISR |
| `rliva` | Reglamento de la LIVA |
| `rlieps` | Reglamento de la LIEPS |
| `rlft` | Reglamento de la LFT |
| `rlss` | Reglamento de la LSS |
| `racerf` | Reglamento de ACERF |

## Gramática formal

```ebnf
query      = ley_refs { "+" ley_refs } ;
ley_refs   = ley ":" art_list ;
art_list   = art_ref { "," art_ref } ;
art_ref    = art_id [ mods ]
           | art_id ".." art_id ;

art_id     = num_ley | num_rmf ;
num_ley    = digitos [ "o" | "º" ] [ "-" sufijo ] ;
num_rmf    = digitos "." digitos "." digitos [ "." digitos ] ;
sufijo     = letra_may { letra_may } ;

mods       = [ "/" apartado ] [ "/" fraccion ] [ "/" inciso ] [ "/" numeral ] ;
apartado   = letra_may ;
fraccion   = romano ;
inciso     = letra_min ;
numeral    = digitos ;

ley        = letra_min { letra_min } ;
digitos    = digito { digito } ;
digito     = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;
letra_may  = "A" | "B" | "C" | ... | "Z" ;
letra_min  = "a" | "b" | "c" | ... | "z" ;
romano     = ( "I" | "V" | "X" | "L" | "C" | "D" | "M" ) { "I" | "V" | "X" | "L" | "C" | "D" | "M" } ;
```

## Extensiones futuras (reservadas)

| Sintaxis | Propósito |
|----------|-----------|
| `@pN` | Párrafo específico: `lisr:28/XXX@p3` |
| `@YYYY` | Versión histórica: `lisr@2024:28` |
| `"texto"` | Búsqueda de texto: `cpeum:123 "salario"` |
| `anexoN` | Anexos RMF: `rmf:anexo1` |

## Detección en texto natural

El DSL también se usa internamente para normalizar referencias detectadas en textos legales:

**Texto original:**
> "los artículos 94, 97, 116 fracción III, y 122 Apartado A, fracción IV de esta Constitución"

**DSL normalizado:**
```
cpeum:94,97,116/III,122/A/IV
```

---

**Versión:** 1.0
**Última actualización:** 2026-01-18
**Repositorio:** https://github.com/jochoa/leyesmx
