#!/bin/bash
# 第 56 题样片（用户本人声音）：等 Actions 上 任务_用户声音_q56 新的一次合成（运行号 > AFTER）→ 全片.sh 只做 q56 各段
# （选段：逐小段选优、问句尾音、整篇响度 / 呼吸 / 节奏检查 → 截图排版检查 → 视频成品核查）→ 像不像评分 + 节奏实测 → 提交推送。出错即停。
# 用法：REC=录音.wav AFTER=9 VOICE=2 bash 高考语法填空/tools/样片56.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=/opt/ttsenv/bin/python
BR=claude/epic-edison-4gkcfb
AFTER=${AFTER:-0}; VOICE=${VOICE:-2}
T=$(mktemp -d)
B=""
for k in $(seq 75); do
  git fetch -q origin gram-tts-out || true
  b=$(git -c core.quotepath=false ls-tree --name-only origin/gram-tts-out runs/ 2>/dev/null | grep '任务_用户声音_q56-' | sort -V | tail -1 || true)
  if [ -n "$b" ] && [ "${b##*-}" -gt "$AFTER" ]; then B=$b; break; fi
  sleep 120
done
[ -n "$B" ] || { echo "2.5 小时内没等到合成结果"; exit 1; }
echo "合成结果：$B"
git archive origin/gram-tts-out "$B" | tar -x -C "$T"
NAME="2026 新课标Ⅰ卷 语法填空 第56题样片（用户本人声音）"
Q=$(python3 -c "import json; print(' '.join(json.load(open('高考语法填空/tts/任务_用户声音_q56.json'))['only']))")
bash 高考语法填空/tools/全片.sh 高考语法填空/稿/2026_新课标Ⅰ卷.json "$T/$B/user$VOICE" "$NAME" $Q
$PY 高考语法填空/tools/像不像.py --录音 "$REC" --参考 高考语法填空/tts/音色/用户本人_*.json --样音 "高考语法填空/audio/$NAME.mp3" \
    --out 高考语法填空/样音/像不像_第56题样片.md
$PY 高考语法填空/tools/讲解节奏.py "高考语法填空/audio/$NAME.mp3" > 高考语法填空/样音/节奏_第56题样片.txt
tail -1 高考语法填空/样音/节奏_第56题样片.txt
$PY tools/防复发/验证/讲解节奏.py
git add "高考语法填空/audio/" "高考语法填空/最终视频/" 高考语法填空/样音/像不像_第56题样片.md 高考语法填空/样音/节奏_第56题样片.txt
git commit -qm "高考语法填空：第 56 题样片第 2 版（改稿、‖ 停顿、问句尾音；节奏、呼吸、响度、成品核查全部通过）"
for i in 1 2 3 4; do git push -q origin "$BR" && break; sleep $((2**i)); done
rm -rf "$T"
echo 样片56完成
