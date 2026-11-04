"""清晰度（老师 2026-11-04：“很多发音都没有发清楚……起码声音要清晰一点”）：程序量“听不听得清”，不靠耳朵。

两类量法，互相独立：
  ① 识别：两个独立的中文识别器（SenseVoice：非自回归 CTC，多语种；Paraformer-zh：非自回归 CIF，纯中文，另一家训练数据）
     各自转写，只比汉字（英文单词、数字、标点不算），算
       cer       字错误率 = 编辑距离 / 参考字数
       pcer      去声调拼音错误率（同音字不算错，只剩“发成别的音”的错）
       xcer      两个识别器互相之间的字差异率（不要参考文字：真声录音没有稿子也能量，真声与合成用同一把尺）
  ② 频谱（只在有声帧上，20 ms 帧）：
       hf4k      4 kHz 以上能量占比（清辅音 s sh x c ch q z f h 的能量主要在 4—10 kHz；发闷 = 低）
       centroid  频谱质心中位（Hz）
       tilt      0.5—4 kHz 的频谱倾斜（dB/倍频程）
       cvr       擦音帧（4 kHz 以上占比 ≥ 0.5 且不是浊音）能量中位 − 浊音帧能量中位（dB）：清辅音被压低 / 切掉就变小
       fric      擦音帧占有声帧的比例
       f0        浊音基频中位（Hz，YIN）
用法：
  python 清晰度.py --wav a.wav --text "稿子原文"              一条
  python 清晰度.py --dir 目录 --稿 稿.json                    目录里 <段 id>[~k].wav 逐条（按 讲解音频.expand 取小段文字）
  python 清晰度.py --long 05.wav --n 30                       长录音：按停顿切 3—9 秒 30 段，只量 xcer 和频谱
"""
import argparse
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
M = HERE / 'models'
SR16 = 16000
HAN = re.compile(r'[一-鿿]')


def han(t):
    t = re.sub(r'<\|[^|]*\|>', '', t or '')
    return HAN.findall(t)


def edits(a, b):
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        p, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (a[i - 1] != b[j - 1]))
    return d[len(b)]


def pinyin(chars):
    from pypinyin import lazy_pinyin
    return lazy_pinyin(''.join(chars)) if chars else []


def rate(ref, hyp):
    return edits(ref, hyp) / max(1, len(ref))


