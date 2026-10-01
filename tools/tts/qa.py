"""音频自检：把生成的音频按时间轴逐句切开，
1) 用语音识别（Parakeet-TDT 0.6B）转回文字，和朗读文本比对，找出可能读错的词；
2) 用 UTMOS（自动预测的平均意见分，1–5 分，真人录音一般 4 分左右）给每句打自然度分。
结果写到 audio/qa_report.json 和 audio/qa_report.md。
"""
import difflib
import glob
import json
import re
from pathlib import Path

import numpy as np

from gaokao_tts import HERE, OUT, verify_loudness
from textnorm import normalize


def words(t):
    t = normalize(t).lower().replace('’', "'").replace('-', ' ')
    return re.sub(r"[^a-z0-9' ]", ' ', t).split()


def diff(ref, hyp):
    """返回 (错误词数, 参考词数, [(参考片段, 识别片段)])；忽略连写差异（longstanding / long standing）。"""
    r, h = words(ref), words(hyp)
    sm = difflib.SequenceMatcher(a=r, b=h, autojunk=False)
    errs, ops = 0, []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            continue
        a, b = ' '.join(r[i1:i2]), ' '.join(h[j1:j2])
        if a.replace(' ', '') == b.replace(' ', ''):
            continue
        errs += max(i2 - i1, j2 - j1)
        ops.append((a, b))
    return errs, len(r), ops


class Checker:
    def __init__(self):
        import sherpa_onnx
        import torch
        d = Path(glob.glob(str(HERE / 'models' / 'sherpa-onnx-nemo-parakeet*'))[0])
        self.asr = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(d / 'encoder.int8.onnx'), decoder=str(d / 'decoder.int8.onnx'),
            joiner=str(d / 'joiner.int8.onnx'), tokens=str(d / 'tokens.txt'),
            model_type='nemo_transducer', num_threads=4)
        self.torch = torch
        self.mos = torch.hub.load(str(HERE / 'models' / 'SpeechMOS'), 'utmos22_strong',
                                  source='local', trust_repo=True)

    def check(self, a16):
        s = self.asr.create_stream()
        s.accept_waveform(16000, a16)
        self.asr.decode_stream(s)
        with self.torch.no_grad():
            mos = float(self.mos(self.torch.from_numpy(a16).unsqueeze(0), 16000))
        return s.result.text, mos


def run(args):
    import soundfile as sf
    import soxr
    timings = json.loads((OUT / 'timings.json').read_text('utf-8'))
    voices = args.voices or list(timings)
    ck = Checker()
    rep_path = OUT / 'qa_report.json'
    report = json.loads(rep_path.read_text('utf-8')) if rep_path.exists() else {}
    for v in voices:
        for pid, r in timings[v].items():
            if args.only and pid not in args.only:
                continue
            # 第一项检查：响度一致性（对 MP3 成品独立测量）
            loud, lerr = verify_loudness((OUT / r['file']).read_bytes(), r['sentences'], -16.0)
            print(f"[{v}] {pid}  响度：{'通过' if not lerr else '未通过 ' + '；'.join(lerr)}  {loud}", flush=True)
            a, sr = sf.read(str(OUT / r['file']), dtype='float32')
            a16 = soxr.resample(a, sr, 16000).astype(np.float32)
            rows = []
            for it in r['sentences']:
                seg = a16[int(it['start'] * 16000): int(it['end'] * 16000)]
                text, mos = ck.check(seg)
                e, n, ops = diff(it['read'], text)
                rows.append({'k': it['k'], 'mos': round(mos, 3), 'err': e, 'n': n, 'asr': text, 'ops': ops})
            report.setdefault(v, {})[pid] = {
                'loudness': loud, 'loudness_ok': not lerr,
                'mos': round(float(np.mean([x['mos'] for x in rows])), 3),
                'wer': round(sum(x['err'] for x in rows) / max(1, sum(x['n'] for x in rows)), 4),
                'sentences': rows}
            print(f"[{v}] {pid}  自然度 {report[v][pid]['mos']:.2f}  识别差异率 {report[v][pid]['wer']:.2%}", flush=True)
            rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), 'utf-8')
    write_md(report)


def write_md(report):
    lines = ['# 音频自检报告', '',
             '自然度：UTMOS 自动评分（1–5，真人有声书录音通常在 4.0–4.3）。'
             '识别差异率：语音识别转回的文字和朗读文本不一致的词所占比例（人名、拼写变体也会算进去，不一定是读错）。', '']
    for v, ps in report.items():
        ms = [p['mos'] for p in ps.values()]
        ws = [p['wer'] for p in ps.values()]
        bad = [pid for pid, p in ps.items() if not p.get('loudness_ok', True)]
        lines += [f'## {v}', '', f'- 文章数：{len(ps)}',
                  f'- **响度一致性（第一项检查）**：{"全部通过" if not bad else "未通过：" + "、".join(bad)}',
                  f'- 平均自然度：{np.mean(ms):.2f}（最低 {min(ms):.2f}）',
                  f'- 平均识别差异率：{np.mean(ws):.2%}', '', '| 文章 | 自然度 | 差异率 | 差异（朗读文本 → 识别结果） |', '|---|---|---|---|']
        for pid, p in ps.items():
            ops = '; '.join(f'{a or "∅"} → {b or "∅"}' for s in p['sentences'] for a, b in s['ops'])[:300]
            lines.append(f"| {pid} | {p['mos']:.2f} | {p['wer']:.2%} | {ops} |")
        lines.append('')
    (OUT / 'qa_report.md').write_text('\n'.join(lines), 'utf-8')
