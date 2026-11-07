#!/bin/bash
# 六级听力原文精读（六级教室黑板 + 原音）：一次启动、出错即停（同 专八/听力/原文/tools/流水线.sh，项目 六级听力）。
#   bash 六级/听力/精读/tools/流水线.sh 截图 202512-1 …   切句 → 原音音轨 → build_vocab（复核定稿指纹）→ 分屏建议 → 分屏定稿 → split_check → 分屏质检 → 截图预检 → 截图（全部程序检查）
#   bash 六级/听力/精读/tools/流水线.sh 视频 202512-1 …   生成 4K 视频 + 全部成品核查（截图要先 --approve）
# 原音 mp3 在 $CET6_WAV/cet6-<套>.mp3（默认 /home/user/wav，sha256 必须在 六级/听力/原始材料/SHA256SUMS）。
# 日志：六级/听力/精读/大字版/流水线_<步骤>.log；最后一行写“流水线完成”或“流水线停止：原因”。
set -u -o pipefail
cd "$(dirname "$0")/../../../.." || exit 1
export DZB_PROJECT=六级听力 ZB_ROOT=六级/听力/精读
unset DZB_VARIANT
PY=/opt/ttsenv/bin/python
C=六级/听力/精读; W=$C/大字版; T=$C/tools; WAV=${CET6_WAV:-/home/user/wav}
step=$1; shift; ids="$*"
mkdir -p $W; log=$W/流水线_$step.log; : > "$log"
stop() { echo "流水线停止：$1（$(date -u +%H:%M)）" | tee -a "$log"; exit 1; }
case $step in
  截图)
    python3 $T/切句.py $ids >> "$log" 2>&1 || stop "切句出错"
    for s in $ids; do $PY 专八/听力/原文/tools/原音音轨.py --cet6 $s --mp3 $WAV/cet6-$s.mp3 >> "$log" 2>&1 || stop "音轨出错 $s"; done
    $PY 专八/tools/build_vocab.py >> "$log" 2>&1 || stop "build_vocab（标注检查 / 复核定稿指纹）不通过"
    $PY 专八/tools/分屏建议.py $ids --project 六级听力 --styles 3 --out $W/分屏方案_当前批.json >> "$log" 2>&1 || stop "分屏建议出错"
    $PY 专八/tools/分屏定稿.py $W/分屏方案_当前批.json $ids >> "$log" 2>&1 || stop "有句子要人工指定分屏（写进 $T/分屏手定.json 后重跑）"
    $PY 专八/tools/split_check.py $T/分屏.json > $W/split_check.log 2>&1
    tail -1 $W/split_check.log | grep -q "ALL OK" || stop "split_check 没有全部通过"
    $PY 专八/tools/分屏质检.py $ids >> "$log" 2>&1 || stop "分屏质检出错"
    q=$(grep -o "分屏质检：[0-9]* 句可疑" "$log" | tail -1); echo "$q" | tee -a "$log"
    case "$q" in *"：0 句可疑") ;; *) stop "$q：逐句读文字，要改的写进 分屏手定.json" ;; esac
    $PY $T/大字版_黑板.py --preflight $ids >> "$log" 2>&1 || stop "截图预检有问题"
    $PY $T/大字版_黑板.py --stills $ids >> "$log" 2>&1 || stop "截图检查出错"
    grep -q "共 [1-9][0-9]* 处问题" "$log" && stop "截图程序检查有问题（见日志）"
    ;;
  视频)
    $PY $T/大字版_黑板.py --video $ids >> "$log" 2>&1 || stop "视频生成或成品核查不通过"
    ;;
  *) stop "不认识的步骤 $step（截图 / 视频）" ;;
esac
echo "流水线完成（$(date -u +%H:%M)）" | tee -a "$log"
