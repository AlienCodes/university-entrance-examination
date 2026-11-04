#!/bin/bash
# 读后续写讲解：一条脚本流到底（出错即停）。视频在 GitHub Actions 上生成并发布 Release（render-gaokao-writing.yml），本机只出音频。
#   等合成结果（分支 gram-tts-out 的 runs/<任务>-<运行号>/）→ 选段（逐小段选优 + 完整处理链：去呼吸、陷波、意群、响度、合格证、节奏）
#   → 按工作流的检出路径建稀疏工作树试排截图（踩坑 84）→ 提交音频 + 清单 高考续写/render.txt 并推送（触发 Actions）
#   → 等 Release 上出现成品 → 下载回来核对 sha256、3840×2160、时长。
# 用法：bash 高考续写/tools/续写全片.sh <讲解目录> <任务文件名（高考语法填空/tts/ 下）> <音色 id> <成品名> <Release 标签> [段 id…（只做这几段）]
#   环境变量 AFTER=运行号下限（只认比它新的合成结果）
#   DROP_TASK=补合成任务文件名…（也要在 OVERLAY_TASK 里）：覆盖它之前，先把它 only 里的段在主合成和前面各补合成里的旧小段全部删掉（稿改了的段，旧文字的合成不许留作候选；
#     不删的话，以前补合成多出来的 take4…6 里旧文字的小段会被选段当候选）；ENGINE=续写视频_v2.py：试排截图用 v2 引擎，render.txt 写第 5 行
set -euo pipefail
cd "$(dirname "$0")/../.."
DIR=$1; TASK=$2; VOICE=$3; NAME=$4; TAG=$5; shift 5
AFTER=${AFTER:-0}
ONLY=(); [ $# -eq 0 ] || ONLY=(--only "$@")
PY=/opt/ttsenv/bin/python
BR=claude/epic-edison-4gkcfb
REPO=AlienCodes/university-entrance-examination
export TMPDIR=${TMPDIR:-/tmp}
T=$(mktemp -d)
python3 高考续写/tools/续写检查.py "$DIR" --副本 高考语法填空/tts/稿_续写_$(basename "$DIR").json
python3 .github/check-browser-match.py .github/workflows/render-gaokao-writing.yml      # 踩坑 78
RUN=""
for k in $(seq 100); do                        # 最多等约 3.3 小时
  git fetch -q origin gram-tts-out || true
  r=$(git -c core.quotepath=false ls-tree --name-only origin/gram-tts-out runs/ 2>/dev/null | grep "${TASK%.json}-" | sort -V | tail -1 || true)   # 踩坑 92
  if [ -n "$r" ] && [ "${r##*-}" -gt "$AFTER" ]; then
    # 合成机中途被停（exit 143）时 collect 照样发布，只少一个 take：每个 take 都有 meta 才收，否则接着等重跑（不悄悄少候选）
    miss=$(python3 高考续写/tools/合成齐全.py "$r" "$VOICE" "高考语法填空/tts/$TASK")
    [ -z "$miss" ] && RUN=$r && break
    echo "合成结果 $r 缺 $miss（合成机被停？），等重跑补齐"
  fi
  sleep 120
done
[ -n "$RUN" ] || { echo "没等到合成结果：$TASK"; exit 1; }
echo "合成结果：$RUN"
git archive origin/gram-tts-out "$RUN" | tar -x -C "$T"
mkdir -p 高考续写/audio
if [ -n "${OVERLAY_TASK:-}" ]; then              # 改了几段稿、只重合成这几段：等补合成结果，覆盖到主合成上（记录随音频提交）
  for u in ${KEEP_ORIG:-}; do                     # 文字没改、原合成读对的小段：先留一份，覆盖后放回原来的 take1…（补合成的多出来的次数照留）
    for d in "$T/$RUN/$VOICE"/take*; do [ -f "$d/$u.wav" ] && mkdir -p "$T/orig/$(basename "$d")" && cp "$d/$u.wav" "$T/orig/$(basename "$d")/"; done
  done
  for OT in $OVERLAY_TASK; do                     # 可以多个，按顺序覆盖
    if [[ " ${DROP_TASK:-} " == *" $OT "* ]]; then  # 稿改了的段：覆盖这个任务之前，删掉主合成和前面各补合成留下的旧小段
      for u in $(python3 -c "import json,sys;print(' '.join(json.load(open(sys.argv[1],encoding='utf-8'))['only']))" "高考语法填空/tts/$OT"); do
        n=$(find "$T/$RUN/$VOICE" -path '*/take*' \( -name "$u.wav" -o -name "$u~*.wav" \) | wc -l)
        find "$T/$RUN/$VOICE" -path '*/take*' \( -name "$u.wav" -o -name "$u~*.wav" \) -delete
        echo "删除 $u 的旧合成 $n 个小段（稿改了，$OT 重新合成）" >> "$T/$RUN/$VOICE/覆盖.txt"
      done
    fi
    bash 高考续写/tools/覆盖补合成.sh "$T/$RUN/$VOICE" "$VOICE" "$OT" "${OVERLAY_AFTER:-0}"
  done
  for u in ${KEEP_ORIG:-}; do
    for d in "$T/orig"/take*; do cp "$d/$u.wav" "$T/$RUN/$VOICE/$(basename "$d")/$u.wav"; echo "$(basename "$d")/$u.wav ← 原合成（放回）" >> "$T/$RUN/$VOICE/覆盖.txt"; done
  done
  for V in ${VERIFY_EN:-}; do                     # 英文逐词核对（纯英文识别）：第一个全读对的那一次加进 LOCK；没有就记下来，不锁
    u=${V%%:*}; ws=${V#*:}; k=$($PY 高考续写/tools/英文逐词核对.py "$T/$RUN/$VOICE" "$DIR/稿.json" "$u" ${ws//,/ } 2>>"高考续写/audio/$NAME.英文核对.txt" | tail -1)
    if [ -n "$k" ]; then LOCK="${LOCK:-} $u=$k"; else echo "⚠ $u（${ws}）没有一次纯英文识别读对，未锁定，交人工核对" | tee -a "高考续写/audio/$NAME.英文核对.txt"; fi
  done
  for L in ${LOCK:-}; do                          # 锁定：某小段只用人工核对过读对的那一次（把它复制到其余各次，选段怎么换都是它）
    u=${L%%=*}; k=${L#*=}; src="$T/$RUN/$VOICE/$k/$u.wav"; [ -f "$src" ] || { echo "锁定的 $src 不存在"; exit 1; }
    for d in "$T/$RUN/$VOICE"/take*; do [ -f "$d/$u.wav" ] && [ "$d/$u.wav" != "$src" ] && cp "$src" "$d/$u.wav"; done
    echo "锁定 $u = $k（人工核对读对的一次）" | tee -a "$T/$RUN/$VOICE/覆盖.txt"
  done
  cp "$T/$RUN/$VOICE/覆盖.txt" "高考续写/audio/$NAME.覆盖.txt"
fi
# 候选的合成单位、段间停顿上限照任务清单传给选段（不传就按默认 mark+lang 展开，找错小段）
read -r SPLIT GAPMAX < <(python3 -c "
import json,sys;t=json.load(open(sys.argv[1],encoding='utf-8'));c=next(c for c in t['candidates'] if c['id']==sys.argv[2])
print(c.get('split',t.get('split','mark+lang')), c.get('gap_max',t.get('gap_max','')))" "高考语法填空/tts/$TASK" "$VOICE")
SEL=(--拆分 "$SPLIT"); [ -z "$GAPMAX" ] || SEL+=(--停顿上限 "$GAPMAX"); [ -z "${TIMBRE:-}" ] || SEL+=(--音色还原 "$TIMBRE")   # 清晰度 v4：TIMBRE='[[60,500,-2.5],[5000,9000,2.0]]'
echo "选段：拆分 $SPLIT，段间停顿上限 ${GAPMAX:-默认}"
if [ -n "${SYNTH_ALLOW_MISSING:-}" ]; then          # 显式放行（公开、有记录）：写进音频旁的记录，随音频提交
  printf '显式放行缺片：%s\n合成结果：%s\n原因：合成机内存顶满被收回（两次），这一片的段只用其余几次的候选；其他缺口照拦（合成齐全.py、合成完整性.py）\n' "$SYNTH_ALLOW_MISSING" "$RUN" > "高考续写/audio/$NAME.放行.txt"
  cat "高考续写/audio/$NAME.放行.txt"
fi
$PY 高考语法填空/tools/选段.py --稿 "$DIR/稿.json" --run "$T/$RUN/$VOICE" --out "高考续写/audio/$NAME.mp3" "${SEL[@]}" "${ONLY[@]}"
$PY 高考语法填空/tools/讲解节奏.py "高考续写/audio/$NAME.mp3" > "高考续写/audio/$NAME.节奏.txt"
[ -z "${AUDIO_ONLY:-}" ] && [ ! -f 高考续写/暂停出视频.txt ] || { rm -rf "$T"; echo "只出音频（AUDIO_ONLY 或 暂停出视频.txt）：高考续写/audio/$NAME.mp3"; exit 0; }
# 踩坑 84：按工作流的检出路径建稀疏工作树，截图全部检查走一遍（只截这段音频用到的屏）
WT=$T/wt
git worktree add -q --no-checkout "$WT" HEAD
git -C "$WT" sparse-checkout set --no-cone $(python3 -c "
import yaml;w=yaml.safe_load(open('.github/workflows/render-gaokao-writing.yml'))
print(' '.join(l.strip() for l in w['jobs']['render']['steps'][0]['with']['sparse-checkout'].splitlines() if l.strip()))")
git -C "$WT" checkout -q
cp 高考续写/audio/"$NAME".* "$WT/高考续写/audio/" 2>/dev/null || { mkdir -p "$WT/高考续写/audio"; cp 高考续写/audio/"$NAME".* "$WT/高考续写/audio/"; }
cp "$DIR"/*.json "$WT/$DIR/"
ln -s "$PWD/tools/tts/models" "$WT/tools/tts/models" 2>/dev/null || true
(cd "$WT" && $PY 高考续写/tools/${ENGINE:-续写视频.py} --稿 "$DIR/稿.json" --音频 "高考续写/audio/$NAME.mp3" --stills --out "$T/st" --png "$T/st/png")
git worktree remove --force "$WT"
printf '# 高考续写视频清单（推送触发 render-gaokao-writing.yml）\n%s\n%s\n%s\n%s\n' "$TAG" "$DIR" "高考续写/audio/$NAME.mp3" "$NAME.mp4" > 高考续写/render.txt
[ -z "${ENGINE:-}" ] || echo "$ENGINE" >> 高考续写/render.txt
git add 高考续写/audio/ 高考续写/render.txt
git commit -qm "高考续写：$NAME 音频（选段 + 完整处理链 + 合格证）；推清单在 GitHub 上生成视频并发布 Release $TAG"
for i in 1 2 3 4; do git push -q origin "$BR" && break; sleep $((2**i)); done
# 等 Release 上出现成品，下载回来核对
U="https://github.com/$REPO/releases/download/$TAG"
EN=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$NAME.mp4")
mkdir -p "$T/dl"
for k in $(seq 90); do                          # 最多等约 3 小时
  if curl -fsSL -o "$T/dl/sha" "$U/$EN.sha256" 2>/dev/null && grep -q . "$T/dl/sha"; then break; fi
  sleep 120
done
curl -fsSL --retry 4 -o "$T/dl/$NAME.mp4" "$U/$EN"
want=$(cut -d' ' -f1 "$T/dl/sha"); got=$(sha256sum "$T/dl/$NAME.mp4" | cut -d' ' -f1)
[ "$want" = "$got" ] || { echo "sha256 不一致：$want ≠ $got"; exit 1; }
info=$(ffprobe -v error -show_entries format=duration:stream=width,height -of csv=p=0 "$T/dl/$NAME.mp4" | tr '\n' ' ')
echo "$info" | grep -q "3840,2160" || { echo "分辨率不对：$info"; exit 1; }
echo "下载核对通过：$U/$EN  sha256 $got  $info"
rm -rf "$T"
echo "续写全片完成 exit 0"
