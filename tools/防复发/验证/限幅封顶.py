"""双向验证（踩坑 121）：专八听力引擎 limited 的“整体增益封顶”。守门（限幅最多压低 ≤ 8 dB、被压时长 ≤ 0.5%）不放宽。
合成信号（不依赖原音）：
  ① 普通信号：目标仍是 −16 LUFS（行为不变）；
  ② 有几处尖峰、增益到 −16 后限幅要压 ~9 dB：旧引擎（b92dfdf）停，新引擎把目标降到 −16 以下、守门通过；
  ③ 尖峰极高（降到 −19 还要压 > 8 dB）：新引擎照样停。
    python3 tools/防复发/验证/限幅封顶.py"""
import ast, subprocess, sys
from pathlib import Path
import numpy as np
import pyloudnorm as pl

R = Path(__file__).resolve().parents[3]
REL = '专八/听力/tools/听力视频.py'
NAMES = ('limited', 'LIMIT_CEIL_DB', 'LIMIT_MAX_DB', 'LIMIT_FLOOR_LUFS', 'TARGET_LUFS', 'LIMIT_MAX_FRAC')


class Stop(Exception):
    pass


def load(src):
    body = [n for n in ast.parse(src).body
            if (isinstance(n, ast.FunctionDef) and n.name in NAMES) or
            (isinstance(n, ast.Assign) and any(getattr(t, 'id', None) in NAMES or
                                                any(getattr(e, 'id', None) in NAMES for e in getattr(t, 'elts', [])) for t in n.targets))]
    ns = {'ROOT': R}

    def die(msg): raise Stop(msg)
    ns['die'] = die
    exec(compile(ast.Module(body, []), 'limited', 'exec'), ns)
    return ns


new = load((R / REL).read_text('utf-8'))
old = load(subprocess.run(['git', '-C', str(R), 'show', f'b92dfdf:{REL}'], capture_output=True, text=True, check=True).stdout)

sr = 48000
rng = np.random.default_rng(0)
base = rng.normal(0, 0.03, (sr * 60, 2)) * (1 + 0.5 * np.sin(np.arange(sr * 60) / sr * 2 * np.pi * 0.7))[:, None]
L0 = pl.Meter(sr).integrated_loudness(base)
ceil = 10 ** (-2.5 / 20)


def spiky(over_db):
    """在 5 处放 2 毫秒尖峰：增益到 −16 LUFS 后比限幅上限高 over_db"""
    x = base.copy(); g16 = 10 ** ((-16 - L0) / 20)
    for k in range(5):
        i = sr * (5 + 10 * k); x[i:i + 96] = ceil * 10 ** (over_db / 20) / g16
    return x


bad = []


def run(ns, x):
    try:
        y = ns['limited'](x, sr, pl); return ns.get('TARGET_LUFS', -16.0), None
    except Stop as e:
        return None, str(e)


for name, x, want_old_stop, want in [('① 普通信号', base, False, lambda t: t == -16.0),
                                      ('② 尖峰压 9 dB', spiky(9.0), True, lambda t: t is not None and -19 <= t < -16),
                                      ('③ 尖峰压 16 dB', spiky(16.0), True, lambda t: t is None)]:
    to, eo = run(old, x)
    tn, en = run(new, x)
    ok_old = (eo is not None) == want_old_stop
    ok_new = want(tn)
    print(('✅' if ok_old else '❌'), name, '旧引擎', '停' if eo else f'通过（目标 {to}）')
    print(('✅' if ok_new else '❌'), name, '新引擎', f'停：{en[:60]}' if en else f'通过（目标 {tn} LUFS）')
    if not (ok_old and ok_new): bad.append(name)
print('限幅封顶双向验证', '通过' if not bad else f'失败 {bad}'); sys.exit(1 if bad else 0)