class Ears:
    """两个中文识别器（sherpa-onnx，模型在 tools/tts/models/）。"""

    def __init__(self, threads=4):
        import sherpa_onnx
        d = Path(glob.glob(str(M / 'sherpa-onnx-sense-voice-*'))[0])
        self.sv = sherpa_onnx.OfflineRecognizer.from_sense_voice(model=str(d / 'model.int8.onnx'), tokens=str(d / 'tokens.txt'),
                                                                 language='zh', use_itn=False, num_threads=threads)
        p = Path(glob.glob(str(M / 'sherpa-onnx-paraformer-zh-*'))[0])
        self.pf = sherpa_onnx.OfflineRecognizer.from_paraformer(paraformer=str(p / 'model.int8.onnx'), tokens=str(p / 'tokens.txt'),
                                                                num_threads=threads)

    @staticmethod
    def _run(r, y):
        s = r.create_stream()
        s.accept_waveform(SR16, y)
        r.decode_stream(s)
        return s.result.text

    def __call__(self, x, sr):
        import soxr
        y = soxr.resample(np.asarray(x, np.float32), sr, SR16).astype(np.float32) if sr != SR16 else np.asarray(x, np.float32)
        y = np.concatenate([np.zeros(SR16 // 5, np.float32), y, np.zeros(SR16 // 5, np.float32)])
        return self._run(self.sv, y), self._run(self.pf, y)


def score_asr(ears, x, sr, text=None):
    a, b = ears(x, sr)
    ha, hb = han(a), han(b)
    out = {'xcer': round(rate(ha, hb) if len(ha) >= len(hb) else rate(hb, ha), 4), 'sv_text': a, 'pf_text': b}
    if text is not None:
        ref = han(text.replace('‖', ''))
        pr = pinyin(ref)
        out.update(n=len(ref), sv_cer=round(rate(ref, ha), 4), pf_cer=round(rate(ref, hb), 4),
                   sv_pcer=round(rate(pr, pinyin(ha)), 4), pf_pcer=round(rate(pr, pinyin(hb)), 4))
    return out


def spectral(x, sr):
    """有声帧上的频谱指标（见文件头）。x 任意采样率（≥ 16 kHz；4 kHz 以上要有内容）。"""
    import librosa
    x = np.asarray(x, np.float64)
    n = int(0.02 * sr)
    h = n // 2
    if len(x) < 4 * n:
        return {}
    fr = librosa.util.frame(np.pad(x, (0, n)), frame_length=n, hop_length=h).T
    win = np.hanning(n)
    S = np.abs(np.fft.rfft(fr * win, axis=1)) ** 2
    f = np.fft.rfftfreq(n, 1 / sr)
    e = S.sum(1) + 1e-12
    edb = 10 * np.log10(e)
    act = edb > edb.max() - 45                       # 有声帧（比最响帧低 45 dB 以内）
    hf = S[:, f >= 4000].sum(1) / e
    cen = (S * f).sum(1) / e
    f0 = librosa.yin(x.astype(np.float32), fmin=65, fmax=400, sr=sr, frame_length=max(2048, 2 * n), hop_length=h)[:len(e)]
    # 浊音：低频（< 1 kHz）占大头且 YIN 给出稳定基频；用低频占比判（YIN 本身不给置信度）
    lf = S[:, f < 1000].sum(1) / e
    voiced = act & (lf > 0.5)
    fric = act & (hf >= 0.5) & ~voiced
    bands = (f >= 500) & (f <= 4000)
    lo = np.log2(f[bands] / 500)
    tilt = []
    for k in np.where(voiced)[0][::4]:
        tilt.append(np.polyfit(lo, 10 * np.log10(S[k, bands] + 1e-12), 1)[0])
    vf0 = f0[voiced]
    vf0 = vf0[(vf0 > 66) & (vf0 < 399)]
    r = {'hf4k': round(float(np.sum(S[act][:, f >= 4000]) / np.sum(e[act])), 4),
         'centroid': round(float(np.median(cen[act])), 0),
         'tilt': round(float(np.median(tilt)), 2) if tilt else None,
         'fric': round(float(fric.sum() / max(1, act.sum())), 4),
         'cvr': round(float(np.median(edb[fric]) - np.median(edb[voiced])), 2) if fric.sum() >= 3 and voiced.sum() >= 3 else None,
         'f0': round(float(np.median(vf0)), 1) if len(vf0) > 20 else None}
    return r


def load(p, sr=None):
    import soundfile as sf
    x, s = sf.read(str(p), dtype='float32', always_2d=True)
    x = x.mean(1)
    if sr and s != sr:
        import soxr
        x = soxr.resample(x, s, sr).astype(np.float32)
        s = sr
    return x, s


def chunks(x, sr, n=30, lo=3.0, hi=9.0, seed=0):
    """长录音按停顿切成 lo—hi 秒的段，均匀取 n 段（确定性）。"""
    H = int(0.01 * sr)
    m = len(x) // H
    db = 10 * np.log10(np.mean(x[:m * H].reshape(m, H) ** 2, 1) + 1e-12)
    sil = db < np.percentile(db, 95) - 35
    segs, st, run = [], None, 0
    for i, s in enumerate(sil):
        if not s and st is None:
            st = i
        if s:
            run += 1
        else:
            run = 0
        if st is not None and s and run >= 25:          # 0.25 秒静音 = 断开
            e = i - run + 1
            if lo * 100 <= e - st <= hi * 100:
                segs.append((st * H, e * H))
            st = None
    if len(segs) > n:
        idx = np.linspace(0, len(segs) - 1, n).round().astype(int)
        segs = [segs[i] for i in idx]
    return segs


def summarize(rows, keys=('sv_cer', 'pf_cer', 'sv_pcer', 'pf_pcer', 'xcer', 'hf4k', 'centroid', 'tilt', 'cvr', 'fric', 'f0')):
    """汇总：识别错误率按字数加权（总错 / 总字），频谱取中位。"""
    out = {'n': len(rows)}
    tot = sum(r.get('n', 0) for r in rows)
    for k in keys:
        v = [r[k] for r in rows if r.get(k) is not None]
        if not v:
            continue
        if k.endswith('cer') and k != 'xcer' and tot:
            out[k] = round(sum(r[k] * r['n'] for r in rows if r.get(k) is not None) / tot, 4)
        else:
            out[k] = round(float(np.median(v) if k != 'xcer' else np.mean(v)), 4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wav')
    ap.add_argument('--text')
    ap.add_argument('--dir')
    ap.add_argument('--稿')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--long')
    ap.add_argument('--n', type=int, default=30)
    ap.add_argument('--tx', help='JSON 列表 [{wav, text}]（真声切片）')
    ap.add_argument('--no-text', action='store_true', help='不输出识别文字（只要数字，真声素材隐私）')
    ap.add_argument('--out')
    a = ap.parse_args()
    ears = Ears()
    rows = []
    if a.wav:
        x, sr = load(a.wav)
        rows.append({'id': Path(a.wav).stem, **score_asr(ears, x, sr, a.text), **spectral(x, sr)})
    if a.long:
        x, sr = load(a.long)
        for k, (p, q) in enumerate(chunks(x, sr, a.n)):
            y = x[p:q]
            rows.append({'id': f'{k}', 'sec': round((q - p) / sr, 2), **score_asr(ears, y, sr), **spectral(y, sr)})
    if a.tx:
        base = Path(a.tx).parent
        for k, t in enumerate(json.loads(Path(a.tx).read_text('utf-8'))):
            x, sr = load(base / t['wav'])
            rows.append({'id': f'{k}', 'sec': round(len(x) / sr, 2), **score_asr(ears, x, sr, t['text']), **spectral(x, sr)})
    if a.dir:
        sys.path.insert(0, str(HERE.parents[1] / '高考语法填空/tools'))
        import 讲解音频 as J
        J.SPLIT = 'mark'
        segs = json.loads(Path(a.稿).read_text('utf-8'))['segments']
        if a.only:
            segs = [s for s in segs if s['id'] in a.only]
        for u in J.expand(segs):
            p = Path(a.dir) / f"{u['id']}.wav"
            if not p.exists() or u['lang'] != 'Chinese' or len(han(u['text'])) < 4:
                continue
            x, sr = load(p)
            rows.append({'id': u['id'], **score_asr(ears, x, sr, u['text']), **spectral(x, sr)})
    if a.no_text:
        for r in rows:
            r.pop('sv_text', None)
            r.pop('pf_text', None)
    res = {'summary': summarize(rows), 'rows': rows}
    s = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(s, 'utf-8')
    print(json.dumps(res['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
