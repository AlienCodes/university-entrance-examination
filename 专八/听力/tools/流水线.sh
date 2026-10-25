#!/bin/bash
# 专八听力视频：一次启动、出错即停（踩坑 73：不用临时串的 && | tail，管道会吞掉退出码）
# 自检 → 字体 → 时间轴 → 截图（每张检查）→ 视频（成品核查）→ 提交发布
set -euo pipefail
cd "$(dirname "$0")"
export TEM8_OUT=${TEM8_OUT:?要设 TEM8_OUT}
WAV=${1:?原音 wav 路径}
PY=/opt/ttsenv/bin/python
$PY 取字体.py
$PY 听力视频.py --自检
$PY 听力视频.py timeline "$WAV"
$PY 听力视频.py stills
$PY 听力视频.py video "$WAV" --试跑      # 480p 极速试跑，帧数、声画时长不对就停（几分钟）
$PY 听力视频.py video "$WAV"
bash 提交发布.sh
echo "流水线全部完成"
