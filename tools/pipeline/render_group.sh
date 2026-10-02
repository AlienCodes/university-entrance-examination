#!/bin/bash
# 用法：render_group.sh 组名 p58 p59 ...   逐个生成并自动核查，失败立即停止
cd "$(dirname "$0")/../video"
g=$1; shift
for p in "$@"; do
  echo "=== $p $(date +%H:%M:%S)"
  if ! /opt/ttsenv/bin/python make_video.py "$p"; then echo "FAILED $p"; echo "GROUPDONE $g FAIL"; exit 1; fi
done
echo "GROUPDONE $g OK"
