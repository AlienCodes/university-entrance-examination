@echo off
rem Install the Spanish reading video kit (Windows). Double-click, or run from cmd:
rem   install_windows.bat            basic install (Supertonic voices + 4K video + checks)
rem   install_windows.bat -Qwen3     also install PyTorch etc. for the Qwen3 voice
rem   install_windows.bat -Mirror    use mirrors inside China (Tsinghua PyPI, npmmirror)
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_windows.ps1" %*
set RC=%ERRORLEVEL%
pause
exit /b %RC%
