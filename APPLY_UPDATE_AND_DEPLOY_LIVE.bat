@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title REALTY SYSTEMS FOUNDRY - UPDATE AND DEPLOY LIVE

echo.
echo ======================================================
echo   REALTY SYSTEMS FOUNDRY - ONE RUN UPDATE + LIVE DEPLOY
echo ======================================================
echo.
echo Local setup, tests, Git pushes, Render deployment,
echo and LIVE verification will run automatically.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\UPDATE_AND_DEPLOY_RENDER.ps1"
if errorlevel 1 goto :fail

echo.
echo SUCCESS: The updated REALTY SYSTEMS FOUNDRY website is LIVE and verified.
echo.
exit /b 0

:fail
echo.
echo DEPLOYMENT STOPPED OR FAILED.
echo Read the exact error above. The script does not report success unless
echo the live Render website passes the final verification.
echo.
exit /b 1
