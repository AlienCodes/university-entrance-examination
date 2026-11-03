"""提速版有没有音质损伤（交接第 3 轮：“不用变速拉伸硬提速，要用先证明无音质损伤”）。对同一次选段的 原速 / 提速 两个成品，
在成品音频上逐小段独立量（不看合成时的分数）：
  ① 识别错词：中文段 SenseVoice（按拼音比，同音字不算），英文段 parakeet（只比单词）——提速版总错数 ≤ 原速；
  ② 说话人相似度（3D-Speaker，跟录音里没用作参考的 6 段真人比）——相差 ≤ 0.01；
  ③ UTMOS 自然度（每 10 秒一窗取平均）——提速版 ≥ 原速 − 0.10。
有一项不过退出码 1。用法：/opt/ttsenv/bin/python 提速验证.py --录音 05.wav 原速.mp3 提速.mp3
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [str(Path(__file__).parent)]


def measure(p, ears, spk, held):
    import soundfile as sf
    import soxr
    import 选型评测 as E
    import 选段 as XD
    y, sr = sf.read(str(p), dtype='float32')
    y = y.mean(1) if y.ndim > 1 else y
    tm = json.loads(Path(p).with_suffix('.timings.json').read_text('utf-8'))
    errs = 0
    for it in tm['items']:
        for u in it['units']:
            a16 = soxr.resample(y[int(u['start'] * sr):int(u['end'] * sr)], sr, 16000).astype(np.float32)
            if re.search(r'[一-鿿]', u['text']):
                errs += E.ed(XD.pinyin_toks(u['text']), XD.pinyin_toks(ears.rec(ears.sv, a16)))
            else:
                errs += E.ed(E.toks(u['text']), E.toks(ears.rec(ears.en, a16)))
    body = y[int(1.5 * sr):len(y) - int(2.0 * sr)]
    sim = float(np.mean([spk(body, sr) @ h for h in held]))
    b16 = soxr.resample(body, sr, 16000).astype(np.float32)
    mos = float(np.mean([ears.utmos(b16[i:i + 160000]) for i in range(0, max(1, len(b16) - 160000), 160000)]))
    return {'errs': errs, 'sim': round(sim, 3), 'utmos': round(mos, 2), 'dur': round(len(y) / sr, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--录音', required=True)
    ap.add_argument('原速')
    ap.add_argument('提速')
    a = ap.parse_args()
    import soundfile as sf
    import 选型评测 as E
    import 像不像 as XB
    ears, spk = E.Ears(), XB.Spk()
    x, sr = sf.read(a.录音, dtype='float32')
    x = x.mean(1) if x.ndim > 1 else x
    dur = len(x) / sr
    held = [spk(x[int(t * sr):int((t + 10) * sr)], sr) for t in np.linspace(60, dur - 70, 7)]
    r0, r1 = measure(a.原速, ears, spk, held), measure(a.提速, ears, spk, held)
    bad = []
    if r1['errs'] > r0['errs']:
        bad.append(f"识别错词变多 {r0['errs']} → {r1['errs']}")
    if abs(r1['sim'] - r0['sim']) > 0.01:
        bad.append(f"相似度变了 {r0['sim']} → {r1['sim']}")
    if r1['utmos'] < r0['utmos'] - 0.10:
        bad.append(f"自然度下降 {r0['utmos']} → {r1['utmos']}")
    print(f"原速 {r0}\n提速 {r1}\n提速验证：{'通过' if not bad else '不通过：' + '；'.join(bad)}")
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
