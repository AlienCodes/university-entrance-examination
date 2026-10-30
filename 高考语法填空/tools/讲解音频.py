"""讲解视频配音的完整处理链（本机做；原始 WAV 由 GitHub Actions 上的 qwen_synth.py 合成）。

规则全部复用 tools/tts/gaokao_tts（只写一处）：每段 segment（段内电平统一 even + BS.1770 统一 level_clause + 淡入淡出）
→ 按稿子的停顿拼接 → master（压缩、按意群 clause_trim、−16 LUFS、限幅）→ final_check（含意群级，关不掉）→ 合格证。
新增（这个模型才需要）：电磁音全频段扫描 tonal_scan——Kokoro 的 9 个固定频点（四级/tools/debuzz.py）不适用于别的声码器，
2 kHz 以上任何窄带峰高出周围超过 +3 dB（铁律 10 的同一上限）就报错；有固定频点时按 debuzz 的做法（60 Hz 带宽单向陷波）去掉。

意群：Qwen 每段整段合成、自己会停顿；段内静音（≥ 0.15 秒）把一段切成几个意群，交给 fine_check 与 clause_trim。
用法：python 讲解音频.py --稿 稿.json --wav 原始目录 --out 成品.mp3 [--lead 1.5 --tail 2.0]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/tts'))
import gaokao_tts as G  # noqa: E402

SR = G.SR
BUZZ_MAX_DB = 3.0
NOTCH = []          # 实测出固定频点再填（Hz）；空 = 不做陷波


def load(path):
    import soundfile as sf
    import soxr
    x, sr = sf.read(str(path), dtype='float32')
    if x.ndim > 1:
        x = x.mean(1)
    if sr != SR:
        x = soxr.resample(x, sr, SR, quality='VHQ').astype(np.float32)
    return x


def inner_parts(x, sr=SR, min_sil=0.15, db=-42):
    """段内停顿切出的意群 [(起, 止)]（秒，相对本段）。"""
    H = int(0.01 * sr)
    n = len(x) // H
    e = 20 * np.log10(np.sqrt(np.mean(x[:n * H].reshape(n, H) ** 2, 1)) + 1e-9)
    on = e > (e.max() + db)
    spans, s = [], None
    for i, v in enumerate(on):
        if v and s is None:
            s = i
        if not v and s is not None:
            spans.append([s, i])
            s = None
    if s is not None:
        spans.append([s, n])
    merged = []
    for sp in spans:
        if merged and (sp[0] - merged[-1][1]) * 0.01 < min_sil:
            merged[-1][1] = sp[1]
        else:
            merged.append(sp)
    return [(a * 0.01, b * 0.01) for a, b in merged]


def notch(x, sr):
    if not NOTCH:
        return x
    from scipy.signal import iirnotch, lfilter
    y = x.astype(np.float64)
    for f0 in NOTCH:
        b, a = iirnotch(f0, f0 / 60.0, sr)
        y = lfilter(b, a, y)
    y = y.astype(np.float32)
    y[x == 0] = 0
    return y


def tonal_scan(a, sr, items, fmin=2000):
    """全频段窄带峰：语音部分的功率谱减去 61 点中值，2 kHz 以上的最大值（dB）及前 5 个峰。"""
    from scipy.ndimage import median_filter
    from scipy.signal import welch
    sp = np.concatenate([a[int(s['start'] * sr):int(s['end'] * sr)] for s in items]).astype(np.float64)
    f, P = welch(sp, sr, nperseg=65536)
    r = 10 * np.log10(P + 1e-20)
    r = r - median_filter(r, 61)
    m = f >= fmin
    idx = np.argsort(r[m])[::-1]
    top, used = [], []
    for i in idx:
        fr = float(f[m][i])
        if all(abs(fr - u) > 30 for u in used):
            used.append(fr)
            top.append((round(fr), round(float(r[m][i]), 1)))
        if len(top) == 5:
            break
    return top[0][1], top


def build(segs, wavdir, lead=1.5, tail=2.0):
    """返回 (48 kHz 成品, items)。items 每段一条：start/end/parts（秒，成品时间轴）、id、text。"""
    pieces = [np.zeros(int(lead * SR), np.float32)]
    t, items = lead, []
    for k, s in enumerate(segs, 1):
        x = G.trim(load(Path(wavdir) / f"{s['id']}.wav"))
        x = notch(x, SR)
        x = G.segment(x)
        parts = inner_parts(x)
        dur = len(x) / SR
        items.append({'k': k, 'id': s['id'], 'start': round(t, 3), 'end': round(t + dur, 3),
                      'parts': [[round(t + p, 3), round(t + q, 3)] for p, q in parts], 'text': s['text']})
        pieces.append(x)
        t += dur
        g = tail if k == len(segs) else s.get('gap', 0.6)
        pieces.append(np.zeros(int(round(g * SR)), np.float32))
        t += int(round(g * SR)) / SR
    a = G.master(np.concatenate(pieces), -16.0, parts=[p for it in items for p in it['parts']])
    return a, items


def render(segs, wavdir, out, lead=1.5, tail=2.0):
    a, items = build(segs, wavdir, lead, tail)
    mx, top = tonal_scan(a, G.OUT_SR, items)
    if mx > BUZZ_MAX_DB:
        raise RuntimeError(f'电磁音：窄带峰 {top}（上限 +{BUZZ_MAX_DB} dB），未输出')
    cert = G.save_checked(Path(out), a, items, -16.0)
    meta = {'duration': round(len(a) / G.OUT_SR, 3), 'items': items, 'buzz_top': top, 'certificate': cert,
            'clause_check': G.CHAIN}
    Path(out).with_suffix('.timings.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), 'utf-8')
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--稿', required=True)
    ap.add_argument('--wav', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--lead', type=float, default=1.5)
    ap.add_argument('--tail', type=float, default=2.0)
    a = ap.parse_args()
    segs = json.loads(Path(a.稿).read_text('utf-8'))['segments']
    m = render(segs, a.wav, a.out, a.lead, a.tail)
    c = m['certificate']['loudness']
    print(f"{a.out}：{m['duration']:.1f}s；整体 {c['integrated_lufs']} LUFS，句间 {c['sentence_max_dev_lu']}，短时 {c['short_term_std_lu']}，"
          f"峰值 {c['peak_dbfs']}，意群 {c.get('clause_nb_min_lu')} / 段尾 {c.get('clause_tail_min_db')}；电磁音最强 {m['buzz_top'][0]}")


if __name__ == '__main__':
    main()
