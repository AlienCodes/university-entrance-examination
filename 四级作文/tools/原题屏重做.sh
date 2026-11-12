#!/bin/bash
# 作文视频原题屏改版后整批重做（一次启动、自己流到底；出错即停）：每个项目 截图 + 全部程序检查 → 登记 → 提交推送 → 改触发清单标签并推送（GitHub 生成、发布）。
# 用法：bash 四级作文/tools/原题屏重做.sh 四级作文:cet4w-2 六级作文:cet6w-2
# 四级先做：它的 GitHub 生成与六级的本机截图同时进行。
set -e -o pipefail
cd "$(dirname "$0")/../.."
PY=/opt/ttsenv/bin/python
push() { for i in 1 2 3 4; do git push -q -u origin claude/epic-edison-4gkcfb && return 0; sleep $((2**i)); done; return 1; }
for job in "$@"; do
  proj=${job%%:*}; tag=${job##*:}
  case $proj in 四级作文) wf=render-cet4-writing.yml; list=.github/cet4-writing-render.txt ;;
                六级作文) wf=render-cet6-writing.yml; list=.github/cet6-writing-render.txt ;;
                *) echo "不认识的项目 $proj"; exit 1 ;; esac
  python3 .github/check-browser-match.py .github/workflows/$wf      # 踩坑 78：本机与 GitHub 浏览器一致
  ids=$(tail -n +2 $list | tr '\n' ' ')
  echo "== $proj 截图（$ids）$(date +%T)"
  $PY $proj/tools/大字版.py --stills $ids 2>&1 | grep -v -i warn | grep -v '^\s*$' | tail -40
  echo "== $proj 登记 $(date +%T)"
  $PY $proj/tools/大字版.py --approve $ids 2>&1 | grep -v -i warn | tail -5
  git add -A $proj
  git commit -qm "$proj 原题屏新版式：全部截图重画、程序检查 0 处、登记

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PYHQnF46mqCrjGHAYcpe3E" || true
  push
  { echo "$tag"; tail -n +2 $list; } > $list.new && mv $list.new $list
  git add $list
  git commit -qm "$proj：触发 GitHub 生成全部视频并重新发布（标签 $tag）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PYHQnF46mqCrjGHAYcpe3E"
  push
  echo "== $proj 已触发 GitHub 生成 $(date +%T)"
done
echo CHAIN_DONE
