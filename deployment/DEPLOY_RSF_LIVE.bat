@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Resolve the release root once. Every path that can contain spaces is kept in a
rem quoted SET assignment and every executable/script path is quoted at launch.
for %%I in ("%~dp0..") do set "RSF_RELEASE_ROOT=%%~fI"
set "NORMAL_DEPLOY=%RSF_RELEASE_ROOT%\scripts\deploy_render_unified.py"
set "RECOVERY_DEPLOY=%RSF_RELEASE_ROOT%\scripts\RECOVER_NEW_RENDER_HOSTING.py"
set "INSTALLED_ROOT=%USERPROFILE%\Documents\RSF Main System"
set "RECOVERY_MARKER=%INSTALLED_ROOT%\runtime\render_recovery_complete.json"
set "LOCAL_PYTHON=%INSTALLED_ROOT%\.venv\Scripts\python.exe"

pushd "%RSF_RELEASE_ROOT%" >nul 2>nul
if errorlevel 1 (
  echo ERROR: Could not open the RSF release folder.
  exit /b 1
)
title RSF MAIN SYSTEM - LIVE DEPLOY

rem First live run after the old Render project was deleted uses the recovery
rem deployer. After recovery is verified, all later runs use the normal deployer.
if exist "%RECOVERY_MARKER%" (
  set "DEPLOY_SCRIPT=%NORMAL_DEPLOY%"
) else (
  set "DEPLOY_SCRIPT=%RECOVERY_DEPLOY%"
  echo.
  echo NEW RENDER HOSTING DETECTED
  echo The old Render project was deleted, so this run will:
  echo   - link the new Postgres database
  echo   - preserve and migrate local Founder/Partner data
  echo   - preserve current password hashes and encrypted password vault
  echo   - migrate protected attachments
  echo   - deploy the exact GitHub commit
  echo   - verify real Name + Password login online
  echo.
)

if not exist "%DEPLOY_SCRIPT%" (
  echo ERROR: Live deployment script was not found.
  echo Expected: "%DEPLOY_SCRIPT%"
  popd
  exit /b 1
)

rem Prefer the installed RSF virtual environment because it is guaranteed to have
rem the release dependencies. The py/python fallbacks keep the launcher portable.
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
  echo The release is NOT complete until LIVE VERIFIED OK appears.
)
popd
exit /b %RC%
