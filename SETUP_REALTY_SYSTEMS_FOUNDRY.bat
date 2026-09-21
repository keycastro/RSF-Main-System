@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title REALTY SYSTEMS FOUNDRY - LOCAL SETUP

echo.
echo ======================================================
echo   REALTY SYSTEMS FOUNDRY - LOCAL SETUP
echo ======================================================
echo.
echo This will:
echo   - migrate the old KEY_CASTRO_WEBSITE folder when present
echo   - install/update the website in Documents\REALTY_SYSTEMS_FOUNDRY
echo   - preserve private local configuration
echo   - run the full website tests
echo   - create REALTY SYSTEMS FOUNDRY and RSF INBOX desktop shortcuts
echo   - open the live website
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\INSTALL_WEBSITE.ps1"
if errorlevel 1 goto :fail

echo.
echo SETUP COMPLETE.
echo From now on, use the REALTY SYSTEMS FOUNDRY desktop shortcut.
echo.
pause
exit /b 0

:fail
echo.
echo SETUP FAILED. Read the message above.
echo.
pause
exit /b 1
