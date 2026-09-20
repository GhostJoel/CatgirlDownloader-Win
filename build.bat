@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal

echo === Installing dependencies ===
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto error

echo === Generating icon ===
python make_icon.py
if errorlevel 1 goto error

echo === Building executable ===
python -m PyInstaller --noconfirm --clean --onefile --windowed --icon "icon.ico" --add-data "icon.ico;." --name CatgirlDownloader app.py
if errorlevel 1 goto error

echo.
echo Done. Output: dist\CatgirlDownloader.exe
goto end

:error
echo.
echo Build failed. See errors above.

:end
echo.
pause
