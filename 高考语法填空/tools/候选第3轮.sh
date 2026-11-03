#!/bin/bash
# 第 56 题第 3、4 轮配音候选（只出音频，不出视频）：等 Actions 上 任务_第3轮_q56 的合成 → 每个候选 选段（逐小段选优，英文按口音分优先；
# 整篇响度 / 意群 / 呼吸 / 电磁音 / 节奏 / 合格证）→ 像不像（整段 + 英文部分相似度）→ 候选汇总（口音、词错率、语速、音高、推荐）→ 提交推送。
# 出错即停；某个候选没过整篇检查只记下、不停。用法：REC=录音.wav AFTER=运行号下限 bash 高考语法填空/tools/候选第3轮.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=/opt/ttsenv/bin/python
BR=claude/epic-edison-4gkcfb
AFTER=${AFTER:-0}
TASK=${TASK:-高考语法填空/tts/任务_第3轮_q56.json}
RN=$(basename "$TASK" .json); RN=${RN#任务_}; RN=${RN%_q56}     # 第3轮 / 第4轮
GAO=高考语法填空/稿/2026_新课标Ⅰ卷.json
T=$(mktemp -d)
R=""
for k in $(seq 90); do
  git fetch -q origin gram-tts-out || true
  r=$(git -c core.quotepath=false ls-tree --name-only origin/gram-tts-out runs/ 2>/dev/null | grep "任务_${RN}_q56-" | sort -V | tail -1 || true)
  [ -n "$r" ] && [ "${r##*-}" -gt "$AFTER" ] && { R=$r; break; }
  sleep 120
done
[ -n "$R" ] || { echo "3 小时内没等到合成结果"; exit 1; }
echo "合成结果：$R"
git archive origin/gram-tts-out "$R" | tar -x -C "$T"
Q=$(python3 -c "import json; print(' '.join(json.load(open('$TASK'))['only']))")
IDS=$(python3 -c "import json; print(' '.join(c['id'] for c in json.load(open('$TASK'))['candidates']))")
OUTS=()
for id in $IDS; do
  o="高考语法填空/样音/${RN}_q56_$id.mp3"
  if $PY 高考语法填空/tools/选段.py --稿 $GAO --run "$T/$R/$id" --out "$o" --only $Q > "$T/$id.log" 2>&1; then
    OUTS+=("$o"); $PY 高考语法填空/tools/讲解节奏.py "$o" > "${o%.mp3}.节奏.txt"
  else echo "候选 $id 没过整篇检查：$(tail -1 "$T/$id.log")"; fi
done
[ ${#OUTS[@]} -gt 0 ] || { echo 所有候选都没过检查; exit 1; }
$PY 高考语法填空/tools/像不像.py --录音 "$REC" --参考 高考语法填空/tts/音色/用户本人_2.json 高考语法填空/tts/音色/用户本人平实_*.json 高考语法填空/tts/音色/用户本人快_*.json \
    --样音 "${OUTS[@]}" ${EXTRA:-} --out 高考语法填空/样音/像不像_${RN}.md
$PY 高考语法填空/tools/候选汇总.py --稿 $GAO --像不像 高考语法填空/样音/像不像_${RN}.md --out 高考语法填空/样音/${RN}_q56_评分.md "${OUTS[@]}" ${EXTRA:-}
git add 高考语法填空/样音/${RN}_q56_* 高考语法填空/样音/像不像_${RN}.md
git commit -qm "高考语法填空：第 56 题${RN}配音候选（英文单独合成去口音、不念 blank、语速与音高对照本人录音；评分与推荐）"
for i in 1 2 3 4; do git push -q origin "$BR" && break; sleep $((2**i)); git pull -q --rebase origin "$BR" || true; done
rm -rf "$T"
echo "候选${RN}完成 exit 0"
