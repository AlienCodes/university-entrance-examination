#!/bin/bash
# 六级资料生成期间的后台自动提交（与 考研/tools/自动提交.sh 相同做法）：每 3 分钟提交推送 六级/长难句、六级/听写卡；给定进程都结束后再提交一次就退出。
cd "$(dirname "$0")/../.." || exit 1
once() {
  git add 六级/长难句 六级/听写卡 2>/dev/null || return
  git diff --cached --quiet && return
  git commit -q -m "六级学习资料（自动提交）：长难句分析、PDF

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Bo2nvX3EdvyJhDdDqVayNH" || return
  for i in 1 2 3 4; do git push -q -u origin claude/epic-edison-4gkcfb && return; sleep $((2 ** i)); done
}
alive() { for p in "$@"; do kill -0 "$p" 2>/dev/null && return 0; done; return 1; }
while alive "$@"; do once; sleep 180; done
once
