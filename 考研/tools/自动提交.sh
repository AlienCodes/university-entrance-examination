#!/bin/bash
# 后台自动提交（虹吸：中间产物由程序自己定时提交推送，不靠模型每轮手动提交）：每 5 分钟把考研的音频、分屏方案、截图汇总/参考文字/总览图提交推送；
# 给定的进程都结束后再提交一次就退出。和音频批量脚本抢 index.lock 时这一轮跳过，下一轮再来。
# 用法：setsid nohup bash 考研/tools/自动提交.sh <PID…> &
cd "$(dirname "$0")/../.." || exit 1
once() {
  git add 考研/audio 考研/tools/分屏.json 考研/大字版/截图/汇总.json 考研/大字版/截图/ref 考研/大字版/截图/k*/总览.jpg 2>/dev/null || return
  git diff --cached --quiet && return
  git commit -q -m "考研（自动提交）：音频、分屏方案、截图汇总与总览图

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Bo2nvX3EdvyJhDdDqVayNH" || return
  for i in 1 2 3 4; do git push -q -u origin claude/epic-edison-4gkcfb && return; sleep $((2 ** i)); done
}
alive() { for p in "$@"; do kill -0 "$p" 2>/dev/null && return 0; done; return 1; }
while alive "$@"; do once; sleep 300; done
once
