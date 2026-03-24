@echo off
setlocal
cd /d "%~dp0backend"

set "PYTHON_EXE=C:\Users\91709\AppData\Local\Programs\Python\Python310\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

echo Starting Dodge AI backend...
echo.
"%PYTHON_EXE%" app.py

echo.
echo Backend stopped. Press any key to close this window.
pause >nul
