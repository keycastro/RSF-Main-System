@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Always resolve the release root first. All later BAT calls are relative to the
rem current directory so Windows never has to reinterpret an unquoted project path.
for %%I in ("%~dp0..") do set "RSF_RELEASE_ROOT=%%~fI"
pushd "%RSF_RELEASE_ROOT%" >nul 2>nul
if errorlevel 1 (
  echo ERROR: Could not open the RSF release folder.
  echo Release: %RSF_RELEASE_ROOT%
  set "FINAL_RC=1"
  goto :finish
)

echo.
echo ============================================================
echo  RSF MAIN SYSTEM - LOCAL UPDATE + LIVE DEPLOY
echo ============================================================
echo.

set "RSF_NO_PAUSE=1"
call "installers\SETUP_RSF_MAIN_SYSTEM.bat"
set "RC=%ERRORLEVEL%"
set "RSF_NO_PAUSE="
if not "%RC%"=="0" (
  echo.
  echo LOCAL UPDATE FAILED. LIVE DEPLOYMENT WAS NOT STARTED.
  set "FINAL_RC=%RC%"
  goto :leave_root
)

echo.
echo ============================================================
echo  LOCAL VERIFIED OK - STARTING LIVE DEPLOYMENT
echo ============================================================
echo.

call "deployment\DEPLOY_RSF_LIVE.bat"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo LOCAL VERIFIED OK
  echo LIVE VERIFIED: FAILED OR NOT COMPLETED
  echo Do not treat this release as complete yet.
  set "FINAL_RC=%RC%"
  goto :leave_root
)

echo.
echo ============================================================
echo  RSF UPDATE COMPLETE
echo ============================================================
echo LOCAL VERIFIED OK
echo LIVE VERIFIED OK
echo.
set "FINAL_RC=0"

:leave_root
popd

:finish
if not defined FINAL_RC set "FINAL_RC=1"
echo.
echo CMD will remain open so you can copy the complete result.
pause
exit /b %FINAL_RC%
