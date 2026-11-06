#!/bin/bash
# 四级听力原文精读（紫黄撞色 --style 5 + 原音）：一次启动、出错即停（同 专八/听力/原文/tools/流水线.sh，项目 四级听力）。
#   bash 四级/听力/精读/tools/流水线.sh 截图 202512-1 …   切句 → 原音音轨 → build_vocab（复核定稿指纹）→ 分屏建议 → 分屏定稿 → split_check → 分屏质检 → 截图预检 → 截图（全部程序检查）
#   bash 四级/听力/精读/tools/流水线.sh 预检 202512-1 …   同“截图”，只到截图预检为止（截图放 GitHub 画）；音轨每做完 2 套就提交推送（MP3 与 timings 同一次提交）
#   bash 四级/听力/精读/tools/流水线.sh 视频 202512-1 …   生成 4K 视频 + 全部成品核查（截图要先 --approve）
# 原音 mp3 在 $CET4_WAV/cet4-<定稿.json 的录音>.mp3（默认 /home/user/wav4，取材料.py 取出；sha256 必须在 四级/听力/原始材料/SHA256SUMS）。
# 日志：四级/听力/精读/大字版/流水线_<步骤>.log；最后一行写“流水线完成”或“流水线停止：原因”。
set -u -o pipefail
cd "$(dirname "$0")/../../../.." || exit 1
export DZB_PROJECT=四级听力 ZB_ROOT=四级/听力/精读
unset DZB_VARIANT
PY=/opt/ttsenv/bin/python
C=四级/听力/精读; W=$C/大字版; T=$C/tools; WAV=${CET4_WAV:-/home/user/wav4}
step=$1; shift; ids="$*"
mkdir -p $W; log=$W/流水线_$step.log; : > "$log"
push_audio() {   # 音轨：MP3、timings、对齐报告同一次提交；推送失败重试 4 次
  git add $C/audio && git diff --cached --quiet && return 0
  git commit -q -m "四级听力精读：原音音轨（至 $1，听对逐句 0）" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || return 1
  for t in 2 4 8 16 0; do git pull -q --rebase --autostash origin claude/epic-edison-4gkcfb && git push -q -u origin claude/epic-edison-4gkcfb && return 0; [ $t = 0 ] && return 1; sleep $t; done
}
stop() { echo "流水线停止：$1（$(date -u +%H:%M)）" | tee -a "$log"; exit 1; }
case $step in
  截图|预检)
    python3 $T/切句.py $ids >> "$log" 2>&1 || stop "切句出错"
    for s in $ids; do grep -q "‖\|（待译）" $C/ann/$s.txt && stop "$s 标注里还有 ‖ / （待译）（合并句.py 之后补完）"; done
    for s in $ids; do rec=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['录音'])" 四级/听力/$s/定稿.json); $PY 专八/听力/原文/tools/原音音轨.py --cet4 $s --mp3 $WAV/cet4-$rec.mp3 >> "$log" 2>&1 || stop "音轨出错 $s"
      if [ $step = 预检 ]; then n=$((${n:-0}+1)); last=$s; [ $((n % 2)) = 0 ] && { push_audio "$s" || stop "音轨提交推送失败 $s"; }; fi; done
    [ $step = 预检 ] && [ $((${n:-0} % 2)) = 1 ] && { push_audio "$last" || stop "音轨提交推送失败 $last"; }
    $PY 专八/tools/build_vocab.py >> "$log" 2>&1 || stop "build_vocab（标注检查 / 复核定稿指纹）不通过"
    $PY 专八/tools/分屏建议.py $ids --project 四级听力 --styles 5 --out $W/分屏方案_当前批.json >> "$log" 2>&1 || stop "分屏建议出错"
    $PY 专八/tools/分屏定稿.py $W/分屏方案_当前批.json $ids >> "$log" 2>&1 || stop "有句子要人工指定分屏（写进 $T/分屏手定.json 后重跑）"
    $PY 专八/tools/split_check.py $T/分屏.json > $W/split_check.log 2>&1
    tail -1 $W/split_check.log | grep -q "ALL OK" || stop "split_check 没有全部通过"
    $PY 专八/tools/分屏质检.py $ids >> "$log" 2>&1 || stop "分屏质检出错"
    q=$(grep -o "分屏质检：[0-9]* 句可疑" "$log" | tail -1); echo "$q" | tee -a "$log"
    case "$q" in *"：0 句可疑") ;; *) stop "$q：逐句读文字，要改的写进 分屏手定.json" ;; esac
    $PY $T/大字版_紫黄.py --preflight $ids >> "$log" 2>&1 || stop "截图预检有问题"
    if [ $step = 预检 ]; then echo "预检全部通过：$ids" | tee -a "$log"; echo "流水线完成（$(date -u +%H:%M)）" | tee -a "$log"; exit 0; fi
    $PY $T/大字版_紫黄.py --stills $ids >> "$log" 2>&1 || stop "截图检查出错"
    grep -q "共 [1-9][0-9]* 处问题" "$log" && stop "截图程序检查有问题（见日志）"
    ;;
  视频)
    $PY $T/大字版_紫黄.py --video $ids >> "$log" 2>&1 || stop "视频生成或成品核查不通过"
    ;;
  *) stop "不认识的步骤 $step（截图 / 视频）" ;;
esac
echo "流水线完成（$(date -u +%H:%M)）" | tee -a "$log"
