"""2025 专八听力原文精读视频的音轨：用听力原音（不是 TTS），逐句对齐、长等待压到 2 秒、只做整体增益。

    /opt/ttsenv/bin/python 专八/听力/原文/tools/原音音轨.py [L1 L2 L3] [--wav /home/user/wav/tem8-2025.wav]

输入：专八/听力/原文/原文.txt（逐句一行）、专八/听力/2025/识别.json（逐词时间）、原音 wav（Release 8-listening-test，sha256 见 2025/README.md）。
输出：专八/听力/原文/audio/原音/<篇目>.mp3、audio/timings.json（与 TTS 的 timings 同格式，键沿用引擎的 cet4_male）、audio/对齐报告.md。

做法（程序找、程序查，出错即停）：
1. 原文词与识别词整段对齐（difflib），每句取第一个、最后一个对上的词的时刻；句子首尾词没对上就往里找最近对上的词；
   每句对上的比例 < 80%、时刻不递增、窗口里有识别出的话不属于任何一句（漏转录），都报错停下。
2. 句子起止用能量细化（10 毫秒帧，噪声底 + 15 dB）：起点往前、终点往后找到真正的静音，不越过相邻句（踩坑 77：识别的时刻比实际晚几十毫秒）。
3. 句与句之间的静音 > 2 秒的，压到 2 秒（保留前 1 秒、后 1 秒，在静音里 20 毫秒交叉淡化）；≤ 2 秒的照原样。句子里面的声音一点不动。
4. 片头 1.5 秒数字静音（第一句 40 毫秒淡入），读完后 0.1 秒淡出、再 2.2 秒数字静音；整体增益到 −16 LUFS，峰值 ≤ −1 dBFS（超过就停，不压缩、不限幅）。
"""
import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

HERE = Path(__file__).resolve().parent
C4 = HERE.parent                     # 专八/听力/原文
ROOT = C4.parents[2]
SRC = C4.parent / '2025'
WIN = {'L1': (0.0, 743.0), 'L2': (743.0, 1164.0), 'L3': (1164.0, 1551.0)}     # 时间轴.json：secB 743.74、part2 1164.27
LEAD, MAXGAP, KEEP, XF, TAIL = 1.5, 2.0, 1.0, 0.02, 2.2


# 识别器漏掉的句子（时刻按能量实测；内容截取 738.5—744 秒单独识别复核：“This is the end of Section A, Mini Lecture.”，2026-10-25）：
# L1 末句 739.8—741.7 有 1.9 秒语音没识别出来、742.2—742.9 识别成 “Mini Lecture”；与 Section B 结尾 “This is the end of Section B Interview.” 句式、时长相同
OVERRIDE = {('L1', 'This is the end of Section A, Mini-Lecture.'): (739.75, 742.95)}


def read_text():
    out, cur = {}, None
    for line in (C4 / '原文.txt').read_text('utf-8').split('\n'):
        if line.startswith('## '):
            cur = line[3:].strip()
            out[cur] = [[]]
        elif cur and not line.strip():
            if out[cur][-1]:
                out[cur].append([])
        elif cur:
            out[cur][-1].append(line.strip())
    return {k: [p for p in v if p] for k, v in out.items()}


def norm(w):
    w = w.lower().replace('’', "'")
    return re.sub(r"[^a-z0-9']", '', w)


NUM = {'1': 'one', '2': 'two', '3': 'three', '4': 'four', '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine', '10': 'ten',
       '20': 'twenty', '24': 'twentyfour', '2025': 'twentytwentyfive', '19th': 'nineteenth'}


def toks(s):
    """一句的词（连字符、破折号处拆开，与识别的分词大致一致）；数字按读法。"""
    ws = [norm(w) for w in re.split(r'[\s—–:]+|(?<=\w)-(?=\w)', s)]
    ws = [y for w in ws for y in ALIAS.get(w, w).split()]
    return [NUM.get(w, w) for w in ws if w]


ALIAS = {'okay': 'ok', 'alan': 'allen', 'practise': 'practice', 'practising': 'practicing', 'favor': 'favour', 'recognized': 'recognised',
         'popularized': 'popularised', 'organizations': 'organisations', 'goert': 'geertz', 'q': 'question', 'qine': 'question', 'iter': 'interview',
         "they're": 'they are', "we're": 'we are', "it's": 'it is'}
