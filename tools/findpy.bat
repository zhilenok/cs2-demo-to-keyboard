@echo off
rem Sets PY / PYW to a supported Python (3.10-3.14). If none is found, installs Python 3.12 automatically.
rem Python 3.15+ is skipped: demoparser2 has no build for it yet.
set "PY="
set "PYW="
call :find
if defined PY goto done
echo.
echo Python 3.12 not found - installing it automatically (one time, a few minutes)...
echo.
rem 1) new Python install manager (py install)
where py >nul 2>nul && py install 3.12
call :find
if defined PY goto done
rem 2) Windows package manager
where winget >nul 2>nul && winget install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements
call :find
if defined PY goto done
echo.
echo ERROR: could not find or install Python 3.12.
echo Install it manually: https://www.python.org/downloads/release/python-31210/
echo (tick "Add python.exe to PATH"), then run this file again.
exit /b 1
:done
echo Using Python: %PY%
exit /b 0

:find
for %%V in (3.12 3.13 3.11 3.14 3.10) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>nul && (
      set "PY=py -%%V"
      set "PYW=pyw -%%V"
    )
  )
)
if defined PY exit /b 0
for %%D in ("%LOCALAPPDATA%\Python\pythoncore-3.12-64" "%LOCALAPPDATA%\Programs\Python\Python312") do (
  if not defined PY (
    if exist "%%~D\python.exe" (
      set PY="%%~D\python.exe"
      set PYW="%%~D\pythonw.exe"
    )
  )
)
if defined PY exit /b 0
python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,14) else 1)" >nul 2>nul && (
  set "PY=python"
  set "PYW=pythonw"
)
exit /b 0
