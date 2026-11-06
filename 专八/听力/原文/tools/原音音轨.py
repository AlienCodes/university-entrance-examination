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

六级听力原文精读（2026-11-04）也用本程序（原音的条目只许一个程序写，踩坑 87）：
    /opt/ttsenv/bin/python 专八/听力/原文/tools/原音音轨.py --cet6 202512-1 --mp3 /home/user/wav/cet6-202512-1.mp3
文字 六级/听力/精读/原文.txt 的 ## <套>（切句.py 从练习会话的 定稿.json 生成），“识别词”= 定稿.json 的逐词时刻（同一份文字，几乎全对上）；
原音 sha256 必须在 六级/听力/原始材料/SHA256SUMS；输出 六级/听力/精读/audio/。
六级是原音模式（raw6，铁律 25 精读例外，总协调 2026-11-04 定）：不增益、不限幅、不重采样、声道照原音，只把句间 > 2 秒的纯静音删到 2 秒
（停顿里有声音就整段保留；删的段 removed_check 再核；MP3 256k 编码后语音段与原音逐样本比 seg_match，不过就停）。
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
        if line.startswith('# '):
            continue
        if line.startswith('## '):
            cur = line[3:].strip()
            out[cur] = [[]]
        elif cur and not line.strip():
            if out[cur][-1]:
                out[cur].append([])
        elif cur:
            if re.search(r' [—–] |\s--\s|"|\'', line):        # 排版与专八阅读一致：破折号不带空格（L3 第 25 句 “sleep — plants” 截图报行首破折号）、弯引号、弯撇号
                raise SystemExit(f'原文.txt 排版不统一（带空格的破折号或直引号）：{line[:60]}')
            out[cur][-1].append(line.strip())
    return {k: [p for p in v if p] for k, v in out.items()}


def norm(w):
    w = w.lower().replace('’', "'")
    return re.sub(r"[^a-z0-9']", '', w).rstrip("'")      # 词尾所有格撇号（Higgins’ well）对齐时不计


NUM = {'1': 'one', '2': 'two', '3': 'three', '4': 'four', '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine', '10': 'ten',
       '20': 'twenty', '24': 'twentyfour', '2025': 'twentytwentyfive', '19th': 'nineteenth'}


FIXOLD = set()        # 六级：原文订正.json 里被替换掉的旧词（定稿的逐词时刻还是旧拼写，Thorn → Foreign），对不上不算漏转录


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
        if j not in used_b and x[0] not in FIXOLD and not any(s0 - 0.05 <= x[1] <= s1 + 0.05 for s0, s1 in spans):
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
    global DB, THR
    DB, THR = db, thr
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


def gap_speech(db, thr, a, b):
    """删掉的一段 [a, b) 秒里有没有声音：10 毫秒帧电平超过门限的帧数 ≥ 3 就算有。门限 = 对齐时的句子起止门限（噪声底 + 15 dB），
    但不低于 −60 dBFS（六级原音句间多是数字静音，噪声底是 −240，−97 dB 的编码毛刺不是声音）。返回有声音的时刻或 None。"""
    seg = db[int(a * 100):int(b * 100)]
    hot = np.nonzero(seg > max(thr, -60.0))[0]
    return round(a + hot[0] / 100, 2) if len(hot) >= 3 else None


def removed_check(pid, db, thr, removed):
    """原音模式：删掉的每一段 [a, b) 都必须是纯静音（gap_speech 为 None），有一段有声音就报。"""
    return [f'{pid} 删掉的 {a:.2f}—{b:.2f}s 里 {t}s 有声音（只许删纯静音）' for a, b in removed if (t := gap_speech(db, thr, a, b)) is not None]


