@echo off
setlocal

:: ========================================
:: KonataAPI Build Script (Conda)
:: ========================================

:: Conda install path
set CONDA_PATH=

:: Conda env name or path
set CONDA_ENV=

echo ========================================
echo   KonataAPI - Build Start
echo ========================================
echo.

:: Init conda
echo [1/4] Activating Conda...
call "%CONDA_PATH%\condabin\conda.bat" activate %CONDA_ENV%
if errorlevel 1 (
    echo [ERROR] Conda activation failed
    pause
    exit /b 1
)

:: Check pyinstaller
echo [2/4] Checking PyInstaller...
where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

:: Clean old files
echo [3/4] Cleaning old files...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "*.spec" del /q *.spec

:: Build
echo [4/4] Building...
echo.

pyinstaller --onefile --windowed --name "KonataAPI" ^
    --icon=assets/icon.ico ^
    --add-data "assets;assets" ^
    --add-data "config;config" ^
    --add-data "src/konata_api;konata_api" ^
    --hidden-import=ttkbootstrap ^
    --hidden-import=ttkbootstrap.themes ^
    --hidden-import=ttkbootstrap.style ^
    --hidden-import=ttkbootstrap.widgets ^
    --hidden-import=ttkbootstrap.widgets.scrolled ^
    --hidden-import=ttkbootstrap.constants ^
    --hidden-import=ttkbootstrap.window ^
    --collect-submodules=ttkbootstrap ^
    --hidden-import=PIL ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=PIL.Image ^
    --hidden-import=PIL.ImageTk ^
    --hidden-import=requests ^
    --hidden-import=httpx ^
    --hidden-import=pystray ^
    --hidden-import=pystray._win32 ^
    --hidden-import=uuid ^
    --hidden-import=matplotlib ^
    --collect-submodules=matplotlib ^
    --clean ^
    --noconfirm ^
    main.py

echo.
if exist "dist\KonataAPI.exe" (
    echo ========================================
    echo   Build Success!
    echo   Output: dist\KonataAPI.exe
    echo ========================================
    if not exist "dist\config" mkdir "dist\config"
    copy "config\config.example.json" "dist\config\" >nul 2>&1
    copy "config\cli_tools.json" "dist\config\" >nul 2>&1
    copy "config\cli_system.json" "dist\config\" >nul 2>&1
    echo   Config files copied to dist\config\
) else (
    echo ========================================
    echo   Build Failed!
    echo ========================================
)

echo.
pause
