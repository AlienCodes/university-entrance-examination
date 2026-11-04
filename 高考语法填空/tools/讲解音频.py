"""讲解视频配音的完整处理链（本机做；原始 WAV 由 GitHub Actions 上的 qwen_synth.py 合成）。

规则全部复用 tools/tts/gaokao_tts（只写一处）：每段 segment（段内电平统一 even + BS.1770 统一 level_clause + 淡入淡出）
→ 按稿子的停顿拼接 → master（压缩、按意群 clause_trim、−16 LUFS、限幅）→ final_check（含意群级，关不掉）→ 合格证。
电磁音（铁律 10）：Qwen3-TTS 声码器自己的固定频点（2026-10-30 统计 5 个音色 13 次合成：下列频点在 8—12 组里高出周围 3—6 dB，
Kokoro 当年是 +11—12 dB）。做法与用户确认的 四级/tools/debuzz.py 相同：每段合成后只在这几个频点做 60 Hz 带宽单向陷波，
检查也同样只在这些频点 ±8 Hz 量（成品语音部分，上限 +3 dB）。全频段扫描 tonal_scan 只作参考、不作判据：
用户确认“完全没有电磁音”的 c40 用全频段扫描也有 +5.8 dB（语音本身的随机起伏），全频段 +3 dB 会把无电磁音的音频误判。

意群：Qwen 每段整段合成、自己会停顿；段内静音（≥ 0.15 秒）把一段切成几个意群，交给 fine_check 与 clause_trim。
用法：python 讲解音频.py --稿 稿.json --wav 原始目录 --out 成品.mp3 [--lead 1.5 --tail 2.0]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/tts'))
import gaokao_tts as G  # noqa: E402
import 去呼吸 as BR  # noqa: E402  去呼吸声（踩坑 89），规则只写一处

SR = G.SR
BUZZ_MAX_DB = 3.0
NOTCH = [5184, 5472, 8778, 10163, 10447, 10778, 10924, 11455]   # Qwen3-TTS 声码器固定频点（Hz）


def load(path):
    import soundfile as sf
    import soxr
    x, sr = sf.read(str(path), dtype='float32')
    if x.ndim > 1:
        x = x.mean(1)
    if sr != SR:
        x = soxr.resample(x, sr, SR, quality='VHQ').astype(np.float32)
    return x


def inner_parts(x, sr=SR, min_sil=0.15, db=-42):
    """段内停顿切出的意群 [(起, 止)]（秒，相对本段）。"""
    H = int(0.01 * sr)
    n = len(x) // H
    e = 20 * np.log10(np.sqrt(np.mean(x[:n * H].reshape(n, H) ** 2, 1)) + 1e-9)
    on = e > (e.max() + db)
    spans, s = [], None
    for i, v in enumerate(on):
        if v and s is None:
            s = i
        if not v and s is not None:
            spans.append([s, i])
            s = None
    if s is not None:
        spans.append([s, n])
    merged = []
    for sp in spans:
        if merged and (sp[0] - merged[-1][1]) * 0.01 < min_sil:
            merged[-1][1] = sp[1]
        else:
            merged.append(sp)
    return [(a * 0.01, b * 0.01) for a, b in merged]


# 每个意群的峰值上限（dBFS）：意群统一到 CLAUSE_LUFS（−23）后，母带整体加约 +7 dB 到 −16 LUFS，限幅器门槛 −1.5 dBFS，
# 所以意群这一级把峰值先限到 −23 + 14.5 = −8.5，母带的限幅器几乎不用再动手。
# 2026-10-30 实测：Qwen3-TTS 的瞬态比 Kokoro 尖，不这样做时母带限幅器要压掉 6.4 dB、约 4% 的采样被压 > 1 dB，
# 尖峰多的意群被压得多，成品里比相邻意群小 1.3—1.8 LU（意群检查报错）。用的是共用处理链同一个前瞻限幅器 G.limit，只是挪到意群这一级、
# 并在之后再按 BS.1770 统一一次（level_clause）。
PEAK_CLAUSE = G.CLAUSE_LUFS + 14.5


def per_clause(x, sr=SR, min_dur=0.5):
    """每个意群各过一次 G.segment（段内电平统一 + BS.1770 统一 + 淡入淡出），意群之间的停顿原样保留。
    与共用处理链的设计一致：Kokoro 按逗号逐个意群合成、每个意群过一次 segment；Qwen 一次合成一整段（含几个意群），
    若整段只过一次 segment，意群之间的电平差没人管，母带的 clause_trim 补上的增益又会被限幅器吃掉（2026-10-30 男老师样音：
    第 2 段英文句末意群低 1.7—3.4 LU，3 次合成、逐段换遍都过不了意群检查）。
    不足 min_dur 的意群并入相邻意群（与 clause_trim 一样，太短的段 BS.1770 量不准）。返回 (音频, [(起, 止)…] 秒)。"""
    P = [list(p) for p in inner_parts(x, sr)]
    M = []
    for p in P:
        if M and (p[1] - p[0] < min_dur or M[-1][1] - M[-1][0] < min_dur):
            M[-1][1] = p[1]
        else:
            M.append(p)
    pad = 0.03
    out, parts, t, prev = [], [], 0.0, 0
    for a, b in M:
        i0, i1 = max(prev, int((a - pad) * sr)), min(len(x), int((b + pad) * sr))
        if i0 > prev:
            out.append(np.zeros(i0 - prev, np.float32))
            t += (i0 - prev) / sr
        y = G.level_clause(G.limit(G.segment(x[i0:i1]), sr, PEAK_CLAUSE))
        parts.append((t + pad if i0 > 0 else t, t + len(y) / sr - (pad if i1 < len(x) else 0)))
        out.append(y)
        t += len(y) / sr
        prev = i1
    return np.concatenate(out), [(round(p, 3), round(q, 3)) for p, q in parts]


def notch(x, sr):
    if not NOTCH:
        return x
    from scipy.signal import iirnotch, lfilter
    y = x.astype(np.float64)
    for f0 in NOTCH:
        b, a = iirnotch(f0, f0 / 60.0, sr)
        y = lfilter(b, a, y)
    y = y.astype(np.float32)
    y[x == 0] = 0
    return y


def tone_check(a, sr, items):
    """只在声码器固定频点 ±8 Hz 量（与 四级/tools/debuzz.measure 同一量法）。返回 (最强频点, dB)。"""
    from scipy.ndimage import median_filter
    from scipy.signal import welch
    sp = np.concatenate([a[int(s['start'] * sr):int(s['end'] * sr)] for s in items]).astype(np.float64)
    f, P = welch(sp, sr, nperseg=65536)
    r = 10 * np.log10(P + 1e-20)
    r = r - median_filter(r, 61)
    m = {f0: float(r[(f > f0 - 8) & (f < f0 + 8)].max()) for f0 in NOTCH}
    f0 = max(m, key=m.get)
    return f0, round(m[f0], 1)


def tonal_scan(a, sr, items, fmin=2000):
    """全频段窄带峰：语音部分的功率谱减去 61 点中值，2 kHz 以上的最大值（dB）及前 5 个峰。"""
    from scipy.ndimage import median_filter
    from scipy.signal import welch
    sp = np.concatenate([a[int(s['start'] * sr):int(s['end'] * sr)] for s in items]).astype(np.float64)
    f, P = welch(sp, sr, nperseg=65536)
    r = 10 * np.log10(P + 1e-20)
    r = r - median_filter(r, 61)
    m = f >= fmin
    idx = np.argsort(r[m])[::-1]
    top, used = [], []
    for i in idx:
        fr = float(f[m][i])
        if all(abs(fr - u) > 30 for u in used):
            used.append(fr)
            top.append((round(fr), round(float(r[m][i]), 1)))
        if len(top) == 5:
            break
    return top[0][1], top


TEMPO = 1.0     # 语音提速倍数（用户 2026-11-03 嫌慢；模型说得比参考慢）。1.0 = 不动；≠ 1 时用 Rubber Band R3（高质量、音高不变）只拉语音，
                # 停顿另外按稿子放，不受影响。只在本机用（Actions 合成机上没装 rubberband）；提速版必须过 提速验证.py（前后识别、相似度、自然度）


def stretch(x, sr, tempo):
    import subprocess
    import tempfile
    import soundfile as sf
    with tempfile.TemporaryDirectory() as d:
        i, o = Path(d) / 'i.wav', Path(d) / 'o.wav'
        sf.write(str(i), x, sr, subtype='FLOAT')
        subprocess.run(['rubberband', '-q', '-3', '-T', str(tempo), str(i), str(o)], check=True, capture_output=True)
        y, _ = sf.read(str(o), dtype='float32')
    return y if y.ndim == 1 else y.mean(1)


PITCH_SEMIS = 0.0          # 降几个半音（保共振峰；用户 2026-11-03 嫌开头“太尖太细”，要浑厚）。0 = 不动（输出逐字节不变）
PITCH_METHOD = 'rubberband'  # 'rubberband'（R3 --formant）或 'world'（pyworld：保持频谱包络只改基频）
TIMBRE_EQ = None           # 音色还原：[[f_lo, f_hi, dB], …]（每段 ±3 dB 内，线性相位 FIR）；None = 不动


def shift_pitch(x, sr, semis, method='rubberband'):
    """降 semis 个半音、保共振峰，长度不变。"""
    if method == 'world':
        import pyworld as pw
        from scipy.ndimage import maximum_filter1d
        d = x.astype(np.float64)
        f0, t = pw.harvest(d, sr, f0_floor=60, f0_ceil=500, frame_period=5.0)
        sp, ap = pw.cheaptrick(d, f0, t, sr), pw.d4c(d, f0, t, sr)
        y = pw.synthesize(f0 * 2 ** (-semis / 12), sp, ap, sr, frame_period=5.0).astype(np.float32)
        y = y[:len(x)] if len(y) >= len(x) else np.pad(y, (0, len(x) - len(y)))
        return y * maximum_filter1d((np.abs(x) > 1e-5).astype(np.float32), int(0.01 * sr))   # 真静音处保持真静音
    import subprocess
    import tempfile
    import soundfile as sf
    with tempfile.TemporaryDirectory() as d:
        i, o = Path(d) / 'i.wav', Path(d) / 'o.wav'
        sf.write(str(i), x, sr, subtype='FLOAT')
        subprocess.run(['rubberband', '-q', '-3', '--formant', '-p', f'{-semis:.4f}', str(i), str(o)], check=True, capture_output=True)
        y, _ = sf.read(str(o), dtype='float32')
    y = y if y.ndim == 1 else y.mean(1)
    return y[:len(x)] if len(y) >= len(x) else np.pad(y, (0, len(x) - len(y)))


def timbre_eq(x, sr, bands):
    from scipy.signal import fftconvolve, firwin2
    fs, gs = [0.0], [1.0]
    bands = sorted(bands)
    for k, (lo, hi, db) in enumerate(bands):
        assert abs(db) <= 3.0 + 1e-9, f'音色还原 {lo}-{hi} Hz {db} dB 超过 ±3 dB'
        g = 10 ** (db / 20)
        if lo * 0.8 > fs[-1]:                       # 与前一段不相接：从 1 平滑过渡
            fs.append(lo * 0.8)
            gs.append(1.0)
        fs += [lo, hi]                              # 相接处频率重复 = 台阶（firwin2 允许）
        gs += [g, g]
        if k + 1 == len(bands) or bands[k + 1][0] * 0.8 > hi * 1.25:
            fs.append(hi * 1.25)
            gs.append(1.0)
    h = firwin2(2049, fs + [sr / 2], gs + [1.0], fs=sr)
    return fftconvolve(x, h)[1024:1024 + len(x)].astype(np.float32)


def prep(x, sr=SR):
    """原始合成 → 去呼吸（任何电平处理之前，踩坑 89）→ 去首尾静音 →（可选）提速 →（可选）降音高保共振峰 / 音色还原 → 陷波。
    build 与 选段 都走这一个。"""
    y = G.trim(BR.debreath(x, sr)[0])
    if TEMPO != 1.0:
        y = G.trim(stretch(y, sr, TEMPO))
    if PITCH_SEMIS:
        y = shift_pitch(y, sr, PITCH_SEMIS, PITCH_METHOD)
    if TIMBRE_EQ:
        y = timbre_eq(y, sr, TIMBRE_EQ)
    return notch(y, sr)


def checks(a, items):
    """成品的电磁音（固定频点）与呼吸声检查；有问题抛 RuntimeError（render 与 Actions 上的 qwen_synth 共用）。返回 (f0, db)。"""
    f0, db = tone_check(a, G.OUT_SR, items)
    if db > BUZZ_MAX_DB:
        raise RuntimeError(f'电磁音：{f0} Hz 高出周围 {db} dB（上限 +{BUZZ_MAX_DB} dB），未输出')
    br = BR.breath_check(a, G.OUT_SR)
    if br:
        raise RuntimeError(f'呼吸声 {len(br)} 处（停顿里的非浊音孤岛，峰值 > {BR.CHK_FLOOR} dBFS）：{br[:6]}，未输出')
    return f0, db


MARK = '‖'
PAUSE_MARK = 0.45      # 稿里 ‖ 处的静音（秒）：用户录音句间停顿 10—90% 分位 0.18—0.46 秒、中位 0.28；第 2 版 0.55 用户嫌慢（2026-11-03），
                       # 缩到 0.40（仍明显长于普通句间停顿；讲解节奏.PAUSE_MIN 同步）
EN_RUN = re.compile(r"[A-Za-z][A-Za-z '’-]*[A-Za-z]")
ZH_PUNCT = '，。：；？！、'
EN_OF = {'，': ',', '。': '.', '：': ':', '；': ';', '？': '?', '！': '!', '、': ','}
LANG_GAP = {'，': 0.18, '、': 0.15, '：': 0.22, '；': 0.25, '。': 0.30, '？': 0.30, '！': 0.30}   # 中英换语种处的静音（秒），按那里的标点；
#                                    用户录音逗号处停顿约 0.15—0.25 秒、句号约 0.3 秒


WORD_GAP = 0.04       # mark+word：句中没有标点处中英切换的静音（秒），只够两段不粘连


def lang_split(text, words=False):
    """中文小段里成句的英文（≥ 2 个词、前后都是标点或段首段尾，如“It is common for them，”“答案就是：to be held。”）单独拆出来，
    按 English 合成（用户 2026-11-03：英文中文口音太重；Qwen 用 Chinese 合成中英混说时英文带口音）。夹在中文里的单个词（hold、it）照旧。
    返回 [(文字, 语种, 后面的静音秒或 None)]；没有可拆的返回一项。"""
    out, pos = [], 0
    for m in EN_RUN.finditer(text):
        a, b = m.span()
        before = text[:a].rstrip()
        after = text[b:].lstrip()
        if not words:
            if len(m.group().split()) < 2:
                continue
            if before and before[-1] not in ZH_PUNCT:
                continue
            if after and after[0] not in ZH_PUNCT:
                continue
        p = after[0] if after and after[0] in ZH_PUNCT else ''
        end = b + (len(text[b:]) - len(after)) + (1 if p else 0)
        head = text[pos:a].strip()
        if head:
            out.append([head, 'Chinese', LANG_GAP.get(head[-1], WORD_GAP if words else 0.18)])
        out.append([m.group() + EN_OF.get(p, ''), 'English', LANG_GAP.get(p, WORD_GAP if words else 0.18)])
        pos = end
    tail = text[pos:].strip()
    if tail:
        out.append([tail, 'Chinese', None])
    elif out:
        out[-1][2] = None
    return [tuple(x) for x in out] or [(text, 'Chinese', None)]


GAP_MAX = None        # 段间停顿上限（秒）；None = 按稿。用户本人录音句间停顿中位 0.31、90% 分位 0.47（拼接检查的停顿分布对照它）
SPLIT = 'mark+lang'   # 合成单位：'mark+lang' = ‖ 处拆 + 中文段里成句的英文单独拆（第 3 轮）；'mark' = 只在 ‖ 处拆；
#                       'mark+word' = 再把中文段里夹的单个英文词也拆出来按 English 合成（GPT-SoVITS 试验，2026-11-04；默认不用）；
#                       'none' = 整段一次合成（用户 2026-11-03：要流畅，少拼接）。任务清单的候选 split 设，选段 --拆分 同步


def units(seg):
    """一段 → 小段：稿里 ‖ 标出必须停顿的边界（说完词义、说完一步推理、答案前、问句后），每个小段单独合成、单独选优，
    拼接时中间放 PAUSE_MARK 秒真静音（停顿由构造保证；讲解节奏.check 用识别对齐独立量）。中文小段里成句的英文再单独拆出（lang_split），
    中间放按标点的短静音。没有 ‖、也没有可拆英文的段原样一个小段。"""
    mode = seg.get('split') or SPLIT          # 段上写了 split 就按段（选段 --退回：整段的停顿不够时只这一段退回拆段）
    if mode == 'none':                        # 整段一次合成（中英混说、‖ 都不拆；停顿用模型自然的停顿）
        return [dict(seg, text=seg['text'].replace(MARK, ''), seg_end=True)]
    ps = [p.strip() for p in seg['text'].split(MARK) if p.strip()]
    sub = []
    for k, p in enumerate(ps, 1):
        last_gap = PAUSE_MARK if k < len(ps) else seg.get('gap', 0.6)
        parts = (lang_split(p, words=mode == 'mark+word') if seg['lang'] == 'Chinese' and mode in ('mark+lang', 'mark+word')
                 else [(p, seg['lang'], None)])
        for j, (t, lang, g) in enumerate(parts):
            sub.append((t, lang, last_gap if j == len(parts) - 1 else g))
    if len(sub) <= 1:
        return [dict(seg, text=seg['text'].replace(MARK, ''), seg_end=True)]
    return [dict(seg, id=f"{seg['id']}~{k}", text=t, lang=lang, parent=seg['id'], gap=g, seg_end=k == len(sub))
            for k, (t, lang, g) in enumerate(sub, 1)]


# 合成长度上限与超时（踩坑 95：2026-11-03 第 3 轮 15 台合成机里 1 台某一段生成停不下来，卡 60 分钟被超时杀掉，整台没有产物）。
# Qwen3-TTS 12 Hz：每秒音频约 12.5 个 token；默认上限 2048（约 164 秒）。按文字估最长时长：汉字 0.45 秒、英文词 0.7 秒（都是
# 正常语速的 2 倍以上），另加 3 秒，换算成 token。生成结果顶到上限（≥ 上限的 95%）或单段超时，就当作“停不下来”，换种子重来。
TOK_PER_SEC = 12.5
UNIT_TIMEOUT = 420     # 秒：单段合成最长用时（实测最长的小段约 90 秒）
MAX_TRIES = 4


def token_cap(text, lang='Chinese'):
    zh = len(re.findall(r'[一-鿿]', text))
    en = len(re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", text))
    return int((zh * 0.45 + en * 0.7 + 3.0) * TOK_PER_SEC)


def run_unit(gen1, seed, cap, timeout=UNIT_TIMEOUT, tries=MAX_TRIES):
    """gen1(seed) → (音频, sr)。顶到上限或超时就换种子（seed + 7919·k）重来，最多 tries 次；都不行抛 RuntimeError。返回 (音频, sr, 第几次)。"""
    import signal

    def on_alarm(*_):
        raise TimeoutError

    last = None
    for k in range(tries):
        old = signal.signal(signal.SIGALRM, on_alarm)
        signal.alarm(int(timeout))
        try:
            x, sr = gen1(seed + 7919 * k)
        except TimeoutError:
            last = f'超时 {timeout} 秒'
            continue
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
        if len(x) / sr * TOK_PER_SEC >= 0.95 * cap:
            last = f'顶到上限 {cap} token（{len(x) / sr:.1f} 秒）'
            continue
        return x, sr, k + 1
    raise RuntimeError(f'换了 {tries} 个种子仍停不下来：{last}')


def expand(segs):
    return [u for s in segs for u in units(s)]


def build(segs, wavdir, lead=1.5, tail=2.0):
    """返回 (48 kHz 成品, items)。items 每段一条：start/end/parts（秒，成品时间轴）、id、text（稿原文，含 ‖）、units（小段的起止与文字）。
    原始音频按小段存（<段 id>~<k>.wav；没有 ‖ 的段就是 <段 id>.wav）。"""
    U = expand(segs)
    a, uitems = _build_units(U, wavdir, lead, tail)
    by = {}
    for u, it in zip(U, uitems):
        by.setdefault(u.get('parent', u['id']), []).append(it)
    items = []
    for k, s in enumerate(segs, 1):
        us = by[s['id']]
        items.append({'k': k, 'id': s['id'], 'start': us[0]['start'], 'end': us[-1]['end'],
                      'parts': [p for x in us for p in x['parts']], 'text': s['text'],
                      'units': [{'id': x['id'], 'start': x['start'], 'end': x['end'], 'text': x['text']} for x in us]})
    return a, items


def _build_units(segs, wavdir, lead, tail):
    pieces = [np.zeros(int(lead * SR), np.float32)]
    t, items = lead, []
    for k, s in enumerate(segs, 1):
        x = prep(load(Path(wavdir) / f"{s['id']}.wav"))
        x, parts = per_clause(x)
        dur = len(x) / SR
        items.append({'k': k, 'id': s['id'], 'start': round(t, 3), 'end': round(t + dur, 3),
                      'parts': [[round(t + p, 3), round(t + q, 3)] for p, q in parts], 'text': s['text']})
        pieces.append(x)
        t += dur
        g = s.get('gap', 0.6)
        if GAP_MAX is not None and s.get('seg_end', True):    # 只压段与段之间；‖ 处（PAUSE_MARK）和中英切换处不动
            g = min(g, GAP_MAX)
        g = tail + 0.05 if k == len(segs) else g     # 结尾多留 50 ms：成品实测结尾静音要 ≥ 2.0 秒（编码延迟会吃掉几毫秒，踩坑 10）
        pieces.append(np.zeros(int(round(g * SR)), np.float32))
        t += int(round(g * SR)) / SR
    a = G.master(np.concatenate(pieces), -16.0, parts=[p for it in items for p in it['parts']])
    return a, items


def render(segs, wavdir, out, lead=1.5, tail=2.0, rhythm=True):
    a, items = build(segs, wavdir, lead, tail)
    f0, db = checks(a, items)
    if rhythm:                     # 标记边界的停顿、问句尾音（识别对齐，独立量；只在本机做，Actions 上没有识别模型）
        import 讲解节奏 as NJ
        rrep, rerr = NJ.check(a, G.OUT_SR, items, {s['id']: s['text'] for s in segs})
        if rerr:
            raise RuntimeError('节奏：' + '；'.join(rerr[:6]) + '，未输出')
        import 拼接检查 as PJ        # 拼接衔接：音高跳变、响度台阶、相邻段语速差、停顿分布（门限取自本人录音）
        jerr = PJ.problems(PJ.boundaries_of(a, G.OUT_SR, items), json.loads(PJ.TARGET.read_text('utf-8')))
        if jerr:
            raise RuntimeError('拼接：' + '；'.join(jerr[:6]) + '，未输出')
        import 多音字 as PY          # 多音字声调（铁律 23；识别对齐 + 音高走向，独立量）
        trep, terr = PY.check_items(a, G.OUT_SR, items)
        if terr:
            raise RuntimeError('声调：' + '；'.join(terr[:6]) + '，未输出')
        import 清晰度 as QX          # 清晰度（踩坑 115）：两个中文识别器 + 4 kHz 以上能量 + 擦音对元音，门槛以老师真声为基准
        crep, cerr = QX.check(a, G.OUT_SR, items)
        if cerr:
            raise RuntimeError('；'.join(cerr) + '，未输出')
    mx, top = tonal_scan(a, G.OUT_SR, items)
    cert = G.save_checked(Path(out), a, items, -16.0)
    meta = {'duration': round(len(a) / G.OUT_SR, 3), 'items': items, 'rhythm': rrep if rhythm else None, 'tones': trep if rhythm else None, 'clarity': crep if rhythm else None, 'buzz_tone': [f0, db], 'buzz_top': top, 'certificate': cert, 'loudness': cert['loudness'],
            'clause_check': G.CHAIN, 'breath': 0}
    Path(out).with_suffix('.timings.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), 'utf-8')
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--稿', required=True)
    ap.add_argument('--wav', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--lead', type=float, default=1.5)
    ap.add_argument('--tail', type=float, default=2.0)
    a = ap.parse_args()
    segs = json.loads(Path(a.稿).read_text('utf-8'))['segments']
    m = render(segs, a.wav, a.out, a.lead, a.tail)
    c = m['certificate']['loudness']
    print(f"{a.out}：{m['duration']:.1f}s；整体 {c['integrated_lufs']} LUFS，句间 {c['sentence_max_dev_lu']}，短时 {c['short_term_std_lu']}，"
          f"峰值 {c['peak_dbfs']}，意群 {c.get('clause_nb_min_lu')} / 段尾 {c.get('clause_tail_min_db')}；电磁音（固定频点）{m['buzz_tone']}，全频段参考 {m['buzz_top'][0]}")


if __name__ == '__main__':
    main()
