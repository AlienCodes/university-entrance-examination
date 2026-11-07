"""听力原音 → 逐词时间（parakeet 识别）+ 停顿表。只读原音，不改动。
用法：python 识别对齐.py 原音.wav 输出目录
输出：识别.json（[[词, 开始秒, 结束秒], ...]）、停顿.json（≥1 秒的静音段 [开始, 结束]）"""
import json, sys, glob
from pathlib import Path
import numpy as np, soundfile as sf, soxr

ROOT = Path(__file__).resolve().parents[3]
src, out = Path(sys.argv[1]), Path(sys.argv[2])
a, sr = sf.read(src, dtype='float32', always_2d=True)
a = soxr.resample(a.mean(1), sr, 16000)
H = 320                                      # 20 ms
n = len(a) // H
db = 10 * np.log10((a[:n*H].reshape(n, H) ** 2).mean(1) + 1e-12)
thr = np.percentile(db, 10) + 12             # 底噪 + 12 dB 以下算静音
sil = db < thr
# 静音段
runs, i = [], 0
while i < n:
    if sil[i]:
        j = i
        while j < n and sil[j]: j += 1
        runs.append((i * 0.02, j * 0.02)); i = j
    else: i += 1
(out / '停顿.json').write_text(json.dumps({'阈值dB': round(float(thr), 1),
    '静音': [[round(s, 2), round(e, 2)] for s, e in runs if e - s >= 1.0]}, ensure_ascii=False), 'utf-8')
# 切块：在 ≥0.25 s 的静音中点切，每块 ≤ 25 s
cuts = [0.0]
mids = [(s + e) / 2 for s, e in runs if e - s >= 0.25]
t = 0.0
for m in mids:
    if m - cuts[-1] > 25:
        prev = [x for x in mids if cuts[-1] + 2 < x < m]
        cuts.append(prev[-1] if prev else m)
    if m - cuts[-1] >= 12: cuts.append(m)
cuts.append(len(a) / 16000)
import sherpa_onnx
d = Path(glob.glob(str(ROOT / 'tools/tts/models/sherpa-onnx-nemo-parakeet*'))[0])
asr = sherpa_onnx.OfflineRecognizer.from_transducer(encoder=str(d/'encoder.int8.onnx'), decoder=str(d/'decoder.int8.onnx'),
    joiner=str(d/'joiner.int8.onnx'), tokens=str(d/'tokens.txt'), model_type='nemo_transducer', num_threads=4)
words = []
for s, e in zip(cuts, cuts[1:]):
    seg = a[int(s*16000):int(e*16000)]
    if (db[int(s/0.02):int(e/0.02)] >= thr).sum() < 10: continue
    st = asr.create_stream(); st.accept_waveform(16000, seg); asr.decode_stream(st)
    r = st.result
    cur = None
    for tok, ts in zip(r.tokens, r.timestamps):
        if tok.startswith(' ') or cur is None:
            if cur: words.append(cur)
            cur = [tok.strip(), round(s + ts, 2), round(s + ts + 0.08, 2)]
        else:
            cur[0] += tok; cur[2] = round(s + ts + 0.08, 2)
    if cur: words.append(cur)
words = [w for w in words if w[0]]
(out / '识别.json').write_text(json.dumps(words, ensure_ascii=False), 'utf-8')
print(len(cuts) - 1, '块', len(words), '词', '阈值', round(float(thr), 1))