def build(pid, paras, R, y, sr, src=None):
    """src：成品用的原声（六级原音模式，原声道、原采样率、不增益）；不给就用单声道 y（专八旧做法）。"""
    al, errs = align(pid, paras, R, y, sr)
    if errs:
        return None, errs
    sents = [s for p in paras for s in p]
    para_of = [pi + 1 for pi, p in enumerate(paras) for _ in p]
    fade_in = 0.04
    pos = al[0]['start'] - fade_in                    # 当前这一段在原音里的起点
    pieces, t_new, times, comp = [], LEAD - fade_in, [], []     # t_new：当前这一段起点在成品里的时刻
    kept, removed = [], []
    for k, x in enumerate(al):
        if k:
            gap = x['start'] - al[k - 1]['end']
            cut_a = al[k - 1]['end'] + KEEP
            if gap > MAXGAP and src is not None and gap_speech(DB, THR, cut_a + XF / 2, x['start'] - KEEP - XF / 2) is not None:
                kept.append((k + 1, round(gap, 2)))     # 原音模式（铁律 25 唯一例外）：停顿里有声音（没转写的笑声、口语）就整段保留，只删纯静音
            elif gap > MAXGAP:                          # 压缩：保留上一句后 1 秒、下一句前 1 秒
                pieces.append((pos, cut_a + XF / 2))
                t_new += (cut_a + XF / 2 - pos) - XF           # 下一段与这一段重叠 XF（交叉淡化）
                pos = x['start'] - KEEP - XF / 2
                comp.append((k + 1, round(gap, 2)))
                removed.append((cut_a + XF / 2, x['start'] - KEEP - XF / 2))
        st = t_new + (x['start'] - pos)
        en = t_new + (x['end'] - pos)
        times.append({'k': k + 1, 'para': para_of[k], 'start': round(st, 3), 'end': round(en, 3), 'text': sents[k], 'read': sents[k],
                      'parts': [[round(st + p0 - x['start'], 3), round(st + p1 - x['start'], 3)] for p0, p1 in x['parts']],
                      'orig': [round(x['start'], 3), round(x['end'], 3)], 'match': x['ratio']})
    if src is not None:
        errs += removed_check(pid, DB, THR, removed)       # 独立再核：删掉的每一段都是纯静音
    if errs:
        return None, errs
    build.kept = kept
    end_orig = al[-1]['end'] + 0.1
    pieces.append((pos, end_orig))
    # 拼接
    mono = (y if y.ndim == 1 else y.mean(axis=1)) if src is None else src
    xf = int(XF * sr)
    out = np.zeros((int(round((LEAD - fade_in) * sr)),) + mono.shape[1:], dtype=np.float64)
    for n, (p0, p1) in enumerate(pieces):
        seg = mono[int(round(p0 * sr)):int(round(p1 * sr))].astype(np.float64)
        if n == 0:
            f = int(fade_in * sr)
            seg[:f] *= np.linspace(0, 1, f).reshape((-1,) + (1,) * (seg.ndim - 1))
        if n and xf:
            ramp = np.linspace(0, 1, xf).reshape((-1,) + (1,) * (seg.ndim - 1))
            out[-xf:] = out[-xf:] * (1 - ramp) + seg[:xf] * ramp
            seg = seg[xf:]
        out = np.concatenate([out, seg])
    f = int(0.1 * sr)
    out[-f:] *= np.linspace(1, 0, f).reshape((-1,) + (1,) * (out.ndim - 1))
    out = np.concatenate([out, np.zeros((int(TAIL * sr),) + out.shape[1:])])
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


