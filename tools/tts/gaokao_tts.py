"""高考阅读真人级朗读：把文章逐句合成为美式英语音频（男声 / 女声）。

用法（在 tools/tts 目录下）：
    python gaokao_tts.py passages                      # 生成全部 70 篇，男女声各一份
    python gaokao_tts.py passages --only p58 p59       # 只生成指定文章
    python gaokao_tts.py passages --voices female      # 只生成女声
    python gaokao_tts.py say "Any English text." -o hello.mp3 --voice male
    python gaokao_tts.py qa --only p58                 # 用语音识别 + 自然度评分自检
    python gaokao_tts.py subs                          # 只按已有时间轴重写字幕（不重新合成）

引擎：Kokoro-82M（本地运行，无需联网和密钥），G2P 用 misaki；
人名、多音词等发音修正在 pronunciations.json，音色在 voices.json。
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                      # 仓库根目录
SENTS = HERE.parent / 'sents.json'             # 70 篇原文（已切句）
ANN = HERE.parent / 'ann'                      # 逐句中文翻译（有则写进双语字幕）
MODELS = HERE / 'models'
OUT = ROOT / 'audio'
SR = 24000                                     # Kokoro 原生采样率
OUT_SR = 48000                                 # 输出采样率（视频剪辑常用）

sys.path.insert(0, str(HERE))
from textnorm import normalize  # noqa: E402


# ---------------------------------------------------------------- 文本与发音
ABBR_FIX = True          # 踩坑 72 的修正开关（只给双向验证用：关掉时 check_double 必须报出 t20:46）


class Pronouncer:
    """原文 -> 朗读文本 -> 音素。应用 pronunciations.json 里的修正。"""

    WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[-'’][A-Za-zÀ-ÖØ-öø-ÿ]+)*")

    def __init__(self, path=HERE / 'pronunciations.json'):
        from misaki import en, espeak
        self.g2p = en.G2P(trf=False, british=False, fallback=espeak.EspeakFallback(british=False))
        data = json.loads(Path(path).read_text('utf-8')) if Path(path).exists() else {}
        self.lexicon = data.get('global', {})          # 词 -> 音素（所有文章通用）
        self.sentence = data.get('sentence', {})       # "p58:5" -> {词: 音素}
        self.text = data.get('text', {})               # "p58:5" -> [[原文片段, 替换]]

    def read_text(self, original, key=None):
        t = normalize(original)
        for target, rep in self.text.get(key, []):
            if target in t:
                t = t.replace(target, rep, 1)
            else:
                raise RuntimeError(f'文本修正未匹配 {key}: {target!r}')
        # 踩坑记录：词内弯撇号会让发音词典丢音（isn’t. 被读成 is），一律换成直撇号
        t = re.sub(r"(?<=[A-Za-z])’(?=[A-Za-z])", "'", t)
        # 踩坑记录：括号内容会被模型跳过；数字、符号会读错。朗读文本里一律不许残留
        # 只允许字母、空白和常规标点；其余任何字符（# @ * + = ₂ 中文等）都可能被读错或跳过
        if key and re.search(r"[^A-Za-zÀ-ÖØ-öø-ÿ\s.,;:!?'\"“”‘’—–\-]", t):
            raise RuntimeError(f'{key} 朗读文本残留括号/数字/符号/中文：{t}')
        return t

    def _mark(self, text, key):
        local = self.sentence.get(key, {})

        def sub(m):
            w = m.group(0)
            ph = local.get(w) or self.lexicon.get(w)
            if ph is None:                                       # Azimi’s：词干有修正时，按英语规则加 -s 的读音
                m2 = re.match(r"^(.+?)[’']s$", w)
                stem_ph = m2 and (local.get(m2.group(1)) or self.lexicon.get(m2.group(1)))
                if stem_ph:
                    ph = stem_ph + possessive_suffix(stem_ph)
            return f'[{w}](/{ph}/)' if ph else w
        out = self.WORD.sub(sub, text)
        if not ABBR_FIX:
            return out
        # 踩坑 72：标了读音的缩写（spaCy 把 Ms. Mr. Ltd. 当成一个词）后面紧跟另一个标了读音的词时，misaki 把后一个词读两遍、
        # 逗号也丢掉（专八 t20:46 “Ms. Chalari,” 读成 Ms. Chalari-Kalari）。把句点放进方括号里就正常（只改这一种写法，别处不变）
        rules = self.g2p.nlp.tokenizer.rules
        return re.sub(r'\[([A-Za-z]+)\]\((/[^)]*/)\)\.(?=\s+\[)',
                      lambda m: f'[{m.group(1)}.]({m.group(2)})' if m.group(1) + '.' in rules else m.group(0), out)

    def phonemes(self, read_text, key=None):
        marked = self._mark(read_text, key)
        ph, _ = self.g2p(marked)
        self.check_double(marked, ph, key)
        return ph

    def check_double(self, marked, ph, key=None):
        """独立检查（踩坑 72）：标了读音的词不许被读两遍。misaki 读两遍时，前后两遍粘在一起、中间没有空格：
        标的读音 + 标的读音，或 不标时的默认读音 + 标的读音（反过来也算）。"""
        for w, p in set(re.findall(r'\[([^\]]+)\]\(/([^)]*)/\)', marked)):
            d = self.g2p(w.rstrip('.'))[0]
            for glued in {p + p, d + p, p + d} if d and d != p else {p + p}:
                if len(p) >= 2 and glued in ph:
                    raise RuntimeError(f'{key} 标了读音的词被读两遍（踩坑 72）：{w} → {ph}')


def possessive_suffix(ph):
    """所有格 's 的读音：咝音后 /ᵻz/，清辅音后 /s/，其余 /z/。"""
    last = ph.rstrip('ˈˌ')[-1:]
    if last in 'szʃʒʧʤ':
        return 'ᵻz'
    if last in 'ptkfθ':
        return 's'
    return 'z'


