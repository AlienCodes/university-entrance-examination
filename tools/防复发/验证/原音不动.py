"""双向验证（踩坑 121）：六级听力练习视频一律原音（老师 2026-11-04 定）。专八听力引擎 orig_match：成品音轨与原音逐样本比，
在 AAC 编码误差内才过。合成信号经真实 AAC 192k 编码：
  正常 0 处；音量改 0.2 dB、整体提到 −16 LUFS（+4 dB）、单声道变双声道、时间错开 10 毫秒都必须报出；
  静态：六级听力视频.py 开着 base.ORIGINAL、没开 base.LIMIT。
    /opt/ttsenv/bin/python tools/防复发/验证/原音不动.py"""
import ast, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf

R = Path(__file__).resolve().parents[3]
src = (R / '专八/听力/tools/听力视频.py').read_text('utf-8')
keep = {'orig_match', 'ORIG_MAX_GAIN_DB', 'ORIG_MIN_SNR_DB', 'ORIG_MAX_SEC_DB'}
body = [n for n in ast.parse(src).body if (isinstance(n, ast.FunctionDef) and n.name in keep) or
        (isinstance(n, ast.Assign) and any(getattr(e, 'id', None) in keep for t in n.targets for e in [t, *getattr(t, 'elts', [])]))]
ns = {}; exec(compile(ast.Module(body, []), 'orig', 'exec'), ns); match = ns['orig_match']

sr, bad = 44100, []
rng = np.random.default_rng(1)
t = np.arange(sr * 20) / sr
env = 0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 1.3 * t))
f0 = 140 + 30 * np.sin(2 * np.pi * 0.4 * t)                     # 像说话：基频缓慢起伏的谐波（白噪声是 AAC 最难编的信号，不像录音）
ph = 2 * np.pi * np.cumsum(f0) / sr
mono = (sum(0.12 / k * np.sin(k * ph) for k in range(1, 12)) * env)[:, None]


def aac(x):
    with tempfile.TemporaryDirectory() as d:
        w, m = Path(d) / 'a.wav', Path(d) / 'a.m4a'
        sf.write(w, x, sr, subtype='FLOAT')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(w), '-c:a', 'aac', '-b:a', '192k', str(m)], check=True)
        pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(m), '-f', 'f32le', '-ac', str(x.shape[1]), '-ar', str(sr), '-'],
                             capture_output=True, check=True).stdout
    return np.frombuffer(pcm, dtype=np.float32).reshape(-1, x.shape[1]).astype(np.float64)[:len(x)]


stereo = np.concatenate([mono, 0.8 * mono], axis=1)
for ref in (mono, stereo):
    dec = aac(ref); tag = f'{ref.shape[1]} 声道'
    for name, d, want in [('正常', dec, False), ('音量 +0.2 dB', dec * 10 ** (0.2 / 20), True), ('整体提到 −16（+4 dB）', dec * 10 ** (4 / 20), True),
                          ('时间错开 10 毫秒', np.roll(dec, int(0.01 * sr), axis=0), True),
                          ('声道数变了', np.repeat(dec[:, :1], 2, axis=1) if ref.shape[1] == 1 else dec[:, :1], True)]:
        got = match(ref, d, sr)
        ok = bool(got) == want
        print(('✅' if ok else '❌'), tag, name, '→', got or '0 处')
        if not ok: bad.append(f'{tag} {name}')
six = (R / '六级/听力/tools/听力视频.py').read_text('utf-8')
st = 'base.ORIGINAL = True' in six and 'base.LIMIT = True' not in six
print(('✅' if st else '❌'), '六级听力视频.py 开原音模式、不开限幅')
if not st: bad.append('六级配置')
print('原音不动双向验证', '通过' if not bad else f'失败 {bad}'); sys.exit(1 if bad else 0)
