#!/bin/bash
# 专八听力原文精读（书卷水墨）：一次启动、出错即停（同 专八/tools/水墨流水线.sh 的做法，项目 专八听力）。
#   bash 专八/听力/原文/tools/流水线.sh 截图 L3 …    原文 → 音轨 + sents → build_vocab（复核定稿指纹）→ 分屏建议 → 分屏定稿 → split_check → 分屏质检 → 截图预检 → 截图（全部程序检查）
#   bash 专八/听力/原文/tools/流水线.sh 视频 L3 …    生成 4K 视频 + 全部成品核查（截图要先 --approve）
# 日志：专八/听力/原文/大字版水墨/流水线_<步骤>.log；最后一行写“流水线完成”或“流水线停止：原因”。
set -u -o pipefail
cd "$(dirname "$0")/../../../.." || exit 1
export DZB_PROJECT=专八听力 DZB_VARIANT=水墨 ZB_ROOT=专八/听力/原文
PY=/opt/ttsenv/bin/python
C=专八/听力/原文; W=$C/大字版水墨; T=$C/tools
step=$1; shift; ids="$*"
mkdir -p $W; log=$W/流水线_$step.log; : > "$log"
stop() { echo "流水线停止：$1（$(date -u +%H:%M)）" | tee -a "$log"; exit 1; }
case $step in
  截图)
    $PY $T/原音音轨.py >> "$log" 2>&1 || stop "音轨出错"
    $PY 专八/tools/build_vocab.py >> "$log" 2>&1 || stop "build_vocab（标注检查 / 复核定稿指纹）不通过"
    $PY 专八/tools/分屏建议.py $ids --project 专八听力 --styles C --out $W/分屏方案_当前批.json >> "$log" 2>&1 || stop "分屏建议出错"
    $PY 专八/tools/分屏定稿.py $W/分屏方案_当前批.json $ids >> "$log" 2>&1 || stop "有句子要人工指定分屏（写进 $T/分屏手定_水墨.json 后重跑）"
    $PY 专八/tools/split_check.py $T/分屏_水墨.json > $W/split_check.log 2>&1
    tail -1 $W/split_check.log | grep -q "ALL OK" || stop "split_check 没有全部通过"
    $PY 专八/tools/分屏质检.py $ids >> "$log" 2>&1 || stop "分屏质检出错"
    q=$(grep -o "分屏质检：[0-9]* 句可疑" "$log" | tail -1); echo "$q" | tee -a "$log"
    case "$q" in *"：0 句可疑") ;; *) stop "$q：逐句读文字，要改的写进 分屏手定_水墨.json" ;; esac
    $PY $T/大字版_水墨.py --preflight $ids >> "$log" 2>&1 || stop "截图预检有问题"
    $PY $T/大字版_水墨.py --stills $ids >> "$log" 2>&1 || stop "截图检查出错"
    grep -q "共 [1-9][0-9]* 处问题" "$log" && stop "截图程序检查有问题（见日志）"
    ;;
  视频)
    $PY $T/大字版_水墨.py --video $ids >> "$log" 2>&1 || stop "视频生成或成品核查不通过"
    ;;
  *) stop "不认识的步骤 $step（截图 / 视频）" ;;
esac
echo "流水线完成（$(date -u +%H:%M)）" | tee -a "$log"