# ---------------------------------------------------------------- 合成引擎
class Engine:
    def __init__(self, models=MODELS):
        from kokoro_onnx import Kokoro
        model, voices = Path(models) / 'kokoro-v1.0.onnx', Path(models) / 'voices-v1.0.bin'
        if not model.exists():
            sys.exit(f'找不到模型 {model}，请先运行 setup 脚本下载。')
        self.k = Kokoro(str(model), str(voices))

    def style(self, spec):
        """spec 可以是 "af_heart" 或 {"am_michael": 0.6, "am_fenrir": 0.4}（音色混合）"""
        if isinstance(spec, str):
            return self.k.get_voice_style(spec)
        total = sum(spec.values())
        return sum(self.k.get_voice_style(v) * (w / total) for v, w in spec.items()).astype(np.float32)

    def synth(self, phonemes, style, speed=1.0):
        a, sr = self.k.create(phonemes, voice=style, speed=speed, is_phonemes=True,
                              trim=True, sentence_pause=0.0, clause_pause=0.0)
        assert sr == SR
        return trim(np.asarray(a, dtype=np.float32))


def trim(a, db=-48, pad=0.04):
    """去掉首尾静音，保留一点点自然的起止。"""
    if not len(a):
        return a
    frame = 240
    n = len(a) // frame
    if n == 0:
        return a
    rms = np.sqrt(np.mean(a[:n * frame].reshape(n, frame) ** 2, axis=1) + 1e-12)
    loud = np.where(20 * np.log10(rms / (np.max(rms) + 1e-12)) > db)[0]
    if not len(loud):
        return a
    p = int(pad * SR)
    return a[max(0, loud[0] * frame - p): min(len(a), (loud[-1] + 1) * frame + p)]


TARGET_DB = -20.0      # 每段语音的“有声部分”统一到这个电平（之后整篇再统一到 LUFS）
MAX_DEV_DB = 1.5       # 响度一致性检查：任何一段与整篇中位数的偏差不得超过这个值


