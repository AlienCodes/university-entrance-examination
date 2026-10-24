"""复盘用的返工统计（程序统计，不手数；铁律 16）：

    python3 tools/防复发/复盘统计.py 专八 --since "2026-10-23 00:00" [--until "2026-10-23 16:40"]

从提交记录里数：同一篇音频生成了几次、截图登记（审阅通过）改了几次、引擎 / 排版检查 / 共用规则改了几次、人工分屏改了几次、
读音修正改了几次。同一篇音频生成两次以上、引擎在批量中途改过，都是返工的信号，复盘时逐条说明根因和以后怎么避免。"""
import collections
import re
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
a = sys.argv[1:]
proj = a[0]
opt = lambda k: a[a.index(k) + 1] if k in a else None
rng = ['--since', opt('--since')] + (['--until', opt('--until')] if opt('--until') else [])


def commits(*paths):
    out = subprocess.run(['git', '-C', str(R), 'log', '--format=%h %ad %s', '--date=format:%H:%M', *rng, '--', *paths],
                         capture_output=True, text=True).stdout.strip().splitlines()
    return out


audio = collections.Counter()
for line in commits(f'{proj}/audio/cet4_male'):
    for pid in re.findall(r'\b([a-z]\d\d)\b', line):
        audio[pid] += 1
redo = {k: v for k, v in audio.items() if v > 1}
groups = {
    '截图登记（审阅通过）': [f'{proj}/tools/画面核查/截图审阅通过.json'],
    '引擎、排版检查、共用规则': [f'{proj}/tools/make_video.py', '中考/tools/画面核查/layoutcheck.py', '中考/tools/画面核查/zh_bind.py',
                         '中考/tools/画面核查/分词补充.txt', f'{proj}/tools/样式'],
    '人工分屏': [f'{proj}/tools/分屏手定_水墨.json', f'{proj}/tools/分屏手定.json'],
    '读音修正': [f'{proj}/tools/读音修正.json'],
    '翻译标注': [f'{proj}/ann'],
}
print(f'# {proj} 返工统计（{" ".join(rng)}）')
print(f'- 音频：生成 {sum(audio.values())} 篇次，其中重做的篇目 {len(redo)} 篇：{dict(sorted(redo.items()))}')
for k, ps in groups.items():
    c = commits(*ps)
    print(f'- {k}：改了 {len(c)} 次')
    for x in c[:12]:
        print(f'    {x[:110]}')
