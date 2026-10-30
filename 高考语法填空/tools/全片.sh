#!/bin/bash
# 全片一次跑完（出错即停）：逐段选优 + 完整处理链 → 截图（排版检查）→ 视频（成品核查）。
# 用法：bash 高考语法填空/tools/全片.sh <稿.json> <原始音频目录 runs/任务_全片-N/音色> <成品名（不含扩展名）>
set -euo pipefail
cd "$(dirname "$0")/../.."
稿=$1; RUN=$2; NAME=$3
PY=/opt/ttsenv/bin/python
mkdir -p 高考语法填空/audio 高考语法填空/最终视频
$PY 高考语法填空/tools/选段.py --稿 "$稿" --run "$RUN" --out "高考语法填空/audio/$NAME.mp3"
$PY 高考语法填空/tools/讲解视频.py --稿 "$稿" --音频 "高考语法填空/audio/$NAME.mp3" --video \
    --out 高考语法填空/最终视频 --png "${TMPDIR:-/tmp}/gram_png_$$" --name "$NAME.mp4"
rm -rf "${TMPDIR:-/tmp}/gram_png_$$"
echo 全片完成
