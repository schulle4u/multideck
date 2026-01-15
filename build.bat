@echo off
REM ============================================
REM Build Script for MultiDeck Audio Player
REM ============================================

setlocal enabledelayedexpansion

REM Configuration
set APP_NAME=MultiDeck Audio Player
set SPEC_FILE=multideck.spec
set DIST_DIR=dist
set BUILD_DIR=build

REM Colors for output (Windows 10+)
set "GREEN=[32m"
set "YELLOW=[33m"
set "RED=[31m"
set "RESET=[0m"

echo.
echo %GREEN%============================================%RESET%
echo %GREEN%  Building %APP_NAME%%RESET%
echo %GREEN%============================================%RESET%
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo %RED%Error: Virtual environment not found.%RESET%
    echo Please create it first with: python -m venv venv
    exit /b 1
)

REM Activate virtual environment
echo %YELLOW%Activating virtual environment...%RESET%
call venv\Scripts\activate.bat

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo %YELLOW%PyInstaller not found. Installing...%RESET%
    pip install pyinstaller
    if errorlevel 1 (
        echo %RED%Error: Failed to install PyInstaller.%RESET%
        exit /b 1
    )
)

REM Check if all dependencies are installed
echo %YELLOW%Checking dependencies...%RESET%
pip install -r requirements.txt
if errorlevel 1 (
    echo %RED%Error: Failed to install dependencies.%RESET%
    exit /b 1
)

REM Clean previous builds
echo %YELLOW%Cleaning previous builds...%RESET%
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%DIST_DIR%\MultiDeck" rmdir /s /q "%DIST_DIR%\MultiDeck"

REM Run PyInstaller
echo %YELLOW%Running PyInstaller...%RESET%
pyinstaller --clean --noconfirm "%SPEC_FILE%"
if errorlevel 1 (
    echo %RED%Error: PyInstaller build failed.%RESET%
    exit /b 1
)

REM Copy additional files and folders
echo %YELLOW%Copying additional files and folders...%RESET%
if exist "LICENSE" copy /y "LICENSE" "%DIST_DIR%\MultiDeck\" >nul
if exist "config.ini.example" copy /y "config.ini.example" "%DIST_DIR%\MultiDeck\" >nul
if exist "locale\" xcopy /E "locale\" "%DIST_DIR%\MultiDeck\locale\" >nul
if exist "docs\" xcopy /E "docs\" "%DIST_DIR%\MultiDeck\docs\" >nul
if exist "README.md" copy /y "README.md" "%DIST_DIR%\MultiDeck\docs\" >nul

echo.
echo %GREEN%============================================%RESET%
echo %GREEN%  Build completed successfully!%RESET%
echo %GREEN%============================================%RESET%
echo.
echo Output directory: %DIST_DIR%\MultiDeck
echo.

REM Show build size
for /f "tokens=3" %%a in ('dir /s "%DIST_DIR%\MultiDeck" ^| findstr "File(s)"') do set SIZE=%%a
echo Total size: %SIZE% bytes
echo.

REM Deactivate virtual environment
deactivate

pause
