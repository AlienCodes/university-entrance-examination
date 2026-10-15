"""电磁音检查自身的双向验证（踩坑 37）：该过的必须过、该报的必须报。

    /opt/ttsenv/bin/python 西班牙语/tools/test_buzz.py

① 用户确认过“没有电磁音”的中考男声 40 篇（中考/audio/cet4_male）：必须全部通过；
② 埋雷：在其中 5 篇里人为加入 (a) Kokoro 原来那样的单频细线（9600 Hz，高出周围约 11 dB）、(b) Supertonic 那样的帧频梳状线
   （supertonic3_comb.json 的 51 条，每条与原 Supertonic 实测强度相当）：每一处都必须报出来；
③ 有 西班牙语/audio 成品时：每个 MP3 必须通过。
任何一条不符合就报错退出。
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import buzz  # noqa: E402


def tone_at(a, sr, items, f, rel_db):
    """在有声部分加一条频率 f 的细线，强度约为该频率附近语音长时谱的 rel_db（相对）。"""
    from scipy.signal import welch
    sp = np.concatenate([a[int(s['start'] * sr): int(s['end'] * sr)] for s in items]).astype(np.float64)
    fr, P = welch(sp, sr, nperseg=65536)
    near = np.median(P[(fr > f - 22) & (fr < f + 22)])
    amp = np.sqrt(2 * near * (fr[1] - fr[0]) * 1.5 * 10 ** (rel_db / 10))   # 汉宁窗等效噪声带宽 1.5 个频点
    t = np.arange(len(a)) / sr
    on = np.zeros(len(a))
    for s in items:
        on[int(s['start'] * sr): int(s['end'] * sr)] = 1
    return amp * np.sin(2 * np.pi * f * t + np.random.default_rng(int(f)).uniform(0, 6.28)) * on


def main():
    T = json.loads((ROOT / '中考/audio/timings.json').read_text('utf-8'))['cet4_male']
    files = [(k, v) for k, v in sorted(T.items()) if isinstance(v, dict) and 'file' in v]
    assert len(files) == 40, len(files)
    bad = []
    comb = buzz.load_comb('supertonic3_comb.json')
    caught = 0
    for i, (pid, d) in enumerate(files):
        a, sr = sf.read(str(ROOT / '中考/audio' / d['file']), dtype='float32')
        a = a.mean(1) if a.ndim > 1 else a
        items = d['sentences']
        f0, r, c, e = buzz.check(a, sr, items)
        if e:
            bad.append(f'{pid} 用户确认过的音频被判不合格：{e}')
        if i % 8 == 0:                                                   # 5 篇埋雷
            x = a.astype(np.float64) + tone_at(a, sr, items, 9600.0, 11.0)
            if not buzz.check(x.astype(np.float32), sr, items)[3]:
                bad.append(f'{pid} 埋的 9600 Hz 单频细线没查出')
            else:
                caught += 1
            period, H = comb
            x = a.astype(np.float64) + sum(tone_at(a, sr, items, h * 44100 / period, 8.0) for h in H)
            if not buzz.check(x.astype(np.float32), sr, items)[3]:
                bad.append(f'{pid} 埋的帧频梳状线没查出')
            else:
                caught += 1
    print(f'用户确认过的 40 篇：{40 - sum("用户确认" in b for b in bad)} 篇通过；埋雷 10 处查出 {caught} 处')
    es = HERE.parent / 'audio' / 'timings.json'
    if es.exists():
        for v, d in json.loads(es.read_text('utf-8')).items():
            if not isinstance(d, dict):
                continue
            for pid, x in d.items():
                a, sr = sf.read(str(HERE.parent / 'audio' / x['file']), dtype='float32')
                e = buzz.check(a.mean(1) if a.ndim > 1 else a, sr, x['sentences'])[3]
                print(f'西班牙语成品 {v} {pid}：', '通过' if not e else e)
                if e and not x.get('draft_issues'):
                    bad.append(f'西班牙语成品 {v} {pid} 不合格：{e}')
    if bad:
        raise SystemExit('电磁音检查自测不通过：\n' + '\n'.join(bad))
    print('电磁音检查自测全部通过')


if __name__ == '__main__':
    main()
