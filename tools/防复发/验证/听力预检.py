"""双向验证（踩坑 122）：六级听力练习视频的预检（只查音频 + 工作流第一道关）。
① 引擎 audio_check（合成信号，states 换成假的时间轴）：原音模式正常 0 处；把旧的限幅关口放回去（b92dfdf 的 limited，
   LIMIT 模式）遇到尖峰必须停；原音模式下音频被改了音量必须停。
② 工作流 render-cet6-listening.yml：precheck 对每套跑 timeline、layout、--自检、audio；render 依赖 precheck；拿掉任何一样都报。
    /opt/ttsenv/bin/python tools/防复发/验证/听力预检.py"""
import ast, importlib, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import yaml

R = Path(__file__).resolve().parents[3]
bad = []


def ok(name, cond, got=''):
    print(('✅' if cond else '❌'), name, '→', got)
    if not cond: bad.append(name)


# ① 引擎
sys.path.insert(0, str(R / '专八/听力/tools'))
base = importlib.import_module('听力视频')


class Stop(Exception):
    pass


def die(msg): raise Stop(msg)


base.die = die
sr, dur = 44100, 20
rng = np.random.default_rng(2)
t = np.arange(sr * dur) / sr
ph = 2 * np.pi * np.cumsum(140 + 30 * np.sin(2 * np.pi * 0.4 * t)) / sr
x = (sum(0.012 / k * np.sin(k * ph) for k in range(1, 12)) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 1.3 * t))))[:, None]
x = np.concatenate([x, x], axis=1)
for k in range(3): x[sr * (3 + 5 * k):sr * (3 + 5 * k) + 96] = 0.99          # 几处 2 毫秒的尖峰（像原音里的爆音）
base.states = lambda: ([], dur + 3.0, {'audioEnd': dur})
old_src = subprocess.run(['git', '-C', str(R), 'show', 'b92dfdf:专八/听力/tools/听力视频.py'], capture_output=True, text=True, check=True).stdout
fn = next(n for n in ast.parse(old_src).body if isinstance(n, ast.FunctionDef) and n.name == 'limited')
ns = dict(vars(base)); exec(compile(ast.Module([fn], []), 'old', 'exec'), ns); old_limited = ns['limited']
real_track = base.audio_track

with tempfile.TemporaryDirectory() as d:
    base.OUT = Path(d)
    import soundfile as sf
    wav = Path(d) / 'in.wav'; sf.write(wav, x, sr, subtype='FLOAT')

    def run(**cfg):
        base.ORIGINAL, base.LIMIT = cfg.get('orig', False), cfg.get('limit', False)
        base.limited = cfg.get('limited', base.limited)
        base.audio_track = cfg.get('track', real_track)
        try:
            base.audio_check(str(wav)); return ''
        except Stop as e:
            return str(e)
    cur_limited = base.limited
    g = run(orig=True); ok('原音模式 正常', g == '', g or '0 处')
    g = run(limit=True, limited=old_limited); ok('放回旧的 −16 + 限幅关口（尖峰）', '限幅压得太多' in g, g[:70])

    def louder(w):
        r = real_track(w); base.ORIG_REF = base.ORIG_REF * 10 ** (-0.3 / 20); return r
    g = run(orig=True, limited=cur_limited, track=louder); ok('原音模式 音频被改了 0.3 dB', '与原音整体音量差' in g, g[:70])

# ② 工作流
wf = R / '.github/workflows/render-cet6-listening.yml'


def wf_problems(y):
    p = []
    j = y.get('jobs', {})
    pc = j.get('precheck')
    if not pc: return ['没有 precheck 任务']
    txt = '\n'.join(s.get('run', '') for s in pc.get('steps', []))
    for need in (' timeline ', ' layout', ' --自检', ' audio '):
        if need not in txt: p.append(f'precheck 没跑{need.strip()}')
    if 'stills' in txt or ' video ' in txt: p.append('precheck 不该截图 / 编码')
    if 'needs.list.outputs.ids' not in str(pc.get('strategy', {})): p.append('precheck 没覆盖本次全部套')
    rn = j.get('render', {}).get('needs', [])
    if 'precheck' not in (rn if isinstance(rn, list) else [rn]): p.append('render 不依赖 precheck')
    return p


y = yaml.safe_load(wf.read_text('utf-8'))
got = wf_problems(y); ok('工作流 现在', not got, got or '0 处')
import copy
for name, mut in [('拿掉 precheck', lambda y: y['jobs'].pop('precheck')),
                  ('render 不等 precheck', lambda y: y['jobs']['render'].__setitem__('needs', ['list'])),
                  ('precheck 不查音频', lambda y: [s.__setitem__('run', s.get('run', '').replace(' audio ', ' x ')) for s in y['jobs']['precheck']['steps']])]:
    yy = copy.deepcopy(y); mut(yy); got = wf_problems(yy); ok(f'工作流 {name}', bool(got), got)
print('听力预检双向验证', '通过' if not bad else f'失败 {bad}'); sys.exit(1 if bad else 0)
