"""独立的响度一致性检查（K 加权瞬时响度，400ms 窗口，ITU-R BS.1770）。
只统计有声窗口：去掉比整体响度低 20 LU 以下的窗口（停顿）。"""
import sys
import numpy as np
import pyloudnorm as pyln
import soundfile as sf


def momentary(path):
    a, sr = sf.read(path, dtype='float64')
    m = pyln.Meter(sr, block_size=0.4)
    filt = a.copy()
    for f in m._filters.values():
        filt = f.apply_filter(filt)
    w, h = int(0.4 * sr), int(0.1 * sr)
    vals = np.array([-0.691 + 10 * np.log10(np.mean(filt[i:i + w] ** 2) + 1e-12) for i in range(0, len(filt) - w, h)])
    gate = m.integrated_loudness(a) - 20
    return vals[vals > gate], m.integrated_loudness(a)


if __name__ == '__main__':
    for p in sys.argv[1:]:
        v, il = momentary(p)
        print(f'{p.split("/")[-2] if "/" in p else p:>8}  整体 {il:6.2f} LUFS  有声窗口标准差 {v.std():.2f} LU  '
              f'5%–95% 区间 {np.percentile(v, 95) - np.percentile(v, 5):.2f} LU')
