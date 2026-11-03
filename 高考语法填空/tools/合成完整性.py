"""合成结果完整性（铁律 16 同类坑全项目查；2026-11-03 续写 runs/任务_续写_样片-16：一台合成机被 GitHub 停掉，collect 照样发布，
r2icl 只有 take2、take3，下游选段悄悄少一个候选）。规则只写一处，选段.py 开头自动调（所有项目、所有脚本都经过它）：
  任务清单里这个候选应有的每一次（takes）× 每一片（parts）都要有 meta_part<k>.json，每个小段（按候选的 split 展开）都要有 WAV；
  缺一个就报错，不往下走（重跑失败的作业后再选段）。
任务清单按合成目录名找：runs/<任务>-<运行号>/<候选> → 高考语法填空/tts/<任务>.json。
用法：python3 合成完整性.py runs/<任务>-<运行号>/<候选> …
显式放行（公开、有记录的决定，只放行点名的那一片；2026-11-03 续写整片 m take2 part13 合成机两次内存顶满被收回）：
  环境变量 SYNTH_ALLOW_MISSING="<候选>/take<k>/part<p>[,…]" → 这一次这一片的 meta 和这一片的段可以缺，别的缺口照拦；放行的内容打印出来。"""
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


def allowed():
    import os
    v = os.environ.get('SYNTH_ALLOW_MISSING', '').strip()
    return {tuple(x.strip().split('/')) for x in v.split(',') if x.strip()}


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
        nparts = task.get('parts', 1)
        part_units = {k: {u['id'] for u in J.expand([x for i, x in enumerate(segs) if i % nparts == k])} for k in range(nparts)}
        J.SPLIT = old
        takes = [f'take{t}' for t in task['takes']]
        parts = range(task.get('parts', 1))
    else:
        takes = sorted(p.name for p in run.glob('take*'))
        units = sorted({w.stem for t in run.glob('take*') for w in t.glob('*.wav') if w.stem != 'design_ref'})
        parts = [0]
        part_units = {}
    ok = allowed()
    for t in takes:
        free = {int(p[4:]) for c, tk, p in ok if c == run.name and tk == t and p.startswith('part')}
        if free:
            print(f'⚠ 显式放行（SYNTH_ALLOW_MISSING）：{run.name}/{t} part{sorted(free)}，这一片的段只用其余几次的候选')
        d = run / t
        if not d.is_dir():
            if set(parts) <= free:          # 这一次的每一片都点名放行（只有一片时整次 = 这一片）
                continue
            errs.append(f'{run.name}/{t} 整次缺失（合成机被停或失败；重跑失败的作业）')
            continue
        for k in parts:
            if k in free:
                continue
            if not (d / f'meta_part{k}.json').exists():
                errs.append(f'{run.name}/{t} 缺 meta_part{k}.json（这一片没跑完）')
        skip = set().union(*(part_units.get(k, set()) for k in free)) if free else set()
        miss = [u for u in units if u not in skip and not (d / f'{u}.wav').exists()]
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
