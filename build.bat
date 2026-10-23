@echo off
rem Builds "dist\CS2 Demo to Keyboard.exe" locally (a few minutes, needs internet once).
rem GitHub can also build it for you: Actions tab -> Release workflow (.github/workflows/release.yml).
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
%PY% -m pip install --user -r requirements.txt pyinstaller
if errorlevel 1 goto fail
%PY% tools\build.py
if errorlevel 1 goto fail
echo.
echo Ready: dist\CS2 Demo to Keyboard.exe
pause
exit /b 0
:fail
echo.
echo ERROR: build failed. See the messages above.
pause
exit /b 1
