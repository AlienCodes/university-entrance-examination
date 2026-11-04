"""声音对比（程序量，不靠感觉）：Actions 合成的原始小段（runs/<任务>/<候选>/take<N>/）逐个候选 × 每次：
  ① 完整处理链 + 全部检查（讲解音频.render：去呼吸 → segment → 母带 → 合格证；呼吸 0、电磁音、节奏、拼接、多音字声调），
     通过的写出 MP3 + 合格证；不通过的记原因（仍按同一条链拼出来量下面几项，只是不出 MP3）；
  ② 浊音基频中位数（librosa.pyin，与 挑参考.f0_median 同一量法）与老师真声的差（半音）；
  ③ 说话人相似度（3D-Speaker ERes2Net 嵌入余弦，像不像.Spk）：与录音里没被用作参考的 6 段真声（各 10 秒）平均；英文段单独量；
  ④ 识别错误：每个小段 SenseVoice 回转（中文按字、英文按词的编辑距离 / 参考长度），英文段再用 parakeet（英文专用）算词错率。
不用 torch（不量 UTMOS），本机代理下不了 torch。
用法：python 声音对比.py --run runs/任务-sovits-6 --稿 稿.json --录音 05.wav --参考 tts/音色/用户本人平实_1.json --mp3 高考续写/预览/声音对比 --out 报告.md
"""
import argparse
import glob
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / '高考语法填空/tools'), str(ROOT / 'tools/tts')]
M = ROOT / 'tools/tts/models'
F0_TEACHER = 106.2      # 协调会话给的老师真声浊音基频中位数（Hz）；本脚本也从录音现量一遍，两个都报


def toks(t):
    t = re.sub(r'<\|[^|]*\|>', '', t).replace('‖', '')
    return [w.lower() for w in re.findall(r"[一-鿿]|[A-Za-z]+(?:['’][A-Za-z]+)?", t)]


def edits(a, b):
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        p, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (a[i - 1] != b[j - 1]))
    return d[len(b)]


class Ears:
    def __init__(self):
        import sherpa_onnx
        d = Path(glob.glob(str(M / 'sherpa-onnx-sense-voice-*'))[0])
        self.sv = sherpa_onnx.OfflineRecognizer.from_sense_voice(model=str(d / 'model.int8.onnx'), tokens=str(d / 'tokens.txt'),
                                                                 use_itn=False, num_threads=4)
        p = Path(glob.glob(str(M / 'sherpa-onnx-nemo-parakeet*'))[0])
        self.en = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(p / 'encoder.int8.onnx'), decoder=str(p / 'decoder.int8.onnx'), joiner=str(p / 'joiner.int8.onnx'),
            tokens=str(p / 'tokens.txt'), model_type='nemo_transducer', num_threads=4)

    def __call__(self, r, x, sr):
        import soxr
        s = r.create_stream()
        s.accept_waveform(16000, soxr.resample(x, sr, 16000).astype(np.float32))
        r.decode_stream(s)
        return s.result.text


def f0_median(x, sr):
    import librosa
    import soxr
    y = soxr.resample(x, sr, 16000).astype(np.float32)
    f0, v, _ = librosa.pyin(y, fmin=65, fmax=400, sr=16000, frame_length=1024)
    f = f0[v & ~np.isnan(f0)]
    return float(np.median(f)) if len(f) > 20 else None


