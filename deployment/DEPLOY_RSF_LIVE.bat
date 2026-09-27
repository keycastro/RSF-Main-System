@echo off
setlocal EnableExtensions DisableDelayedExpansion

for %%I in ("%~dp0..") do set "RSF_RELEASE_ROOT=%%~fI"
set "DEPLOY_SCRIPT=%RSF_RELEASE_ROOT%\scripts\deploy_render_unified.py"

pushd "%RSF_RELEASE_ROOT%" >nul 2>nul
if errorlevel 1 (
  echo ERROR: Could not open the RSF release folder.
  exit /b 1
)
title RSF MAIN SYSTEM - LIVE DEPLOY

if not exist "%DEPLOY_SCRIPT%" (
  echo ERROR: Live deployment script was not found.
  echo Expected: %DEPLOY_SCRIPT%
  popd
  exit /b 1
)

rem Prefer the Windows Python launcher so the deployment never depends on a
rem project path with spaces. Fall back to an explicitly quoted venv executable.
where py.exe >nul 2>nul
if not errorlevel 1 goto :run_py

where python.exe >nul 2>nul
if not errorlevel 1 goto :run_python

set "LOCAL_PYTHON=%RSF_RELEASE_ROOT%\.venv\Scripts\python.exe"
if exist "%LOCAL_PYTHON%" goto :run_local

set "LOCAL_PYTHON=%USERPROFILE%\Documents\RSF Main System\.venv\Scripts\python.exe"
if exist "%LOCAL_PYTHON%" goto :run_local

echo ERROR: Python 3 was not found for live deployment.
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
  echo The release is NOT complete until LIVE VERIFIED OK appears.
)
popd
exit /b %RC%
