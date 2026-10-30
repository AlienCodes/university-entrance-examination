@echo off
REM Windows 一键安装：双击运行，或在命令行运行 setup_windows.bat （加 --qa 安装自检工具）
cd /d "%~dp0"
python -m venv .venv || goto :err
.venv\Scripts\python -m pip install -U pip setuptools wheel || goto :err
.venv\Scripts\pip install -r requirements.txt || goto :err
if "%1"=="--qa" .venv\Scripts\pip install -r requirements-qa.txt
.venv\Scripts\python download_models.py %* || goto :err
echo 安装完成。示例： .venv\Scripts\python gaokao_tts.py say "Hello, nice to meet you." -o hello.mp3
pause
exit /b 0
:err
echo 安装失败，请确认已安装 Python 3.10 以上版本并勾选 Add to PATH。
pause
exit /b 1
