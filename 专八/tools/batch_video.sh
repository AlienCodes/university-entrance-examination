#!/bin/bash
# 按给定顺序逐篇生成专八 4K 视频（make_video.py 内含全部成品核查），每篇完成即提交推送（铁律 9）。
cd "$(dirname "$0")/../.." || exit 1
for id in "$@"; do
  /opt/ttsenv/bin/python 专八/tools/make_video.py "$id" || { echo "视频未通过：$id"; continue; }
  git add 专八/最终视频 && git commit -q -m "专八视频：$id

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Bo2nvX3EdvyJhDdDqVayNH" && git push -q -u origin claude/epic-edison-4gkcfb
done
echo 全部完成
