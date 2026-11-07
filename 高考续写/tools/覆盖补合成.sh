#!/bin/bash
# 补合成覆盖：等补合成任务的结果（每个 take 都齐，合成齐全.py），把它的小段 WAV 覆盖到已解出的主合成目录的同名 take 上。
# 用于改了几段稿、只重合成这几段（2026-11-03 续写整片 s1z 问句尾音上扬）。覆盖了哪些写进 <主目录>/覆盖.txt。
# 用法：bash 高考续写/tools/覆盖补合成.sh <解出的主合成目录…/<候选>> <候选 id> <补合成任务文件名> [运行号下限]
set -euo pipefail
cd "$(dirname "$0")/../.."
MAIN=$1; VOICE=$2; TASK=$3; AFTER=${4:-0}
RUN=""
for k in $(seq 90); do
  git fetch -q origin gram-tts-out || true
  r=$(git -c core.quotepath=false ls-tree --name-only origin/gram-tts-out runs/ 2>/dev/null | grep "${TASK%.json}-" | sort -V | tail -1 || true)
  if [ -n "$r" ] && [ "${r##*-}" -gt "$AFTER" ]; then
    miss=$(python3 高考续写/tools/合成齐全.py "$r" "$VOICE" "高考语法填空/tts/$TASK")
    [ -z "$miss" ] && RUN=$r && break
    echo "补合成 $r 缺 $miss，等重跑补齐"
  fi
  sleep 60
done
[ -n "$RUN" ] || { echo "没等到补合成结果：$TASK"; exit 1; }
T=$(mktemp -d)
git archive origin/gram-tts-out "$RUN/$VOICE" | tar -x -C "$T"
n=0
for d in "$T/$RUN/$VOICE"/take*; do
  t=$(basename "$d"); mkdir -p "$MAIN/$t"          # 补合成多出来的次数（take4…）只含这几段，选段把它们当多出来的候选
  for w in "$d"/*.wav; do
    b=$(basename "$w"); [ "$b" = design_ref.wav ] && continue
    cp "$w" "$MAIN/$t/$b"; echo "$t/$b ← $RUN" >> "$MAIN/覆盖.txt"; n=$((n+1))
  done
done
rm -rf "$T"
echo "补合成覆盖：$RUN → $n 个小段"
