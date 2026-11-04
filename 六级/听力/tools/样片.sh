#!/bin/bash
# 六级听力练习视频样片：开头说明 + Section A 第一段对话 + 第 1—N 题（CET6_CUT=N），出错即停（pipefail，踩坑 73、77）
# 用法：bash 样片.sh <套> 原音.mp3 [N=4]      输出 $CET6_OUT/（4K 成品 + 1080p 预览）
set -euo pipefail
cd "$(dirname "$0")/../../.."
SID=$1; MP3=$2; export CET6_CUT=${3:-4}
export CET6_OUT=${CET6_OUT:-/tmp/cet6listen/$SID-sample}
P=/opt/ttsenv/bin/python; T=六级/听力/tools/听力视频.py
mkdir -p "$CET6_OUT"
$P $T $SID --自检
$P $T $SID timeline "$MP3"
# 截断的原音（与识别同一个解码器 soundfile 读），整体增益到 −16 LUFS + 前瞻限幅（原音电平.py）
END=$($P -c "import json;print(json.load(open('六级/听力/$SID/时间轴.json'))['audioEnd'])")
$P 六级/听力/tools/原音电平.py "$MP3" "$CET6_OUT/cut.wav" "$END"
$P $T $SID stills
$P $T $SID video "$CET6_OUT/cut.wav" --试跑
$P $T $SID video "$CET6_OUT/cut.wav"
F="$CET6_OUT/$(ls "$CET6_OUT" | grep 视频版真题考试.mp4)"
ffmpeg -y -v error -i "$F" -vf scale=1920:1080:flags=lanczos -c:v libx264 -crf 20 -preset medium -c:a copy -movflags +faststart "$CET6_OUT/样片_1080p.mp4"
echo "样片完成：$CET6_OUT/样片_1080p.mp4"
