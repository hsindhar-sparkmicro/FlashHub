@echo off
REM Build script for Windows

echo === Building FlashHub for Windows ===

REM Activate virtual environment if it exists
if exist vnev\Scripts\activate.bat (
    call vnev\Scripts\activate.bat
)

REM Install PyInstaller if not present
pip install pyinstaller

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build with spec file
pyinstaller FlashHub.spec

echo.
echo === Build Complete ===
echo Executable created: dist\FlashHub.exe
echo.
pause
