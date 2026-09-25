@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
echo.
echo ============================================================
echo  RSF MAIN SYSTEM - SETUP
echo ============================================================
echo.

set "INSTALLER=%~dp0..\scripts\INSTALL_RSF_PARTNER_SYSTEM.py"
set "PYTHON="

if exist "%USERPROFILE%\Documents\RSF Main System\.venv\Scripts\python.exe" set "PYTHON=%USERPROFILE%\Documents\RSF Main System\.venv\Scripts\python.exe"
if not defined PYTHON if exist "%USERPROFILE%\Documents\RSF Main System\.venv\Scripts\python.exe" set "PYTHON=%USERPROFILE%\Documents\RSF Main System\.venv\Scripts\python.exe"
if defined PYTHON goto :run

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -c "import sys; print(sys.executable)" > "%TEMP%\rsf_python_path.txt" 2>nul
  if not errorlevel 1 set /p PYTHON=<"%TEMP%\rsf_python_path.txt"
  del /q "%TEMP%\rsf_python_path.txt" >nul 2>nul
)
if defined PYTHON goto :run

where python.exe >nul 2>nul
if not errorlevel 1 set "PYTHON=python.exe"

if not defined PYTHON (
  echo ERROR: Python 3 was not found.
  echo Install Python 3.10 or newer, enable "Add Python to PATH", then run this setup again.
  pause
  exit /b 1
)

:run
"%PYTHON%" "%INSTALLER%"
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo SETUP FAILED. Review the message above.
  pause
  exit /b %CODE%
)

echo.
echo SETUP COMPLETE.
echo Two online desktop shortcuts have been recreated: "Realty Systems Foundry Website" and "RSF Partner System".
pause
exit /b 0
