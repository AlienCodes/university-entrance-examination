#!/bin/bash
# 用户本人声音：一条命令从录音到第 56 题样音（出错即停）。录音在 Release user-voice（用户自己上传；本人同意声音克隆与公开使用）。
#   ① 下载 Release user-voice 的录音（已下载的用 REC=路径 跳过），核对 sha256（SHA=… 给了就核）；
#   ② 挑参考.py 程序挑参考片段（无剪辑接缝、无呼吸）→ tts/音色/用户本人_N.json + 挑选.md（只存 spans 与文字，不存音频）；
#   ③ 当前任务.txt ← 任务_用户声音.json；预演（CI 同款自检 + 假模型走真处理链）；提交推送 → 触发 Actions 合成；
#   ④ 等 gram-tts-out 出现 runs/任务_用户声音-*（每 2 分钟看一次，最多 2 小时），取回后每个候选 选段.py → 样音/D<N>_用户本人.mp3，提交推送。
# 用法：[REC=05.wav] [SHA=…] [SKIP_PICK=1] bash 高考语法填空/tools/用户声音.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=/opt/ttsenv/bin/python
REPO=aliencodes/university-entrance-examination
BR=claude/epic-edison-4gkcfb
T=$(mktemp -d)
if [ -z "${REC:-}" ]; then
  curl -sSf "https://api.github.com/repos/$REPO/releases/tags/user-voice" > "$T/rel.json"
  N=$(python3 -c "import json; a=[x for x in json.load(open('$T/rel.json'))['assets'] if x['name'].lower().endswith(('.wav','.mp3','.m4a','.flac'))]; assert len(a)==1, a; print(a[0]['name'])")
  curl -sSfL -o "$T/$N" "https://github.com/$REPO/releases/download/user-voice/$N"
  REC="$T/$N"
fi
[ -z "${SHA:-}" ] || echo "$SHA  $REC" | sha256sum -c -
if [ -z "${SKIP_PICK:-}" ]; then
  $PY 高考语法填空/tools/挑参考.py --录音 "$REC" --名 用户本人
fi
printf '任务_用户声音.json\n# %s 用户本人声音第 56 题样音\n' "$(date -u +%FT%TZ)" > 高考语法填空/tts/当前任务.txt
CI_PY=${CI_PY:-python3} bash tools/防复发/预演_qwen/预演.sh 任务_用户声音.json
git add 高考语法填空/tts/音色/用户本人* 高考语法填空/tts/当前任务.txt 高考语法填空/tts/任务_用户声音.json
git commit -qm "高考语法填空：用户本人声音参考片段（程序挑选：无剪辑接缝、无呼吸），触发第 56 题样音合成"
for i in 1 2 3 4; do git push -q origin "$BR" && break; sleep $((2**i)); done
echo "已触发；等 Actions 合成"
R=""
for k in $(seq 60); do
  git fetch -q origin gram-tts-out || true
  R=$(git ls-tree --name-only origin/gram-tts-out runs/ 2>/dev/null | grep '任务_用户声音-' | sort -V | tail -1 || true)
  if [ -n "$R" ]; then break; fi
  sleep 120
done
[ -n "$R" ] || { echo "2 小时内没等到合成结果"; exit 1; }
rm -rf "$T/out"; mkdir -p "$T/out"
git archive origin/gram-tts-out "$R" | tar -x -C "$T/out"
for d in "$T/out/$R"/user*; do
  n=${d##*user}
  $PY 高考语法填空/tools/选段.py --稿 高考语法填空/tts/样稿_56.json --run "$d" --out "高考语法填空/样音/D${n}_用户本人.mp3" || echo "候选 user$n 没过检查"
done
ls 高考语法填空/样音/D*_用户本人.mp3
git add 高考语法填空/样音/D*_用户本人.*
git commit -qm "高考语法填空：用户本人声音第 56 题样音（完整处理链、去呼吸、呼吸检查、合格证）"
for i in 1 2 3 4; do git push -q origin "$BR" && break; sleep $((2**i)); done
rm -rf "$T"
echo 用户声音样音完成
