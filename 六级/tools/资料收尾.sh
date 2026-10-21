#!/bin/bash
# 六级学习资料收尾（一次启动、自己流到底）：等 4 份标准 PDF 生成完、60 篇长难句分析全部通过程序检查 → 排版长难句 PDF →
# 每 10 篇提交推送一次 → 写发布清单触发 release-cet6-materials.yml。日志：六级/资料收尾.log
cd "$(dirname "$0")/../.." || exit 1
PY=/opt/ttsenv/bin/python
while pgrep -f "make_dictation[.]py all" >/dev/null; do sleep 30; done
grep -q "^60 " <(ls -d 六级/听写卡/*/ | wc -l) || echo "⚠️ 听写卡文件夹数：$(ls -d 六级/听写卡/*/ | wc -l)"
until $PY 六级/tools/长难句.py check >/dev/null 2>&1; do sleep 60; done
echo "$(date +%T) 60 篇长难句分析全部通过检查"
$PY 六级/tools/长难句.py pdf || { echo "❌ 长难句 PDF 失败"; exit 1; }
commit() {      # 抢 index.lock 时等一等再试
  for i in 1 2 3 4 5 6; do git add "$@" && { git diff --cached --quiet || git commit -q -m "$MSG

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Bo2nvX3EdvyJhDdDqVayNH"; } && break; sleep 10; done
  for i in 1 2 3 4 5; do git push -q -u origin claude/epic-edison-4gkcfb && return 0; sleep $((5 * i)); done; echo "❌ 推送失败"; exit 1
}
mapfile -t F < <(ls -d 六级/听写卡/*/ | sort)
for ((i = 0; i < ${#F[@]}; i += 10)); do
  MSG="六级学习资料：第 $((i + 1))—$((i + 10)) 篇（5 份 PDF）" commit "${F[@]:i:10}"
  echo "$(date +%T) 已推送第 $((i + 1))—$((i + 10)) 篇"
done
MSG="六级长难句分析：60 篇 256 句（程序挑句、程序检查）" commit 六级/长难句
echo cet6-materials-60 > .github/cet6-materials-release.txt
MSG="发布六级学习资料（60 篇 × 5 份 PDF + 朗读音频）" commit .github/cet6-materials-release.txt
echo "$(date +%T) 已触发发布 cet6-materials-60"
