"""讲解配音的节奏检查（用户 2026-10-30 看第 56 题样片：“hold，举办”之后紧接“既然给了词”几乎没停；“是不是谓语呢？”尾音轻飘上扬）。

稿子里用 ‖ 标出必须停顿的边界（说完词义、说完一个推理步骤、给出答案前后、问句之后）。处理链（讲解音频.expand）在 ‖ 处把一段拆成
几个“小段”分别合成、逐个选优，拼接时中间放 PAUSE_MARK 秒真静音——停顿由构造保证。这里是**独立的检查**（不看 timings 里写的时间）：
  pause_problems：用识别器（SenseVoice，带时间戳）把成品这一段的文字对齐到时间，找到 ‖ 前最后一个字、‖ 后第一个字，量两者之间
                  最长的连续静音（比本段最响处低 35 dB 以下），短于 PAUSE_MIN 就报；
  question_problems：每个问句（？结尾的小段，或识别对齐到的 ？ 位置）量最后约 300 毫秒浊音的音高走向：
                  末尾 100 毫秒的音高中位数比前 200 毫秒高出 RISE_MAX 半音以上 = 轻飘上扬，报。
门限按实测定：用户本人录音的句间停顿 10—90% 分位 0.18—0.46 秒（剪掉换气之后），所以标记边界放 0.55 秒、检查下限 0.45 秒；
问句尾音见 RISE_MAX 的注释。
用法（单独量一个成品）：/opt/ttsenv/bin/python 讲解节奏.py 成品.mp3 [--稿 稿.json]（稿里的 ‖ 与 ？ 套到 timings 的各段上）
"""
import difflib
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).parent), str(ROOT / 'tools/tts')]

MARK = '‖'
PAUSE_MARK = 0.55     # 处理：标记边界放的静音（秒）
PAUSE_MIN = 0.45      # 检查：标记边界的最短静音（秒）
RISE_MAX = 2.0        # 检查：问句末尾 100 ms 比前 200 ms 高出的半音数上限（实测见 讲解节奏.md）


def toks(s):
    s = s.lower().replace('’', "'")
    return re.findall(r"[一-鿿]|[a-z]+(?:'[a-z]+)?|[？?]", s)


class Aligner:
    def __init__(self):
        import 挑参考 as P
        self.r = P.ASR().r

    def __call__(self, y, sr):
        """返回 [(词, 开始秒)]（中文按字，英文按词，标点不算）。"""
        import soxr
        s = self.r.create_stream()
        s.accept_waveform(16000, soxr.resample(y, sr, 16000).astype(np.float32))
        self.r.decode_stream(s)
        out, prev_en = [], False
        for raw, t in zip(s.result.tokens, s.result.timestamps):
            tk = raw.strip()
            if re.fullmatch(r"[a-zA-Z']+", tk) and prev_en and not raw.startswith(' '):
                out[-1] = (out[-1][0] + tk.lower(), out[-1][1])      # 英文子词并回前一个词
                continue
            got = [ch for ch in toks(tk) if ch not in '？?']
            out += [(ch, float(t)) for ch in got]
            prev_en = bool(got) and bool(re.fullmatch(r"[a-z']+", got[-1]))
        return out


def align_index(ref, hyp):
    """ref 下标 → hyp 下标（只给相同或替换对齐上的）。"""
    m = {}
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ref, [h for h, _ in hyp], autojunk=False).get_opcodes():
        if op in ('equal', 'replace'):
            for k in range(min(i2 - i1, j2 - j1)):
                m[i1 + k] = j1 + k
    return m


