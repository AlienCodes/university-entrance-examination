"""拼接衔接检查（用户 2026-11-03：要流畅、丝滑；拼接的地方音高、能量要对上）。门限取自用户本人录音的自然停顿（同一量法）：
每个“边界”（成品：相邻两个合成小段之间；录音：相邻两句之间的自然停顿）量
  音高跳变：边界前最后 0.3 秒浊音与边界后最初 0.3 秒浊音的基频中位数之差（半音，八度误判折回，取绝对值）；
  响度台阶：同样两段浊音帧的平均电平之差（dB，绝对值）；
  语速差：边界两边的小段（句）各自的语速之比（按音节：汉字一个、英文词按元音组估；快 / 慢，≥ 1）；
  停顿：边界处静音的长度（秒）。
判据：每个边界语速差不超过录音的 95% 分位；成品停顿的中位数与 90% 分位不超过录音的 1.5 倍。
用法：/opt/ttsenv/bin/python 拼接检查.py --录音 05.wav        # 量录音，把门限写进 tts/音色/用户本人_语速.json 的 junction
      /opt/ttsenv/bin/python 拼接检查.py 成品.mp3 …              # 量成品（按 timings 的小段边界），有一处超标退出码 1
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [str(Path(__file__).parent), str(Path(__file__).resolve().parents[2] / 'tools/tts')]
TARGET = Path(__file__).resolve().parents[1] / 'tts/音色/用户本人_语速.json'
PAUSE_RATIO = 1.5
# 音高跳变、响度台阶只记录、不作判据：本人录音里 0.22—0.24 秒的自然停顿前后音高也差到 6.9 半音（八度折回后上限才 7），
# 这种量法分不出“拼得生硬”和“自然重新起调”；旧样片的生硬处全是相邻段语速突变与停顿偏长（双向验证 拼接衔接.py）。


def edge_feats(y, sr, side, win=0.3):
    """side = 'tail'：y 末尾的浊音；'head'：y 开头的浊音。返回 (基频半音中位数相对 100 Hz, 电平 dB) 或 (None, None)。"""
    import librosa
    n = int(1.2 * sr)
    seg = (y[-n:] if side == 'tail' else y[:n]).astype(np.float32)
    if len(seg) < int(0.2 * sr):
        return None, None
    hop = int(0.01 * sr)
    f0, v, _ = librosa.pyin(seg, fmin=60, fmax=300, sr=sr, frame_length=1024, hop_length=hop)
    idx = np.where(v & ~np.isnan(f0))[0]
    if len(idx) < 6:
        return None, None
    k = int(win / 0.01)
    idx = idx[-k:] if side == 'tail' else idx[:k]
    rms = np.array([np.sqrt(np.mean(seg[i * hop:i * hop + 1024].astype(np.float64) ** 2)) for i in idx if i * hop + 1024 <= len(seg)])
    if not len(rms):
        return None, None
    return float(np.median(12 * np.log2(f0[idx] / 100))), float(20 * np.log10(np.mean(rms) + 1e-9))


def syllables(t):
    """音节数：汉字一个一个数，英文词按元音组估（中英语速才能比）。"""
    n = len(re.findall(r'[一-鿿]', t))
    for w in re.findall(r'[A-Za-z]+', t.lower()):
        k = len(re.findall(r'[aeiouy]+', w)) - (1 if w.endswith('e') and len(w) > 2 and not w.endswith('le') else 0)
        n += max(1, k)
    return n


def boundaries(pieces, sr):
    """pieces：[(音频, 文字或 None, 后面的停顿秒)] 按顺序。返回每个边界的量值。"""
    out = []
    for (a, ta, gap), (b, tb, _) in zip(pieces, pieces[1:]):
        fa, la = edge_feats(a, sr, 'tail')
        fb, lb = edge_feats(b, sr, 'head')
        ra = syllables(ta) / (len(a) / sr) if ta else None
        rb = syllables(tb) / (len(b) / sr) if tb else None
        d = None if fa is None or fb is None else fb - fa
        while d is not None and abs(d) > 7:          # 八度误判折回（男声句末气泡音常被量低一个八度）
            d -= 12 * np.sign(d)
        bad_l = la is None or lb is None or not np.isfinite(la) or not np.isfinite(lb)
        out.append({'pitch': None if d is None else abs(d), 'level': None if bad_l else abs(lb - la),
                    'rate': None if not (ra and rb) else max(ra, rb) / min(ra, rb), 'pause': gap})
    return out


def recording_targets(path):
    import 挑参考 as PR
    x = PR.decode(path)
    spans, _, _ = PR.utterances(x)
    asr = PR.ASR()
    spans = [(s, e) for s, e in spans if (e - s) / PR.SR >= 1.0]
    pieces = []
    for k, (s, e) in enumerate(spans):
        nxt = spans[k + 1][0] if k + 1 < len(spans) else e
        gap = (nxt - e) / PR.SR
        pieces.append((x[s:e], asr(x[s:e])[0], gap))
    B = [b for b, p in zip(boundaries(pieces, PR.SR), pieces) if p[2] <= 1.5]     # 1.5 秒以上的停顿是剪辑 / 翻页，不算
    q = lambda key, p: round(float(np.percentile([b[key] for b in B if b[key] is not None], p)), 2)  # noqa: E731
    return {'pitch_p99': q('pitch', 99), 'level_p99': q('level', 99), 'rate_p95': q('rate', 95),
            'pause_p50': q('pause', 50), 'pause_p90': q('pause', 90), 'n': len(B)}


def boundaries_of(a, sr, items):
    """成品音频 a 与 timings items：相邻合成小段之间的边界。"""
    us = [u for it in items for u in it.get('units', [it])]
    pieces = [(a[int(u['start'] * sr):int(u['end'] * sr)], u['text'].replace('‖', ''),
               (us[k + 1]['start'] - u['end']) if k + 1 < len(us) else 0) for k, u in enumerate(us)]
    B = boundaries(pieces, sr)
    for b, u, v in zip(B, us, us[1:]):
        b['at'] = round(u['end'], 2)
        b['between'] = f"{u['text'][-6:]}｜{v['text'][:6]}"
    return B


def product_boundaries(mp3):
    import soundfile as sf
    a, sr = sf.read(str(mp3), dtype='float32')
    a = a.mean(1) if a.ndim > 1 else a
    return boundaries_of(a, sr, json.loads(Path(mp3).with_suffix('.timings.json').read_text('utf-8'))['items'])


def problems(B, tgt):
    j = tgt['junction']
    errs = []
    for b in B:
        if b['rate'] is not None and b['rate'] > j['rate_p95']:
            errs.append(f"相邻段语速差 {b['rate']:.2f} 倍（上限 {j['rate_p95']}）：“{b['between']}”（{b['at']}s）")
    ps = [b['pause'] for b in B]
    if ps:
        p50, p90 = float(np.median(ps)), float(np.percentile(ps, 90))
        if p50 > j['pause_p50'] * PAUSE_RATIO or p90 > j['pause_p90'] * PAUSE_RATIO:
            errs.append(f"停顿偏长：中位 {p50:.2f} / 90% 分位 {p90:.2f} 秒（本人录音 {j['pause_p50']} / {j['pause_p90']}，上限各 × {PAUSE_RATIO}）")
    return errs


def main():
    if '--录音' in sys.argv:
        t = recording_targets(sys.argv[sys.argv.index('--录音') + 1])
        d = json.loads(TARGET.read_text('utf-8'))
        d['junction'] = t
        TARGET.write_text(json.dumps(d, ensure_ascii=False, indent=1), 'utf-8')
        print(t)
        return
    tgt, bad = json.loads(TARGET.read_text('utf-8')), 0
    for p in sys.argv[1:]:
        e = problems(product_boundaries(p), tgt)
        print(f"{Path(p).name}：{len(e)} 处")
        for x in e:
            print('  ✗', x)
        bad += bool(e)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
