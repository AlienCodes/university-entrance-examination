"""电磁音（铁律第 10 条）：去除和测量语音模型声码器叠加的固定频率细线。

两类声码器、两种去除方法（都只动模型固定的那几条线，其余音质不变）：
  Kokoro：9 个固定频点 → 60 Hz 带宽的单向陷波（与四级相同，用户试听确认过），voices.json 的 "debuzz" 写频点。
  Supertonic 3：帧频梳状线（supertonic3_comb.json：51 条，都是 44100/1024 Hz 的整数倍，与声码器每 512 个采样一帧对齐）
    → deline：每个合成片段在原始输出上（44.1 kHz、帧网格从第 0 个采样开始、还没裁剪），用最小二乘把这 51 条线拟合出来再减掉。
      幅度模型：随这一段 4–16 kHz 的包络（每 512 采样一帧）变化，静音帧为 0（2026-10-15 实测：伪迹只在声码器出声时出现、
      大小跟着高频走；按“有声就是常数”去减，会在高频很弱的元音帧里反而补进 +24 dB 的线，频谱好看、耳朵会听到——踩坑 ① 同类）。
      去掉的部分在任何一帧都不超过这一帧自己的 4–16 kHz 内容（99% 帧低于 −6.7 dB），静音里不加任何东西。
    voices.json 写 "deline": "supertonic3_comb.json"。

检查（成品 MP3、视频音轨各自独立测量，任何一项不合格就报错、不输出）：
  ① 梳状线自校准：在有声部分的长时频谱上，比较 2–16 kHz 所有 43.07 Hz 整数倍处（梳齿）与它们正中间（k+½，对照）的
    相对电平，最强 5 个的平均差 ≤ 1.0 dB。没有梳状电磁音的声音（用户确认过的中考男声 40 篇）是 0.2–0.6 dB，
    Supertonic 原始输出 2.3–3.6 dB，去除后 0.15 dB。
  ② 全频段兜底：2–16 kHz 任何窄带峰高出周围 ≤ 7.5 dB（防新的强频点）。标定：用户确认无电磁音的中考男声 40 篇
    中位 6.1、最高 7.1 dB；Kokoro 原来的电磁音 +11 dB 以上。
  （旧标准“全频段任何峰 ≤ 3 dB”会把这 40 篇用户确认过的音频全部判为不合格——那是语音本身的细节，不是电磁音。2026-10-15 改。）
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
COMB_MAX_DB = 1.0
FULL_MAX_DB = 7.5
MAX_DB = FULL_MAX_DB
COMB_BASE = 44100 / 1024


# ---------------------------------------------------------------- 测量
def _rel_spectrum(x, sr, items):
    from scipy.ndimage import median_filter
    from scipy.signal import welch
    sp = np.concatenate([x[int(s['start'] * sr): int(s['end'] * sr)] for s in items]).astype(np.float64)
    f, P = welch(sp, sr, nperseg=65536)
    r = 10 * np.log10(P + 1e-20)
    return f, r - median_filter(r, 61)


def scan(x, sr, items, lo=2000, hi=16000, top=12, floor=1.5):
    """返回 [(频率 Hz, 高出周围 dB)]，从强到弱。items：[{start, end}] 只看有声部分。"""
    f, r = _rel_spectrum(x, sr, items)
    m = (f >= lo) & (f <= min(hi, sr / 2 - 200))
    fm, rm = f[m], r[m]
    peaks = []
    for i in np.argsort(rm)[::-1]:
        if rm[i] < floor or len(peaks) >= top:
            break
        if all(abs(fm[i] - q) > 30 for q, _ in peaks):
            peaks.append((round(float(fm[i]), 1), round(float(rm[i]), 2)))
    return peaks


def comb_excess(x, sr, items, base=COMB_BASE, lo=2000, hi=16000, tol=1.5):
    """梳齿（k × base）与对照（(k+½) × base）处相对电平最强 5 个的平均差（dB）。"""
    f, r = _rel_spectrum(x, sr, items)
    K = np.arange(int(np.ceil(lo / base)), int(hi / base))
    on = np.array([r[(f > k * base - tol) & (f < k * base + tol)].max() for k in K])
    off = np.array([r[(f > (k + .5) * base - tol) & (f < (k + .5) * base + tol)].max() for k in K])
    return float(np.sort(on)[-5:].mean() - np.sort(off)[-5:].mean())


def check(x, sr, items):
    """返回 (最强频点 Hz, 高出 dB, 梳状线差 dB, 错误列表)。"""
    pk = scan(x, sr, items, top=1)
    f0, r = pk[0] if pk else (0.0, 0.0)
    c = comb_excess(x, sr, items)
    errs = []
    if c > COMB_MAX_DB:
        errs.append(f'电磁音：声码器帧频梳状线高出对照 {c:.2f} dB（上限 {COMB_MAX_DB} dB）')
    if r > FULL_MAX_DB:
        errs.append(f'电磁音：{f0:.0f} Hz 高出周围 {r:.1f} dB（上限 {FULL_MAX_DB} dB）')
    return f0, r, c, errs


# ---------------------------------------------------------------- 去除
def debuzz(x, sr, tones, bw=60.0):
    """Kokoro：只在给定的固定频点做 60 Hz 带宽的单向（因果）陷波；原本是 0 的采样保持 0。"""
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


def load_comb(name):
    d = json.loads((HERE / name).read_text('utf-8'))
    return int(d['period']), np.array(d['harmonics'], np.float64)


def segment_lines(x, sr, period, lo=2000, hi=16000, thr_db=4.0, nper=16384):
    """这一段里另外突出的梳齿（k × sr/period，k 可以是奇数）：段内 Welch 平均谱（方差小，偶然超过门限的概率约 0.3%）
    在梳齿处比周围（±40 Hz、避开所有梳齿 ±3 Hz）中位数高出 thr_db 的。"""
    from scipy.signal import welch
    if len(x) < nper * 2:
        return []
    f, P = welch(x.astype(np.float64), sr, nperseg=nper)
    base = sr / period
    off = np.abs(((f / base + 0.5) % 1) - 0.5) * base > 3.0
    out = []
    for k in range(int(np.ceil(lo / base)), int(hi / base) + 1):
        near = (f > k * base - 40) & (f < k * base + 40)
        ref = np.median(P[near & off])
        pk = P[(f > k * base - 1.5) & (f < k * base + 1.5)].max()
        if pk > ref * 10 ** (thr_db / 10):
            out.append(k)
    return out


def deline(x, sr, comb, gate_db=35.0, frame=512, ramp=220, chunk=65536, adaptive=True):
    """Supertonic：在一个原始合成片段上减掉帧频梳状线（见文件开头）。x 必须是模型原样输出（44.1 kHz，未裁剪）。
    去掉的线 = 固定清单 ∪ 这一段里另外突出的梳齿（segment_lines）。"""
    from scipy.signal import butter, sosfiltfilt
    period, H = comb
    if adaptive:
        H = np.array(sorted(set(H.astype(int).tolist()) | set(segment_lines(x, sr, period))), np.float64)
    if sr != 44100:
        raise ValueError(f'deline 只能用在 Supertonic 原始输出（44100 Hz）上，收到 {sr} Hz')
    x = x.astype(np.float64)
    n = len(x)
    if n < frame * 4:
        return x.astype(np.float32)
    m = n // frame * frame

    def rms(y):
        e = np.sqrt((y[:m].reshape(-1, frame) ** 2).mean(1))
        return np.r_[e, e[-1:]]
    e = rms(x)
    on = 20 * np.log10(e + 1e-12) > 20 * np.log10(e.max() + 1e-12) - gate_db
    eh = rms(sosfiltfilt(butter(6, [4000, 16000], 'bp', fs=sr, output='sos'), x))
    if not on.any() or eh[on].mean() <= 0:
        return x.astype(np.float32)
    w = np.repeat(on * eh / eh[on].mean(), frame)[:n]
    w = np.r_[w, np.full(n - len(w), w[-1])]
    k = np.hanning(2 * ramp + 1)
    w = np.convolve(w, k / k.sum(), 'same')
    # 最小二乘：分块累加正规方程，内存与片段长度无关
    A = np.zeros((2 * len(H), 2 * len(H)))
    b = np.zeros(2 * len(H))
    for s in range(0, n, chunk):
        t = np.arange(s, min(n, s + chunk))
        ph = 2 * np.pi * np.outer(t, H) / period
        M = np.concatenate([np.cos(ph), np.sin(ph)], 1) * w[t, None]
        A += M.T @ M
        b += M.T @ x[t]
    c = np.linalg.solve(A + 1e-9 * np.eye(len(A)) * np.trace(A) / len(A), b)
    y = x.copy()
    for s in range(0, n, chunk):
        t = np.arange(s, min(n, s + chunk))
        ph = 2 * np.pi * np.outer(t, H) / period
        y[t] -= (np.concatenate([np.cos(ph), np.sin(ph)], 1) * w[t, None]) @ c
    return y.astype(np.float32)
