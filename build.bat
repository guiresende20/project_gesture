@echo off
echo ============================================
echo   Gesture Keys - Build Installer
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)

REM Install build dependencies
echo [1/3] Installing dependencies...
pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [2/3] Building GestureKeys.exe ...
echo This may take a few minutes...
echo.
python -m PyInstaller gesture_keys.spec --noconfirm
if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   BUILD COMPLETE!
echo ============================================
echo.
echo Output: dist\GestureKeys\GestureKeys.exe
echo.
echo To distribute, share the whole dist\GestureKeys folder.
echo Users run GestureKeys.exe from inside that folder - no install needed!
echo.
pause
