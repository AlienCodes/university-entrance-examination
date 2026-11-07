#!/bin/bash
# 第 56 题样片（用户本人声音）：等 Actions 上两组合成（7—8 秒参考 user2：任务_用户声音_q56；接缝补底噪的 20 秒长参考 userL1：任务_用户声音_q56长）
# → 每组 选段（只 q56 各段：逐小段选优、问句尾音；整篇响度 / 呼吸 / 节奏检查）出候选 → 像不像评分 + 节奏实测
# → 选更好的（节奏检查过 → 相似度高；差不到 0.01 看自然度）→ 全片.sh 出样片（截图排版检查 + 成品核查）→ 提交推送。出错即停。
# 用法：REC=录音.wav AFTER=9 bash 高考语法填空/tools/样片56.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=/opt/ttsenv/bin/python
BR=claude/epic-edison-4gkcfb
AFTER=${AFTER:-0}
T=$(mktemp -d)
ls_runs() { git -c core.quotepath=false ls-tree --name-only origin/gram-tts-out runs/ 2>/dev/null | grep "$1" | sort -V | tail -1 || true; }
A=""; L=""
for k in $(seq 75); do
  git fetch -q origin gram-tts-out || true
  a=$(ls_runs '任务_用户声音_q56-'); l=$(ls_runs '任务_用户声音_q56长-')
  [ -n "$a" ] && [ "${a##*-}" -gt "$AFTER" ] && A=$a
  [ -n "$l" ] && L=$l
  [ -n "$A" ] && [ -n "$L" ] && break
  sleep 120
done
[ -n "$A" ] && [ -n "$L" ] || { echo "2.5 小时内没等到两组合成：$A $L"; exit 1; }
echo "合成结果：$A  $L"
git archive origin/gram-tts-out "$A" "$L" | tar -x -C "$T"
Q=$(python3 -c "import json; print(' '.join(json.load(open('高考语法填空/tts/任务_用户声音_q56.json'))['only']))")
OUTS=()
for run in "$T/$A/user2" "$T/$L/userL1"; do
  id=${run##*/}
  o="高考语法填空/样音/第56题候选_$id.mp3"
  if $PY 高考语法填空/tools/选段.py --稿 高考语法填空/稿/2026_新课标Ⅰ卷.json --run "$run" --out "$o" --only $Q; then
    OUTS+=("$o"); $PY 高考语法填空/tools/讲解节奏.py "$o" > "${o%.mp3}.节奏.txt"
  else echo "候选 $id 没过整篇检查"; fi
done
[ ${#OUTS[@]} -gt 0 ] || { echo 两个候选都没过检查; exit 1; }
$PY 高考语法填空/tools/像不像.py --录音 "$REC" --参考 高考语法填空/tts/音色/用户本人_*.json 高考语法填空/tts/音色/用户本人长_*.json \
    --样音 "${OUTS[@]}" --out 高考语法填空/样音/像不像_第56题候选.md
BEST=$(python3 - <<'PY'
import re
rows = [l.split('|') for l in open('高考语法填空/样音/像不像_第56题候选.md', encoding='utf-8') if '第56题候选_' in l]
rows = [(re.search(r'候选_(\w+)\.mp3', r[1]).group(1), float(r[2]), float(r[3])) for r in rows]
top = max(s for _, s, _ in rows)
print(max([r for r in rows if r[1] >= top - 0.01], key=lambda r: r[2])[0])
PY
)
echo "选用：$BEST"
RUN=$([ "$BEST" = userL1 ] && echo "$T/$L/userL1" || echo "$T/$A/user2")
NAME="2026 新课标Ⅰ卷 语法填空 第56题样片（用户本人声音）"
bash 高考语法填空/tools/全片.sh 高考语法填空/稿/2026_新课标Ⅰ卷.json "$RUN" "$NAME" $Q
$PY 高考语法填空/tools/讲解节奏.py "高考语法填空/audio/$NAME.mp3" > 高考语法填空/样音/节奏_第56题样片.txt
echo "选用 $BEST" >> 高考语法填空/样音/像不像_第56题候选.md
$PY tools/防复发/验证/讲解节奏.py
git add "高考语法填空/audio/" "高考语法填空/最终视频/" 高考语法填空/样音/第56题候选_* 高考语法填空/样音/像不像_第56题候选.md 高考语法填空/样音/节奏_第56题样片.txt
git commit -qm "高考语法填空：第 56 题样片第 2 版（改稿、‖ 停顿、问句尾音；短 / 长参考对比，选用 $BEST；节奏、呼吸、响度、成品核查全部通过）"
for i in 1 2 3 4; do git push -q origin "$BR" && break; sleep $((2**i)); done
rm -rf "$T"
echo 样片56完成
