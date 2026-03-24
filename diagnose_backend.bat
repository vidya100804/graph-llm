@echo off
setlocal
cd /d "%~dp0backend"

set "LOGFILE=%~dp0backend-startup.log"
if exist "%LOGFILE%" del "%LOGFILE%"

echo Dodge AI backend diagnostic > "%LOGFILE%"
echo =========================>> "%LOGFILE%"
echo Working directory: %CD%>> "%LOGFILE%"
echo.>> "%LOGFILE%"

set "PYTHON_EXE=C:\Users\91709\AppData\Local\Programs\Python\Python310\python.exe"
if exist "%PYTHON_EXE%" (
  echo Using Python: %PYTHON_EXE%>> "%LOGFILE%"
  "%PYTHON_EXE%" --version >> "%LOGFILE%" 2>&1
  echo.>> "%LOGFILE%"
  echo Starting backend...>> "%LOGFILE%"
  "%PYTHON_EXE%" app.py >> "%LOGFILE%" 2>&1
) else (
  echo Python not found at expected path. Falling back to PATH lookup.>> "%LOGFILE%"
  python --version >> "%LOGFILE%" 2>&1
  echo.>> "%LOGFILE%"
  echo Starting backend...>> "%LOGFILE%"
  python app.py >> "%LOGFILE%" 2>&1
)

echo.>> "%LOGFILE%"
echo Backend process exited.>> "%LOGFILE%"

echo Diagnostic written to:
echo %LOGFILE%
echo.
type "%LOGFILE%"
echo.
echo Press any key to close this window.
pause >nul
