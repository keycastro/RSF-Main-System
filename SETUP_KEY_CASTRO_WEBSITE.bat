@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title KEY CASTRO WEBSITE - ONE-TIME SETUP

echo.
echo ======================================================
echo   KEY CASTRO WEBSITE - ONE-TIME LOCAL SETUP
echo ======================================================
echo.
echo This will:
echo   - install the website into your Documents folder
echo   - create an isolated Python environment
echo   - install the required packages
echo   - generate local security configuration
echo   - run local website tests
echo   - create the KEY CASTRO desktop icon
echo   - launch the website in your browser
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\INSTALL_WEBSITE.ps1"
if errorlevel 1 goto :fail

echo.
echo SETUP COMPLETE.
echo From now on, use the KEY CASTRO desktop icon.
echo.
pause
exit /b 0

:fail
echo.
echo SETUP FAILED. Read the message above and check the logs if created.
echo.
pause
exit /b 1
