"""双向验证 + 检查：高考听力每个画面状态至少 1 帧（踩坑 131）。
run 42932631483：2019-shq、2021-shq 的 render 在编码前停“画面状态时长 ≤ 0 帧”（2025-xkb2 同样）——录音里没有“听力结束”说明，
时间轴的结束屏落在录音末尾，与答案屏同一时刻。修正：结束屏至少停 END_MIN 秒（录音之后补静音，原音不动），答案屏顺延。
precheck 只跑 时间轴 / 版式 / 自检 / 音频，没有一步把全部画面状态按帧排一遍，所以到 render 编码前才暴露。
  ① 现在的引擎：49 套 states() 按帧排，每个状态 ≥ 1 帧、结束屏 ≥ END_MIN 秒，其余 45 套的状态时刻与修正前逐个相同；
  ② 修正前的引擎（d336b29）必须报出 2019-shq、2021-shq、2025-xkb2，以及 2021-zj6（录音没有“第二节”说明，说明屏 0 秒）；
  ③ 引擎 layout（precheck 跑）开头调 frame_check：任何状态 ≤ 0 帧就停，不留到 render 编码前。
    /opt/ttsenv/bin/python tools/防复发/验证/结束屏时长.py"""
import json
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ENG = ROOT / '高考听力/tools/听力视频.py'
IDS = [l.strip() for l in (ROOT / '.github/gaokao-listening-all.txt').read_text('utf-8').splitlines() if l.strip()]


def load(src, sid):
    sys.argv = ['x', sid, 'none']
    for k in [k for k in sys.modules if k in ('base', '听力视频')]: del sys.modules[k]
    m = types.ModuleType('gk'); m.__file__ = str(ENG)
    exec(compile(src, str(ENG), 'exec'), m.__dict__)
    return m


def frames(src, sid):
    m = load(src, sid); b = m.base
    L, total, T = b.states()
    fr = [round((t + b.LEAD) * b.FPS) for t, s in L] + [round((total + b.LEAD) * b.FPS)]
    bad = [L[i][1]['kind'] for i in range(len(L)) if fr[i + 1] <= fr[i]]
    end = [fr[i + 1] - fr[i] for i in range(len(L)) if L[i][1]['kind'] == 'end']
    return bad, end, [(round(t, 4), s['kind']) for t, s in L], b.FPS, getattr(m, 'END_MIN', None)


def main():
    import os
    os.environ.setdefault('GK_OUT', '/tmp/gk-endcheck')
    new = ENG.read_text('utf-8')
    old = subprocess.run(['git', '-C', str(ROOT), 'show', 'd336b29:高考听力/tools/听力视频.py'], capture_output=True, text=True, check=True).stdout
    probs, olds = [], []
    for sid in IDS:
        bn, en, ln, fps, em = frames(new, sid)
        bo, eo, lo, _, _ = frames(old, sid)
        if bn: probs.append(f'{sid}：{bn} 时长 ≤ 0 帧')
        if not en or min(en) < round(em * fps): probs.append(f'{sid}：结束屏 {en} 帧 < {em} 秒')
        if bo: olds.append(sid)
        elif ln != lo: probs.append(f'{sid}：本来没问题的套状态时刻变了')
    print(f'① 现在 {len(IDS)} 套：{len(probs)} 处')
    for p in probs: print('  ', p)
    want = {'2019-shq', '2021-shq', '2025-xkb2', '2021-zj6'}
    if "elif c == 'layout': frame_check(); layout()" not in new: probs.append('引擎 layout 没先调 frame_check')
    print(f'② 修正前的引擎报出：{olds}（应含 {sorted(want)}）')
    sys.exit(0 if not probs and want <= set(olds) else 1)


if __name__ == '__main__':
    main()
