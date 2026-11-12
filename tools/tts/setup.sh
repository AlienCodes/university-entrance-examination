#!/usr/bin/env bash
# Mac / Linux 一键安装：bash setup.sh        （加 --qa 安装自检工具）
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install -U pip setuptools wheel
.venv/bin/pip install -r requirements.txt
if [ "$1" = "--qa" ]; then .venv/bin/pip install -r requirements-qa.txt; fi
.venv/bin/python download_models.py "$@"
echo "安装完成。示例： .venv/bin/python gaokao_tts.py say \"Hello, nice to meet you.\" -o hello.mp3"
