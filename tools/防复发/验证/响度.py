"""双向验证：响度检查 verify_loudness（铁律 2；踩坑 1、2、63、66）。用合成的“朗读”信号，测仓库里真正在用的那份函数：
正常 → 0 处；某句 +6 dB、0 dBFS 咔哒、6 秒区段 +4 dB、整体 −20 LUFS → 各自必须报出；
长静音原题屏（踩坑 63）、书信格式行（踩坑 66）不误报，但正文里真的波动照样查出。几秒跑完。
    python3 tools/防复发/验证/响度.py"""
import io
import sys

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

sys.path.insert(0, __import__('os').path.dirname(__file__))
from _抽取 import load  # noqa: E402
sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__file__), '..', '..', 'tts'))   # verify_loudness 的意群检查要导入 响度细查

g = load('tools/tts/gaokao_tts.py', ['LIMITS', 'verify_loudness', 'edge_span'], {'np': np})
V, EDGE = g['verify_loudness'], g['edge_span']
SR = 24000
rng = np.random.default_rng(7)
bad = []


def speech(sec):
    """像朗读的信号：有色噪声 × 4 Hz 音节包络。"""
    n = int(sec * SR)
    x = np.convolve(rng.standard_normal(n), np.ones(6) / 6, 'same')
    env = 0.6 + 0.4 * np.sin(2 * np.pi * 4 * np.arange(n) / SR) ** 2
    return x * env


def build(lead=1.5, durs=(3.2,) * 12, gap=0.8, tail=2.0):
    parts, items, t = [np.zeros(int(lead * SR))], [], lead
    gaps = gap if isinstance(gap, (list, tuple)) else [gap] * len(durs)
    for d, gp in zip(durs, gaps):
        parts.append(speech(d))
        items.append({'start': t, 'end': t + d})
        t += d
        parts.append(np.zeros(int(gp * SR)))
        t += gp
    parts.append(np.zeros(int(tail * SR)))
    return np.concatenate(parts), items


def norm(a, lufs=-16.0):
    m = pyln.Meter(SR)
    return a * 10 ** ((lufs - m.integrated_loudness(a)) / 20)


def run(a, items, span=None):
    buf = io.BytesIO()
    sf.write(buf, a.astype(np.float32), SR, format='WAV', subtype='FLOAT')
    return V(buf.getvalue(), items, -16.0, span)[1]


def case(name, errs, want=None):
    ok = (not errs) if want is None else any(want in e for e in errs)
    print(f"  {'✅' if ok else '❌'} {name}：{errs or '0 处'}")
    if not ok:
        bad.append(name)


def seg(items, i):
    return slice(int(items[i]['start'] * SR), int(items[i]['end'] * SR))


a, it = build()
a = norm(a)
case('正常 → 0', run(a, it))
b = a.copy(); b[seg(it, 5)] *= 10 ** (6 / 20); b = norm(b)
case('某句 +6 dB → 句间响度偏差', run(b, it), '句间响度偏差')
b = a.copy(); b[int(10 * SR)] = 0.999
case('0 dBFS 咔哒 → 峰值', run(b, it), '峰值')
b = a.copy(); b[int(it[3]['start'] * SR):int(it[4]['end'] * SR)] *= 10 ** (4 / 20); b = norm(b)
case('6 秒区段 +4 dB → 短时响度波动', run(b, it), '短时响度波动')
case('整体 −20 LUFS → 整体响度', run(norm(a, -20.0), it), '整体响度')

# 踩坑 63：片头之后 10 秒静音的原题屏，第一句在 11.5 秒才开口
a2, it2 = build(lead=11.5)
a2 = norm(a2)
case('长静音原题屏 → 0（踩坑 63 不误报）', run(a2, it2))
b = a2.copy(); b[int(it2[3]['start'] * SR):int(it2[4]['end'] * SR)] *= 10 ** (4 / 20); b = norm(b)
case('长静音原题屏 + 正文 6 秒 +4 dB → 照样报出', run(b, it2), '短时响度波动')

# 踩坑 66：书信开头一行、结尾两行格式行（不到 1 秒），前后是静音
a3, it3 = build(durs=(0.7,) + (3.2,) * 12 + (0.6, 0.7), gap=[2.5] + [0.8] * 11 + [2.5, 1.5, 0.8])
a3 = norm(a3)
sp = EDGE(it3, [1, 2])
case('书信格式行、不用 edge_span → 报出（踩坑 66 原样重现）', run(a3, it3), '短时响度波动')
case('书信格式行 + edge_span → 0（踩坑 66 不误报）', run(a3, it3, sp))
b = a3.copy(); b[int(it3[2]['start'] * SR):int(it3[3]['end'] * SR)] *= 10 ** (4 / 20); b = norm(b)
case('书信格式行旁边的正文 +4 dB → 照样报出', run(b, it3, sp), '短时响度波动')

print('响度双向验证：' + ('全部通过' if not bad else f'{len(bad)} 处失败：{bad}'))
sys.exit(1 if bad else 0)
