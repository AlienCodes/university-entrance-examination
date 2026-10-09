"""电磁音（铁律第 10 条）：测量和去除语音模型声码器叠加的固定频率窄带音。

四级的 debuzz.py 只针对 Kokoro 的 9 个固定频点。西班牙语可能换用别的语音模型，声码器频点不同，
所以这里在 2–16 kHz 全频段找窄带峰（与四级同样的方法：长时频谱减去周围 ±22 Hz 的中位数），
上限同样是 +3 dB；去除方法也与四级相同（用户试听确认过的）：只在找到的固定频点做 60 Hz 带宽的单向陷波，
原本无声的地方保持无声。
"""
import numpy as np

MAX_DB = 3.0


def scan(x, sr, items, lo=2000, hi=16000, top=12, floor=1.5):
    """返回 [(频率 Hz, 高出周围 dB)]，从强到弱。items：[{start, end}] 只看有声部分。"""
    from scipy.ndimage import median_filter
    from scipy.signal import welch
    sp = np.concatenate([x[int(s['start'] * sr): int(s['end'] * sr)] for s in items]).astype(np.float64)
    f, P = welch(sp, sr, nperseg=65536)
    r = 10 * np.log10(P + 1e-20)
    r = r - median_filter(r, 61)
    m = (f >= lo) & (f <= min(hi, sr / 2 - 200))
    fm, rm = f[m], r[m]
    peaks = []
    for i in np.argsort(rm)[::-1]:
        if rm[i] < floor or len(peaks) >= top:
            break
        if all(abs(fm[i] - q) > 30 for q, _ in peaks):
            peaks.append((round(float(fm[i]), 1), round(float(rm[i]), 2)))
    return peaks


def check(x, sr, items):
    pk = scan(x, sr, items)
    f0, r = pk[0] if pk else (0.0, 0.0)
    errs = [f'电磁音：{f0:.0f} Hz 高出周围 {r:.1f} dB（上限 {MAX_DB} dB）'] if r > MAX_DB else []
    return f0, r, errs


def debuzz(x, sr, tones, bw=60.0):
    """只在给定的固定频点做 60 Hz 带宽的单向（因果）陷波；原本是 0 的采样保持 0。"""
    from scipy.signal import iirnotch, lfilter
    if not tones:
        return x
    y = x.astype(np.float64)
    for f0 in tones:
        b, a = iirnotch(f0, f0 / bw, sr)
        y = lfilter(b, a, y)
    y = y.astype(np.float32)
    y[x == 0] = 0
    return y
