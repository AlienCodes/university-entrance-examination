"""去呼吸声（踩坑 89；任何声音、任何模型都用这一份）。

用户 2026-10-30：“不要间隙有那么大的呼吸声。”实测（Qwen3-TTS 男老师原始合成）：换气是停顿里一个孤立的鼓包——
没有周期性（不是浊音）、比本段最响处低 25—50 dB、长 0.2—0.5 秒，两头有深谷与词隔开；之后的段内电平统一、意群统一
还会把它抬高（旧样音 A 成品里到了 −22 dBFS）。词首、词尾的清辅音（s、x、h、f、t）总是和元音连在一起、中间没有深谷，
所以按“含浊音的连续段 = 词核”保留，不会切到辅音（踩坑 27；识别比对证明：旧样音 A 30 段次识别结果去呼吸前后完全相同）。

  debreath(x, sr)      处理（任何电平处理之前）：词核（相对本段最响帧 −40 dB 以上的连续帧，含浊音帧或峰值 > −18 dB）
                       两头各多留 30 ms，其余（停顿里的换气、底噪）换成真静音，边界 5 ms 渐变。量法：自相关周期性、相对电平。
  breath_check(a, sr)  检查（成品上独立量，量法不同，踩坑 2）：绝对电平（dBFS）+ YIN 判浊音；长 ≥ 0.1 秒、峰值 > −60 dBFS、
                       比最响处低 8 dB 以上、没有浊音、3 kHz 以上能量占比 < 0.5（不是擦音）、400 Hz 以下 < 0.05（不带嗓音）、两头被 −60 dBFS 以下隔开的孤岛就算一处呼吸。空表 = 合格。
双向验证：python3 tools/防复发/验证/呼吸声.py
用法：python3 去呼吸.py 音频…   # 列出每个文件的呼吸处
"""
import sys

import numpy as np

CORE_FLOOR = -40     # 处理：词核 = 相对本段最响帧 −40 dB 以上的连续帧，且含浊音帧（或峰值 > CORE_LOUD，响的清辅音串）
CORE_LOUD = -18
VOICED = 0.5         # 自相关周期性
MARGIN = 0.03        # 词核两头多留（秒），再 5 ms 淡出淡入
CHK_FLOOR = -60.0    # 检查：dBFS
CHK_MIN = 0.10       # 检查：秒
BLOCK = 2000         # 分块帧数
HF_CONS = 0.5        # 孤岛 3 kHz 以上能量占比 ≥ 此值 = 清辅音（塞音成阻后的 -ts、-s 尾音等），不是换气：处理不切、检查不报
                     # 实测：旧样音 A 的 17 处换气占比 0.04—0.31；s、x 等擦音 0.78—0.82


LF_VOICE = 0.05      # 孤岛 400 Hz 以下能量占比 ≥ 此值 = 带嗓音的尾音（鼻音、弱化元音，周期性没量出来），不是换气
                     # 实测：旧样音 A 的换气 0.00—0.02；四六级等已发布成品里被旧规则报出的孤岛 10% 分位 0.07、中位 0.12


def bands(y, sr):
    """(3 kHz 以上能量占比, 400 Hz 以下能量占比)。"""
    y = np.asarray(y, np.float64)
    if len(y) < 16:
        return 0.0, 1.0
    S = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2
    f = np.fft.rfftfreq(len(y), 1 / sr)
    tot = S.sum() + 1e-30
    return float(S[f > 3000].sum() / tot), float(S[f < 400].sum() / tot)


def breath_like(y, sr):
    """换气的频谱：既不是擦音（高频为主），也不带嗓音（低频几乎没有）。"""
    hf, lf = bands(y, sr)
    return hf < HF_CONS and lf < LF_VOICE


