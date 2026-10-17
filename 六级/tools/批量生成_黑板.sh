#!/bin/bash
# 六级黑板：逐篇做到底，每篇一做完就备份（用户 2026-10-17：“做好的东西没有及时备份在 GitHub，容器一重启就全没了”）：
# 大字版.py --video <篇>（做好、核查过的自动跳过）→ verify_all 这一篇（独立重测）→ 提交 → 推送 → 移出工作区（sparse-checkout，省磁盘）。
# 已提交的篇目跳过；任何一步不过就停（STOP），可续跑。
cd /home/user/university-entrance-examination
LOG=六级/样片/日志/batch.log
PY=/opt/ttsenv/bin/python
[ -n "$1" ] && while kill -0 "$1" 2>/dev/null; do sleep 10; done      # 等上一个脚本留下的那一篇做完
name() { $PY -c "import sys; sys.path.insert(0,'六级/tools'); import json, make_video as M; P={p['id']:p for p in json.load(open('六级/data/vocab.json',encoding='utf-8'))['passages']}; print(M.video_name(P['$1']))" 2>/dev/null; }
gitretry() { for i in 1 2 3 4 5 6; do "$@" && return 0; sleep $((i*5)); done; return 1; }
ids=$($PY -c "import json;print(' '.join(p['id'] for p in json.load(open('六级/data/vocab.json',encoding='utf-8'))['passages']))")
for id in $ids; do
  n=$(name $id)
  git ls-files --error-unmatch "六级/最终视频_黑板/$n" >/dev/null 2>&1 && continue
  echo "$(date -u +%H:%M) 生成 $id" >> $LOG
  $PY 六级/tools/大字版.py --video $id >> $LOG 2>&1 || { echo "STOP $id 生成或成品核查不通过" >> $LOG; exit 1; }
  [ -f "六级/最终视频_黑板/$n" ] || { echo "STOP $id 没有成品" >> $LOG; exit 1; }
  $PY 六级/tools/verify_all.py $id >> $LOG 2>&1 || { echo "STOP verify_all $id 不通过" >> $LOG; exit 1; }
  cp 六级/核查报告_黑板.md "六级/样片/成品核查/核查报告_$id.md"
  gitretry git add -A "六级/最终视频_黑板/$n" 六级/样片 六级/核查报告_黑板.md
  gitretry git commit -qm "六级黑板视频 $id（成品核查 + verify_all 全部通过）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Bo2nvX3EdvyJhDdDqVayNH"
  for i in 1 2 3 4; do timeout 900 git push -qu origin claude/epic-edison-4gkcfb && break || sleep $((2**i)); done
  git status -sb | head -1 | grep -q ahead && { echo "STOP 推送失败 $id" >> $LOG; exit 1; }
  git sparse-checkout add "!/六级/最终视频_黑板/$n" >> $LOG 2>&1
  echo "$(date -u +%H:%M) 已备份到 GitHub 并移出工作区：$id；剩余磁盘 $(df -h . | tail -1 | awk '{print $4}')" >> $LOG
done
echo "$(date -u +%H:%M) 全部完成" >> $LOG
