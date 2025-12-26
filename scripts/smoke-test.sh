#!/bin/bash
#
# LeyesMX - Smoke Tests
# Verifica que los componentes principales funcionan antes de deploy
#

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# Contadores
PASSED=0
FAILED=0

# Configuracion
API_URL="${API_URL:-http://localhost:3010}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Cargar .env si existe
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a; source "$PROJECT_DIR/.env"; set +a
fi

PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_DB="${PG_DB:-leyesmx}"
PG_USER="${PG_USER:-leyesmx}"
PG_PASS="${PG_PASS:-leyesmx}"

check() {
    local name="$1"
    local cmd="$2"

    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $name"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

check_output() {
    local name="$1"
    local cmd="$2"
    local expected="$3"

    local output=$(eval "$cmd" 2>/dev/null || echo "")
    if echo "$output" | grep -q "$expected"; then
        echo -e "${GREEN}✓${NC} $name"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $name (expected: $expected)"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

echo ""
echo "======================================"
echo "     LeyesMX - Smoke Tests"
echo "======================================"
echo ""

# --- Base de Datos ---
echo "Base de Datos:"
check "PostgreSQL conecta" \
    "PGPASSWORD=$PG_PASS psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c 'SELECT 1'"

check "Tabla leyes existe" \
    "PGPASSWORD=$PG_PASS psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c 'SELECT COUNT(*) FROM leyes'"

check "Tabla articulos existe" \
    "PGPASSWORD=$PG_PASS psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c 'SELECT COUNT(*) FROM articulos'"

check "Funcion buscar_articulos existe" \
    "PGPASSWORD=$PG_PASS psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c \"SELECT proname FROM pg_proc WHERE proname = 'buscar_articulos'\""

echo ""

# --- API (solo si PostgREST esta corriendo) ---
echo "API PostgREST:"
if curl -s "$API_URL/" > /dev/null 2>&1; then
    check "PostgREST responde" \
        "curl -sf '$API_URL/'"

    check_output "GET /leyes devuelve JSON" \
        "curl -sf '$API_URL/leyes'" \
        "codigo"

    check_output "POST /rpc/buscar funciona" \
        "curl -sf -X POST '$API_URL/rpc/buscar' -H 'Content-Type: application/json' -d '{\"q\":\"impuesto\",\"limite\":1}'" \
        "id"

    check_output "POST /rpc/buscar rechaza query vacio" \
        "curl -s -X POST '$API_URL/rpc/buscar' -H 'Content-Type: application/json' -d '{\"q\":\"\"}'" \
        "vacio"
else
    echo -e "${RED}✗${NC} PostgREST no responde en $API_URL (omitiendo tests de API)"
    FAILED=$((FAILED + 1))
fi

echo ""

# --- Frontend ---
echo "Frontend:"
check "package.json existe" \
    "[ -f '$PROJECT_DIR/frontend/package.json' ]"

check "TypeScript compila" \
    "cd '$PROJECT_DIR/frontend' && npm run build"

echo ""

# --- Resumen ---
echo "======================================"
TOTAL=$((PASSED + FAILED))
echo -e "Resultado: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC} ($TOTAL total)"
echo "======================================"
echo ""

if [ $FAILED -gt 0 ]; then
    exit 1
fi
