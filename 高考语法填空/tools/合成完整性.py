"""合成结果完整性（铁律 16 同类坑全项目查；2026-11-03 续写 runs/任务_续写_样片-16：一台合成机被 GitHub 停掉，collect 照样发布，
r2icl 只有 take2、take3，下游选段悄悄少一个候选）。规则只写一处，选段.py 开头自动调（所有项目、所有脚本都经过它）：
  任务清单里这个候选应有的每一次（takes）× 每一片（parts）都要有 meta_part<k>.json，每个小段（按候选的 split 展开）都要有 WAV；
  缺一个就报错，不往下走（重跑失败的作业后再选段）。
任务清单按合成目录名找：runs/<任务>-<运行号>/<候选> → 高考语法填空/tts/<任务>.json。
用法：python3 合成完整性.py runs/<任务>-<运行号>/<候选> …"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def task_of(run):
    m = re.match(r'(.+)-(\d+)$', Path(run).resolve().parent.name)
    if not m:
        return None
    p = ROOT / '高考语法填空/tts' / f'{m.group(1)}.json'
    return p if p.exists() else None


def problems(run):
    """run：某个候选的合成目录。返回问题列表（找不到任务清单时只查目录里已有的每次是否齐全）。"""
    sys.path[:0] = [str(HERE), str(ROOT / 'tools/tts')]
    import 讲解音频 as J
    run = Path(run)
    tp = task_of(run)
    errs = []
    task = json.loads(tp.read_text('utf-8')) if tp else None
    cand = next((c for c in task['candidates'] if c['id'] == run.name), None) if task else None
    if task and not cand:
        return [f'任务清单 {tp.name} 里没有候选 {run.name}']
    segs = None
    if task:
        segs = json.loads((ROOT / task['script']).read_text('utf-8'))['segments']
        if task.get('only'):
            segs = [s for s in segs if s['id'] in task['only']]
        old = J.SPLIT
        J.SPLIT = cand.get('split', task.get('split', 'mark+lang'))
        units = [u['id'] for u in J.expand(segs)]
        J.SPLIT = old
        takes = [f'take{t}' for t in task['takes']]
        parts = range(task.get('parts', 1))
    else:
        takes = sorted(p.name for p in run.glob('take*'))
        units = sorted({w.stem for t in run.glob('take*') for w in t.glob('*.wav') if w.stem != 'design_ref'})
        parts = [0]
    for t in takes:
        d = run / t
        if not d.is_dir():
            errs.append(f'{run.name}/{t} 整次缺失（合成机被停或失败；重跑失败的作业）')
            continue
        for k in parts:
            if not (d / f'meta_part{k}.json').exists():
                errs.append(f'{run.name}/{t} 缺 meta_part{k}.json（这一片没跑完）')
        miss = [u for u in units if not (d / f'{u}.wav').exists()]
        if miss:
            errs.append(f'{run.name}/{t} 缺 {len(miss)} 个小段：{miss[:5]}')
    return errs


if __name__ == '__main__':
    bad = 0
    for r in sys.argv[1:]:
        e = problems(r)
        for x in e:
            print('✗', x)
        print(f'{r}：{"齐全" if not e else f"{len(e)} 处缺失"}')
        bad += bool(e)
    sys.exit(1 if bad else 0)
