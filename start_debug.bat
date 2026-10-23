@echo off
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
where python >nul 2>nul && (python CS2Keys.pyw) || (py CS2Keys.pyw)
pause
