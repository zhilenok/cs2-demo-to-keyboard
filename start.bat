@echo off
rem Run from source: installs libraries on first run, then starts the app without a console.
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
%PY% -c "import demoparser2, customtkinter, tkinterdnd2, PIL" >nul 2>nul
if errorlevel 1 (
  echo Installing libraries - first run or update, please wait...
  %PY% -m pip install --user -r requirements.txt
  %PY% -c "import demoparser2, customtkinter, tkinterdnd2, PIL" >nul 2>nul
  if errorlevel 1 (
    echo.
    echo ERROR: library was not installed. See the messages above.
    pause
    exit /b 1
  )
)
start "" %PY%w CS2Keys.pyw
