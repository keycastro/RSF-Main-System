@echo off
setlocal EnableExtensions DisableDelayedExpansion
for %%I in ("%~dp0..") do set "RSF_RELEASE_ROOT=%%~fI"
set "DEPLOY_SCRIPT=%RSF_RELEASE_ROOT%\scripts\deploy_render_unified.py"
set "LOCAL_PYTHON=%USERPROFILE%\Documents\RSF Main System\.venv\Scripts\python.exe"

pushd "%RSF_RELEASE_ROOT%" >nul 2>nul
if errorlevel 1 (
  echo ERROR: Could not open the RSF release folder.
  exit /b 1
)
title RSF MAIN SYSTEM - VERIFIED MAIN DEPLOY

echo.
echo RSF deployment rule:
echo   1. Merge verified GitHub PR to main
echo   2. Deploy exact main commit
echo   3. Verify live health and workspace
echo.
echo Direct source publishing and password-recovery deployment are disabled.
echo.

if not exist "%DEPLOY_SCRIPT%" (
  echo ERROR: Deployment script was not found.
  popd
  exit /b 1
)

if exist "%LOCAL_PYTHON%" goto :run_local
where py.exe >nul 2>nul
if not errorlevel 1 goto :run_py
where python.exe >nul 2>nul
if not errorlevel 1 goto :run_python

echo ERROR: Python 3 was not found.
popd
exit /b 1

:run_py
py.exe -3 "%DEPLOY_SCRIPT%"
goto :done

:run_python
python.exe "%DEPLOY_SCRIPT%"
goto :done

:run_local
"%LOCAL_PYTHON%" "%DEPLOY_SCRIPT%"

:done
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo LIVE DEPLOYMENT AND LIVE CHECK PASSED.
) else (
  echo LIVE DEPLOYMENT DID NOT COMPLETE.
)
popd
exit /b %RC%
