#!/bin/bash
# 六级听力练习视频样片：开头说明 + Section A 第一段对话 + 第 1—N 题（CET6_CUT=N），出错即停（pipefail，踩坑 73、77）
# 只管调度：截断原音、整体增益 + 限幅、编码、1080p 预览都在专八引擎里（考试原声，不是 TTS）
# 用法：bash 样片.sh <套> 原音.mp3 [N=4]      输出 $CET6_OUT/
set -euo pipefail
cd "$(dirname "$0")/../../.."
SID=$1; MP3=$2; export CET6_CUT=${3:-4}
export CET6_OUT=${CET6_OUT:-/tmp/cet6listen/$SID-sample}
P=/opt/ttsenv/bin/python; T=六级/听力/tools/听力视频.py
mkdir -p "$CET6_OUT"
$P $T $SID --自检
$P $T $SID timeline "$MP3"
$P $T $SID stills
$P $T $SID video "$MP3" --试跑
$P $T $SID video "$MP3"
$P $T $SID preview
echo "样片完成"
