# LeyesMX - Scripts SQL

## Fuente de Verdad

Estos archivos SQL son la **fuente de verdad** para el schema de la base de datos.

- La base de datos se regenera desde estos scripts
- **No se permiten cambios manuales** en la BD
- Los cambios deben hacerse en los archivos SQL y aplicarse con `deploy.sh`

## Estructura

```
sql/
├── deploy.sh        # Script para aplicar SQL a la BD
├── 01_schema.sql    # Tablas, índices, constraints
├── 02_api.sql       # Vistas y funciones para PostgREST
├── README.md        # Esta documentación
└── legacy/          # Archivos históricos (no usar)
```

## Uso

### Aplicar todos los cambios

```bash
cd backend/sql
./deploy.sh
```

### Ver qué se aplicaría (sin cambios)

```bash
./deploy.sh --dry-run
```

### Aplicar solo un archivo

```bash
./deploy.sh --file 02    # Aplica solo 02_api.sql
```

## Flujo de Trabajo

1. **Modificar** el archivo SQL correspondiente
2. **Probar** con `--dry-run` para verificar sintaxis
3. **Aplicar** con `./deploy.sh`
4. **Verificar** que la aplicación funcione
5. **Commit** los cambios al repositorio

## Archivos

| Archivo | Contenido | Dependencias |
|---------|-----------|--------------|
| `01_schema.sql` | Schema `leyesmx`, tablas, índices | Ninguna |
| `02_api.sql` | Vistas, funciones RPC, permisos | 01_schema.sql |

## Convenciones

- Los archivos se ejecutan en **orden numérico** (01, 02, 03...)
- Usar `CREATE OR REPLACE` para funciones y vistas
- Usar `IF NOT EXISTS` para tablas y schemas
- Incluir `GRANT` de permisos en el mismo archivo

## Configuración

El script usa variables de entorno desde `.env` en la raíz del proyecto:

```bash
PG_HOST=localhost
PG_PORT=5432
PG_DB=digiapps
PG_USER=leyesmx
PG_PASS=leyesmx
```

## Troubleshooting

### Error de conexión

```bash
./deploy.sh --dry-run  # Verifica configuración sin conectar
```

### PostgREST no ve los cambios

El script recarga automáticamente PostgREST después del deploy.
Si no funciona:

```bash
pkill -SIGUSR1 postgrest
```

### Rollback

No hay rollback automático. Para revertir:

1. Restaurar archivo SQL desde git
2. Ejecutar `./deploy.sh`
