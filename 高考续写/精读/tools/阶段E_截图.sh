#!/bin/bash
# 高考续写精读阶段 E 前半（一次启动、自己流到底）：每篇 分屏建议 → 分屏定稿（规则见 分屏定稿.py）→ split_check → 截图 + 全部程序检查（大字版.py --stills）。
# 音频还在重新生成的篇目（WAIT_LOG 里列出的批次），等它的“自然度”自检行出现（音频与识别自检都做完）再做，换屏时刻要用最终音频。
# 中途不碰 git（音频批量脚本在逐篇提交，两边同时提交会抢 index.lock）；全部做完后由协调人统一提交 分屏.json。
# 用法：bash 高考续写/精读/tools/阶段E_截图.sh k02 k05 …     日志：高考续写/精读/大字版/日志/阶段E.log；每篇结果 高考续写/精读/大字版/日志/分屏_<篇目>.json
cd "$(dirname "$0")/../../.." || exit 1
PY=/opt/ttsenv/bin/python
L=高考续写/精读/大字版/日志; mkdir -p "$L"
WAIT_LOG=${WAIT_LOG:-$L/audio_pron.log}
WAIT_IDS=${WAIT_IDS:-}
fail=()
for pid in "$@"; do
  if [[ " $WAIT_IDS " == *" $pid "* ]]; then
    echo "$(date +%T) $pid 等最终音频…"
    until grep -q "^\[female\] $pid  自然度" "$WAIT_LOG"; do sleep 30; done
  fi
  echo "$(date +%T) $pid 分屏建议"
  $PY 高考续写/精读/tools/分屏建议.py --project 高考续写 "$pid" --out "$L/分屏_$pid.json" > "$L/分屏建议_$pid.log" 2>&1 || { echo "❌ $pid 分屏建议失败"; fail+=("$pid"); break; }
  $PY 高考续写/精读/tools/分屏定稿.py "$L/分屏_$pid.json" "$pid" || { echo "❌ $pid 分屏定稿失败"; fail+=("$pid"); break; }
  $PY -c "import json,sys; d=json.load(open('高考续写/精读/tools/分屏.json')); json.dump({sys.argv[1]: d.get(sys.argv[1], {})}, open(sys.argv[2], 'w'), ensure_ascii=False)" "$pid" "$L/plan_$pid.json"
  $PY 高考续写/精读/tools/split_check.py "$L/plan_$pid.json" 2>&1 | grep -v -i warn | tail -1 | grep -q "ALL OK" || { echo "❌ $pid split_check 未通过"; fail+=("$pid"); break; }
  $PY 高考续写/精读/tools/大字版.py --preflight "$pid" > "$L/预检_$pid.log" 2>&1 || { echo "❌ $pid 预检未通过（$L/预检_$pid.log）"; fail+=("$pid"); break; }
  if $PY 高考续写/精读/tools/大字版.py --stills "$pid" > "$L/截图_$pid.log" 2>&1 && grep -q "全部通过" "$L/截图_$pid.log"; then
    echo "✅ $(grep -E "^$pid：" "$L/截图_$pid.log" | tail -1)"
  else
    echo "❌ $pid 截图检查未通过（$L/截图_$pid.log）"; fail+=("$pid"); break
  fi
done
echo "$(date +%T) 全部完成；未通过：${fail[*]:-无}"
