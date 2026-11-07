"""讲解配音的语速与语调检查（用户 2026-11-03：“语速太慢”“语气像哄小学生”——要成熟、自然、稍快）。

目标取自用户本人的讲课录音，录音和成品用**同一种量法**（不看稿子、不看 timings，独立量）：
  按停顿切句（挑参考.utterances，停顿 ≥ 0.25 秒）→ 每句 ≥ 1 秒的用 SenseVoice 识别，数汉字 + 英文词 → 语速 = 总字数 / 总时长（字 / 秒）；
  每句的音高起伏 = 浊音帧基频的标准差（半音，librosa.pyin）。
判据：成品语速 ≥ 录音语速 × RATE_MIN_RATIO；成品各句音高起伏的中位数 ≤ 录音各句的 75% 分位（“哄小孩”的语气是音高大起大落）。
用法：/opt/ttsenv/bin/python 语速语调.py --录音 05.wav               # 量录音，写目标 tts/音色/用户本人_语速.json
      /opt/ttsenv/bin/python 语速语调.py 成品.mp3 [成品2.mp3 …]       # 量成品、对照目标，有一处不合格退出码 1
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [str(Path(__file__).parent)]
TARGET = Path(__file__).resolve().parents[1] / 'tts/音色/用户本人_语速.json'
RATE_MIN_RATIO = 1.0


def measure(x, sr, asr=None):
    """x：单声道音频。返回 {rate, f0sd_median, n, dur, tokens, per: [...]}。"""
    import soxr
    import 挑参考 as PR
    if sr != PR.SR:
        x = soxr.resample(x, sr, PR.SR, quality='VHQ').astype(np.float32)
    asr = asr or PR.ASR()
    spans, _, _ = PR.utterances(x)
    per, T, N = [], 0.0, 0
    for s, e in spans:
        d = (e - s) / PR.SR
        if d < 1.0:
            continue
        y = x[s:e]
        text, _ = asr(y)
        n = len(re.findall(r'[一-鿿]|[A-Za-z]+', text))
        if not n:
            continue
        _, sd = PR.f0_median(y)
        per.append({'t': round(s / PR.SR, 2), 'dur': round(d, 2), 'n': n, 'rate': round(n / d, 2),
                    'f0sd': None if sd is None else round(sd, 2), 'text': text})
        T += d
        N += n
    sds = [p['f0sd'] for p in per if p['f0sd'] is not None]
    return {'rate': round(N / T, 3) if T else 0.0, 'f0sd_median': round(float(np.median(sds)), 2) if sds else None,
            'f0sd_p75': round(float(np.percentile(sds, 75)), 2) if sds else None, 'n': len(per), 'dur': round(T, 1),
            'tokens': N, 'per': per}


def problems(m, tgt):
    errs = []
    lo = tgt['rate'] * RATE_MIN_RATIO
    if m['rate'] < lo:
        errs.append(f"语速太慢：{m['rate']:.2f} 字/秒（用户录音 {tgt['rate']:.2f}，下限 {lo:.2f}）")
    if m['f0sd_median'] is None or m['f0sd_median'] > tgt['f0sd_p75']:
        errs.append(f"音高起伏太大：各句中位 {m['f0sd_median']} 半音（用户录音 75% 分位 {tgt['f0sd_p75']}）")
    return errs


def check_file(p, asr=None):
    import soundfile as sf
    a, sr = sf.read(str(p), dtype='float32')
    m = measure(a if a.ndim == 1 else a.mean(1), sr, asr)
    return m, problems(m, json.loads(TARGET.read_text('utf-8')))


def main():
    if '--录音' in sys.argv:
        import 挑参考 as PR
        src = Path(sys.argv[sys.argv.index('--录音') + 1])
        m = measure(PR.decode(src), PR.SR)
        out = {'说明': '用户本人讲课录音（Release user-voice）的语速与音高起伏，语速语调.py 量（与成品同一种量法）。',
               'source': src.name, **{k: v for k, v in m.items() if k != 'per'},
               'rate_p25_p50_p75': [round(float(np.percentile([p['rate'] for p in m['per']], q)), 2) for q in (25, 50, 75)]}
        TARGET.write_text(json.dumps(out, ensure_ascii=False, indent=1), 'utf-8')
        print(json.dumps({k: v for k, v in out.items() if k != '说明'}, ensure_ascii=False))
        return
    import 挑参考 as PR
    asr, bad = PR.ASR(), 0
    for p in sys.argv[1:]:
        m, e = check_file(p, asr)
        print(f"{Path(p).name}：语速 {m['rate']:.2f} 字/秒，音高起伏中位 {m['f0sd_median']} 半音（{m['n']} 句 {m['dur']} 秒）"
              + ('' if not e else '  ✗ ' + '；'.join(e)))
        bad += bool(e)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
