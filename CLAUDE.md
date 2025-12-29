# Instrucciones para Claude

## Reglas de interacción

- **No hacer cambios sin solicitud.** Si el usuario pregunta algo, responde sin modificar código.
- **Esperar confirmación antes de actuar.** Presenta opciones y espera que el usuario elija.

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

- [PROYECTO.md](PROYECTO.md) - Arquitectura, scripts, base de datos, API
- [DESARROLLO.md](DESARROLLO.md) - Flujo de trabajo e importación
- [PRODUCCION.md](PRODUCCION.md) - Despliegue con Caddy
