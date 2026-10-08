"""去电磁音（候选方案，用户看样片确认前不得用于成品）。

电磁音来源：语音模型声码器在朗读时叠加的固定频率细音。统计 46 篇成品：下列 10 个频点在每一篇都出现，
且高出周围 5 dB 以上（最强 9600 Hz，约 +12 dB）。
上一次失败的教训（极窄陷波，电磁音反而更重）：带宽 4 Hz 的陷波余振约 80 毫秒，又用了双向滤波，字头之前也出现细音，
而且一次陷了 65 个频点。本方案：只处理这 10 个固定频点；每个带宽 60 Hz（余振约 5 毫秒，被语音本身掩盖）；
单向（因果）滤波，字头之前不会出现任何东西。原本无声处保持无声。
"""
import numpy as np
from scipy.signal import iirnotch, lfilter

TONES = [4800, 5900, 7670, 8260, 8960, 9600, 10420, 10760, 10980]      # 8220/8300 两个相邻频点合为 8260（带宽加宽）
BW = {8260: 140}
DEFAULT_BW = 60.0


def debuzz(x, sr):
    y = x.astype(np.float64)
    for f0 in TONES:
        b, a = iirnotch(f0, f0 / BW.get(f0, DEFAULT_BW), sr)
        y = lfilter(b, a, y)
    y = y.astype(np.float32)
    y[x == 0] = 0
    return y
