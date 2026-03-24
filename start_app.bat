@echo off
setlocal
cd /d "%~dp0"

start "Dodge AI Backend" cmd /k ""%~dp0start_backend.bat""
timeout /t 3 >nul
start "" http://127.0.0.1:5000
