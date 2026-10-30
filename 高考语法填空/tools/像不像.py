"""克隆样音像不像用户本人（程序量，不靠感觉）：
  ① 说话人相似度：3D-Speaker ERes2Net 说话人嵌入的余弦相似度，跟录音里**没被用作参考**的 6 段真人语音（各 10 秒）比，取平均；
     标尺：同一个人两段真人录音约 0.90，不同的人（设计音色男老师 A）约 0.39；
  ② 自然度：UTMOS（英文训练的模型，中文只作参考）；
  ③ 真人录音自己的分数作对照（真人 vs 真人）。
模型：tools/tts/models/3dspeaker_eres2net_base_zh_16k.onnx（sherpa-onnx speaker-recongition-models 发布页，已 gitignore）。
用法：/opt/ttsenv/bin/python 像不像.py --录音 05.wav --参考 tts/音色/用户本人_1.json … --样音 a.mp3 b.mp3 [--out 结果.md]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).parent), str(ROOT / 'tools/tts')]
M = ROOT / 'tools/tts/models'


class Spk:
    def __init__(self):
        import sherpa_onnx
        self.ex = sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(M / '3dspeaker_eres2net_base_zh_16k.onnx'), num_threads=4))

    def __call__(self, x, sr):
        import soxr
        s = self.ex.create_stream()
        s.accept_waveform(16000, soxr.resample(x, sr, 16000).astype(np.float32))
        s.input_finished()
        e = np.array(self.ex.compute(s))
        return e / np.linalg.norm(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--录音', required=True)
    ap.add_argument('--参考', nargs='+', default=[])
    ap.add_argument('--样音', nargs='+', required=True)
    ap.add_argument('--out')
    a = ap.parse_args()
    import soundfile as sf
    import torch
    x, sr = sf.read(a.录音, dtype='float32')
    x = x.mean(1) if x.ndim > 1 else x
    used = []
    for r in a.参考:
        w = json.loads(Path(r).read_text('utf-8'))['window_sec']
        used.append((w[0] - 15, w[1] + 15))
    dur = len(x) / sr
    starts = [t for t in np.linspace(60, dur - 70, 40) if all(t + 10 < u0 or t > u1 for u0, u1 in used)]
    starts = [starts[i] for i in np.linspace(0, len(starts) - 1, 7).astype(int)]
    spk = Spk()
    held = [spk(x[int(t * sr):int((t + 10) * sr)], sr) for t in starts]
    mos = torch.hub.load(str(M / 'SpeechMOS'), 'utmos22_strong', source='local', trust_repo=True)

    def utmos(y, s):
        import soxr
        y16 = soxr.resample(y, s, 16000).astype(np.float32)
        with torch.no_grad():
            return float(mos(torch.from_numpy(y16).unsqueeze(0), 16000))

    base = held[0]
    rows = [('真人（录音另一段，对照）', float(np.mean([base @ h for h in held[1:]])), utmos(x[int(starts[0] * sr):int((starts[0] + 10) * sr)], sr))]
    for p in a.样音:
        y, s = sf.read(p, dtype='float32')
        y = y.mean(1) if y.ndim > 1 else y
        y = y[int(1.5 * s):len(y) - int(2.0 * s)]                   # 去掉片头片尾静音
        e = spk(y, s)
        rows.append((Path(p).name, float(np.mean([e @ h for h in held[1:]])), float(np.mean([utmos(y[i:i + 10 * s], s) for i in range(0, max(1, len(y) - 10 * s), 10 * s)]))))
    lines = ['| 音频 | 说话人相似度（与真人，0.90≈同一人，0.39≈别人） | UTMOS 自然度 |', '|---|---|---|']
    lines += [f'| {n} | {sim:.3f} | {u:.2f} |' for n, sim, u in rows]
    print('\n'.join(lines))
    if a.out:
        Path(a.out).write_text('\n'.join(lines) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
