@echo off
setlocal EnableExtensions DisableDelayedExpansion

for %%I in ("%~dp0..") do set "RSF_RELEASE_ROOT=%%~fI"
set "PUBLISH_SCRIPT=%RSF_RELEASE_ROOT%\scripts\PUBLISH_RSF_ONLINE.py"

pushd "%RSF_RELEASE_ROOT%" >nul 2>nul
if errorlevel 1 (
  echo ERROR: Could not open the RSF release folder.
  exit /b 1
)
title RSF MAIN SYSTEM - SAFE SOURCE PUBLISH

if not exist "%PUBLISH_SCRIPT%" (
  echo ERROR: Publish script was not found.
  echo Expected: %PUBLISH_SCRIPT%
  popd
  exit /b 1
)

where py.exe >nul 2>nul
if not errorlevel 1 goto :run_py

where python.exe >nul 2>nul
if not errorlevel 1 goto :run_python

set "LOCAL_PYTHON=%RSF_RELEASE_ROOT%\.venv\Scripts\python.exe"
if exist "%LOCAL_PYTHON%" goto :run_local

set "LOCAL_PYTHON=%USERPROFILE%\Documents\RSF Main System\.venv\Scripts\python.exe"
if exist "%LOCAL_PYTHON%" goto :run_local

echo ERROR: Python 3 was not found.
popd
exit /b 1

:run_py
py.exe -3 "%PUBLISH_SCRIPT%"
goto :done

:run_python
python.exe "%PUBLISH_SCRIPT%"
goto :done

:run_local
"%LOCAL_PYTHON%" "%PUBLISH_SCRIPT%"

:done
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