def cet6_setup(sid, mp3, lv='六级'):
    """六级 / 四级模式（lv）：换成 <lv>/听力/精读 的目录、窗口、“识别词”（定稿逐词时刻）、限幅上限；返回 (R, y, sr, META 一条)。
    四级（2026-11-06）与六级同一套做法，只换目录、原音文件名（cet4-<定稿.json 的 录音>.mp3，如 cet4-t202206-1、cet4-s202209-1）和试卷名。"""
    global C4, CEIL
    import hashlib
    pre = {'六级': 'cet6', '四级': 'cet4'}[lv]
    C4 = ROOT / lv / '听力' / '精读'
    CEIL = 10 ** (-2.5 / 20)
    d = json.loads((ROOT / lv / '听力' / sid / '定稿.json').read_text('utf-8'))
    want = f"{pre}-{d['录音']}.mp3" if lv == '四级' else f'{pre}-{sid}.mp3'     # 四级：定稿用的是哪一段录音（考试视频同一段）
    if Path(mp3).name != want:
        raise SystemExit(f'{sid} 的原音应是 {want}（定稿.json 的录音），给的是 {Path(mp3).name}')
    h = hashlib.sha256(Path(mp3).read_bytes()).hexdigest()
    sums = (ROOT / lv / '听力' / '原始材料' / 'SHA256SUMS').read_text('utf-8')
    if f'{h}  {want}' not in sums:
        raise SystemExit(f'原音 sha256 不在 SHA256SUMS（{want}）：{h}')
    wav = Path('/tmp') / f'{pre}raw-{sid}.wav'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(mp3), str(wav)], check=True)
    y, sr = sf.read(wav)
    wav.unlink()
    if d.get('待核'):
        raise SystemExit(f'{sid}：定稿.json 还有待核')
    W = [list(w[:3]) for w in d['词']]
    fx = json.loads((C4 / '原文订正.json').read_text('utf-8')).get(sid, [])
    FIXOLD.update(t for f in fx for t in set(toks(f[0])) - set(toks(f[1])))
    i = 0
    while i < len(W):                   # 解析补进来的词没有时刻：在前一个词的终点与后一个词的起点之间均分（句子起止随后按能量细化）
        if W[i][1] is None:
            j = i
            while j < len(W) and W[j][1] is None:
                j += 1
            t0 = W[i - 1][2] if i else 0.0
            t1 = W[j][1] if j < len(W) else t0 + 0.4 * (j - i)
            step = (t1 - t0) / (j - i)
            for q in range(i, j):
                W[q][1], W[q][2] = round(t0 + step * (q - i), 3), round(t0 + step * (q - i + 1), 3)
            i = j
        i += 1
    R = [[t, w[1], w[2]] for w in W for t in toks(w[0])]
    # 订正里一对一换掉的词（Sara → Sarah、Roger → Rogers、Thorn → Foreign）：“识别词”也照换，只换新文字里已经没有的旧词
    T6 = {t for p in read_text().get(sid, []) for x in p for t in toks(x)}
    for f in fx:
        o_, n_ = toks(f[0]), toks(f[1])
        if len(o_) == len(n_):
            for a_, b_ in zip(o_, n_):
                if a_ != b_ and a_ not in T6:
                    for r in R:
                        if r[0] == a_:
                            r[0] = b_
        elif ''.join(o_).replace("'", '') == ''.join(n_).replace("'", '') and o_:      # 四级：只是拆 / 并（That s → That’s、user friendly → user-friendly 不拆的写法）：识别词同样拆并，时刻取首尾
            i = 0
            while i + len(o_) <= len(R):
                if [r[0] for r in R[i:i + len(o_)]] == o_:
                    a_, b_ = R[i][1], R[i + len(o_) - 1][2]
                    st = (b_ - a_) / len(n_)
                    R[i:i + len(o_)] = [[t, round(a_ + st * q, 3), round(a_ + st * (q + 1), 3)] for q, t in enumerate(n_)]
                    i += len(n_)
                else:
                    i += 1
    WIN[sid] = (0.0, len(y) / sr + 1)
    yy, mm, n = sid[:4], int(sid[4:6]), sid[-1]
    return R, y, sr, (f'{yy}年{mm}月大学英语{lv} 第{n}套', 'Part II Listening', int(yy), mm, int(n))      # passage 用英文斜体字体，只放英文（踩坑 64）


ORIG_MAX_GAIN_DB, ORIG_MIN_SNR_DB, ORIG_MAX_SEC_DB = 0.05, 30.0, 1.0     # 与 专八/听力/tools/听力视频.orig_match 同一套门限（MP3 256k 实测：语音段信噪比约 60 dB；192k 时 LAME 低通让增益差到 −0.27 dB，不用）


def seg_match(pairs, sr):
    """语音段与原音逐样本比（铁律 25 精读例外：只许删纯静音，语音一点不动）：pairs = [(原音这一句, 成品这一句), …]，
    整体增益差 ≤ 0.05 dB、残差信噪比 ≥ 30 dB、逐秒电平差 ≤ 1 dB（> −50 dBFS 的秒）；返回 (问题列表, 测量值)。"""
    ref = np.concatenate([p for p, _ in pairs]); dec = np.concatenate([q for _, q in pairs])
    if ref.shape != dec.shape:
        return [f'语音段形状 {dec.shape} ≠ 原音 {ref.shape}'], {}
    ref = ref.reshape(len(ref), -1); dec = dec.reshape(len(dec), -1)
    e = (ref * ref).sum()
    g = 20 * np.log10(max((dec * ref).sum() / e, 1e-12)); r = dec - ref
    snr = 10 * np.log10(e / max((r * r).sum(), 1e-30))
    n = len(ref) // sr
    ra = np.sqrt((ref[:n * sr] ** 2).reshape(n, -1).mean(1)); rd = np.sqrt((dec[:n * sr] ** 2).reshape(n, -1).mean(1))
    m = ra > 10 ** (-50 / 20)
    sec = float(np.abs(20 * np.log10(np.maximum(rd[m], 1e-12) / ra[m])).max()) if m.any() else 0.0
    bad = []
    if abs(g) > ORIG_MAX_GAIN_DB: bad.append(f'语音段与原音整体音量差 {g:+.3f} dB')
    if snr < ORIG_MIN_SNR_DB: bad.append(f'语音段与原音残差信噪比 {snr:.1f} dB')
    if sec > ORIG_MAX_SEC_DB: bad.append(f'语音段与原音逐秒电平差最多 {sec:.2f} dB')
    return bad, {'gain_db': round(float(g), 4), 'snr_db': round(float(snr), 1), 'sec_db': round(sec, 3)}


