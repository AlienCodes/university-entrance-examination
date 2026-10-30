"""双向验证：电磁音检查（铁律 10）。合成“朗读”信号上：干净 → 0；叠加 9600 Hz 细音（+12 dB，旧音频的强度）→ 必须报出；
用 debuzz 去掉之后 → 0；叠加不在固定频点的 6500 Hz 细音 → 不归这项管（只证明检查只看那 9 个频点，不乱报）。
    python3 tools/防复发/验证/电磁音.py"""
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / '四级' / 'tools'))
import debuzz  # noqa: E402

SR = 24000
rng = np.random.default_rng(3)
n = SR * 120
x = np.convolve(rng.standard_normal(n), np.ones(3) / 3, 'same') * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * np.arange(n) / SR) ** 2)
x = (x / np.abs(x).max() * 0.5).astype(np.float32)
items = [{'start': s, 'end': s + 4.0} for s in range(0, 116, 5)]
bad = []


def tone(f, db):
    t = np.arange(n) / SR
    from scipy.signal import welch
    f0, P = welch(x.astype(np.float64), SR, nperseg=65536)
    floor = np.median(P[(f0 > f - 300) & (f0 < f + 300)])       # 周围的功率谱密度；汉宁窗等效噪声带宽 1.5 × SR / nperseg
    a = np.sqrt(2 * floor * 10 ** (db / 10) * 1.5 * SR / 65536)
    return (x + a * np.sin(2 * np.pi * f * t)).astype(np.float32)


def case(name, sig, want):
    f0, v, errs = debuzz.check(sig, SR, items)
    ok = bool(errs) == want
    print(f"  {'✅' if ok else '❌'} {name}：最强 {f0} Hz {v:+.1f} dB")
    if not ok:
        bad.append(name)


case('干净 → 0', x, False)
buzzy = tone(9600, 12)
case('叠加 9600 Hz +12 dB → 报出', buzzy, True)
case('debuzz 处理后 → 0', debuzz.debuzz(buzzy, SR), False)
case('6500 Hz（不在固定频点）→ 不报', tone(6500, 12), False)
print('电磁音双向验证：' + ('全部通过' if not bad else f'{len(bad)} 处失败：{bad}'))
sys.exit(1 if bad else 0)