def split_of(td):
    m = json.loads((Path(td) / 'meta_part0.json').read_text('utf-8'))
    return m['candidate'].get('split', m.get('split', 'mark'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--稿', required=True)
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--录音', required=True)
    ap.add_argument('--参考', nargs='*', default=[])
    ap.add_argument('--mp3', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--gap-max', type=float, default=0.32, help='段间停顿上限（讲解音频.GAP_MAX；Qwen 第 6 轮同为 0.32，本人句间停顿中位 0.31）')
    a = ap.parse_args()
    import soundfile as sf
    import gaokao_tts as G
    import 讲解音频 as J
    from 像不像 import Spk
    J.SPLIT = 'mark'
    J.GAP_MAX = a.gap_max
    segs = json.loads(Path(a.稿).read_text('utf-8'))['segments']
    run = Path(a.run)
    takes = sorted(run.glob('*/take*'))
    only = a.only or json.loads((takes[0] / 'meta_part0.json').read_text('utf-8')).get('only')
    if not only:   # meta 里没有就按小段文件推
        have = {p.stem.split('~')[0] for p in takes[0].glob('*.wav')}
        only = [s['id'] for s in segs if s['id'] in have]
    segs = [s for s in segs if s['id'] in only]
    x, sr = sf.read(a.录音, dtype='float32')
    x = x.mean(1) if x.ndim > 1 else x
    used = [tuple(json.loads(Path(r).read_text('utf-8'))['window_sec']) for r in a.参考]
    dur = len(x) / sr
    starts = [t for t in np.linspace(60, dur - 70, 40) if all(t + 10 < u0 - 15 or t > u1 + 15 for u0, u1 in used)]
    starts = [starts[i] for i in np.linspace(0, len(starts) - 1, 7).astype(int)]
    spk = Spk()
    held = [spk(x[int(t * sr):int((t + 10) * sr)], sr) for t in starts]
    real_sim = float(np.mean([held[0] @ h for h in held[1:]]))
    real_f0 = float(np.median([f0_median(x[int(t * sr):int((t + 10) * sr)], sr) for t in starts]))
    cen = np.mean(held[1:], 0)
    cen /= np.linalg.norm(cen)
    ears = Ears()
    mp3d = Path(a.mp3)
    mp3d.mkdir(parents=True, exist_ok=True)
    rows, detail = [], []
    for td in takes:
        cid, tk = td.parent.name, td.name
        J.SPLIT = split_of(td)                # 与合成时同一种拆法（候选的 split，sovits_synth 默认 mark）
        out = mp3d / f'{run.name}_{cid}_{tk}.mp3'
        try:
            J.render(segs, td, out)
            chk = '全部通过'
        except RuntimeError as e:
            chk = str(e)[:160]
            out = None
        y, items = J.build(segs, td)
        ysr = G.OUT_SR
        f0 = f0_median(y, ysr)
        sim = float(spk(y, ysr) @ cen)
        en_parts = [y[int(u['start'] * ysr):int(u['end'] * ysr)] for it in items for u in it['units']
                    if not any('一' <= ch <= '鿿' for ch in u['text'])]
        en_sim = float(spk(np.concatenate(en_parts), ysr) @ cen) if en_parts else None
        E = N = Ew = Nw = 0
        for u in J.expand(segs):
            w, wsr = sf.read(str(td / f"{u['id']}.wav"), dtype='float32')
            ref = toks(u['text'])
            hyp = toks(ears(ears.sv, w, wsr))
            e = edits(ref, hyp)
            E, N = E + e, N + len(ref)
            enw = None
            if u['lang'] == 'English':
                hw = toks(ears(ears.en, w, wsr))
                enw = edits(ref, hw)
                Ew, Nw = Ew + enw, Nw + len(ref)
            detail.append((cid, tk, u['id'], e, len(ref), ' '.join(hyp), enw))
        rows.append(dict(cid=cid, take=tk, chk=chk, mp3=out.name if out else None, f0=f0,
                         st=12 * np.log2(f0 / real_f0) if f0 else None, st106=12 * np.log2(f0 / F0_TEACHER) if f0 else None,
                         sim=sim, en_sim=en_sim, err=E / max(N, 1), wer=Ew / max(Nw, 1) if Nw else None))
        print(rows[-1], flush=True)
    # 每个候选每句挑最好的一次（识别错数 + 英文词错数最少，同分取前一次），拼成一份再走一遍完整处理链（另出合格证）
    import tempfile
    best_rows = []
    for cid in sorted({r['cid'] for r in rows}):
        tmp = Path(tempfile.mkdtemp())
        J.SPLIT = split_of(run / cid / 'take1')
        pick = {}
        for u in J.expand(segs):
            sc, tk = min((e + (w or 0), t) for c, t, uid, e, n, h, w in detail if c == cid and uid == u['id'])
            pick[u['id']] = tk
            shutil.copy(run / cid / tk / f"{u['id']}.wav", tmp / f"{u['id']}.wav")
        out = mp3d / f'{run.name}_{cid}_每句最好.mp3'
        try:
            J.render(segs, tmp, out)
            chk = '全部通过'
        except RuntimeError as e:
            chk, out = str(e)[:160], None
        best_rows.append((cid, chk, out.name if out else None, pick))
        print(cid, '每句最好', chk, pick, flush=True)
    L = ['# 声音对比（GPT-SoVITS 专属模型）', '', f'运行：`{run.name}`；{len(segs)} 句（{" ".join(only)}）；真声：{Path(a.录音).name}',
         f'真声对照：相似度（真声两段之间）{real_sim:.3f}；真声浊音基频中位数 {real_f0:.1f} Hz（协调会话给的 {F0_TEACHER} Hz）', '',
         '| 候选 | 次 | 处理链与全部检查 | 基频 Hz | 与真声差（半音） | 与 106.2 Hz 差 | 相似度 | 英文部分相似度 | 识别错误率（SenseVoice） | 英文词错率（parakeet） |',
         '|---|---|---|---|---|---|---|---|---|---|']
    fm = lambda v, f='{:.3f}': '—' if v is None else f.format(v)  # noqa: E731
    for r in rows:
        L.append(f"| {r['cid']} | {r['take']} | {r['chk']} | {fm(r['f0'], '{:.1f}')} | {fm(r['st'], '{:+.2f}')} | {fm(r['st106'], '{:+.2f}')} | "
                 f"{fm(r['sim'])} | {fm(r['en_sim'])} | {fm(r['err'])} | {fm(r['wer'])} |")
    L += ['', '## 每个候选每句最好的一次拼成一份', '', '| 候选 | 处理链与全部检查 | MP3 | 每句用的是哪一次 |', '|---|---|---|---|']
    L += [f"| {c} | {k} | {m or '—'} | {' '.join(f'{u}:{t[4:]}' for u, t in p.items())} |" for c, k, m, p in best_rows]
    L += ['', '## 每个小段的识别', '', '| 候选 | 次 | 小段 | 错 / 字词数 | SenseVoice 识别 | parakeet 错词 |', '|---|---|---|---|---|---|']
    L += [f'| {c} | {t} | {u} | {e}/{n} | {h} | {"—" if w is None else w} |' for c, t, u, e, n, h, w in detail]
    Path(a.out).write_text('\n'.join(L) + '\n', 'utf-8')
    for p in mp3d.glob(f'{run.name}_*.mp3'):        # 没过检查的不留（render 不写文件；保险起见按表再核一遍）
        if p.name not in {r['mp3'] for r in rows} | {b[2] for b in best_rows}:
            p.unlink()
    shutil.copy(a.out, mp3d / f'{run.name}_报告.md')


if __name__ == '__main__':
    main()
