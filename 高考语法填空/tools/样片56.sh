#!/bin/bash
# 用户本人声音：等两个 Actions 合成（第 56 题样稿 × 两个参考、正式稿 q56 × 两个参考）→ 每个参考 选段 出样音（完整处理链、去呼吸、合格证）
# → 像不像.py 量说话人相似度与自然度 → 相似度高的那个参考做第 56 题样片（全片.sh 只做 q56 各段：截图排版检查 + 成品核查）→ 提交推送。出错即停。
# 用法：REC=录音.wav bash 高考语法填空/tools/样片56.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=/opt/ttsenv/bin/python
BR=claude/epic-edison-4gkcfb
T=$(mktemp -d)
latest() { git ls-tree --name-only origin/gram-tts-out runs/ 2>/dev/null | grep "$1" | sort -V | tail -1 || true; }
A0=$(git fetch -q origin gram-tts-out; latest '任务_用户声音-'); B0=$(latest '任务_用户声音_q56-')
A=""; B=""
for k in $(seq 75); do
  git fetch -q origin gram-tts-out || true
  a=$(latest '任务_用户声音-'); b=$(latest '任务_用户声音_q56-')
  [ "$a" != "$A0" ] && A=$a; [ "$b" != "$B0" ] && B=$b
  [ -n "$A" ] && [ -n "$B" ] && break
  sleep 120
done
[ -n "$A" ] && [ -n "$B" ] || { echo "2.5 小时内没等到两个合成结果：A=$A B=$B"; exit 1; }
echo "合成结果：$A  $B"
git archive origin/gram-tts-out "$A" "$B" | tar -x -C "$T"
OUT=()
for d in "$T/$A"/user*; do
  n=${d##*user}
  if $PY 高考语法填空/tools/选段.py --稿 高考语法填空/tts/样稿_56.json --run "$d" --out "高考语法填空/样音/D${n}_用户本人.mp3"; then
    OUT+=("高考语法填空/样音/D${n}_用户本人.mp3")
  else echo "参考 $n 的样音没过检查"; fi
done
[ ${#OUT[@]} -gt 0 ] || { echo 没有样音过检查; exit 1; }
$PY 高考语法填空/tools/像不像.py --录音 "$REC" --参考 高考语法填空/tts/音色/用户本人_*.json --样音 "${OUT[@]}" 高考语法填空/样音/A_男老师_去呼吸.mp3 \
    --out 高考语法填空/样音/像不像.md
BEST=$(python3 - <<'PY'
import re
rows = [l.split('|') for l in open('高考语法填空/样音/像不像.md', encoding='utf-8') if l.startswith('| D')]
best = max(rows, key=lambda r: (float(r[2]), float(r[3])))
print(re.match(r'\s*D(\d+)', best[1]).group(1))
PY
)
echo "相似度最高：参考 $BEST"
git add 高考语法填空/样音/D*_用户本人.* 高考语法填空/样音/像不像.md
git commit -qm "高考语法填空：用户本人声音第 56 题样音（两个参考；完整处理链、去呼吸、呼吸检查、合格证；像不像评分）"
for i in 1 2 3 4; do git push -q origin "$BR" && break; sleep $((2**i)); done
Q=$(python3 -c "import json; print(' '.join(json.load(open('高考语法填空/tts/任务_用户声音_q56.json'))['only']))")
bash 高考语法填空/tools/全片.sh 高考语法填空/稿/2026_新课标Ⅰ卷.json "$T/$B/user$BEST" "2026 新课标Ⅰ卷 语法填空 第56题样片（用户本人声音）" $Q
git add "高考语法填空/audio/" "高考语法填空/最终视频/"
git commit -qm "高考语法填空：第 56 题样片（用户本人声音，参考 $BEST；截图排版检查与成品核查全部通过）"
for i in 1 2 3 4; do git push -q origin "$BR" && break; sleep $((2**i)); done
rm -rf "$T"
echo 样片56完成
