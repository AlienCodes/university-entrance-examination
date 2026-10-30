"""配音选型评测（程序比，不靠感觉）：对 Actions 合成的原始 WAV（runs/<任务>/<候选>/take<N>/<段>.wav）逐段：
  ① 中英识别回转（SenseVoice，zh/en 混合）：中文按字、英文按词的编辑距离 / 参考长度（错误率），列出差异；
  ② 英文段再用 parakeet（英文专用）识别，词错误率；
  ③ UTMOS 自然度（英文训练的模型，中文只作参考）；
  ④ 语调起伏：浊音段基频的标准差（半音）——越大越“抑扬顿挫”，太小就是平调；
  ⑤ 电磁音全频段扫描（讲解音频.tonal_scan，上限 +3 dB）。
输出每个候选 × 每次的汇总表 + 每段明细（评测结果.json），挑每个候选最好的一次。
用法：/opt/ttsenv/bin/python 选型评测.py --run 目录 --稿 样稿.json"""
import argparse
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
M = ROOT / 'tools/tts/models'
sys.path.insert(0, str(Path(__file__).parent))


def toks(s):
    s = s.lower().replace('’', "'")
    return re.findall(r"[一-鿿]|[a-z]+(?:'[a-z]+)?", s)


def ed(a, b):
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        p, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (a[i - 1] != b[j - 1]))
    return d[len(b)]


def diff(ref, hyp):
    import difflib
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ref, hyp).get_opcodes():
        if op != 'equal':
            out.append(f"{''.join(ref[i1:i2]) if all(len(x) == 1 for x in ref[i1:i2]) else ' '.join(ref[i1:i2])}→"
                       f"{''.join(hyp[j1:j2]) if all(len(x) == 1 for x in hyp[j1:j2]) else ' '.join(hyp[j1:j2])}")
    return out


class Ears:
    def __init__(self):
        import sherpa_onnx
        import torch
        d = Path(glob.glob(str(M / 'sherpa-onnx-sense-voice-*'))[0])
        self.sv = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(d / 'model.int8.onnx'), tokens=str(d / 'tokens.txt'), use_itn=False, num_threads=4)
        p = glob.glob(str(M / 'sherpa-onnx-nemo-parakeet*'))
        self.en = None
        if p:
            p = Path(p[0])
            self.en = sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=str(p / 'encoder.int8.onnx'), decoder=str(p / 'decoder.int8.onnx'),
                joiner=str(p / 'joiner.int8.onnx'), tokens=str(p / 'tokens.txt'), model_type='nemo_transducer', num_threads=4)
        self.torch = torch
        self.mos = torch.hub.load(str(M / 'SpeechMOS'), 'utmos22_strong', source='local', trust_repo=True)

    def rec(self, r, a16):
        s = r.create_stream()
        s.accept_waveform(16000, a16)
        r.decode_stream(s)
        return re.sub(r'<\|[^|]*\|>', '', s.result.text)

    def utmos(self, a16):
        with self.torch.no_grad():
            return float(self.mos(self.torch.from_numpy(a16).unsqueeze(0), 16000))


def f0_spread(x, sr):
    import librosa
    f0, vflag, _ = librosa.pyin(x, fmin=65, fmax=400, sr=sr, frame_length=1024)
    f = f0[vflag & ~np.isnan(f0)]
    if len(f) < 10:
        return None
    st = 12 * np.log2(f / np.median(f))
    return float(np.std(st))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--稿', required=True)
    ap.add_argument('--out')
    a = ap.parse_args()
    import soundfile as sf
    import soxr
    import 讲解音频 as J
    segs = json.loads(Path(a.稿).read_text('utf-8'))['segments']
    ears = Ears()
    res = {}
    for cand in sorted(Path(a.run).iterdir()):
        for take in sorted(cand.glob('take*')):
            rows, R, E = [], 0, 0
            for s in segs:
                w = take / f"{s['id']}.wav"
                if not w.exists():
                    rows.append({'id': s['id'], 'missing': True})
                    continue
                x, sr = sf.read(str(w), dtype='float32')
                a16 = soxr.resample(x, sr, 16000).astype(np.float32)
                hyp = ears.rec(ears.sv, a16)
                ref = toks(s['text'])
                h = toks(hyp)
                e = ed(ref, h)
                R += len(ref)
                E += e
                row = {'id': s['id'], 'err': e, 'n': len(ref), 'diff': diff(ref, h), 'sec': round(len(x) / sr, 2),
                       'mos': round(ears.utmos(a16), 2), 'f0_st': f0_spread(x, sr)}
                if s['lang'] == 'English' and ears.en:
                    eh = toks(ears.rec(ears.en, a16))
                    row['en_err'] = ed(ref, eh)
                    row['en_diff'] = diff(ref, eh)
                rows.append(row)
            ok = [r for r in rows if not r.get('missing')]
            items = []
            t = 0
            pieces = []
            for s in segs:
                w = take / f"{s['id']}.wav"
                if w.exists():
                    x, sr = sf.read(str(w), dtype='float32')
                    x = soxr.resample(x, sr, 48000).astype(np.float32)
                    items.append({'start': t / 48000, 'end': (t + len(x)) / 48000})
                    pieces.append(x)
                    t += len(x)
            buzz = J.tonal_scan(np.concatenate(pieces), 48000, items) if pieces else (None, [])
            f0 = [r['f0_st'] for r in ok if r.get('f0_st')]
            res[f'{cand.name}/{take.name}'] = {
                'err_rate': round(E / max(R, 1), 4), 'errors': E, 'missing': len(rows) - len(ok),
                'mos': round(float(np.mean([r['mos'] for r in ok])), 3) if ok else None,
                'f0_st': round(float(np.mean(f0)), 2) if f0 else None,
                'sec': round(sum(r['sec'] for r in ok), 1), 'buzz_max': buzz[0], 'buzz_top': buzz[1],
                'en_err': sum(r.get('en_err', 0) for r in ok), 'rows': rows}
            r = res[f'{cand.name}/{take.name}']
            print(f"{cand.name}/{take.name}: 错误率 {r['err_rate']:.3f}（{E}/{R}），英文段错 {r['en_err']}，缺 {r['missing']}，"
                  f"UTMOS {r['mos']}，语调起伏 {r['f0_st']} 半音，{r['sec']}s，电磁音最强 {buzz[0]} dB", flush=True)
    out = Path(a.out or Path(a.run) / '评测结果.json')
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), 'utf-8')


if __name__ == '__main__':
    main()
