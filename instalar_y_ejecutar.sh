#!/bin/bash
#
# Instalador y ejecutor de Leyes MX Downloader
# Para Ubuntu 24.04
#
set -e

echo "=========================================="
echo "  LEYES MX DOWNLOADER - INSTALACION"
echo "=========================================="
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar si somos root o tenemos sudo
check_sudo() {
    if [[ $EUID -ne 0 ]]; then
        if ! command -v sudo &> /dev/null; then
            echo -e "${RED}Error: Este script requiere sudo${NC}"
            exit 1
        fi
        SUDO="sudo"
    else
        SUDO=""
    fi
}

# Instalar dependencias del sistema
install_system_deps() {
    echo -e "${YELLOW}[1/4] Instalando dependencias del sistema...${NC}"

    $SUDO apt-get update -qq

    # Python y herramientas básicas
    $SUDO apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        curl \
        wget \
        wkhtmltopdf \
        libxrender1 \
        libxext6 \
        libfontconfig1 \
        libjpeg-turbo8 \
        fontconfig \
        fonts-liberation \
        fonts-dejavu-core

    echo -e "${GREEN}  Dependencias del sistema instaladas${NC}"
}

# Crear entorno virtual
create_venv() {
    echo -e "${YELLOW}[2/4] Creando entorno virtual Python...${NC}"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    VENV_DIR="$SCRIPT_DIR/.venv"

    if [ -d "$VENV_DIR" ]; then
        echo "  Entorno virtual ya existe, actualizando..."
    else
        python3 -m venv "$VENV_DIR"
    fi

    source "$VENV_DIR/bin/activate"

    # Actualizar pip
    pip install --upgrade pip -q

    echo -e "${GREEN}  Entorno virtual creado: $VENV_DIR${NC}"
}

# Instalar dependencias Python
install_python_deps() {
    echo -e "${YELLOW}[3/4] Instalando dependencias Python...${NC}"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    pip install -r "$SCRIPT_DIR/requirements.txt" -q

    # Instalar playwright browsers
    echo "  Instalando navegador para Playwright..."
    playwright install chromium --with-deps 2>/dev/null || true

    echo -e "${GREEN}  Dependencias Python instaladas${NC}"
}

# Crear directorio /doc si no existe
create_doc_dir() {
    echo -e "${YELLOW}[4/4] Preparando directorio /doc...${NC}"

    if [ ! -d "/doc" ]; then
        $SUDO mkdir -p /doc
        $SUDO chown $(whoami):$(whoami) /doc
        echo -e "${GREEN}  Directorio /doc creado${NC}"
    else
        echo "  Directorio /doc ya existe"
        # Verificar permisos
        if [ ! -w "/doc" ]; then
            $SUDO chown $(whoami):$(whoami) /doc
        fi
    fi
}

# Ejecutar el script principal
run_downloader() {
    echo ""
    echo "=========================================="
    echo "  EJECUTANDO DESCARGA"
    echo "=========================================="
    echo ""

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    source "$SCRIPT_DIR/.venv/bin/activate"

    python3 "$SCRIPT_DIR/descargar_leyes_mx.py"
}

# Main
main() {
    check_sudo
    install_system_deps
    create_venv
    install_python_deps
    create_doc_dir

    echo ""
    echo -e "${GREEN}=========================================="
    echo "  INSTALACION COMPLETADA"
    echo "==========================================${NC}"
    echo ""

    # Preguntar si ejecutar
    read -p "¿Ejecutar la descarga ahora? [S/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]] || [[ -z $REPLY ]]; then
        run_downloader
    else
        echo ""
        echo "Para ejecutar manualmente:"
        echo "  source $(dirname "$0")/.venv/bin/activate"
        echo "  python3 $(dirname "$0")/descargar_leyes_mx.py"
    fi
}

main "$@"