def frames_db(y, sr, hop=0.01, win=0.03):
    H, W = int(hop * sr), int(win * sr)
    n = max(0, (len(y) - W) // H + 1)
    if n == 0:
        return np.zeros(0)
    e = np.array([np.mean(y[i * H:i * H + W].astype(np.float64) ** 2) for i in range(n)])
    return 10 * np.log10(e + 1e-20)


def longest_silence(y, sr, t0, t1, ref_db):
    """[t0, t1] 内最长的连续静音（帧电平 < ref_db − 35）秒数。"""
    L = frames_db(y[max(0, int(t0 * sr)):int(t1 * sr)], sr)
    best = run = 0
    for v in L:
        run = run + 1 if v < ref_db - 35 else 0
        best = max(best, run)
    return best * 0.01


def tail_rise(y, sr, t_end):
    """t_end 之前的浊音尾巴：末 100 ms 与前 200 ms 的音高中位数之差（半音）。返回 (半音, 尾巴结束时刻) 或 (None, None)。"""
    import librosa
    a = y[max(0, int((t_end - 0.8) * sr)):int((t_end + 0.05) * sr)].astype(np.float32)
    f0, v, _ = librosa.pyin(a, fmin=60, fmax=400, sr=sr, frame_length=2048, hop_length=int(0.01 * sr))
    idx = np.where(v & ~np.isnan(f0))[0]
    if len(idx) < 12:
        return None, None
    last = idx[-1]
    seg = [i for i in idx if i > last - 30]                     # 最后 300 ms 的浊音帧
    a1 = [f0[i] for i in seg if i > last - 10]
    a0 = [f0[i] for i in seg if i <= last - 10]
    if len(a1) < 4 or len(a0) < 6:
        return None, None
    return float(12 * np.log2(np.median(a1) / np.median(a0))), (t_end - 0.8) + last * 0.01


def item_audio(a, sr, it):
    return a[int(it['start'] * sr):int(it['end'] * sr)]


def check(a, sr, items, marked_text, al=None):
    """items：timings 的各段；marked_text：段 id → 带 ‖ 的稿文字。返回 (报告行, 问题)。"""
    al = al or Aligner()
    rep, errs = [], []
    for it in items:
        txt = marked_text.get(it['id'])
        if not txt or (MARK not in txt and '？' not in txt):
            continue
        y = item_audio(a, sr, it)
        hyp = al(y, sr)
        ref_db = float(np.percentile(frames_db(y, sr), 99))
        pieces = txt.split(MARK)
        ref_all = [t for t in toks(''.join(pieces)) if t not in '？?']
        m = align_index(ref_all, hyp)
        pos = 0
        for k, p in enumerate(pieces):
            n = len([t for t in toks(p) if t not in '？?'])
            if k + 1 < len(pieces) and n:
                i_last, i_next = pos + n - 1, pos + n
                if i_last in m and i_next in m:
                    t0, t1 = hyp[m[i_last]][1], hyp[m[i_next]][1]
                    sil = longest_silence(y, sr, t0, t1, ref_db)
                    rep.append({'id': it['id'], '边界': f"{p.strip()[-6:]}‖{pieces[k + 1].strip()[:6]}", '停顿秒': round(sil, 2)})
                    if sil < PAUSE_MIN:
                        errs.append(f"{it['id']}：“{p.strip()[-6:]}‖{pieces[k + 1].strip()[:6]}”停顿 {sil:.2f} 秒（下限 {PAUSE_MIN}）（{it['start'] + t0:.2f}s）")
                else:
                    errs.append(f"{it['id']}：边界“{p.strip()[-6:]}‖”识别对不上，量不了停顿")
            # 问句：这一小段里每个 ？ 前的最后一个字
            sub = re.split(r'(？)', p)
            cnt = pos
            for j in range(0, len(sub) - 1, 2):
                cnt += len([t for t in toks(sub[j]) if t not in '？?'])
                if sub[j + 1] == '？' and cnt - 1 in m:
                    i = m[cnt - 1]
                    t_word = hyp[i][1]
                    t_next = hyp[i + 1][1] if i + 1 < len(hyp) else len(y) / sr
                    rise, t_end = tail_rise(y, sr, min(t_next, t_word + 0.8))
                    q = sub[j].strip()[-8:] + '？'
                    rep.append({'id': it['id'], '问句': q, '尾音半音': None if rise is None else round(rise, 2)})
                    if rise is not None and rise > RISE_MAX:
                        errs.append(f"{it['id']}：问句“{q}”尾音上扬 {rise:.1f} 半音（上限 {RISE_MAX}）（{it['start'] + t_word:.2f}s）")
            pos += n
    return rep, errs


def main():
    import soundfile as sf
    mp3 = Path(sys.argv[1])
    tm = json.loads(mp3.with_suffix('.timings.json').read_text('utf-8'))
    marked = {it['id']: it['text'] for it in tm['items']}
    if '--稿' in sys.argv:
        doc = json.loads(Path(sys.argv[sys.argv.index('--稿') + 1]).read_text('utf-8'))
        marked = {s['id']: s['text'] for s in doc['segments']}
    a, sr = sf.read(str(mp3), dtype='float32')
    rep, errs = check(a if a.ndim == 1 else a.mean(1), sr, tm['items'], marked)
    for r in rep:
        print(r)
    for e in errs:
        print('  ✗', e)
    print(f'节奏检查：{len(errs)} 处')


if __name__ == '__main__':
    main()
