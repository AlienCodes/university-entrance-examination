"""双向验证：合成结果完整性（踩坑 99，同踩坑 98；2026-11-03 续写 runs/任务_续写_样片-16 缺 take1，collect 照样发布，候选会悄悄少掉）。CI 能跑。
  ① 按 任务_续写_样片.json 造一个齐全的合成目录 → 0 处；拿掉 take1（-16 的情形）→ 报；拿掉一个小段 WAV → 报；拿掉 meta → 报；
  ② 真实的 -16（能取到 gram-tts-out 分支时）→ 报缺 take1；
  ③ 入口：选段.py 开头调 合成完整性.problems，不完整就退出。
    python3 tools/防复发/验证/合成完整性.py"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / '高考语法填空/tools'), str(ROOT / 'tools/tts')]
import 合成完整性 as WZ  # noqa: E402
import 讲解音频 as J  # noqa: E402

bad = []
TASK = '任务_续写_样片'
task = json.loads((ROOT / f'高考语法填空/tts/{TASK}.json').read_text('utf-8'))
c = task['candidates'][0]
segs = json.loads((ROOT / task['script']).read_text('utf-8'))['segments']
if task.get('only'):
    segs = [s for s in segs if s['id'] in task['only']]
J.SPLIT = c.get('split', task.get('split', 'mark+lang'))
units = [u['id'] for u in J.expand(segs)]
J.SPLIT = 'mark+lang'
tmp = Path(tempfile.mkdtemp())
run = tmp / f'{TASK}-99' / c['id']
for t in task['takes']:
    d = run / f'take{t}'
    d.mkdir(parents=True)
    (d / 'meta_part0.json').write_text('{}')
    for u in units:
        (d / f'{u}.wav').write_bytes(b'')
e0 = WZ.problems(run)
shutil.rmtree(run / f"take{task['takes'][0]}")
e1 = WZ.problems(run)
d2 = run / f"take{task['takes'][1]}"
(d2 / f'{units[-1]}.wav').unlink()
e2 = WZ.problems(run)
(d2 / 'meta_part0.json').unlink()
e3 = WZ.problems(run)
print(f'① 齐全 {len(e0)} 处（应 0）；缺一次 {len(e1)}；再缺一个小段 {len(e2)}；再缺 meta {len(e3)}')
if e0 or not any('整次缺失' in x for x in e1) or not any('缺 1 个小段' in x for x in e2) or not any('meta_part0' in x for x in e3):
    bad.append('①')
shutil.rmtree(tmp)
real = tempfile.mkdtemp()
r = subprocess.run(f'git -C "{ROOT}" archive origin/gram-tts-out "runs/{TASK}-16" | tar -x -C "{real}"', shell=True, capture_output=True)
if r.returncode == 0 and (Path(real) / f'runs/{TASK}-16').exists():
    e = [x for d in (Path(real) / f'runs/{TASK}-16').iterdir() for x in WZ.problems(d)]
    print(f'② 真实 -16：{e}')
    if not any('take1' in x for x in e):
        bad.append('② 真实 -16 没报缺 take1')
else:
    print('② 取不到 gram-tts-out（CI 上正常），跳过')
shutil.rmtree(real, ignore_errors=True)
if 'WZ.problems(a.run)' not in (ROOT / '高考语法填空/tools/选段.py').read_text('utf-8'):
    bad.append('③ 选段没接完整性检查')
print('合成完整性双向验证', '通过' if not bad else '失败：' + '、'.join(bad))
sys.exit(1 if bad else 0)
