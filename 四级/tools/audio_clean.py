"""去除电磁音（铁律，用户 2026-10-08）。

来源：语音模型 Kokoro 的声码器在朗读时会叠加一组固定频率的窄带音（4800 Hz、9600 Hz 等，4.5–11.5 kHz 一带最多），
男声高频能量低，这些音盖不住，听起来就是“电磁音”。它们在每篇里频率都一样，不是语音本身的成分。
做法：整篇合成后、压缩之前，测出长时频谱里比周围（±22 Hz 中值）高 3 dB 以上的窄峰，逐个用极窄的陷波器（带宽 4 Hz）一次去掉；
只动这些频点，整体能量变化约 0.01 dB，其余音质不变。
检查：对 MP3 成品和视频音轨独立测量有声部分，1.5–11.9 kHz 内任何窄峰高出周围超过 MAX_TONE_DB 就报错、不输出。
"""
import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import filtfilt, iirnotch, welch

LO, HI = 1500, 11900       # 模型输出 24 kHz 采样，12 kHz 以上没有内容
CUT_DB = 3.0               # 高出周围 3 dB 以上的窄峰全部陷掉
BW = 4.0                   # 陷波带宽（Hz）
MAX_TONE_DB = 6.0          # 成品检查上限（处理前最强的 9600 Hz 约 +11～+13 dB）


def tones(x, sr, thr=CUT_DB):
    f, P = welch(x.astype(np.float64), sr, nperseg=65536)
    db = 10 * np.log10(P + 1e-20)
    r = db - median_filter(db, 61)
    return [(float(f[i]), float(r[i])) for i in range(1, len(f) - 1)
            if LO < f[i] < HI and r[i] > thr and r[i] >= r[i - 1] and r[i] >= r[i + 1]]


def dehum(x, sr):
    """一次性检测并陷掉窄带音（不迭代：陷波后两侧会显得“凸起”，迭代会越陷越多）。"""
    y = x.astype(np.float64)
    for f0, _ in tones(x, sr):
        b, a = iirnotch(f0, f0 / BW, sr)
        y = filtfilt(b, a, y)
    # 陷波器有很长的余振，会把一点点信号（约 −58 dB）带进原本完全无声的片头和句间停顿；原来是 0 的地方恢复为 0（铁律：停顿必须无声）
    y[x == 0] = 0
    return y.astype(np.float32)


def speech(x, sr, items):
    return np.concatenate([x[int(s['start'] * sr): int(s['end'] * sr)] for s in items])


def check(x, sr, items):
    """返回 (最强窄峰频率, 高出 dB, 错误列表)。"""
    t = tones(speech(x, sr, items), sr, thr=0)
    f0, r = max(t, key=lambda z: z[1]) if t else (0.0, 0.0)
    errs = [f'电磁音：{f0:.0f} Hz 窄带音高出周围 {r:.1f} dB（上限 {MAX_TONE_DB} dB）'] if r > MAX_TONE_DB else []
    return f0, r, errs
