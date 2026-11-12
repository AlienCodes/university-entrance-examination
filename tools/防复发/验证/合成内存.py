"""双向验证：合成机常驻内存（踩坑 101；2026-11-03 第 6 轮 synth(12) 每段常驻约 14.4 GB / 16 GB，被 GitHub 收回）。CI 能跑。
  ① 机制：子进程里分配约 800 MB 小数组再释放（留少量不释放、造碎片），不调 malloc_trim 时常驻内存降不下来；
     调 qwen_synth.trim_heap 后至少降 300 MB——证明“还给系统”有效（不改变任何计算）；
  ② 接入：qwen_synth 在模型加载后、每段合成后都调 trim_heap，记 rss_after_load_mb / rss_peak_mb，超过 RSS_WARN_MB（≤ 12000）记进 meta；
     工作流“合成”步骤设 MALLOC_ARENA_MAX。
  缺口：本机加载不了真模型（HuggingFace 被代理拦），真实降幅看下一次合成 meta 的 rss_after_load_mb。
    python3 tools/防复发/验证/合成内存.py"""
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
bad = []
code = r'''
import sys, numpy as np
sys.path.insert(0, sys.argv[1])
import qwen_synth as Q
keep, xs = [], [np.ones(8000, np.float64) for _ in range(12000)]   # 64 KB × 12000 ≈ 770 MB，走堆分配
for i, x in enumerate(xs):
    if i % 200 == 0:
        keep.append(x)
r0 = Q.rss_mb(); del xs, x
import gc; gc.collect()
r1 = Q.rss_mb()
if sys.argv[2] == '1':
    Q.trim_heap()
r2 = Q.rss_mb()
print(r0, r1, r2)
'''
tools = str(ROOT / '高考语法填空/tools')
a = [int(v) for v in subprocess.run([sys.executable, '-c', code, tools, '0'], capture_output=True, text=True).stdout.split()]
b = [int(v) for v in subprocess.run([sys.executable, '-c', code, tools, '1'], capture_output=True, text=True).stdout.split()]
print(f'① 不 trim：分配后 {a[0]} → 释放后 {a[2]} MB；trim：{b[0]} → {b[2]} MB')
if not (a[0] - a[2] < 300 <= b[0] - b[2]):
    bad.append('① trim_heap 没把内存还给系统（或不 trim 也能降，验证不成立）')
src = (ROOT / '高考语法填空/tools/qwen_synth.py').read_text('utf-8')
import re  # noqa: E402
w = re.search(r'RSS_WARN_MB = (\d+)', src)
ok2 = (w and int(w.group(1)) <= 12000 and src.count('trim_heap()') >= 3 and 'rss_after_load_mb' in src and 'rss_peak_mb' in src
       and src.index('from_pretrained(c[\'model\'], **kw)\n        gc.collect()\n        trim_heap()') > 0)
wf = yaml.safe_load((ROOT / '.github/workflows/tts-grammar-qwen.yml').read_text('utf-8'))
st = next(x for x in wf['jobs']['synth']['steps'] if x.get('name') == '合成')
if not ok2 or 'MALLOC_ARENA_MAX' not in (st.get('env') or {}):
    bad.append('② qwen_synth / 工作流没接上')
print('② 接入', '对' if '②' not in ' '.join(bad) else '错')
print('合成内存双向验证', '通过' if not bad else '失败：' + '、'.join(bad))
sys.exit(1 if bad else 0)
