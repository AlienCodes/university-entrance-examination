#!/bin/bash
# 读后续写 v2（逐句屏新讲法 + 全片英文配中文）：一条命令流到底，出错即停。只合成了逐句屏新段（任务_续写_补逐块 / 补逐块英文），其余复用 v1 整片的合成。
#   preview：等合成结果 → 选段只出开头预览 t01—s2h 的音频（完整处理链 + 合格证）→ 提交 → 本机 v2 4K（截图检查 + 成品核查全部）→ 1080p 推 高考续写/预览/
#   full：  同样的叠加 → 选段整片 → 按工作流检出路径试排 v2 截图 → 提交音频 + render.txt（第 5 行 续写视频_v2.py）→ Actions 生成 4K、核查、发布 Release → 下载核对
# 用法：SP=<scratchpad> bash 高考续写/tools/续写v2整片.sh preview|full
set -euo pipefail
cd "$(dirname "$0")/../.."
STAGE=$1
D=高考续写/讲解/2026_新课标Ⅰ卷
BR=claude/epic-edison-4gkcfb
# v1 整片的叠加（交接_整片收尾.md）+ 逐句屏新段；s4b3 换了文字，原来锁定的 s4b3=take1 去掉
export SYNTH_ALLOW_MISSING=m/take2/part13 KEEP_ORIG="a01~2" LOCK="f04=take1 s3p1~1=take5"
export OVERLAY_TASK="任务_续写_补s1z.json 任务_续写_补拼接.json 任务_续写_补声调.json 任务_续写_补英文.json 任务_续写_补拼接2.json 任务_续写_补开头.json 任务_续写_补逐块.json 任务_续写_补逐块英文.json"
export DROP_TASK="任务_续写_补逐块.json"
export AFTER=0
if [ "$STAGE" = preview ]; then
  IDS=$(python3 -c "
import json;s=[x['id'] for x in json.load(open('$D/稿.json',encoding='utf-8'))['segments']];print(' '.join(s[s.index('t01'):s.index('s2h')+1]))")
  N="2026 新课标Ⅰ卷 读后续写 讲解 开头预览 v2（用户本人声音）"
  AUDIO_ONLY=1 bash 高考续写/tools/续写全片.sh "$D" 任务_续写_全片.json m "预览/$N" none $IDS
  git add 高考续写/audio/预览/
  git commit -qm "高考续写：开头预览 v2 音频（逐块屏新段 + 其余复用 v1 合成；选段 + 完整处理链 + 合格证）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BA1TPFroGqVyR4NdqKc357"
  for i in 1 2 3 4; do git pull -q --rebase origin "$BR" && git push -q origin "$BR" && break; sleep $((2**i)); done
  MP3="高考续写/audio/预览/$N.mp3" OUTN="2026 新课标Ⅰ卷 读后续写 讲解 开头预览 v2（逐块翻 + 中文）" bash 高考续写/tools/续写预览_v2.sh
elif [ "$STAGE" = full ]; then
  export VERIFY_EN="s3b1:towed s4b1:drove s11b1:drove" ENGINE=续写视频_v2.py
  bash 高考续写/tools/续写全片.sh "$D" 任务_续写_全片.json m "2026 新课标Ⅰ卷 读后续写 讲解 v2（用户本人声音）" xuxie-2026-1-v2
else
  echo "用法：$0 preview|full"; exit 1
fi
