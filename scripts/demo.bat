@echo off
setlocal
cd /d "%~dp0.."
call "%~dp0start_influxdb.bat"
if errorlevel 1 exit /b 1
set "PYTHON_CMD=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_CMD=.venv\Scripts\python.exe"
"%PYTHON_CMD%" cli\demo.py
endlocal
