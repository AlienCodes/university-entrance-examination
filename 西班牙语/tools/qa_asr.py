"""语音识别回转比对（内容核查）：成品 MP3 逐句送进语音识别，和原文逐词比较，找出漏读、多读、读错的词。

    /opt/es_tts_envs/sherpa/bin/python 西班牙语/tools/qa_asr.py --model 识别模型文件夹 es01 成品.mp3 [--sents 1-9] [--out 结果.md] [--json 结果.json]

为什么要做：Qwen3-TTS 是大语言模型式的合成，偶尔会跳词、重复、读错；Supertonic 也可能吞音。画面英文/西语和朗读不一致
就是错误视频（踩坑 20、27），所以每个成品都要识别一遍，每一处差异都要人工判定是“识别器听错”还是“合成真读错”。

识别模型：sherpa-onnx 的 NeMo Parakeet TDT 0.6B v3（多语种，含西班牙语，int8）：
    https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2
    （约 490 MB，解压后传 --model 解压出来的文件夹；用完可以删掉）
运行环境：sherpa-onnx 1.13.8 的 Python（/opt/es_tts_envs/sherpa/bin/python），另需系统里有 ffmpeg（解码 MP3）。

切句：成品里句与句之间是 0.8 秒数字静音、句内停顿只有 0.28 秒，所以按“≥ 0.6 秒的静音”切开，
切出来的句数必须等于原文句数（--sents 指定时等于指定的句数），对不上就报错（不猜）。
比较：小写、去掉标点、去掉重音符号后逐词对齐（difflib）；另外单列“只差重音符号”的词
（如 amplío / amplio：重音位置不同，可能是读错了重音，也可能只是识别器写法不同，要人工听）。
输出：Markdown 表（每句一行：原文、识别结果、差异），判定一栏留给人工填写。差异为 0 的句子判定写“一致”。
"""
import argparse
import difflib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ES = HERE.parent
SR = 16000


def decode(mp3):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp3), '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32)


def split_sentences(a, min_gap=0.6, thr_db=-60.0, hop=0.01):
    """按 ≥ min_gap 秒的静音切句，返回 [(开始秒, 结束秒)]。"""
    h = int(hop * SR)
    n = len(a) // h
    e = 20 * np.log10(np.sqrt((a[:n * h].reshape(n, h) ** 2).mean(1)) + 1e-12)
    voiced = e > thr_db
    out, i = [], 0
    while i < n:
        if not voiced[i]:
            i += 1
            continue
        s = i
        last = i
        j = i
        while j < n:
            if voiced[j]:
                last = j
            elif (j - last) * hop >= min_gap:
                break
            j += 1
        out.append((s * hop, (last + 1) * hop))
        i = j
    return out


def strip_accents(w):
    return ''.join(c for c in unicodedata.normalize('NFD', w) if unicodedata.category(c) != 'Mn')


def words(text):
    t = re.sub(r"[¿¡.,;:!?—\-\"'“”‘’()«»]", ' ', text.lower())
    return t.split()


def compare(ref, hyp):
    """返回 (逐词差异列表, 只差重音的词列表)。差异：('漏读'|'多读'|'不同', 原文片段, 识别片段)。"""
    rw, hw = words(ref), words(hyp)
    rn, hn = [strip_accents(w) for w in rw], [strip_accents(w) for w in hw]
    diffs, accents = [], []
    sm = difflib.SequenceMatcher(a=rn, b=hn, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            for a, b in zip(rw[i1:i2], hw[j1:j2]):
                if a != b:
                    accents.append((a, b))
        elif op == 'delete':
            diffs.append(('漏读', ' '.join(rw[i1:i2]), ''))
        elif op == 'insert':
            diffs.append(('多读', '', ' '.join(hw[j1:j2])))
        else:
            diffs.append(('不同', ' '.join(rw[i1:i2]), ' '.join(hw[j1:j2])))
    return diffs, accents


def recognizer(model):
    import sherpa_onnx
    d = Path(model)

    def one(pat):
        f = sorted(d.glob(pat))
        if not f:
            raise SystemExit(f'qa_asr.py：{d} 里找不到 {pat}')
        return str(f[0])
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=one('encoder*.onnx'), decoder=one('decoder*.onnx'), joiner=one('joiner*.onnx'),
        tokens=one('tokens.txt'), model_type='nemo_transducer', num_threads=4, decoding_method='greedy_search')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pid')
    ap.add_argument('mp3')
    ap.add_argument('--model', required=True)
    ap.add_argument('--sents')
    ap.add_argument('--out')
    ap.add_argument('--json')
    ap.add_argument('--title', default='')
    a = ap.parse_args()
    p = json.loads((ES / '文章' / f'{a.pid}.json').read_text('utf-8'))
    allsent = [s['es'] for para in p['paras'] for s in para]
    ks = list(range(1, len(allsent) + 1))
    if a.sents:
        pick = set()
        for x in a.sents.split(','):
            lo, _, hi = x.partition('-')
            pick |= set(range(int(lo), int(hi or lo) + 1))
        ks = [k for k in ks if k in pick]
    audio = decode(a.mp3)
    spans = split_sentences(audio)
    if len(spans) != len(ks):
        raise SystemExit(f'qa_asr.py：{a.mp3} 按静音切出 {len(spans)} 句，原文是 {len(ks)} 句，对不上（不猜，请检查音频）')
    rec = recognizer(a.model)
    rows = []
    for k, (t0, t1) in zip(ks, spans):
        s = rec.create_stream()
        seg = audio[max(0, int((t0 - 0.15) * SR)): int((t1 + 0.15) * SR)]
        s.accept_waveform(SR, seg)
        rec.decode_stream(s)
        hyp = s.result.text.strip()
        d, acc = compare(allsent[k - 1], hyp)
        rows.append({'k': k, 'start': round(t0, 2), 'end': round(t1, 2), 'ref': allsent[k - 1], 'hyp': hyp,
                     'diffs': d, 'accents': acc})
    nd = sum(len(r['diffs']) for r in rows)
    nw = sum(len(words(r['ref'])) for r in rows)
    md = [f'### {a.title or Path(a.mp3).name}', '',
          f'识别模型：{Path(a.model).name}；共 {len(rows)} 句 {nw} 词，逐词差异 {nd} 处'
          f'（{sum(1 for r in rows if not r["diffs"])} 句完全一致），只差重音符号 {sum(len(r["accents"]) for r in rows)} 处。', '',
          '| 句 | 原文 | 识别结果 | 差异 | 判定 |', '|---|---|---|---|---|']
    for r in rows:
        ds = '；'.join(f'{t}：{x or "—"} → {y or "—"}' for t, x, y in r['diffs'])
        ds += ('；' if ds and r['accents'] else '') + '；'.join(f'重音：{x} → {y}' for x, y in r['accents'])
        md.append(f"| {r['k']} | {r['ref']} | {r['hyp']} | {ds or '无'} | {'一致' if not ds else '（待人工判定）'} |")
    text = '\n'.join(md) + '\n'
    if a.out:
        Path(a.out).write_text(text, 'utf-8')
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), 'utf-8')
    print(text)


if __name__ == '__main__':
    main()
