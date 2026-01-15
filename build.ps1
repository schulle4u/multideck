# ============================================
# Build Script for MultiDeck Audio Player
# PowerShell Version
# ============================================

param(
    [switch]$Debug,
    [switch]$OneFile,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

# Configuration
$AppName = "MultiDeck Audio Player"
$SpecFile = "multideck.spec"
$DistDir = "dist"
$BuildDir = "build"

function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

Write-Host ""
Write-ColorOutput Green "============================================"
Write-ColorOutput Green "  Building $AppName"
Write-ColorOutput Green "============================================"
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-ColorOutput Red "Error: Virtual environment not found."
    Write-Host "Please create it first with: python -m venv venv"
    exit 1
}

# Activate virtual environment
Write-ColorOutput Yellow "Activating virtual environment..."
& ".\venv\Scripts\Activate.ps1"

# Check if PyInstaller is installed
$pyinstaller = pip show pyinstaller 2>$null
if (-not $pyinstaller) {
    Write-ColorOutput Yellow "PyInstaller not found. Installing..."
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-ColorOutput Red "Error: Failed to install PyInstaller."
        exit 1
    }
}

# Install dependencies
Write-ColorOutput Yellow "Checking dependencies..."
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-ColorOutput Red "Error: Failed to install dependencies."
    exit 1
}

# Clean previous builds
if ($Clean -or $true) {
    Write-ColorOutput Yellow "Cleaning previous builds..."
    if (Test-Path $BuildDir) {
        Remove-Item -Recurse -Force $BuildDir
    }
    if (Test-Path "$DistDir\MultiDeck") {
        Remove-Item -Recurse -Force "$DistDir\MultiDeck"
    }
}

# Build PyInstaller arguments
$pyinstallerArgs = @("--clean", "--noconfirm")

if ($Debug) {
    Write-ColorOutput Yellow "Debug mode enabled - console window will be visible"
    # Modify spec temporarily or use command line
}

if ($OneFile) {
    Write-ColorOutput Yellow "Building single-file executable..."
    $pyinstallerArgs += "--onefile"
    $pyinstallerArgs += "src\main.py"
    $pyinstallerArgs += "--name=MultiDeck"
    $pyinstallerArgs += "--windowed"
    $pyinstallerArgs += "--add-data=locale;locale"
    $pyinstallerArgs += "--add-data=docs;docs"
    $pyinstallerArgs += "--hidden-import=numpy"
    $pyinstallerArgs += "--hidden-import=sounddevice"
    $pyinstallerArgs += "--hidden-import=soundfile"
    $pyinstallerArgs += "--hidden-import=wx.adv"
    $pyinstallerArgs += "--collect-data=sounddevice"
    $pyinstallerArgs += "--collect-data=soundfile"
} else {
    $pyinstallerArgs += $SpecFile
}

# Run PyInstaller
Write-ColorOutput Yellow "Running PyInstaller..."
& pyinstaller @pyinstallerArgs
if ($LASTEXITCODE -ne 0) {
    Write-ColorOutput Red "Error: PyInstaller build failed."
    exit 1
}

# Copy additional files and folders
Write-ColorOutput Yellow "Copying additional files and folders..."
$outputDir = if ($OneFile) { $DistDir } else { "$DistDir\MultiDeck" }

if (Test-Path "LICENSE") {
    Copy-Item "LICENSE" $outputDir -Force
}
if (Test-Path "config.ini.example") {
    Copy-Item "config.ini.example" $outputDir -Force
}

Write-Host ""
Write-ColorOutput Green "============================================"
Write-ColorOutput Green "  Build completed successfully!"
Write-ColorOutput Green "============================================"
Write-Host ""
Write-Host "Output directory: $outputDir"
Write-Host ""

# Show build size
$size = (Get-ChildItem $outputDir -Recurse | Measure-Object -Property Length -Sum).Sum
$sizeMB = [math]::Round($size / 1MB, 2)
Write-Host "Total size: $sizeMB MB"
Write-Host ""

# Deactivate virtual environment
deactivate
