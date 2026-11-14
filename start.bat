@echo off
rem Run from source: installs libraries on first run, then starts the app without a console.
cd /d "%~dp0"
call "%~dp0tools\findpy.bat"
if errorlevel 1 (
  pause
  exit /b 1
)
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
start "" %PYW% CS2Keys.pyw
