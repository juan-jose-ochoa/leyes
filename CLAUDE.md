# Instrucciones para Claude

## Git

- **No hacer commit a menos que se solicite explícitamente.** Espera a que el usuario diga "haz commit", "commit", o similar antes de ejecutar `git commit`.

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
