#!/bin/bash
# 一组（5 篇）：音频（去电磁音 + 自检）→ 视频 → 本组总核查 → 全部通过才发布 Release（用户要求每 5 个一组发一个包）
# 用法：bash 四级/tools/group.sh cet4-02 c35 c34 c33 c32 c31
cd "$(dirname "$0")/../.." || exit 1
tag=$1; shift
bash 四级/tools/batch_audio.sh "$@"
bash 四级/tools/batch_video.sh "$@"
/opt/ttsenv/bin/python 四级/tools/verify_all.py "$@"
rc=$?
echo "verify exit $rc"
[ $rc -eq 0 ] || { echo "核查未通过，不发布 $tag"; exit 1; }
/opt/ttsenv/bin/python - "$tag" "$@" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, '四级/tools')
from make_video import video_name
P = {p['id']: p for p in json.load(open('四级/data/vocab.json'))['passages']}
names = [video_name(P[i]) for i in sys.argv[2:]]
assert all((Path('四级/最终视频') / n).exists() for n in names)
Path('.github/cet4-videos-release.txt').write_text(sys.argv[1] + '\n' + '\n'.join(names) + '\n', 'utf-8')
PY
git add 四级/核查报告.md .github/cet4-videos-release.txt && git commit -q -m "发布 Release $tag：$* 全部核查通过

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Bo2nvX3EdvyJhDdDqVayNH" && git push -q -u origin claude/epic-edison-4gkcfb && echo "已触发发布 $tag"
