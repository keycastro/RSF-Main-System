@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Resolve the source root before using any relative paths.
rem This stays correct even when this BAT is called through a quoted path with spaces.
pushd "%~dp0.." >nul 2>nul
if errorlevel 1 (
  echo.
  echo ERROR: Could not open the RSF setup source folder.
  echo Setup location: %~f0
  if not "%RSF_NO_PAUSE%"=="1" pause
  exit /b 1
)
set "SOURCE=%CD%"
set "INSTALLER=%SOURCE%\scripts\INSTALL_RSF_PARTNER_SYSTEM.py"

echo.
echo ============================================================
echo  RSF MAIN SYSTEM - SETUP
echo ============================================================
echo.

if not exist "%INSTALLER%" (
  echo ERROR: Installer script was not found.
  echo Expected: %INSTALLER%
  popd
  if not "%RSF_NO_PAUSE%"=="1" pause
  exit /b 1
)

rem Never build a command string from a path. Each executable/script path is
rem passed as its own quoted argument so "RSF Main System" cannot be split.
set "LOCAL_PYTHON=%USERPROFILE%\Documents\RSF Main System\.venv\Scripts\python.exe"
if exist "%LOCAL_PYTHON%" goto :run_local

where py.exe >nul 2>nul
if not errorlevel 1 goto :run_py

where python.exe >nul 2>nul
if not errorlevel 1 goto :run_python

echo ERROR: Python 3 was not found.
echo Install Python 3.10 or newer, enable "Add Python to PATH", then run this setup again.
popd
if not "%RSF_NO_PAUSE%"=="1" pause
exit /b 1

:run_local
"%LOCAL_PYTHON%" "%INSTALLER%"
goto :after_run

:run_py
py.exe -3 "%INSTALLER%"
goto :after_run

:run_python
python.exe "%INSTALLER%"

:after_run
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo SETUP FAILED. Review the message above.
  popd
  if not "%RSF_NO_PAUSE%"=="1" pause
  exit /b %CODE%
)

echo.
echo LOCAL SETUP COMPLETE.
echo Local files and data were verified.
echo Live Render deployment was NOT run by this local setup file.
echo Use SETUP_AND_DEPLOY_RSF_MAIN_SYSTEM.bat when you want local + live verification.
popd
if not "%RSF_NO_PAUSE%"=="1" pause
exit /b 0
