#!/bin/bash
#
# LeyesMX - Script de Deploy SQL
#
# Aplica los scripts SQL en orden a la base de datos.
# Fuente de verdad: estos archivos SQL definen el schema completo.
#
# Uso:
#   ./deploy.sh              # Aplica todos los SQL
#   ./deploy.sh --dry-run    # Muestra qué se ejecutaría sin aplicar
#   ./deploy.sh --file 02    # Aplica solo archivos que empiecen con 02
#

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Cargar variables de entorno
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Configuración (defaults si no están en .env)
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_DB="${PG_DB:-digiapps}"
PG_USER="${PG_USER:-leyesmx}"
PG_PASS="${PG_PASS:-leyesmx}"

# Opciones
DRY_RUN=false
FILE_FILTER=""

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_help() {
    echo "LeyesMX - Deploy SQL"
    echo ""
    echo "Uso: $0 [opciones]"
    echo ""
    echo "Opciones:"
    echo "  --dry-run     Muestra qué se ejecutaría sin aplicar cambios"
    echo "  --file XX     Aplica solo archivos que empiecen con XX (ej: 02)"
    echo "  --help        Muestra esta ayuda"
    echo ""
    echo "Archivos SQL (orden de ejecución):"
    for f in "$SCRIPT_DIR"/[0-9]*.sql; do
        [ -f "$f" ] && echo "  $(basename "$f")"
    done
    echo ""
    echo "Configuración actual:"
    echo "  Host: $PG_HOST:$PG_PORT"
    echo "  Base: $PG_DB"
    echo "  User: $PG_USER"
}

check_connection() {
    log_info "Verificando conexión a PostgreSQL..."
    if PGPASSWORD="$PG_PASS" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -c "SELECT 1" > /dev/null 2>&1; then
        log_ok "Conexión exitosa a $PG_HOST:$PG_PORT/$PG_DB"
        return 0
    else
        log_error "No se pudo conectar a PostgreSQL"
        log_info "Verifica las variables de entorno en .env"
        return 1
    fi
}

apply_sql() {
    local file="$1"
    local filename=$(basename "$file")

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] Aplicaría: $filename"
        return 0
    fi

    log_info "Aplicando: $filename"

    if PGPASSWORD="$PG_PASS" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -f "$file" > /tmp/sql_output.txt 2>&1; then
        log_ok "$filename aplicado correctamente"
        return 0
    else
        log_error "Error aplicando $filename:"
        cat /tmp/sql_output.txt
        return 1
    fi
}

main() {
    # Parsear argumentos
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --file)
                FILE_FILTER="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Opción desconocida: $1"
                show_help
                exit 1
                ;;
        esac
    done

    echo ""
    echo "=========================================="
    echo "       LeyesMX - Deploy SQL"
    echo "=========================================="
    echo ""

    # Verificar conexión (a menos que sea dry-run)
    if [ "$DRY_RUN" = false ]; then
        check_connection || exit 1
    fi
    echo ""

    # Encontrar y aplicar archivos SQL
    local count=0
    local errors=0

    for f in "$SCRIPT_DIR"/[0-9]*.sql; do
        [ ! -f "$f" ] && continue

        # Filtrar si se especificó --file
        if [ -n "$FILE_FILTER" ]; then
            if [[ ! $(basename "$f") == ${FILE_FILTER}* ]]; then
                continue
            fi
        fi

        if apply_sql "$f"; then
            count=$((count + 1))
        else
            errors=$((errors + 1))
        fi
    done

    echo ""
    if [ "$DRY_RUN" = true ]; then
        log_info "Dry-run completado. $count archivo(s) se aplicarían."
    elif [ $errors -eq 0 ]; then
        log_ok "Deploy completado. $count archivo(s) aplicados."

        # Recargar schema de PostgREST si está corriendo
        if pgrep -x postgrest > /dev/null; then
            log_info "Recargando schema de PostgREST..."
            pkill -SIGUSR1 postgrest
            log_ok "PostgREST recargado"
        fi
    else
        log_error "Deploy completado con $errors error(es)."
        exit 1
    fi
}

main "$@"
