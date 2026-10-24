#!/bin/bash
# 专八书卷水墨：分屏 → 截图，一次启动、出错即停（踩坑 73：以前的临时脚本前一步失败了照样往下跑，分屏方案没写进去就画了 40 分钟截图、报 593 处）。
#   bash 专八/tools/水墨流水线.sh 分屏 t11 t12 …      分屏建议（--resume）→ 分屏定稿（要人工指定的句子一次全部列出、退出码 1）→ split_check（必须 ALL OK）→ 分屏质检 + 截图预检
#   bash 专八/tools/水墨流水线.sh 截图 t11 t12 …      大字版_水墨.py --stills（开画前预检：人名、缺字、分屏方案、空屏，有一处不开画）
# 日志：专八/大字版水墨/流水线_<步骤>.log；最后一行写“流水线完成”或“流水线停止：原因”。音频（batch_audio.sh）和语音识别核对要人判断，不在这里。
set -u
cd "$(dirname "$0")/../.." || exit 1
export DZB_VARIANT=水墨
PY=/opt/ttsenv/bin/python
W=专八/大字版水墨
step=$1; shift
ids="$*"
log=$W/流水线_$step.log
: > "$log"
stop() { echo "流水线停止：$1（$(date -u +%H:%M)）" | tee -a "$log"; exit 1; }
case $step in
  分屏)
    $PY 专八/tools/分屏建议.py $ids --styles C --out $W/分屏方案_当前批.json --resume >> "$log" 2>&1 || stop "分屏建议出错"
    $PY 专八/tools/分屏定稿.py $W/分屏方案_当前批.json $ids >> "$log" 2>&1 || stop "有句子要人工指定分屏（见日志，写进 分屏手定_水墨.json 后重跑同一条命令）"
    $PY 专八/tools/split_check.py 专八/tools/分屏_水墨.json > $W/split_check_水墨.log 2>&1
    tail -1 $W/split_check_水墨.log | grep -q "ALL OK" || stop "split_check 没有全部通过"
    # 2026 三篇：分屏质检、截图预检原来另跑，可疑句第二轮才发现（多跑一遍流水线）；现在同一次跑完、一起列出
    $PY 专八/tools/分屏质检.py $ids >> "$log" 2>&1 || stop "分屏质检出错"
    q=$(grep -o "分屏质检：[0-9]* 句可疑" "$log" | tail -1); echo "$q" | tee -a "$log"
    $PY 专八/tools/大字版_水墨.py --preflight $ids >> "$log" 2>&1 || stop "截图预检有问题（见日志）"
    case "$q" in *"：0 句可疑") ;; *) stop "$q：逐句读文字，要改的写进 分屏手定_水墨.json 后重跑；读过确认无误的不用改" ;; esac
    ;;
  截图)
    $PY 专八/tools/大字版_水墨.py --stills $ids >> "$log" 2>&1 || stop "截图检查有问题（见日志）"
    ;;
  *) stop "不认识的步骤 $step（分屏 / 截图）" ;;
esac
echo "流水线完成（$(date -u +%H:%M)）" | tee -a "$log"
