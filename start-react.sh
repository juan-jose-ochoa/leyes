#!/bin/bash
#
# LeyesMX - Script de inicio de servicios
#
# Uso:
#   ./start.sh          # Inicia backend (PostgREST) y frontend
#   ./start.sh backend  # Solo backend
#   ./start.sh frontend # Solo frontend
#   ./start.sh db       # Solo verificar base de datos
#

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directorio del proyecto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Agregar ~/.local/bin al PATH si existe
if [ -d "$HOME/.local/bin" ]; then
    export PATH="$HOME/.local/bin:$PATH"
fi

# Cargar variables de entorno desde .env si existe
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
    LOADED_ENV=1
fi

# Configuracion (defaults si no estan en .env)
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_DB="${PG_DB:-leyesmx}"
PG_USER="${PG_USER:-leyesmx}"
PG_PASS="${PG_PASS:-leyesmx}"

POSTGREST_PORT="${POSTGREST_PORT:-3010}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# Funciones de utilidad
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar PostgreSQL
check_postgres() {
    log_info "Verificando PostgreSQL..."

    if ! command -v psql &> /dev/null; then
        log_error "psql no encontrado. Instala PostgreSQL."
        return 1
    fi

    if PGPASSWORD=$PG_PASS psql -h $PG_HOST -U $PG_USER -d $PG_DB -c "SELECT 1" &> /dev/null; then
        log_success "PostgreSQL conectado ($PG_HOST:$PG_PORT/$PG_DB)"

        # Mostrar estadisticas
        STATS=$(PGPASSWORD=$PG_PASS psql -h $PG_HOST -U $PG_USER -d $PG_DB -t -c \
            "SELECT COUNT(*) FROM leyesmx.leyes" 2>/dev/null || echo "0")
        ARTS=$(PGPASSWORD=$PG_PASS psql -h $PG_HOST -U $PG_USER -d $PG_DB -t -c \
            "SELECT COUNT(*) FROM leyesmx.articulos" 2>/dev/null || echo "0")
        log_info "  Leyes: $(echo $STATS | tr -d ' '), Articulos: $(echo $ARTS | tr -d ' ')"
        return 0
    else
        log_error "No se pudo conectar a PostgreSQL"
        log_info "Verifica que PostgreSQL este corriendo:"
        log_info "  sudo systemctl start postgresql"
        return 1
    fi
}

# Iniciar PostgREST
start_postgrest() {
    log_info "Iniciando PostgREST en puerto $POSTGREST_PORT..."

    if ! command -v postgrest &> /dev/null; then
        log_warn "PostgREST no instalado. Instalando..."
        log_info "Descarga desde: https://github.com/PostgREST/postgrest/releases"
        log_info "O instala con: "
        log_info "  # Ubuntu/Debian"
        log_info "  wget https://github.com/PostgREST/postgrest/releases/download/v12.0.2/postgrest-v12.0.2-linux-static-x64.tar.xz"
        log_info "  tar xJf postgrest-v12.0.2-linux-static-x64.tar.xz"
        log_info "  sudo mv postgrest /usr/local/bin/"
        return 1
    fi

    # Verificar si ya esta corriendo
    if lsof -i :$POSTGREST_PORT &> /dev/null; then
        log_warn "Puerto $POSTGREST_PORT ya en uso"
        return 0
    fi

    # Generar archivo de configuracion con credenciales actuales
    cat > backend/postgrest.local.conf << EOF
# Auto-generated from environment variables - DO NOT COMMIT
db-uri = "postgres://$PG_USER:$PG_PASS@$PG_HOST:$PG_PORT/$PG_DB"
db-schemas = "leyesmx"
db-anon-role = "web_anon"
server-host = "127.0.0.1"
server-port = $POSTGREST_PORT
db-pool = 10
db-pool-acquisition-timeout = 10
openapi-mode = "follow-privileges"
log-level = "info"
max-rows = 1000
EOF
    log_info "Configuracion generada en backend/postgrest.local.conf"

    # Iniciar PostgREST en background
    postgrest backend/postgrest.local.conf &
    POSTGREST_PID=$!

    sleep 1
    if kill -0 $POSTGREST_PID 2>/dev/null; then
        log_success "PostgREST iniciado (PID: $POSTGREST_PID)"
        log_info "  API disponible en: http://localhost:$POSTGREST_PORT"
        echo $POSTGREST_PID > .postgrest.pid
    else
        log_error "PostgREST fallo al iniciar"
        return 1
    fi
}

