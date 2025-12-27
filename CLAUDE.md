# Instrucciones para Claude

## Git

- **No hacer commit a menos que se solicite explícitamente.** Espera a que el usuario diga "haz commit", "commit", o similar antes de ejecutar `git commit`.
- **Protocolo de solicitud de commit**
    - Junto con la solicitud de commit, siempre debo a presentar el resultado de la ejecución de los tests con **cero errores**. Si los test fallan, no debe de hacerse commit.
    - Tampoco se toleran warnings del linter o del typescript, los warnings invitan a refactorizar el código. Indica los warnings encontrados o **cero warnings** en su defecto. No se aceptará la solicitud de commit con warnings.

## Proyecto

Este proyecto parsea documentos legales mexicanos (leyes, RMF) y los carga a PostgreSQL para consulta.

### Estructura principal

```
scripts/
├── rmf/                    # Módulo de parsing RMF
│   ├── extractor.py        # Extracción de DOCX
│   ├── parser.py           # Parsing estructural
│   ├── validador.py        # Validación + segunda pasada
│   └── models.py           # Dataclasses
├── tests/                  # Tests pytest
├── parsear_rmf.py          # CLI para parsear RMF
├── cargar_rmf_db.py        # Carga JSON a PostgreSQL
└── descargar_rmf.py        # Descarga RMF del SAT
```

### Tests

```bash
pytest scripts/tests/ -v
```
