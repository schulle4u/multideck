#!/bin/bash
# ============================================
# Build Script for MultiDeck Audio Player
# ============================================

set -e

# Configuration
APP_NAME="MultiDeck Audio Player"
SPEC_FILE="multideck.spec"
DIST_DIR="dist"
BUILD_DIR="build"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

echo ""
echo -e "${GREEN}============================================${RESET}"
echo -e "${GREEN}  Building ${APP_NAME}${RESET}"
echo -e "${GREEN}============================================${RESET}"
echo ""

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Linux*)     PLATFORM="Linux";;
    Darwin*)    PLATFORM="macOS";;
    *)          PLATFORM="Unknown";;
esac

echo -e "${YELLOW}Detected platform: ${PLATFORM}${RESET}"

# Check if virtual environment exists
if [ ! -f "venv/bin/activate" ]; then
    echo -e "${RED}Error: Virtual environment not found.${RESET}"
    echo "Please create it first with: python3 -m venv venv"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${RESET}"
source venv/bin/activate

# Check if PyInstaller is installed
if ! pip show pyinstaller > /dev/null 2>&1; then
    echo -e "${YELLOW}PyInstaller not found. Installing...${RESET}"
    pip install pyinstaller
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to install PyInstaller.${RESET}"
        exit 1
    fi
fi

# Check if all dependencies are installed
echo -e "${YELLOW}Checking dependencies...${RESET}"
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to install dependencies.${RESET}"
    exit 1
fi

# Clean previous builds
echo -e "${YELLOW}Cleaning previous builds...${RESET}"
[ -d "${BUILD_DIR}" ] && rm -rf "${BUILD_DIR}"
[ -d "${DIST_DIR}/MultiDeck" ] && rm -rf "${DIST_DIR}/MultiDeck"
[ -d "${DIST_DIR}/MultiDeck.app" ] && rm -rf "${DIST_DIR}/MultiDeck.app"

# Run PyInstaller
echo -e "${YELLOW}Running PyInstaller...${RESET}"
pyinstaller --clean --noconfirm "${SPEC_FILE}"
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: PyInstaller build failed.${RESET}"
    exit 1
fi

# Determine output directory (macOS creates .app bundle, Linux creates folder)
if [ "${PLATFORM}" = "macOS" ] && [ -d "${DIST_DIR}/MultiDeck.app" ]; then
    OUTPUT_DIR="${DIST_DIR}/MultiDeck.app/Contents/Resources"
    mkdir -p "${OUTPUT_DIR}"
else
    OUTPUT_DIR="${DIST_DIR}/MultiDeck"
fi

# Copy additional files and folders
echo -e "${YELLOW}Copying additional files and folders...${RESET}"
[ -f "LICENSE" ] && cp "LICENSE" "${OUTPUT_DIR}/"
[ -f "config.ini.example" ] && cp "config.ini.example" "${OUTPUT_DIR}/"
[ -d "locale" ] && cp -r "locale" "${OUTPUT_DIR}/"
[ -d "docs" ] && cp -r "docs" "${OUTPUT_DIR}/"
[ -f "README.md" ] && mkdir -p "${OUTPUT_DIR}/docs" && cp "README.md" "${OUTPUT_DIR}/docs/"

echo ""
echo -e "${GREEN}============================================${RESET}"
echo -e "${GREEN}  Build completed successfully!${RESET}"
echo -e "${GREEN}============================================${RESET}"
echo ""
echo "Output directory: ${OUTPUT_DIR}"
echo ""

# Show build size
if [ "${PLATFORM}" = "macOS" ] && [ -d "${DIST_DIR}/MultiDeck.app" ]; then
    SIZE=$(du -sh "${DIST_DIR}/MultiDeck.app" | cut -f1)
    echo "Total size: ${SIZE}"
else
    SIZE=$(du -sh "${OUTPUT_DIR}" | cut -f1)
    echo "Total size: ${SIZE}"
fi
echo ""

# Deactivate virtual environment
deactivate
