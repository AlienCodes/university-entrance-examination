"""双向验证：四级听力 录音 ↔ 试卷 配对关卡（四级/听力/tools/对照表.py）。
① 对调第 1 / 2 套两段录音的文字：必须在“文件名与内容不一致”里列出这两段（下游按内容取）；
② 去掉一段录音：那份试卷“没有录音”，关卡必须失败；
③ 让一份试卷的文字冒充另一份：两份试卷抢同一段录音，关卡必须失败（领先 < 0.15 或没有录音）；
正常时这几段一个都不许报。"""
import os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
T = ROOT / '四级/听力/tools/对照表.py'
def run(**kw):
    env = {k: v for k, v in os.environ.items() if not k.startswith('CET4_')}; env.update(kw)
    r = subprocess.run([sys.executable, str(T)], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout
bad = []
code, out = run()
for x in ('t202512-1', 't202512-2', '202406-1'):
    if x in out: bad.append(f'正常时就报了 {x}')
c, o = run(CET4_SWAP='t202512-1:t202512-2')
if not all(f'{a}：文件名标的是' in o for a in ('t202512-1', 't202512-2')): bad.append('① 对调没列出')
c, o = run(CET4_DROP='t202406-1')
if c == 0 or '202406-1：没有录音' not in o: bad.append('② 去掉录音没拦下')
c, o = run(CET4_DUP='202512-1:202512-2')
if c == 0 or '202512-' not in o: bad.append('③ 试卷冒充没拦下')
print('\n'.join(bad) or '通过：对调列出、去掉录音拦下、试卷冒充拦下；正常时不报')
sys.exit(1 if bad else 0)
