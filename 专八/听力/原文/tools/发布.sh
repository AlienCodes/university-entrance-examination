#!/bin/bash
# 三个视频成品核查全部通过后：按考试顺序（L1 讲座、L2 Part One、L3 Part Two）写发布清单 .github/tem8-listening-text-release.txt，
# 连同成品提交推送 → 触发 release-tem8-listening-text.yml（核对 sha256、zipfile 打包、发布 tem8-listening-text-2025、下载核对）。出错即停。
set -euo pipefail
cd "$(dirname "$0")/../../../.."
D=专八/听力/原文/最终视频_水墨
R=专八/听力/原文/大字版水墨/成品核查
L=.github/tem8-listening-text-release.txt
names=("2025年专八听力 Section A 讲座：工作记忆.mp4" "2025年专八听力 Section B Part One 访谈：休息与工作（上）.mp4" "2025年专八听力 Section B Part Two 访谈：休息与工作（下）.mp4")
echo tem8-listening-text-2025 > $L.tmp
for n in "${names[@]}"; do
  [ -f "$D/$n" ] || { echo "停止：没有成品 $n"; exit 1; }
  python3 -c "import json,sys;r=json.load(open(sys.argv[1]));sys.exit(0 if r['ok'] else 1)" "$R/${n%.mp4}_核查.json" || { echo "停止：$n 成品核查没通过"; exit 1; }
  echo "$(sha256sum "$D/$n" | cut -d' ' -f1) $n" >> $L.tmp
done
mv $L.tmp $L
git add "$D" "$R" $L
git commit -qm "专八听力原文精读：3 个视频成品（核查全部通过）+ 发布清单，触发发布 tem8-listening-text-2025

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FjMDTZWJnjjhhSfUzyiGkp"
ok=0
for i in 1 2 3 4; do
  git pull -q --no-rebase --no-edit origin claude/epic-edison-4gkcfb && git push -q origin claude/epic-edison-4gkcfb && { ok=1; break; }
  sleep $((2**i))
done
[ $ok = 1 ] || { echo "停止：推送失败"; exit 1; }
echo "已推送发布清单：$(($(wc -l < $L) - 1)) 个视频"
