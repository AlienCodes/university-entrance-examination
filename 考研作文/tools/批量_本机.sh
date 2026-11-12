#!/bin/bash
# 考研作文批量（本机部分，一次启动、自己流到底；失败就停）：数据 → 读音登记检查 → 音频 → 语音识别核对 → 分屏 → 截图 + 全部程序检查 → 提交推送
# 用法：bash 考研作文/tools/批量_本机.sh w01 w03 …   （视频在 GitHub Actions 上生成：.github/kaoyan-writing-render.txt）
set -e -o pipefail
cd "$(dirname "$0")/../.."
PY=/opt/ttsenv/bin/python
IDS="$*"
T=考研作文/tools
$PY $T/build_vocab.py
$PY $T/pron_check.py 2>&1 | grep -v -i warn | tail -3
echo "== 音频"; $PY $T/make_audio.py $IDS 2>&1 | grep -v -i warn | grep "^\[\|未通过" 
echo "== 语音识别核对"; $PY $T/qa_audio.py $IDS 2>&1 | grep "识别差异率" || true
echo "== 分屏"; $PY $T/分屏建议.py $IDS --out 考研作文/大字版/分屏建议.json 2>&1 | grep "不合格\|找不到" | head -40 || true
$PY $T/分屏定稿.py 考研作文/大字版/分屏建议.json $IDS 2>&1 | grep -v -i warn | tail -3
echo "== 截图"; $PY $T/大字版.py --stills $IDS 2>&1 | grep -v -i warn | grep -v "^\s*$" | tail -60 || true
git add -A 考研作文
git commit -qm "考研作文批量（本机）：音频、识别核对、分屏、截图检查（$IDS）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Bo2nvX3EdvyJhDdDqVayNH" || true
for i in 1 2 3; do git push -q -u origin claude/epic-edison-4gkcfb && break || sleep $((2**i)); done
echo CHAIN_DONE
