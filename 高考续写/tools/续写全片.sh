#!/bin/bash
# 读后续写讲解：一条脚本流到底（出错即停）。等 Actions 合成结果（分支 gram-tts-out 的 runs/<任务>-<运行号>/）
# → 选段（逐小段选优 + 完整处理链：去呼吸、陷波、意群、响度、合格证、节奏）→ 续写视频（截图排版检查 → 视频 → 成品核查）→ 提交推送。
# 用法：bash 高考续写/tools/续写全片.sh <讲解目录> <任务文件名（高考语法填空/tts/ 下）> <音色 id> <成品名> [AFTER=运行号下限] [段 id…（只做这几段）]
set -euo pipefail
cd "$(dirname "$0")/../.."
DIR=$1; TASK=$2; VOICE=$3; NAME=$4; shift 4
AFTER=${AFTER:-0}
ONLY=(); [ $# -eq 0 ] || ONLY=(--only "$@")
PY=/opt/ttsenv/bin/python
BR=claude/epic-edison-4gkcfb
export TMPDIR=${TMPDIR:-/tmp}
T=$(mktemp -d)
KEY="${TASK%.json}-"
python3 高考续写/tools/续写检查.py "$DIR" --副本 高考语法填空/tts/稿_续写_$(basename "$DIR").json
RUN=""
for k in $(seq 100); do                        # 最多等约 3.3 小时
  git fetch -q origin gram-tts-out || true
  r=$(git -c core.quotepath=false ls-tree --name-only origin/gram-tts-out runs/ 2>/dev/null | grep "$KEY" | sort -V | tail -1 || true)   # 中文路径不转义（踩坑 92）
  [ -n "$r" ] && [ "${r##*-}" -gt "$AFTER" ] && RUN=$r && break
  sleep 120
done
[ -n "$RUN" ] || { echo "没等到合成结果：$KEY"; exit 1; }
echo "合成结果：$RUN"
git archive origin/gram-tts-out "$RUN" | tar -x -C "$T"
mkdir -p 高考续写/audio 高考续写/最终视频
$PY 高考语法填空/tools/选段.py --稿 "$DIR/稿.json" --run "$T/$RUN/$VOICE" --out "高考续写/audio/$NAME.mp3" "${ONLY[@]}"
$PY 高考续写/tools/续写视频.py --稿 "$DIR/稿.json" --音频 "高考续写/audio/$NAME.mp3" --video \
    --out 高考续写/最终视频 --png "$T/png" --name "$NAME.mp4"
$PY 高考语法填空/tools/讲解节奏.py "高考续写/audio/$NAME.mp3" > "高考续写/audio/$NAME.节奏.txt"
git add 高考续写/audio/ "高考续写/最终视频/$NAME.mp4"
git commit -qm "高考续写：$NAME（选段 + 完整处理链 + 截图排版检查 + 成品核查全部通过）"
for i in 1 2 3 4; do git push -q origin "$BR" && break; sleep $((2**i)); done
rm -rf "$T"
echo "续写全片完成 exit 0"
