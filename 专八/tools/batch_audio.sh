#!/bin/bash
# 按给定顺序逐篇生成专八音频并做语音识别自检；每篇完成即提交推送（铁律 9）。
# 用法：bash 专八/tools/batch_audio.sh c60 c59 …
cd "$(dirname "$0")/../.." || exit 1
PY=/opt/ttsenv/bin/python
for id in "$@"; do
  $PY 专八/tools/make_audio.py "$id" || { echo "音频未通过：$id"; continue; }
  $PY 专八/tools/qa_audio.py "$id" || echo "自检出错：$id"
  git add 专八/audio && git commit -q -m "专八音频：$id（新停顿规则）及自检

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Bo2nvX3EdvyJhDdDqVayNH" && git push -q -u origin claude/epic-edison-4gkcfb
done
echo 全部完成