FILLER = {'uh', 'um'}


def asr_seq(aw, vocab):
    """识别词 → 与原文可比的词：同义归一、去语气词、连字符拆开、相邻两词拼起来是原文里的词就合并（story tellers → storytellers）。
    返回 [(词, 开始, 结束)]。"""
    out = []
    for w, s, e in aw:
        for x in (norm(v) for v in w.split('-')):
            if not x or x in FILLER:
                continue
            for z in ALIAS.get(x, x).split():
                out.append([NUM.get(z, z), s, e])
    i, res = 0, []
    while i < len(out):
        if i + 1 < len(out) and out[i][0] + out[i + 1][0] in vocab and (out[i][0], out[i + 1][0]) in MERGE:
            res.append([out[i][0] + out[i + 1][0], out[i][1], out[i + 1][2]])
            i += 2
            continue
        res.append(out[i])
        i += 1
    return res


MERGE = {('story', 'tellers'), ('dai', 'yu'), ('week', 'end'), ('worth', 'while'), ('to', 'night'), ('every', 'day'), ('t', 'v')}


def frames_db(y, sr, hop=0.01):
    n = int(sr * hop)
    m = len(y) // n
    e = np.sqrt(np.mean(y[:m * n].reshape(m, n) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(e)


def align(pid, paras, R, y, sr):
    a, b = WIN[pid]
    aw = [x for x in R if a <= x[1] < b]
    sents = [s for p in paras for s in p]
    A, owner = [], []
    for k, s in enumerate(sents):
        t = toks(s)
        A += t
        owner += [k] * len(t)
    vocab = set(A) | {'daiyu', 'tv'}
    aw = asr_seq(aw, vocab)
    B = [x[0] for x in aw]
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    match = {}
    for blk in sm.get_matching_blocks():
        for d in range(blk.size):
            match[blk.a + d] = blk.b + d
    errs, rows = [], []
    used_b = set(match.values())
    times = []
    for k, s in enumerate(sents):
        idx = [i for i, o in enumerate(owner) if o == k]
        got = [match[i] for i in idx if i in match]
        ratio = len(got) / len(idx)
        if (pid, s) in OVERRIDE:
            times.append([*OVERRIDE[(pid, s)], ratio])
            continue
        if ratio < 0.8 or not got:
            errs.append(f'{pid} 第 {k + 1} 句只对上 {ratio:.0%}：{s[:60]}')
            times.append(None)
            continue
        times.append([aw[min(got)][1], aw[max(got)][2], ratio])
    # 漏转录：识别出的词没有对上任何原文词，且落在两句之间（不在任何一句的时间范围内）
    spans = [(t[0], t[1]) for t in times if t]
    for j, x in enumerate(aw):
        if j not in used_b and not any(s0 - 0.05 <= x[1] <= s1 + 0.05 for s0, s1 in spans):
            errs.append(f'{pid} {x[1]:.2f}s 识别出“{x[0]}”，不属于任何一句（漏转录？）')
    if errs:
        return None, errs
    for k in range(1, len(times)):
        if times[k][0] < times[k - 1][1] - 0.05:
            errs.append(f'{pid} 第 {k + 1} 句起点 {times[k][0]:.2f}s 早于上一句终点 {times[k - 1][1]:.2f}s')
    # 能量细化
    db = frames_db(y, sr)
    floor = np.percentile(db[int(a * 100):int(b * 100)], 10)
    thr = floor + 15
    out = []
    for k, (s0, s1, ratio) in enumerate(times):
        lo = times[k - 1][1] if k else max(a, s0 - 0.5)
        hi = times[k + 1][0] if k + 1 < len(times) else min(b, s1 + 0.8)
        i = int(s0 * 100)
        while i > int(lo * 100) + 2 and i > int((s0 - 0.3) * 100) and db[i - 1] > thr:
            i -= 1
        j = int(s1 * 100)
        while j < int(hi * 100) - 2 and j < int((s1 + 0.6) * 100) and db[j] > thr:
            j += 1
        # 句内的停顿（≥ 0.15 秒低于门限）：分屏只在停顿处换屏（分屏建议.py 的 pause_ok 读 parts）
        parts, run0, seg0 = [], None, i
        for q in range(i, j):
            if db[q] <= thr:
                run0 = q if run0 is None else run0
            else:
                if run0 is not None and q - run0 >= 15 and run0 > seg0:
                    parts.append([seg0 / 100, run0 / 100])
                    seg0 = q
                run0 = None
        parts.append([seg0 / 100, j / 100])
        out.append({'k': k + 1, 's0': s0, 's1': s1, 'start': i / 100, 'end': j / 100, 'ratio': round(ratio, 3), 'parts': parts})
    return out, errs


def build(pid, paras, R, y, sr):
    al, errs = align(pid, paras, R, y, sr)
    if errs:
        return None, errs
    sents = [s for p in paras for s in p]
    para_of = [pi + 1 for pi, p in enumerate(paras) for _ in p]
    fade_in = 0.04
    pos = al[0]['start'] - fade_in                    # 当前这一段在原音里的起点
    pieces, t_new, times, comp = [], LEAD - fade_in, [], []     # t_new：当前这一段起点在成品里的时刻
    for k, x in enumerate(al):
        if k:
            gap = x['start'] - al[k - 1]['end']
            if gap > MAXGAP:                            # 压缩：保留上一句后 1 秒、下一句前 1 秒
                cut_a = al[k - 1]['end'] + KEEP
                pieces.append((pos, cut_a + XF / 2))
                t_new += (cut_a + XF / 2 - pos) - XF           # 下一段与这一段重叠 XF（交叉淡化）
                pos = x['start'] - KEEP - XF / 2
                comp.append((k + 1, round(gap, 2)))
        st = t_new + (x['start'] - pos)
        en = t_new + (x['end'] - pos)
        times.append({'k': k + 1, 'para': para_of[k], 'start': round(st, 3), 'end': round(en, 3), 'text': sents[k], 'read': sents[k],
                      'parts': [[round(st + p0 - x['start'], 3), round(st + p1 - x['start'], 3)] for p0, p1 in x['parts']],
                      'orig': [round(x['start'], 3), round(x['end'], 3)], 'match': x['ratio']})
    end_orig = al[-1]['end'] + 0.1
    pieces.append((pos, end_orig))
    # 拼接
    mono = y if y.ndim == 1 else y.mean(axis=1)
    xf = int(XF * sr)
    out = np.zeros(int(round((LEAD - fade_in) * sr)), dtype=np.float64)
    for n, (p0, p1) in enumerate(pieces):
        seg = mono[int(round(p0 * sr)):int(round(p1 * sr))].astype(np.float64)
        if n == 0:
            f = int(fade_in * sr)
            seg[:f] *= np.linspace(0, 1, f)
        if n and xf:
            ramp = np.linspace(0, 1, xf)
            out[-xf:] = out[-xf:] * (1 - ramp) + seg[:xf] * ramp
            seg = seg[xf:]
        out = np.concatenate([out, seg])
    f = int(0.1 * sr)
    out[-f:] *= np.linspace(1, 0, f)
    out = np.concatenate([out, np.zeros(int(TAIL * sr))])
    return (out, times, comp), []


CEIL = 10 ** (-1.5 / 20)        # 限幅上限 −1.5 dBFS（编码成 MP3 后峰值仍 ≤ −1，成品实测）


def limit(x, sr):
    """前瞻限幅（与 TTS 处理链的限幅同一思路）：只在样本超过上限的地方、在前后 5 毫秒内平滑地把增益压下来，其余样本不动。
    返回（处理后的音频，统计：最大压低 dB、被压低的时长比例）。"""
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    need = np.minimum(1.0, CEIL / np.maximum(np.abs(x), 1e-9))
    L = int(0.005 * sr)
    env = minimum_filter1d(need, size=2 * L + 1)
    env = uniform_filter1d(env, size=L + 1)
    env = np.minimum(env, need)
    y = x * env
    return y, {'max_db': round(float(-20 * np.log10(env.min())), 2), 'frac': round(float((env < 0.999).mean()), 5)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ids', nargs='*', default=list(WIN))
    ap.add_argument('--wav', default='/home/user/wav/tem8-2025.wav')
    a = ap.parse_args()
    import hashlib
    h = hashlib.sha256(Path(a.wav).read_bytes()).hexdigest()
    if h != 'e7973102a3bba6358bc97e4a32af7efb20e1a871cbc8921fb8b325444bb7e1c7':
        raise SystemExit(f'原音 sha256 不对：{h}')
    y, sr = sf.read(a.wav)
    if y.ndim == 2:
        d = np.abs(y[:, 0] - y[:, 1]).max()
        print(f'左右声道最大差 {d:.4f}（取平均成单声道）')
    mono = y.mean(axis=1) if y.ndim == 2 else y
    R = json.loads((SRC / '识别.json').read_text('utf-8'))
    T = read_text()
    tf = C4 / 'audio' / 'timings.json'
    allt = json.loads(tf.read_text('utf-8')) if tf.exists() else {'cet4_male': {}}
    rep = ['# 原音音轨对齐报告（程序生成）', '']
    bad = []
    for pid in a.ids:
        res, errs = build(pid, T[pid], R, mono, sr)
        if errs:
            bad += errs
            continue
        out, times, comp = res
        meter = pyln.Meter(sr)
        speech = np.concatenate([out[int(t['start'] * sr):int(t['end'] * sr)] for t in times])
        lufs = meter.integrated_loudness(out)
        g = 10 ** ((-16.0 - lufs) / 20)
        out, gr = limit(out * g, sr)
        lufs2 = meter.integrated_loudness(out)
        out = out * 10 ** ((-16.0 - lufs2) / 20)          # 限幅后响度略降，再补一次整体增益（峰值仍在上限内，下面实测）
        out, gr2 = limit(out, sr)
        peak = 20 * np.log10(np.abs(out).max())
        lufs3 = meter.integrated_loudness(out)
        if peak > -1.0 or abs(lufs3 + 16) > 0.3:
            bad.append(f'{pid} 响度 {lufs3:.2f} LUFS、峰值 {peak:.2f} dBFS 不合格')
            continue
        dev = []
        for t in times:
            s = out[int(t['start'] * sr):int(t['end'] * sr)]
            dev.append(meter.integrated_loudness(s) if len(s) > sr * 0.5 else float('nan'))
        dst = C4 / 'audio' / '原音'
        dst.mkdir(parents=True, exist_ok=True)
        wav = dst / f'{pid}.wav'
        sf.write(wav, out.astype(np.float32), sr, subtype='PCM_16')
        mp3 = dst / f'{pid}.mp3'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(wav), '-ar', '24000', '-ac', '1', '-c:a', 'libmp3lame', '-b:a', '192k', str(mp3)], check=True)
        wav.unlink()
        dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(mp3)],
                                   capture_output=True, text=True).stdout)
        allt['cet4_male'][pid] = {'file': f'原音/{pid}.mp3', 'duration': round(dur, 3), 'source': '原音',
                                  'loudness': {'integrated_lufs': round(lufs3, 2), 'peak_dbfs': round(peak, 2), 'limiter_max_db': gr['max_db'], 'limiter_frac': gr['frac']},
                                  'compressed_gaps': comp, 'sentences': times}
        dd = [x for x in dev if x == x]
        rep += [f'## {pid}', f'- {len(times)} 句，成品 {dur:.2f} 秒（原音 {times[-1]["orig"][1] - times[0]["orig"][0]:.1f} 秒）',
                f'- 压到 2 秒的等待 {len(comp)} 处：' + '，'.join(f'第 {k} 句前 {g_}s' for k, g_ in comp),
                f'- 整体 {lufs3:.2f} LUFS，峰值 {peak:.2f} dBFS；前瞻限幅最多压低 {gr["max_db"]} dB、占 {gr["frac"]:.3%} 的时长；逐句响度 {min(dd):.1f}—{max(dd):.1f} LUFS（原音，只作参考）',
                f'- 对上比例最低的 5 句：' + '，'.join(f'第 {t["k"]} 句 {t["match"]:.0%}' for t in sorted(times, key=lambda t: t['match'])[:5]), '']
        print(f'{pid}: {len(times)} 句 {dur:.1f}s，压缩 {len(comp)} 处，{lufs3:.2f} LUFS，峰值 {peak:.2f} dBFS，限幅最多 {gr["max_db"]} dB（{gr["frac"]:.3%}）')
    if bad:
        print('停止：\n  ' + '\n  '.join(bad))
        sys.exit(1)
    tf.write_text(json.dumps(allt, ensure_ascii=False, indent=1), 'utf-8')
    (C4 / 'audio' / '对齐报告.md').write_text('\n'.join(rep), 'utf-8')


if __name__ == '__main__':
    main()
