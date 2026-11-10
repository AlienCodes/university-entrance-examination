#!/usr/bin/env python3
"""高考听力原音 → 语音块（按 ≥0.35 秒静音切开）+ 每块 SenseVoice 识别（自动判中 / 英，带文字）。只读原音。
中文说明（“听第6段材料，回答第6、7题”“第一节”）就靠它定位：开头剪切锚点、每组题的切屏点。
用法：python 分块识别.py 原音.wav 输出目录  → 分块.json [[开始, 结束, 语言, 文字], ...]"""
import glob, json, sys
from pathlib import Path
import numpy as np, soundfile as sf, soxr

ROOT = Path(__file__).resolve().parents[2]
src, out = Path(sys.argv[1]), Path(sys.argv[2])
a, sr = sf.read(src, dtype='float32', always_2d=True)
a = soxr.resample(a.mean(1), sr, 16000)
H = 320
n = len(a) // H
db = 10 * np.log10((a[:n * H].reshape(n, H) ** 2).mean(1) + 1e-12)
thr = np.percentile(db, 10) + 12
sp = db >= thr
runs, i = [], 0
while i < n:
    if sp[i]:
        j = i
        while j < n and (sp[j] or (j + 18 < n and sp[j:j + 18].any())): j += 1   # 0.35 秒以内的间隙并进来
        if j - i >= 8: runs.append((i * 0.02, j * 0.02))
        i = j
    else: i += 1
import sherpa_onnx
d = Path(glob.glob(str(ROOT / 'tools/tts/models/sherpa-onnx-sense-voice-*'))[0])
r = sherpa_onnx.OfflineRecognizer.from_sense_voice(model=str(d / 'model.int8.onnx'), tokens=str(d / 'tokens.txt'),
                                                   language='auto', use_itn=True, num_threads=4)
res = []
for s, e in runs:
    seg = a[int(max(0, s - 0.1) * 16000):int((e + 0.1) * 16000)]
    if e - s > 25:                                    # 太长的块对半识别（只为文字；时刻用块边界）
        pass
    st = r.create_stream(); st.accept_waveform(16000, seg); r.decode_stream(st)
    lang = (st.result.lang or '').strip('<|>')
    res.append([round(s, 2), round(e, 2), lang, st.result.text.strip()])
(out / '分块.json').write_text(json.dumps(res, ensure_ascii=False, indent=0), 'utf-8')
print(len(res), '块', '中文', sum(x[2] == 'zh' for x in res), '阈值', round(float(thr), 1))
