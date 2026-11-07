#!/bin/bash
# 六级黑板 60 篇全部做完（批量日志出现“全部完成”）后自动发布：按篇目顺序写 .github/cet6-chalk-release.txt → 提交推送 → GitHub Actions 打包发布。
# 用法：setsid nohup 六级/tools/发布_黑板.sh &    （等批量做完再动 git，不与批量脚本抢）
cd /home/user/university-entrance-examination
LOG=六级/样片/日志/batch.log
until grep -q '全部完成' $LOG; do grep -q 'STOP' $LOG && { echo "$(date -u +%H:%M) 批量停了，不发布" >> $LOG; exit 1; }; sleep 60; done
/opt/ttsenv/bin/python - <<'PY' > .github/cet6-chalk-release.txt
import json, subprocess, sys
sys.path.insert(0, '六级/tools')
import make_video as M
P = json.load(open('六级/data/vocab.json', encoding='utf-8'))['passages']
names = [M.video_name(p) for p in P]
tracked = set(subprocess.run(['git', 'ls-files', '六级/最终视频_黑板'], capture_output=True, text=True).stdout.splitlines())
missing = [n for n in names if f'六级/最终视频_黑板/{n}' not in tracked]
if missing:
    sys.exit(f'还没提交的视频：{missing}')
print('cet6-chalk')
print('\n'.join(names))
PY
[ $? -eq 0 ] || { echo "$(date -u +%H:%M) 发布清单生成失败（有视频没提交）" >> $LOG; exit 1; }
git add .github/cet6-chalk-release.txt && git commit -qm "发布六级教室黑板大字版 60 个视频（Release cet6-chalk）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Bo2nvX3EdvyJhDdDqVayNH"
for i in 1 2 3 4; do timeout 600 git push -qu origin claude/epic-edison-4gkcfb && break || sleep $((2**i)); done
echo "$(date -u +%H:%M) 已推送发布清单（Release cet6-chalk 由 GitHub Actions 打包发布）" >> $LOG
