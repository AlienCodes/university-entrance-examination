@echo off
rem Generate Spanish reading videos (Windows). Runs the kit's batch.py with the kit's .venv Python; arguments are passed through.
rem   (this file) es01
rem   (this file) all --voice supertonic3_M1F5_25 --style 5
rem   (this file) --list   /   --check   /   --help
setlocal
set "KIT=%~dp0"
set "PY=%KIT%.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [error] Not installed yet. Double-click install_windows.bat first.
  pause
  exit /b 1
)
set "BATCH="
for /d %%D in ("%KIT%*") do if exist "%%~fD\tools\batch.py" set "BATCH=%%~fD\tools\batch.py"
if not defined BATCH (
  echo [error] tools\batch.py not found next to this file.
  pause
  exit /b 1
)
set PYTHONUTF8=1
"%PY%" -X utf8 "%BATCH%" %*
set RC=%ERRORLEVEL%
if "%~1"=="" pause
exit /b %RC%
