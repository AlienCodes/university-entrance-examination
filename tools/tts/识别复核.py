"""语音识别差异的复核（踩坑 27、40、72；专八 t11–t27 时在草稿区临时写的两个工具，收进仓库）：

    /opt/ttsenv/bin/python tools/tts/识别复核.py 专八 截取 t20:40 t17:42 …
        成品音频里这一句：整句前后多留 0.5 秒重新识别 + 按音频分句（timings 的 parts）逐段截取识别
    /opt/ttsenv/bin/python tools/tts/识别复核.py 专八 试合成 t17:42 '{}' t17:42 '{"to":"tˈu"}' …
        按该项目 make_audio 的同一流程单独合成这一句两次（可加逐句读音覆盖 {词: 音标}），转 16 kHz 后识别

判断（识别差异已核.md 的做法）：三种截取都错、单句试合成两次也错 → 真读错，改读音（读音修正.json）后试合成识别正确才重新生成；
任何一种截取识别正确 → 识别器按上下文猜错，不改。"""
import glob
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
R = HERE.parent.parent
proj, mode, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
SRC = {'六级': '仔细阅读', '四级': '仔细阅读', '考研作文': '作文', '六级作文': '作文', '四级作文': '作文'}.get(proj, '阅读')
sys.path[:0] = [str(HERE), str(R / proj / 'tools')]
if proj in ('四级', '六级'):
    sys.path.insert(1, str(R / '四级' / 'tools'))
import sherpa_onnx  # noqa: E402

d = Path(glob.glob(str(HERE / 'models' / 'sherpa-onnx-nemo-parakeet*'))[0])
asr = sherpa_onnx.OfflineRecognizer.from_transducer(encoder=str(d / 'encoder.int8.onnx'), decoder=str(d / 'decoder.int8.onnx'),
                                                    joiner=str(d / 'joiner.int8.onnx'), tokens=str(d / 'tokens.txt'),
                                                    model_type='nemo_transducer', num_threads=4)


def rec(a):
    s = asr.create_stream()
    s.accept_waveform(16000, a)
    asr.decode_stream(s)
    return s.result.text


if mode == '截取':
    T = json.loads((R / proj / 'audio' / 'timings.json').read_text('utf-8'))['cet4_male']
    cache = {}
    for item in rest:
        pid, k = item.split(':')
        tm = T[pid]
        if tm['file'] not in cache:
            raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(R / proj / 'audio' / tm['file']), '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
                                 capture_output=True).stdout
            cache[tm['file']] = np.frombuffer(raw, np.float32)
        a, it = cache[tm['file']], tm['sentences'][int(k) - 1]
        cut = lambda x, y: a[max(0, int(x * 16000)):int(y * 16000)]
        print(f'== {item}  朗读文本：{it["read"]}')
        print('  整句前后多留 0.5 秒：', rec(cut(it['start'] - 0.5, it['end'] + 0.5)))
        for j, (x, y) in enumerate(it['parts']):
            print(f'  分句 {j + 1}：', rec(cut(x - 0.3, y + 0.3)))
elif mode == '试合成':
    import make_audio as M
    from scipy.signal import resample_poly
    G = M.G
    vcfg = json.loads((G.HERE / 'voices.json').read_text('utf-8'))[M.VOICE]
    engine, pron = G.Engine(), G.Pronouncer()
    style = engine.style(vcfg['style'])
    P = {p['id']: p for p in json.loads((R / proj / SRC / 'sents.json').read_text('utf-8'))}
    while rest:
        key, ov = rest[0], json.loads(rest[1])
        rest = rest[2:]
        pid, k = key.split(':')
        en = [s for para in P[pid]['sents'] for s in para][int(k) - 1]
        read = pron.read_text(en, key)
        base = dict(pron.sentence.get(key, {}))
        pron.sentence[key] = {**base, **ov}
        for rep in (1, 2):
            a, _ = M.synth_sentence(read, key, engine, pron, style, vcfg.get('speed', 1.0), vcfg)
            print(f'{key} {ov or "原读音"} 第 {rep} 次：{rec(resample_poly(a, 2, 3).astype(np.float32))}', flush=True)
        pron.sentence[key] = base
else:
    sys.exit(__doc__)