def _frames(x, sr, hop=0.01, win=0.03):
    H, W = int(hop * sr), int(win * sr)
    n = max(0, (len(x) - W) // H + 1)
    if n == 0:
        return np.zeros(0), np.zeros(0), H, W
    lvl, per = np.empty(n), np.empty(n)
    for b0 in range(0, n, BLOCK):                    # 分块算（逐帧独立，结果与一次算完相同；长音频不爆内存）
        b1 = min(n, b0 + BLOCK)
        idx = np.arange(W)[None, :] + H * np.arange(b0, b1)[:, None]
        f = x[idx].astype(np.float64)
        lvl[b0:b1] = 10 * np.log10(np.mean(f ** 2, 1) + 1e-20)
        g = f - f.mean(1, keepdims=True)
        ac = np.fft.irfft(np.abs(np.fft.rfft(g, 2 * W)) ** 2)[:, :W]
        ac = ac / (ac[:, :1] + 1e-20)
        per[b0:b1] = ac[:, int(sr / 400):int(sr / 60)].max(1)
    return lvl, per, H, W


def cores(x, sr):
    """处理端：要保留的词核掩码（逐样本 bool）与去掉的部分 [(起秒, 止秒, 峰值相对 dB)]（只列峰值高于 −60 的）。"""
    lvl, per, H, W = _frames(x, sr)
    keep = np.zeros(len(x), bool)
    if not len(lvl):
        return keep, []
    ref = np.percentile(lvl, 99)
    act = lvl > ref + CORE_FLOOR
    m = int(MARGIN * sr)
    i, n = 0, len(lvl)
    while i < n:
        if not act[i]:
            i += 1
            continue
        j = i
        while j < n and act[j]:
            j += 1
        if (per[i:j] > VOICED).any() or lvl[i:j].max() > ref + CORE_LOUD or not breath_like(x[i * H:(j - 1) * H + W], sr):
            keep[max(0, i * H - m):min(len(x), (j - 1) * H + W + m)] = True
        i = j
    gone, i = [], 0
    while i < n:
        s = i * H
        if keep[min(s + W // 2, len(x) - 1)] or lvl[i] < ref - 60:
            i += 1
            continue
        j = i
        while j < n and not keep[min(j * H + W // 2, len(x) - 1)] and lvl[j] >= ref - 60:
            j += 1
        if j - i >= 5:
            gone.append((round(i * H / sr, 2), round(((j - 1) * H + W) / sr, 2), round(float(lvl[i:j].max() - ref), 1)))
        i = j
    return keep, gone


def debreath(x, sr):
    """返回 (处理后的音频, 去掉的部分)。词核以外（停顿里的换气、底噪）一律换成真静音，边界 5 ms 淡出淡入。"""
    y = np.array(x, dtype=np.float32, copy=True)
    keep, gone = cores(y, sr)
    g = keep.astype(np.float32)
    fd = int(0.005 * sr)
    if fd > 1:
        g = np.convolve(g, np.ones(fd, np.float32) / fd, mode='same')
        g = np.minimum(g, 1.0)
    return y * g, gone


def breath_check(a, sr):
    """成品检查：返回 [(起秒, 止秒, 峰值 dBFS)]，空表 = 合格。量法与 debreath 独立：绝对电平 + 倒谱判浊音。"""
    a = np.asarray(a, dtype=np.float64)
    if a.ndim > 1:
        a = a.mean(1)
    H, W = int(0.01 * sr), int(0.04 * sr)
    n = max(0, (len(a) - W) // H + 1)
    if n == 0:
        return []
    q0, q1 = int(sr / 400), int(sr / 70)
    lvl, voiced = np.empty(n), np.empty(n, bool)
    for b0 in range(0, n, BLOCK):
        b1 = min(n, b0 + BLOCK)
        fr = a[np.arange(W)[None, :] + H * np.arange(b0, b1)[:, None]]
        lvl[b0:b1] = 10 * np.log10(np.mean(fr ** 2, 1) + 1e-20)
        # 浊音：YIN 累积均值归一化差分函数（与处理端的自相关峰不同的算法），70—400 Hz 内最小值 < 0.35
        g = fr - fr.mean(1, keepdims=True)
        ac = np.fft.irfft(np.abs(np.fft.rfft(g, 2 * W)) ** 2)[:, :W // 2]
        d = 2 * (ac[:, :1] - ac)
        d[:, 0] = 0
        cm = d[:, 1:] * np.arange(1, d.shape[1]) / (np.cumsum(d[:, 1:], 1) + 1e-20)
        voiced[b0:b1] = cm[:, q0 - 1:q1 - 1].min(1) < 0.35
    ref = np.percentile(lvl, 99)
    act = lvl > CHK_FLOOR
    out, i = [], 0
    while i < n:
        if not act[i]:
            i += 1
            continue
        j = i
        while j < n and act[j]:
            j += 1
        if ((j - i) * H / sr >= CHK_MIN and not voiced[i:j].any() and lvl[i:j].max() < ref - 8
                and breath_like(a[i * H:(j - 1) * H + W], sr)):
            out.append((round(i * H / sr, 2), round(((j - 1) * H + W) / sr, 2), round(float(lvl[i:j].max()), 1)))
        i = j
    return out


def _load(p):
    import soundfile as sf
    x, sr = sf.read(str(p), dtype='float32')
    return (x.mean(1) if x.ndim > 1 else x), sr


def main():
    for p in sys.argv[1:]:
        x, sr = _load(p)
        r = breath_check(x, sr)
        print(p, f'呼吸 {len(r)} 处', r[:10])


if __name__ == '__main__':
    main()