# Iniciar Frontend
start_frontend() {
    log_info "Iniciando frontend en puerto $FRONTEND_PORT..."

    cd frontend

    # Verificar node_modules
    if [ ! -d "node_modules" ]; then
        log_info "Instalando dependencias npm..."
        npm install
    fi

    # Verificar si ya esta corriendo
    if lsof -i :$FRONTEND_PORT &> /dev/null; then
        log_warn "Puerto $FRONTEND_PORT ya en uso"
        cd ..
        return 0
    fi

    # Iniciar en background
    npm run dev &
    FRONTEND_PID=$!

    sleep 2
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        log_success "Frontend iniciado (PID: $FRONTEND_PID)"
        log_info "  App disponible en: http://localhost:$FRONTEND_PORT"
        echo $FRONTEND_PID > ../.frontend.pid
    else
        log_error "Frontend fallo al iniciar"
        cd ..
        return 1
    fi

    cd ..
}

# Detener servicios
stop_services() {
    log_info "Deteniendo servicios..."

    if [ -f .postgrest.pid ]; then
        PID=$(cat .postgrest.pid)
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            log_success "PostgREST detenido"
        fi
        rm .postgrest.pid
    fi

    if [ -f .frontend.pid ]; then
        PID=$(cat .frontend.pid)
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            log_success "Frontend detenido"
        fi
        rm .frontend.pid
    fi

    # Matar procesos huerfanos
    pkill -f "postgrest backend/postgrest" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
}

# Mostrar ayuda
show_help() {
    echo "LeyesMX - Script de inicio"
    echo ""
    echo "Uso: $0 [comando]"
    echo ""
    echo "Comandos:"
    echo "  (sin args)  Inicia backend y frontend"
    echo "  backend     Solo inicia PostgREST API"
    echo "  frontend    Solo inicia servidor de desarrollo"
    echo "  db          Solo verifica conexion a base de datos"
    echo "  stop        Detiene todos los servicios"
    echo "  status      Muestra estado de servicios"
    echo "  import      Importa datos a PostgreSQL"
    echo "  help        Muestra esta ayuda"
    echo ""
    echo "Puertos:"
    echo "  PostgreSQL: $PG_PORT"
    echo "  PostgREST:  $POSTGREST_PORT"
    echo "  Frontend:   $FRONTEND_PORT"
}

# Mostrar estado
show_status() {
    echo "=== Estado de Servicios ==="
    echo ""

    # PostgreSQL
    if PGPASSWORD=$PG_PASS psql -h $PG_HOST -U $PG_USER -d $PG_DB -c "SELECT 1" &> /dev/null; then
        echo -e "PostgreSQL:  ${GREEN}ACTIVO${NC} ($PG_HOST:$PG_PORT)"
    else
        echo -e "PostgreSQL:  ${RED}INACTIVO${NC}"
    fi

    # PostgREST
    if lsof -i :$POSTGREST_PORT &> /dev/null; then
        echo -e "PostgREST:   ${GREEN}ACTIVO${NC} (http://localhost:$POSTGREST_PORT)"
    else
        echo -e "PostgREST:   ${RED}INACTIVO${NC}"
    fi

    # Frontend
    if lsof -i :$FRONTEND_PORT &> /dev/null; then
        echo -e "Frontend:    ${GREEN}ACTIVO${NC} (http://localhost:$FRONTEND_PORT)"
    else
        echo -e "Frontend:    ${RED}INACTIVO${NC}"
    fi
}

# Importar datos
import_data() {
    log_info "Importando datos a PostgreSQL..."

    if [ ! -d ".venv" ]; then
        log_error "Virtualenv no encontrado. Crea con: python3 -m venv .venv"
        return 1
    fi

    source .venv/bin/activate
    python backend/scripts/importar_leyes.py
}

# Main
main() {
    echo ""
    echo "=========================================="
    echo "        LeyesMX - Servidor Local"
    echo "=========================================="
    echo ""

    if [ -n "$LOADED_ENV" ]; then
        log_success "Configuracion cargada desde .env"
    else
        log_warn "Usando configuracion por defecto (crea .env desde .env.example)"
    fi
    echo ""

    case "${1:-all}" in
        all)
            check_postgres || exit 1
            start_postgrest
            start_frontend
            echo ""
            log_success "Servicios iniciados!"
            echo ""
            echo "  API:      http://localhost:$POSTGREST_PORT"
            echo "  Frontend: http://localhost:$FRONTEND_PORT"
            echo ""
            echo "Presiona Ctrl+C para detener..."

            # Esperar a que terminen
            trap stop_services EXIT
            wait
            ;;
        backend)
            check_postgres || exit 1
            start_postgrest
            trap stop_services EXIT
            wait
            ;;
        frontend)
            start_frontend
            trap stop_services EXIT
            wait
            ;;
        db)
            check_postgres
            ;;
        stop)
            stop_services
            ;;
        status)
            show_status
            ;;
        import)
            check_postgres || exit 1
            import_data
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Comando desconocido: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
