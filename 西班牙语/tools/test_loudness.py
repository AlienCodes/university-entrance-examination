"""响度检查（loudness.py）自身的双向验证（踩坑 37）：该过的必须过、该报的必须报。只用合成信号，不需要任何音频文件。

    python 西班牙语/tools/test_loudness.py

“朗读”用平稳的带限噪声（200–5000 Hz）代替（每句同一电平，削顶到 −1.5 dBFS），时间轴和成品一样：片头 1.5 秒、句间 0.8 秒、逗号 0.28 秒、结尾 2 秒，整体 −16 LUFS。
① 该过：理想朗读的 2 句短文（约 12 秒）、6 句短文、30 句长文，loudness.measure 必须全部通过；
   同时确认：连片头片尾静音一起算（整段算法）时，短文的短时波动被明显抬高（2 句短文多出 ≥ 0.15 LU），长文几乎不变（< 0.05 LU）
   ——片头片尾的静音量的是文章长短，不是朗读响度，这正是改测量范围的原因。
② 该报（埋雷）：
   a. 一句轻 3 dB（句间偏差）；
   b. 长句里每 3 秒忽大忽小 ±2 dB（短时波动，各句平均电平相同）；
   c. 整体 −18 LUFS（整体响度）；
   d. 一处尖峰到 −0.3 dBFS（峰值）；
   e. 朗读部分只有 3 秒（测不了短时波动，必须报错，不能静默通过）。
   每一处都必须报出对应的那一项。任何一条不符合就报错退出。
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import loudness  # noqa: E402

SR = 48000
RNG = np.random.default_rng(20261015)


def noise(n):
    f = np.fft.rfft(RNG.standard_normal(n))
    fr = np.fft.rfftfreq(n, 1 / SR)
    f[(fr < 200) | (fr > 5000)] = 0
    return np.fft.irfft(f, n)


def article(sents, gain_db=None, wobble_db=0.0, lufs=-16.0):
    """sents：[(句长秒, [逗号位置秒…]), …]。返回 (整段音频, items)。"""
    import pyloudnorm as pyln
    parts, items, t = [np.zeros(int(1.5 * SR))], [], 1.5
    for i, (dur, commas) in enumerate(sents):
        st = t
        cuts = [0.0] + list(commas) + [dur]
        for j in range(len(cuts) - 1):
            n = int((cuts[j + 1] - cuts[j]) * SR)
            x = noise(n)
            x = x / np.sqrt(np.mean(x ** 2)) * 0.1
            if gain_db and i in gain_db:
                x *= 10 ** (gain_db[i] / 20)
            if wobble_db:
                tt = np.arange(n) / SR + (t - st)
                x *= 10 ** (wobble_db * np.sign(np.sin(2 * np.pi * tt / 6.0)) / 20)
            parts.append(x)
            t += n / SR
            if j < len(cuts) - 2:
                parts.append(np.zeros(int(0.28 * SR)))
                t += 0.28
        items.append({'start': round(st, 3), 'end': round(t, 3)})
        g = 2.0 if i == len(sents) - 1 else 0.8
        parts.append(np.zeros(int(g * SR)))
        t += g
    a = np.concatenate(parts)
    m = pyln.Meter(SR)
    for _ in range(3):
        a *= 10 ** ((lufs - m.integrated_loudness(a)) / 20)
        a = np.clip(a, -10 ** (-1.5 / 20), 10 ** (-1.5 / 20))
    return a, items


def main():
    bad = []
    short2 = [(3.0, []), (4.9, [1.0])]
    six = [(3.5, []), (4.2, []), (3.8, [1.4]), (3.9, []), (4.4, [1.0]), (1.6, [])]
    long30 = [(4.0 + (i % 5) * 0.7, [1.6] if i % 3 == 0 else []) for i in range(30)]

    edge = {}
    for name, s in [('2 句短文', short2), ('6 句短文', six), ('30 句长文', long30)]:
        a, items = article(s)
        rep, errs = loudness.measure(a, SR, items)
        print(f'① {name}：短时波动 {rep["short_term_std_lu"]} LU（整段算法 {rep["short_term_std_whole_lu"]} LU），'
              f'整体 {rep["integrated_lufs"]} LUFS，句间偏差 {rep["sentence_max_dev_lu"]} LU', '通过' if not errs else errs)
        if errs:
            bad.append(f'理想朗读（{name}）被判不合格：{errs}')
        edge[name] = rep['short_term_std_whole_lu'] - rep['short_term_std_lu']
    print(f'   片头片尾静音给短时波动带来的额外数值：2 句短文 +{edge["2 句短文"]:.2f} LU，30 句长文 +{edge["30 句长文"]:.2f} LU')
    if not (edge['2 句短文'] >= 0.15 and edge['30 句长文'] < 0.05):
        bad.append('片头片尾静音的影响没有随文章变短而明显变大：改测量范围的理由不成立，请重新核对')

    planted = [
        ('a 一句轻 3 dB', article(six, gain_db={2: -3.0}), '句间响度偏差'),
        ('b 每 3 秒忽大忽小 ±2 dB', article([(9.0, [4.5])] * 4, wobble_db=2.0), '短时响度波动'),
        ('c 整体 −18 LUFS', article(six, lufs=-18.0), '整体响度'),
        ('e 朗读部分只有 3 秒', article([(3.0, [])]), '测不了'),
    ]
    a, items = article(six)
    a = a.copy()
    k = int((items[1]['start'] + 0.5) * SR)
    a[k] = 10 ** (-0.3 / 20)
    planted.insert(3, ('d 尖峰 −0.3 dBFS', (a, items), '峰值'))
    caught = 0
    for name, (a, items), key in planted:
        rep, errs = loudness.measure(a, SR, items)
        hit = any(key in e for e in errs)
        caught += hit
        print(f'② {name}：', '查出' if hit else '没查出', errs)
        if not hit:
            bad.append(f'埋雷「{name}」没查出（应报「{key}」）')
    print(f'埋雷 {len(planted)} 处，查出 {caught} 处')
    if bad:
        raise SystemExit('响度检查自测不通过：\n' + '\n'.join(bad))
    print('响度检查自测全部通过')


if __name__ == '__main__':
    main()
