"""逐句听对（踩坑 124）：成品音轨里每一句的时间窗，用语音识别独立听一遍，与这句原文比——对不上就是时间轴放错了地方。

为什么要它：六级精读的原音音轨，句子时刻取自 定稿.json 的逐词时刻，没有时刻的词按前后均分；原音音轨.py 的“对上比例”拿原文跟原文比，
永远 100%（自己查自己，踩坑 2）。202312-2 试音念了两遍说明，定稿 把第一遍的文字对到第二遍的声音上、第二遍文字没有时刻，
第 6—10 句被均分到 5 秒的“试音结束，现在开始”上，所有检查都过，截图时分屏找不到“at”才露出来。

    /opt/ttsenv/bin/python tools/tts/听对.py 202312-2 [202512-1 …]     # 量六级精读成品音轨（默认全部）
"""
import difflib
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIN_WORDS = 4          # 原文（不算数字）不到 4 个词的短句（Exactly.）识别常常差一两个词，不判
MIN_RATIO = 0.5        # 原文的词听到不到一半就报；放错地方的句子 0.0—0.1

_ASR = []


def norm(s):
    return re.sub(r'[^a-z0-9 ]', '', s.lower().replace('-', ' ').replace('centre', 'center')).split()


def recognizer():
    if not _ASR:
        import sherpa_onnx
        d = Path(glob.glob(str(ROOT / 'tools' / 'tts' / 'models' / 'sherpa-onnx-nemo-parakeet*'))[0])
        _ASR.append(sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(d / 'encoder.int8.onnx'), decoder=str(d / 'decoder.int8.onnx'), joiner=str(d / 'joiner.int8.onnx'),
            tokens=str(d / 'tokens.txt'), model_type='nemo_transducer', num_threads=4))
    return _ASR[0]


def load16(path):
    import numpy as np
    import soundfile as sf
    import soxr
    a, sr = sf.read(str(path), dtype='float32')
    if a.ndim == 2:
        a = a.mean(axis=1)
    return soxr.resample(a, sr, 16000).astype(np.float32)


def heard(a16, t0, t1):
    asr = recognizer()
    st = asr.create_stream()
    st.accept_waveform(16000, a16[int(t0 * 16000): int(t1 * 16000)])
    asr.decode_stream(st)
    return st.result.text


def problems(a16, windows, texts):
    """windows：每句 (起, 止) 秒；texts：每句原文。返回 [(句号, 相似度, 原文, 听到的)]。"""
    out = []
    for k, ((t0, t1), s) in enumerate(zip(windows, texts), 1):
        a = [w for w in norm(s) if not re.search(r'\d', w)]       # 数字识别成英文读法（2018 → twenty eighteen），不算
        if len(a) < MIN_WORDS:
            continue
        b = norm(heard(a16, t0, t1))
        r = sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()) / len(a)      # 原文的词听到了几成
        if r < MIN_RATIO:
            out.append((k, round(r, 2), s[:60], ' '.join(b)[:60]))
    return out


def cet6_texts(pid):
    v = json.loads((ROOT / '六级' / '听力' / '精读' / 'data' / 'vocab.json').read_text('utf-8'))
    p = next(x for x in v['passages'] if x['id'] == pid)
    return [s['en'] for pa in p['paras'] for s in pa]


def cet6_check(pid, mp3=None, timings=None):
    tm = timings or json.loads((ROOT / '六级' / '听力' / '精读' / 'audio' / 'timings.json').read_text('utf-8'))['cet4_male'][pid]
    a16 = load16(mp3 or ROOT / '六级' / '听力' / '精读' / 'audio' / tm['file'])
    return problems(a16, [(x['start'], x['end']) for x in tm['sentences']], cet6_texts(pid))


if __name__ == '__main__':
    T = json.loads((ROOT / '六级' / '听力' / '精读' / 'audio' / 'timings.json').read_text('utf-8'))['cet4_male']
    bad = 0
    for pid in sys.argv[1:] or sorted(T):
        ps = cet6_check(pid)
        bad += len(ps)
        print(pid, f'{len(ps)} 句对不上', *[f'\n  第 {k} 句 {r}：{s} ｜ 听到：{h}' for k, r, s, h in ps], flush=True)
    sys.exit(1 if bad else 0)
