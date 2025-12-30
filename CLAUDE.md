SIEMPRE ESTAMOS EN MODO ANÁLISIS/DISEÑO A MENOS QUE SE INDIQUE LO CONTRARIO!!! DESPUÉS DE CUALQUIER CAMBIO, VOLVEMOS INMEDIATAMENTE A MODO ANALISIS-DISEÑO, DESPUÉS DEL MODO ANÁILIS-DISEÑO SEGUIMOS EN MODO ANÁLISIS-DISEÑO. NUNCA ESTAMOS EN MODO ESCRIBEPRONTO, SOLO SE ESCRIBE CODIGO DESPUÉS DE PASAR RIGUROSAMENTE POR LAS FASES CAUTELOSAMENTE HASTA LLEGAR A UNA IMPLEMENTACIÓN PROBADA, DEMOSTRADA, CONSENSUADA ¿TIENES ALGUNA PREGUNTA?

No es error, quiero volverlo a repetir
SIEMPRE ESTAMOS EN MODO ANÁLISIS/DISEÑO A MENOS QUE SE INDIQUE LO CONTRARIO!!! DESPUÉS DE CUALQUIER CAMBIO, VOLVEMOS INMEDIATAMENTE A MODO ANALISIS-DISEÑO, DESPUÉS DEL MODO ANÁILIS-DISEÑO SEGUIMOS EN MODO ANÁLISIS-DISEÑO. NUNCA ESTAMOS EN MODO ESCRIBEPRONTO, SOLO SE ESCRIBE CODIGO DESPUÉS DE PASAR RIGUROSAMENTE POR LAS FASES CAUTELOSAMENTE HASTA LLEGAR A UNA IMPLEMENTACIÓN PROBADA, DEMOSTRADA, CONSENSUADA ¿TIENES ALGUNA PREGUNTA?

# Instrucciones para Claude

## Reglas de interacción

- **No hacer cambios sin solicitud.** Si el usuario pregunta algo, responde sin modificar código.
- **Esperar confirmación antes de actuar.** Presenta opciones y espera que el usuario elija.
- **Proceso de desarrollo:** Primero análisis y entendimiento del problema, luego diseño, patrones y algoritmos. El código se escribe solo al final, nunca antes de entender completamente el problema.
- **No precipitarse a escribir código sin cumplir con el proceso de desarrollo**

## Git

- **No hacer commit a menos que se solicite explícitamente.**
- **Protocolo de commit:**
  - Presentar resultado de tests con **cero errores**
  - **Cero warnings** de linter/TypeScript

## Base de datos

- **Ser selectivo por ley.** Solo afectar la ley específica, nunca otras.
- **No ejecutar NI DELETE NI UPDATE directo en la BD.** Con el fin de prevenir errores, se debe de usar un procedimineto en la base de datos o un script local aprobado para la modificación de los datos.

## Calidad de código

### FAIL FAST
- **Validación BLOQUEA, no solo reporta** - Si algo falla, el proceso ABORTA
- `importar.py` DEBE llamar validación internamente antes de escribir
- Si validación falla → importación ABORTA con código de error

### Definición de "Terminado"
Un script NO está terminado si:
- Tiene comentarios `TODO`, `FIXME`, `HACK`
- Usa valores por defecto en lugar de lógica real
- No tiene validación de entrada/salida
- No tiene tests o verificación post-ejecución

## Guías del proyecto

- [README.md](README.md) - Arquitectura, scripts, base de datos, API
- [backend/docs/DESARROLLO.md](backend/docs/DESARROLLO.md) - Flujo de trabajo e importación
- [backend/docs/PRODUCCION.md](backend/docs/PRODUCCION.md) - Despliegue con Caddy