def active_db(x, sr=SR):
    """有声部分的平均电平（dB）：只统计比最响帧低 30 dB 以内的 20ms 帧，忽略停顿和气声。"""
    n = int(0.02 * sr)
    f = x[:len(x) // n * n].reshape(-1, n)
    if not len(f):
        return -120.0
    e = np.sqrt(np.mean(f ** 2, axis=1) + 1e-12)
    act = e[20 * np.log10(e / e.max()) > -30]
    return float(20 * np.log10(np.sqrt(np.mean(act ** 2)) + 1e-12))


def level(x, target=TARGET_DB):
    g = np.clip(target - active_db(x), -12, 12)
    return (x * 10 ** (g / 20)).astype(np.float32)


EVEN_TOL = 1.5     # 段内电平统一：比本段中位数低超过这个值（dB）才往上补
EVEN_MAX = 12.0    # 最多补这么多（dB）：插入语 “…, however,” 曾被模型读得低 12—15 dB（专八 t23:33）


def voiced(x, sr, H):
    """每 H 个采样一帧（窗 30 ms）是否浊音：自相关在 80—400 Hz 基频范围的归一化峰值 > 0.5，且不比本段最响处低 45 dB 以上。
    元音、浊辅音为真；气声、s/f/sh 等清辅音、停顿为假（按周期性判断，与音量无关，很轻的词照样算进来）。"""
    W = int(0.03 * sr)
    n = len(x) // H
    xp = np.concatenate([np.asarray(x, np.float64), np.zeros(W)])
    fr = np.stack([xp[i * H:i * H + W] for i in range(n)]) * np.hanning(W)
    nf = 1 << (2 * W - 1).bit_length()
    sp = np.fft.rfft(fr, nf, axis=1)
    ac = np.fft.irfft(np.abs(sp) ** 2, nf, axis=1)[:, :W]
    # 汉宁窗的自相关会随时延衰减，除以窗本身的自相关做无偏校正
    wac = np.fft.irfft(np.abs(np.fft.rfft(np.hanning(W), nf)) ** 2, nf)[:W]
    lo, hi = int(sr / 400), int(sr / 80)
    r = (ac[:, lo:hi] / wac[lo:hi]) / (ac[:, :1] / wac[0] + 1e-20)
    e = 10 * np.log10(ac[:, 0] / W + 1e-20)
    return (r.max(axis=1) > 0.5) & (e > e.max() - 45)


def even(x, sr=SR, tol=EVEN_TOL, gmax=EVEN_MAX):
    """段内电平统一（踩坑 85，用户 2026-10-29“偶尔一个地方声音突然小了一点”）。
    模型常在一段（逗号到逗号）的最后一两个词、或插入语上把声音收小：原始合成的段尾 0.8 秒元音比段内其余低 5—8 dB，
    成品里 1% 的意群末尾低 4.6 dB 以上；分段 level 只把整段平均拉齐、1 秒慢速电平器又跟不上，都补不全。
    做法：K 计权 10 ms 帧；只用浊音帧（voiced，按周期性判断）测电平：300 ms 窗内浊音帧的平均能量，与整段浊音的平均能量比，
    低于 tol 的地方只往上补（≤ gmax），增益 70 ms 平滑。
    清音、气声、停顿帧不参与测量，沿用相邻浊音帧的增益，且补完不超过整段浊音平均（句尾安静元音后的 s、ts 不会被抬得比主体还响）。
    在压缩、去电磁音之前做（铁律 10 的陷波照旧），只改慢变的电平，不改频响。"""
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    import pyloudnorm as pyln
    H = int(0.01 * sr)
    n = len(x) // H
    if n < 20:
        return x
    f = np.asarray(x, dtype=np.float64)
    for flt in pyln.Meter(sr)._filters.values():
        f = flt.apply_filter(f)
    e = np.mean(f[:n * H].reshape(n, H) ** 2, axis=1) + 1e-20
    v = voiced(x, sr, H)[:n]
    if v.sum() < 10:
        return x
    num = uniform_filter1d(np.where(v, e, 0.0), 31, mode='constant')
    den = uniform_filter1d(v.astype(float), 31, mode='constant')
    idx = np.where(den > 1e-6)[0]
    E = np.interp(np.arange(n), idx, 10 * np.log10(num[idx] / den[idx]))       # 没有浊音的地方沿用相邻值
    ref = 10 * np.log10(np.mean(e[v]))
    g = np.clip(ref - E - tol, 0.0, gmax)
    Ls = 10 * np.log10(uniform_filter1d(e, 5, mode='nearest'))
    g = np.minimum(g, np.where(v, gmax, np.maximum(0.0, ref - Ls)))           # 清音帧补完不超过整段浊音平均
    g = uniform_filter1d(minimum_filter1d(g, 5, mode='nearest'), 7, mode='nearest')
    t = (np.arange(n) + 0.5) * H
    gs = 10 ** (np.interp(np.arange(len(x)), t, g) / 20)
    return (np.asarray(x) * gs).astype(np.float32)


CLAUSE_LUFS = -23.0  # 每段（意群）的 BS.1770 门限响度统一到这个值，之后整篇再统一到 −16 LUFS


def gated_lufs(x, sr=SR):
    """BS.1770 门限响度（K 计权、400 ms 块、75% 重叠、−70 LUFS 绝对门限、−10 LU 相对门限）；不足一个块按整段能量算。"""
    import pyloudnorm as pyln
    f = np.asarray(x, dtype=np.float64)
    for flt in pyln.Meter(sr)._filters.values():
        f = flt.apply_filter(f)
    z = f ** 2
    W, Hb = int(0.4 * sr), int(0.1 * sr)
    if len(z) < W:
        return -0.691 + 10 * np.log10(np.mean(z) + 1e-20) if len(z) else -120.0
    c = np.concatenate([[0.0], np.cumsum(z)])
    st = np.arange(0, len(z) - W + 1, Hb)
    e = (c[st + W] - c[st]) / W
    e = e[-0.691 + 10 * np.log10(e + 1e-20) > -70]
    if not len(e):
        return -120.0
    e = e[-0.691 + 10 * np.log10(e + 1e-20) > -0.691 + 10 * np.log10(np.mean(e)) - 10]
    return float(-0.691 + 10 * np.log10(np.mean(e)))


def level_clause(x, sr=SR, target=CLAUSE_LUFS):
    """整段电平：按 BS.1770 门限响度把每段（意群）统一到 target。
    原来的 level / level_k 按“比本段最响帧低 30 dB 以内的 20 ms 帧”的 RMS 算，与人耳响度（BS.1770）差 ±1 LU：
    k48 拼接后、母带处理前意群之间就有 −0.8～+1.2 LU 的离散（成品最差 −1.8 LU）。
    检查（verify_loudness 的意群检查）测的是经过陷波、压缩、慢速电平、限幅、MP3 编码之后的成品，埋雷双向验证证明它查得出。"""
    g = np.clip(target - gated_lufs(x, sr), -12, 12)
    return (np.asarray(x) * 10 ** (g / 20)).astype(np.float32)


def segment(x):
    """每段合成后的统一处理（规则只写一处，各项目的 synth_sentence 都调这里）：段内电平统一（even）→ 整段按 BS.1770 响度统一（level_clause）→ 边缘淡入淡出。
    踩坑 85 起取代各项目原来的“先 level 再 fade”（四级 make_audio 的 level_k 等不再用于分段）。"""
    return fade(level_clause(even(x)))


LIMITS = {'integrated': 0.7, 'sentence_dev': 2.0, 'short_term_std': 1.0, 'peak_db': -1.0}


def edge_span(items, edge):
    """考研作文书信、通知的格式行（称呼 Dear Paul,、结束语 Yours, Li Ming、通知标题与署名）不到 1 秒语音、前后都是静音，
    3 秒短时窗口罩在上面几乎全是静音，把“短时响度波动”算大（11 篇书信 1.03—1.29 LU，正文本身没变）。
    edge = [开头格式行数, 结尾格式行数]：短时窗口只量正文（第一句正文开口前 0.8 秒到最后一句正文读完后 0.8 秒，即句间停顿）；
    格式行照样逐句核对与中位数的偏差（≤ 2 LU）、整体响度、峰值。"""
    head, tail = edge
    return (items[head]['start'] - 0.8, items[len(items) - 1 - tail]['end'] + 0.8)


def verify_loudness(mp3_bytes, items, target_lufs, span=None, fine=True):
    """第一项检查：对编码后的 MP3 成品做独立测量（ITU-R BS.1770 K 加权响度）。
    整体响度、每句响度偏差、3 秒短时响度波动、峰值，任何一项超标都返回失败原因。
    fine：意群级检查（踩坑 85，响度细查.fine_check）。2026-10-29 起生成的音频一律检查（timings 记 clause_check）；
    此前已发布的成品不追溯（用户 2026-10-29 决定），verify_videos、check_pitfalls 按 timings 有无 clause_check 传入。"""
    import io
    import pyloudnorm as pyln
    import soundfile as sf
    a, sr = sf.read(io.BytesIO(mp3_bytes), dtype='float64')
    m = pyln.Meter(sr)
    il = m.integrated_loudness(a)
    sent = []
    for it in items:
        seg = a[int(it['start'] * sr):int(it['end'] * sr)]
        if len(seg) > 0.5 * sr:
            sent.append(m.integrated_loudness(seg))
    med = float(np.median(sent))
    dev = max(abs(x - med) for x in sent)
    f = a.copy()
    for flt in m._filters.values():
        f = flt.apply_filter(f)
    W, H = 3 * sr, sr // 2
    # 短时窗口从“第一句开口前 1.5 秒”开始量（与标准片头完全相同）：考研作文片头之后还有 10 秒静音的原题屏，从 0 秒量会多出两个只有
    # 0.5—1 秒语音的窗口，把波动算大（w02 实测 1.13 LU，语音本身并没有变化）。片头 1.5 秒的项目 t0 = 0，测量与原来逐字节相同。
    t0 = items[0]['start'] - 1.5 if items and items[0]['start'] - 1.5 > 0.5 else 0.0
    end = len(f)
    if span:                                       # 考研作文书信：只量正文（edge_span）
        t0, end = span[0], min(len(f), int(span[1] * sr))
    st = np.array([-0.691 + 10 * np.log10(np.mean(f[i:i + W] ** 2) + 1e-12) for i in range(int(t0 * sr), end - W, H)])
    st = st[st > il - 10]
    peak = 20 * np.log10(np.max(np.abs(a)) + 1e-12)
    rep = {'integrated_lufs': round(float(il), 2), 'sentence_max_dev_lu': round(float(dev), 2),
           'short_term_std_lu': round(float(st.std()), 2), 'peak_dbfs': round(float(peak), 2)}
    errs = []
    if abs(il - target_lufs) > LIMITS['integrated']:
        errs.append(f'整体响度 {il:.2f} LUFS（目标 {target_lufs}）')
    if dev > LIMITS['sentence_dev']:
        errs.append(f'句间响度偏差 {dev:.2f} LU（上限 {LIMITS["sentence_dev"]}）')
    if st.std() > LIMITS['short_term_std']:
        errs.append(f'短时响度波动 {st.std():.2f} LU（上限 {LIMITS["short_term_std"]}）')
    if peak > LIMITS['peak_db']:
        errs.append(f'峰值 {peak:.2f} dBFS（上限 {LIMITS["peak_db"]}）')
    if fine:
        import importlib
        frep, ferrs = importlib.import_module('响度细查').fine_check(a if a.ndim == 1 else a.mean(1), sr, items)
        rep.update(frep)
        errs += ferrs
    return rep, errs


CHAIN = 'clause-v1'    # 处理链版本：段内电平统一 even + 每段 BS.1770 统一 + 意群级检查（踩坑 85，2026-10-29）
LEGACY = HERE / '响度旧成品清单.json'   # 2026-10-29 之前已发布的成品（不追溯，用户决定）：按 文件|时长|响度 登记，新生成的不可能撞上


def certificate(mp3_bytes, rep):
    """音频合格证：处理链版本、成品 MP3 的 sha256、全部响度测量（含意群级最差值）。只有检查全部通过才会写出来。"""
    return {'chain': CHAIN, 'passed': True, 'mp3_sha256': hashlib.sha256(mp3_bytes).hexdigest(), 'loudness': rep,
            'limits': dict(LIMITS, **__import__('importlib').import_module('响度细查').FINE_LIMITS),
            'date': time.strftime('%Y-%m-%d')}


def legacy_key(tm):
    L = tm.get('loudness') or {}
    return f"{tm.get('file')}|{tm.get('duration')}|{L.get('integrated_lufs')}|{L.get('sentence_max_dev_lu')}|{L.get('short_term_std_lu')}"


def is_legacy(tm):
    return LEGACY.exists() and legacy_key(tm) in set(json.loads(LEGACY.read_text('utf-8'))['keys'])


def certificate_problems(tm, mp3_path=None):
    """视频生成前 / 后核对音频合格证。旧成品（响度旧成品清单）放行；其余必须是当前处理链、检查通过、（给了 MP3 时）sha256 一致。"""
    if is_legacy(tm):
        return []
    c = tm.get('certificate') or {}
    errs = []
    if tm.get('clause_check') != CHAIN or c.get('chain') != CHAIN:
        errs.append(f"音频不是当前处理链 {CHAIN} 生成的（没有意群级电平统一与检查），不许生成视频")
    elif not c.get('passed'):
        errs.append('音频合格证显示检查未通过')
    if mp3_path is not None and not errs:
        side = Path(str(mp3_path)[:-4] + '.loudness.json')
        if not side.exists():
            errs.append(f'缺少合格证文件 {side.name}')
        elif json.loads(side.read_text('utf-8')).get('mp3_sha256') != hashlib.sha256(Path(mp3_path).read_bytes()).hexdigest():
            errs.append('合格证与 MP3 不符（MP3 在检查之后被改过）')
    return errs


CLAUSE = re.compile(r'(?:(?<=[,;:—])|(?<=[,;:—]["”’)]))\s+(?=\S)')


def synth_sentence(read, key, engine, pron, style, speed, cfg):
    """按逗号、分号、冒号、破折号分段合成，段间加停顿（clause_pause 秒；为 0 时整句合成）。"""
    cp = cfg.get('clause_pause', 0)
    parts = [x for x in CLAUSE.split(read) if x.strip()] if cp else [read]
    # 太短的片段（单个词）并入后一段，避免一字一顿
    merged = []
    for x in parts:
        if merged and len(merged[-1].split()) < 2:
            merged[-1] += ' ' + x
        else:
            merged.append(x)
    # 每段都以标点结尾，否则模型会把最后一个词收得太急
    merged = [x if i == len(merged) - 1 or re.search(r'[,;:—.!?]["”’)]*$', x) else x + ','
              for i, x in enumerate(merged)]
    out, parts, t = [], [], 0.0
    for i, x in enumerate(merged):
        seg = segment(engine.synth(pron.phonemes(x, key), style, speed))   # 段内电平统一 + 整段浊音电平 + 淡入淡出（踩坑 85）
        parts.append((t, t + len(seg) / SR))
        out.append(seg)
        t += len(seg) / SR
        if i < len(merged) - 1:
            pause = cp * (1.4 if x.rstrip('”"’ ').endswith((';', ':')) else 1.0)
            out.append(np.zeros(int(pause * SR), np.float32))
            t += int(pause * SR) / SR
    return np.concatenate(out), parts


def gap_after(sentence, para_end, cfg):
    """句间停顿：段落结尾更长；长句、问句后稍长一点，接近真人朗读的节奏。"""
    if cfg.get('fixed_sentence_gap'):          # 铁律：句与句之间固定停顿（0.8 秒）
        return cfg['paragraph_pause'] if para_end else cfg['sentence_pause']
    if para_end:
        return cfg['paragraph_pause']
    words = len(sentence.split())
    g = cfg['sentence_pause'] + min(0.15, 0.004 * words)
    if sentence.rstrip('”"’ ').endswith('?'):
        g += 0.08
    return g


# ---------------------------------------------------------------- 后期处理
def _smooth_gain(g_db, block_s, attack, release):
    """逐块平滑增益（dB）：增益下降用 attack，回升用 release。"""
    a, r = np.exp(-block_s / attack), np.exp(-block_s / release)
    out = np.empty_like(g_db)
    cur = 0.0
    for i, g in enumerate(g_db):
        c = a if g < cur else r
        cur = c * cur + (1 - c) * g
        out[i] = cur
    return out


def _apply_block_gain(x, g_db, block):
    g = 10 ** (np.repeat(g_db, block)[:len(x)] / 20)
    if len(g) < len(x):
        g = np.concatenate([g, np.full(len(x) - len(g), g[-1] if len(g) else 1.0)])
    return (x * g).astype(np.float32)


def compress(x, sr, ratio=3.0, knee=6.0, above=4.0, attack=0.010, release=0.150):
    """语音压缩器：阈值设在有声部分平均电平以上 above dB，超过部分按 ratio 压缩（软拐点）。"""
    block = int(0.002 * sr)
    n = len(x) // block
    f = x[:n * block].reshape(n, block)
    lvl = 10 * np.log10(np.mean(f ** 2, axis=1) + 1e-12)
    thr = active_db(x, sr) + above
    over = lvl - thr
    gr = np.where(over <= -knee / 2, 0.0,
                  np.where(over >= knee / 2, over * (1 / ratio - 1),
                           (1 / ratio - 1) * (over + knee / 2) ** 2 / (2 * knee)))
    return _apply_block_gain(x, _smooth_gain(gr, block / sr, attack, release), block)


def limit(x, sr, ceiling_db=-1.5, lookahead=0.005, release=0.060):
    """前瞻限幅器：保证采样峰值不超过 ceiling。"""
    ceil = 10 ** (ceiling_db / 20)
    block = int(0.001 * sr)
    n = -(-len(x) // block)
    pad = np.concatenate([np.abs(x), np.zeros(n * block - len(x), np.float32)])
    pk = pad.reshape(n, block).max(axis=1)
    la = int(lookahead / 0.001)
    pk = np.array([pk[i:i + la + 1].max() for i in range(n)])      # 提前看 lookahead
    need = np.minimum(0.0, 20 * np.log10(ceil / np.maximum(pk, 1e-9)))
    g = _smooth_gain(need, 0.001, 1e-4, release)
    g = np.minimum(g, need)                                           # 绝不放过超限的块
    y = _apply_block_gain(x, g, block)
    return np.clip(y, -ceil, ceil)


def clause_trim(a, parts, sr=OUT_SR, rng=3.0):
    """意群间再统一（踩坑 85）：压缩与慢速电平会让意群之间重新差出 ±1 LU（短意群 “After all,” 被带响 1.06 LU，后一段相对小 1.0 LU，
    六级作文 c21）。按 BS.1770 门限响度把每个意群拉回本篇意群中位数（≤ ±rng dB）；增益只在意群之间停顿的中点切换（静音处，10 ms 斜坡）。
    不足 0.5 秒的意群不单独调，跟随前一段。parts：[[起, 止], …]（秒，按时间顺序）。"""
    if not parts:
        return a
    L = [gated_lufs(a[int(s * sr):int(e * sr)], sr) if e - s >= 0.5 else None for s, e in parts]
    ok = [x for x in L if x is not None]
    if not ok:
        return a
    med = float(np.median(ok))
    gains, last = [], 0.0
    for x in L:
        last = float(np.clip(med - x, -rng, rng)) if x is not None else last
        gains.append(last)
    g = np.zeros(len(a))
    edges = [0] + [int((parts[i][1] + parts[i + 1][0]) / 2 * sr) for i in range(len(parts) - 1)] + [len(a)]
    for i, gd in enumerate(gains):
        g[edges[i]:edges[i + 1]] = gd
    r = int(0.01 * sr)
    g = np.convolve(np.pad(g, r, mode='edge'), np.ones(2 * r + 1) / (2 * r + 1), mode='valid')[:len(a)]
    return (a * 10 ** (g / 20)).astype(np.float32)


def master(a, target_lufs=-16.0, peak_db=-1.5, parts=None):
    """母带处理：重采样到 48k → 压缩 → 意群间再统一（parts，踩坑 85）→ 统一响度到 target_lufs → 前瞻限幅。"""
    import soxr
    import pyloudnorm as pyln
    a = soxr.resample(a, SR, OUT_SR, quality='VHQ').astype(np.float32)
    a = compress(a, OUT_SR)
    if parts:
        a = clause_trim(a, parts)
    meter = pyln.Meter(OUT_SR)
    for _ in range(2):                    # 限幅会让响度略降，迭代一次补偿
        a = a * 10 ** ((target_lufs - meter.integrated_loudness(a)) / 20)
        a = limit(a.astype(np.float32), OUT_SR, peak_db)
    return a.astype(np.float32)


def fade(x, ms=5):
    n = min(len(x) // 2, int(ms / 1000 * SR))
    if n:
        r = np.linspace(0, 1, n, dtype=np.float32)
        x = x.copy()
        x[:n] *= r
        x[-n:] *= r[::-1]
    return x


def write_mp3(path, a, sr=OUT_SR, kbps=128):
    Path(path).write_bytes(encode_mp3(a, sr, kbps))


def encode_mp3(a, sr=OUT_SR, kbps=128):
    import lameenc
    enc = lameenc.Encoder()
    enc.set_bit_rate(kbps)
    enc.set_in_sample_rate(sr)
    enc.set_channels(1)
    enc.set_quality(2)
    pcm = (np.clip(a, -1, 1) * 32767).astype('<i2').tobytes()
    return enc.encode(pcm) + enc.flush()


def write_wav(path, a, sr=OUT_SR):
    import soundfile as sf
    sf.write(str(path), a, sr, subtype='PCM_16')


# ---------------------------------------------------------------- 字幕
def fmt_ts(t, sep=','):
    h, rem = divmod(int(round(t * 1000)), 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f'{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}'


def load_zh(pid):
    """读取 tools/ann/pXX.txt 里的逐句中文翻译（如果已经做好）。"""
    p = ANN / f'{pid}.txt'
    zh = {}
    if p.exists():
        for line in p.read_text('utf-8').splitlines():
            m = re.match(r'^(\d+) (.+)$', line)
            if m:
                zh[int(m.group(1))] = m.group(2).strip()
    return zh


def write_subs(base, items, zh):
    srt, vtt = [], ['WEBVTT', '']
    for i, it in enumerate(items, 1):
        en = clean_display(it['text'])
        lines = [en] + ([zh[it['k']]] if it['k'] in zh else [])
        srt += [str(i), f"{fmt_ts(it['start'])} --> {fmt_ts(it['end'])}", *lines, '']
        vtt += [f"{fmt_ts(it['start'], '.')} --> {fmt_ts(it['end'], '.')}", *lines, '']
    Path(str(base) + '.srt').write_text('\n'.join(srt), 'utf-8')
    Path(str(base) + '.vtt').write_text('\n'.join(vtt), 'utf-8')


def clean_display(s):
    """字幕里显示原文，但去掉中文注释括号。"""
    s = re.sub(r'\s*[（(][^()（）]*[一-鿿][^()（）]*[)）]', '', s)
    return re.sub(r'\s{2,}', ' ', s).strip()


# ---------------------------------------------------------------- 文章
def load_passages():
    return json.loads(SENTS.read_text('utf-8'))


def file_stem(p):
    """p58_2026_全国Ⅰ卷_阅读C —— 编号在前，文件夹里自然按年份、全国卷优先排序。"""
    paper = re.sub(r'[（）()·\s]+', '', p['paper'])
    return f"{p['id']}_{p['year']}_{paper}_阅读{p['part']}"


def render_passage(p, voice_name, vcfg, engine, pron, out_dir, wav=False, log=print):
    style = engine.style(vcfg['style'])
    speed = vcfg.get('speed', 1.0)
    pieces, items = [], []
    t = vcfg['lead_in']
    pieces.append(np.zeros(int(vcfg['lead_in'] * SR), np.float32))
    k = 0
    for pi, para in enumerate(p['sents']):
        for si, s in enumerate(para):
            k += 1
            key = f"{p['id']}:{k}"
            read = pron.read_text(s, key)
            audio, parts = synth_sentence(read, key, engine, pron, style, speed, vcfg)
            dur = len(audio) / SR
            items.append({'k': k, 'para': pi + 1, 'start': round(t, 3), 'end': round(t + dur, 3),
                          'parts': [[round(t + a, 3), round(t + b, 3)] for a, b in parts],
                          'text': s, 'read': read})
            pieces.append(audio)
            t += dur
            g = vcfg['tail'] if (pi == len(p['sents']) - 1 and si == len(para) - 1) \
                else gap_after(s, si == len(para) - 1, vcfg)
            pieces.append(np.zeros(int(round(g * SR)), np.float32))
            t += int(round(g * SR)) / SR
    lufs = vcfg.get('lufs', -16.0)
    a = master(np.concatenate(pieces), lufs, parts=[pt for it in items for pt in it['parts']])   # 意群间再统一（踩坑 85）
    dip = os.environ.get('LOUDNESS_TEST_DIP')        # 双向验证用：在真实流程里把第 k 句第 j 段压低 db（如 "3:1:2"），检查必须报错、不出文件
    if dip:
        k_, j_, db_ = dip.split(':')
        s_, e_ = items[int(k_) - 1]['parts'][int(j_) - 1]
        a = a.copy()
        a[int(s_ * OUT_SR):int(e_ * OUT_SR)] *= 10 ** (-float(db_) / 20)
    mp3 = encode_mp3(a, kbps=vcfg.get('kbps', 128))
    rep, errs = verify_loudness(mp3, items, lufs, **({'span': edge_span(items, p['edge'])} if p.get('edge') else {}))   # 第一项检查：成品响度一致（书信格式行见 edge_span）
    if errs:
        raise RuntimeError(f"{p['id']} {voice_name} 响度检查未通过，未输出文件：" + '；'.join(errs))
    log(f"  响度检查通过：整体 {rep['integrated_lufs']} LUFS，句间最大偏差 {rep['sentence_max_dev_lu']} LU，"
        f"短时波动 {rep['short_term_std_lu']} LU，峰值 {rep['peak_dbfs']} dBFS；意群检查（{CHAIN}）：比相邻意群最多小 "
        f"{-rep.get('clause_nb_min_lu', 0):.2f} LU（上限 1.2），段尾最多小 {-rep.get('clause_tail_min_db', 0):.2f} dB（上限 4.0）")
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / file_stem(p)
    Path(str(base) + '.mp3').write_bytes(mp3)
    if wav:
        write_wav(str(base) + '.wav', a)
    write_subs(base, items, load_zh(p['id']))
    cert = certificate(mp3, rep)                       # 合格证（踩坑 85）：MP3 旁边一份，timings 里一份；没有合格证的音频 verify_videos 拒绝
    Path(str(base) + '.loudness.json').write_text(json.dumps(cert, ensure_ascii=False, indent=1), 'utf-8')
    return {'file': f"{out_dir.name}/{base.name}.mp3", 'duration': round(len(a) / OUT_SR, 3),
            'loudness': rep, 'sentences': items, 'clause_check': CHAIN, 'certificate': cert}


def cmd_passages(args):
    voices = json.loads((HERE / 'voices.json').read_text('utf-8'))
    names = args.voices or list(voices)
    P = load_passages()
    if args.only:
        P = [p for p in P if p['id'] in set(args.only)]
    engine, pron = Engine(), Pronouncer()
    tpath = OUT / 'timings.json'
    timings = json.loads(tpath.read_text('utf-8')) if tpath.exists() else {}
    for v in names:
        vcfg = voices[v]
        for i, p in enumerate(P, 1):
            t0 = time.time()
            r = render_passage(p, v, vcfg, engine, pron, OUT / v, wav=args.wav)
            r.update(name=f"{p['year']} {p['paper']} 阅读{p['part']}")
            timings.setdefault(v, {})[p['id']] = r
            print(f'[{v} {i}/{len(P)}] {r["file"]}  {r["duration"]:.1f}s 音频，用时 {time.time() - t0:.1f}s', flush=True)
            OUT.mkdir(parents=True, exist_ok=True)
            tpath.write_text(json.dumps(timings, ensure_ascii=False, indent=1), 'utf-8')


def cmd_say(args):
    voices = json.loads((HERE / 'voices.json').read_text('utf-8'))
    vcfg = voices[args.voice]
    engine, pron = Engine(), Pronouncer()
    style = engine.style(vcfg['style'])
    text = args.text if args.text != '-' else sys.stdin.read()
    sents = re.split(r'(?<=[.!?])["”’)]*\s+(?=["“‘(]?[A-Z0-9])', text.strip())
    pieces, allp, t = [np.zeros(int(0.3 * SR), np.float32)], [], 0.3
    for i, s in enumerate(sents):
        au, ps = synth_sentence(pron.read_text(s), None, engine, pron, style, args.speed or vcfg.get('speed', 1.0), vcfg)
        allp += [[t + x, t + y] for x, y in ps]
        pieces.append(au)
        t += len(au) / SR
        gap = np.zeros(int((vcfg['tail'] if i == len(sents) - 1 else gap_after(s, False, vcfg)) * SR), np.float32)
        pieces.append(gap)
        t += len(gap) / SR
    a = master(np.concatenate(pieces), vcfg.get('lufs', -16.0), parts=allp)
    out = Path(args.output)
    (write_wav if out.suffix.lower() == '.wav' else write_mp3)(out, a)
    print(f'已保存 {out}（{len(a) / OUT_SR:.1f} 秒）')


def cmd_subs(args):
    """不重新合成，只用 timings.json + 最新的中文翻译重写 .srt/.vtt。"""
    timings = json.loads((OUT / 'timings.json').read_text('utf-8'))
    n = 0
    for v, ps in timings.items():
        for pid, r in ps.items():
            write_subs(OUT / r['file'][:-4], r['sentences'], load_zh(pid))
            n += 1
    print(f'已更新 {n} 份字幕')


def cmd_qa(args):
    import qa
    qa.run(args)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('passages', help='生成文章音频')
    a.add_argument('--only', nargs='*', help='只生成这些编号，如 p58 p59')
    a.add_argument('--voices', nargs='*', help='female / male（默认全部）')
    a.add_argument('--wav', action='store_true', help='另存一份无损 WAV（剪视频用）')
    a.set_defaults(fn=cmd_passages)
    b = sp.add_parser('say', help='把任意英文转成音频')
    b.add_argument('text', help='要朗读的英文；用 - 表示从标准输入读取')
    b.add_argument('-o', '--output', default='say.mp3')
    b.add_argument('--voice', default='female')
    b.add_argument('--speed', type=float)
    b.set_defaults(fn=cmd_say)
    c = sp.add_parser('qa', help='语音识别 + 自然度自检')
    c.add_argument('--only', nargs='*')
    c.add_argument('--voices', nargs='*')
    c.set_defaults(fn=cmd_qa)
    d = sp.add_parser('subs', help='只重写字幕')
    d.set_defaults(fn=cmd_subs)
    args = ap.parse_args()
    args.fn(args)


if __name__ == '__main__':
    main()