def raw6(pid, paras, R, mono, y, sr, allt, rep):
    """六级精读原音模式（总协调 2026-11-04 定，铁律 25 唯一例外）：不增益、不压缩、不限幅、不重采样、声道照原音；
    句间超过 2 秒的纯静音删到 2 秒（删的段里有声音就停），垫片头 1.5 秒、片尾 2.2 秒数字静音；
    编码后解码，逐句与原音逐样本比（seg_match），不过就停、不写 timings。"""
    res, errs = build(pid, paras, R, mono, sr, src=y)
    if errs:
        return errs
    out, times, comp = res
    if np.abs(out).max() > 1.0:
        return [f'{pid} 拼接后样本超过满幅（原音不许限幅）']
    dst = C4 / 'audio' / '原音'
    dst.mkdir(parents=True, exist_ok=True)
    wav, mp3 = dst / f'{pid}.wav', dst / f'{pid}.mp3'
    sf.write(wav, out.astype(np.float32), sr, subtype='FLOAT')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(wav), '-c:a', 'libmp3lame', '-b:a', '256k', str(mp3)], check=True)      # 256k：语音段信噪比实测见对齐报告（门限 30 dB）
    wav.unlink()
    ch = y.shape[1] if y.ndim == 2 else 1
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp3), '-f', 'f32le', '-ac', str(ch), '-ar', str(sr), '-'], capture_output=True, check=True).stdout
    dec = np.frombuffer(raw, dtype=np.float32).astype(np.float64).reshape(-1, ch)
    src = y.reshape(len(y), -1)
    pairs = []
    for t in times:
        n = int(round((t['orig'][1] - t['orig'][0]) * sr))
        a0, b0 = int(round(t['orig'][0] * sr)), int(round(t['start'] * sr))
        pairs.append((src[a0:a0 + n], dec[b0:b0 + n]))
    probs, meas = seg_match(pairs, sr)
    if probs:
        mp3.unlink()
        return [f'{pid} ' + p for p in probs]
    sys.path.insert(0, str(ROOT / 'tools' / 'tts'))
    import 听对                         # 踩坑 124：每句的时间窗独立听一遍，与原文对不上 = 时刻放错了地方（对上比例是原文比原文，查不出）
    heard = 听对.problems(听对.load16(mp3), [(t['start'], t['end']) for t in times], [s for p in paras for s in p])
    if heard:
        mp3.unlink()
        return [f'{pid} 第 {k} 句听到的与原文对不上（相似度 {r}）：{s} ｜ 听到：{h}' for k, r, s, h in heard]
    meter = pyln.Meter(sr)
    lufs = meter.integrated_loudness(dec)
    peak = 20 * np.log10(np.abs(dec).max())
    dur = len(dec) / sr
    allt['cet4_male'][pid] = {'file': f'原音/{pid}.mp3', 'duration': round(dur, 3), 'source': '原音', 'mode': '原音不动',
                              'sample_rate': sr, 'channels': ch, 'raw_match': meas,
                              'loudness': {'integrated_lufs': round(lufs, 2), 'peak_dbfs': round(peak, 2), '说明': '原音不增益，只记录'},
                              'compressed_gaps': comp, 'kept_gaps': build.kept, 'sentences': times}
    rep += [f'## {pid}', f'- {len(times)} 句，成品 {dur:.2f} 秒（原音 {times[-1]["orig"][1] - times[0]["orig"][0]:.1f} 秒），{sr} Hz {ch} 声道（照原音）',
            f'- 删到 2 秒的纯静音 {len(comp)} 处：' + '，'.join(f'第 {k} 句前 {g_}s' for k, g_ in comp),
            f'- 停顿里有声音、整段保留的 {len(build.kept)} 处：' + '，'.join(f'第 {k} 句前 {g_}s' for k, g_ in build.kept),
            f'- 原音不动：语音段与原音逐样本比 增益差 {meas["gain_db"]:+.4f} dB、信噪比 {meas["snr_db"]} dB、逐秒电平差 ≤ {meas["sec_db"]} dB；整体 {lufs:.2f} LUFS、峰值 {peak:.2f} dBFS（只记录）',
            f'- 对上比例最低的 5 句：' + '，'.join(f'第 {t["k"]} 句 {t["match"]:.0%}' for t in sorted(times, key=lambda t: t['match'])[:5]), '']
    print(f'{pid}: {len(times)} 句 {dur:.1f}s，删纯静音 {len(comp)} 处，原音比对 {meas}，{lufs:.2f} LUFS，峰值 {peak:.2f} dBFS')
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ids', nargs='*', default=list(WIN))
    ap.add_argument('--wav', default='/home/user/wav/tem8-2025.wav')
    ap.add_argument('--cet6', help='六级听力原文精读的一套，如 202512-1')
    ap.add_argument('--cet4', help='四级听力原文精读的一套，如 202206-1（与 --cet6 同一套做法）')
    ap.add_argument('--mp3', help='六级 / 四级模式：这一套的原音 mp3')
    a = ap.parse_args()
    import hashlib
    LV = '六级'
    if a.cet4:
        a.cet6, LV = a.cet4, '四级'      # 下面的六级分支四级照走（目录已由 cet6_setup 换成 四级/听力/精读）
    if a.cet6:
        R, y, sr, M6 = cet6_setup(a.cet6, a.mp3, LV)
        a.ids = [a.cet6]
    else:
        h = hashlib.sha256(Path(a.wav).read_bytes()).hexdigest()
        if h != 'e7973102a3bba6358bc97e4a32af7efb20e1a871cbc8921fb8b325444bb7e1c7':
            raise SystemExit(f'原音 sha256 不对：{h}')
        y, sr = sf.read(a.wav)
    if y.ndim == 2:
        d = np.abs(y[:, 0] - y[:, 1]).max()
        print(f'左右声道最大差 {d:.4f}（取平均成单声道）')
    mono = y.mean(axis=1) if y.ndim == 2 else y
    if not a.cet6:
        R = json.loads((SRC / '识别.json').read_text('utf-8'))
    T = read_text()
    # 句子定稿（ann_lib / build_vocab 读 阅读/sents.json，ZB_ROOT=专八/听力/原文）：每次从 原文.txt 重写，保证与音轨同一份文字
    META = {'L1': ('Section A', 'A'), 'L2': ('Section B Part One', 'B'), 'L3': ('Section B Part Two', 'B')}
    (C4 / '阅读').mkdir(exist_ok=True)
    if a.cet6:              # 六级：sents.json 里每套一条，只换这一套
        sj = C4 / '阅读' / 'sents.json'
        rows = [r for r in (json.loads(sj.read_text('utf-8')) if sj.exists() else []) if r['id'] != a.cet6]
        rows.append({'id': a.cet6, 'year': M6[2], 'month': M6[3], 'set': M6[4], 'passage': M6[1], 'paper': M6[0], 'part': 'L', 'words': 0, 'sents': T[a.cet6]})
        sj.write_text(json.dumps(sorted(rows, key=lambda r: r['id']), ensure_ascii=False, indent=1), 'utf-8')
    else:
        (C4 / '阅读' / 'sents.json').write_text(json.dumps(
            [{'id': k, 'year': 2025, 'month': 3, 'set': 1, 'passage': META[k][0], 'paper': '2025年专八听力', 'part': META[k][1], 'words': 0, 'sents': v}
             for k, v in T.items()], ensure_ascii=False, indent=1), 'utf-8')
    tf = C4 / 'audio' / 'timings.json'
    tf.parent.mkdir(parents=True, exist_ok=True)
    allt = json.loads(tf.read_text('utf-8')) if tf.exists() else {'cet4_male': {}}
    rep = ['# 原音音轨对齐报告（程序生成）', '']
    bad = []
    for pid in a.ids:
        if a.cet6:
            r6 = raw6(pid, T[pid], R, mono, y, sr, allt, rep)
            if r6:
                bad += r6
            continue
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
        if peak > 20 * np.log10(CEIL) + 0.5 or abs(lufs3 + 16) > 0.3:
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
    (C4 / 'audio' / (f'对齐报告_{a.cet6}.md' if a.cet6 else '对齐报告.md')).write_text('\n'.join(rep), 'utf-8')


if __name__ == '__main__':
    main()
