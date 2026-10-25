#!/bin/bash
# 成品核查通过后：成品放进 专八/听力/最终视频/（> 90 MB 就按 90 MB 切段，GitHub 单文件上限 100 MB），
# 写发布清单 .github/tem8-listening-release.txt，提交推送 → 触发 release-tem8-listening.yml（拼回、核对 sha256、zipfile 打包、发布、下载核对）。
set -euo pipefail
cd "$(dirname "$0")/../../.."
OUT=${TEM8_OUT:?}
NAME='2025年 专八听力 视频版真题考试.mp4'
SRC="$OUT/$NAME"
[ -f "$SRC" ] || { echo "停止：没有成品（核查不通过会删除成品）"; exit 1; }
python3 -c "import json,sys;r=json.load(open('专八/听力/2025/核查报告.json'));sys.exit(1 if r['问题'] else 0)" || { echo "停止：核查报告有问题"; exit 1; }
D=专八/听力/最终视频
rm -rf "$D"; mkdir -p "$D"
sha=$(sha256sum "$SRC" | cut -d' ' -f1)
split -b 90M -d -a 2 "$SRC" "$D/$NAME.part"
{ echo tem8-listening-2025; echo "$NAME"; echo "$sha"; (cd "$D" && ls -1 | sort); } > .github/tem8-listening-release.txt
cat "$D"/*.part* | sha256sum | grep -q "$sha" || { echo "停止：分段拼回不一致"; exit 1; }
git add "$D" .github/tem8-listening-release.txt 专八/听力/2025/核查报告.json 专八/听力/2025/时间轴.json
git commit -qm "专八听力 2025 视频版真题考试：成品（分段提交）+ 发布清单，触发发布 tem8-listening-2025

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YGt3soXoAhqVXEXfDohr2h"
for i in 1 2 3 4; do git push -q origin claude/epic-edison-4gkcfb && break || sleep $((2**i)); done
echo "已推送：$(ls "$D" | wc -l) 段，sha256 $sha"
