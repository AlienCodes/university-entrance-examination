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
import json
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
                print(f'  ! 文本修正未匹配 {key}: {target!r}', file=sys.stderr)
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
        return self.WORD.sub(sub, text)

    def phonemes(self, read_text, key=None):
        ph, _ = self.g2p(self._mark(read_text, key))
        return ph


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


LIMITS = {'integrated': 0.7, 'sentence_dev': 2.0, 'short_term_std': 1.0, 'peak_db': -1.0}


def verify_loudness(mp3_bytes, items, target_lufs):
    """第一项检查：对编码后的 MP3 成品做独立测量（ITU-R BS.1770 K 加权响度）。
    整体响度、每句响度偏差、3 秒短时响度波动、峰值，任何一项超标都返回失败原因。"""
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
    st = np.array([-0.691 + 10 * np.log10(np.mean(f[i:i + W] ** 2) + 1e-12) for i in range(0, len(f) - W, H)])
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
    return rep, errs


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
        seg = fade(level(engine.synth(pron.phonemes(x, key), style, speed)))   # 每段先统一响度，边缘淡入淡出
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


def master(a, target_lufs=-16.0, peak_db=-1.5):
    """母带处理：重采样到 48k → 压缩 → 统一响度到 target_lufs → 前瞻限幅。"""
    import soxr
    import pyloudnorm as pyln
    a = soxr.resample(a, SR, OUT_SR, quality='VHQ').astype(np.float32)
    a = compress(a, OUT_SR)
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
    a = master(np.concatenate(pieces), lufs)
    mp3 = encode_mp3(a, kbps=vcfg.get('kbps', 128))
    rep, errs = verify_loudness(mp3, items, lufs)              # 第一项检查：成品响度一致
    if errs:
        raise RuntimeError(f"{p['id']} {voice_name} 响度检查未通过，未输出文件：" + '；'.join(errs))
    log(f"  响度检查通过：整体 {rep['integrated_lufs']} LUFS，句间最大偏差 {rep['sentence_max_dev_lu']} LU，"
        f"短时波动 {rep['short_term_std_lu']} LU，峰值 {rep['peak_dbfs']} dBFS")
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / file_stem(p)
    Path(str(base) + '.mp3').write_bytes(mp3)
    if wav:
        write_wav(str(base) + '.wav', a)
    write_subs(base, items, load_zh(p['id']))
    return {'file': f"{out_dir.name}/{base.name}.mp3", 'duration': round(len(a) / OUT_SR, 3),
            'loudness': rep, 'sentences': items}


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
    pieces = [np.zeros(int(0.3 * SR), np.float32)]
    for i, s in enumerate(sents):
        pieces.append(synth_sentence(pron.read_text(s), None, engine, pron, style, args.speed or vcfg.get('speed', 1.0), vcfg)[0])
        pieces.append(np.zeros(int((vcfg['tail'] if i == len(sents) - 1 else gap_after(s, False, vcfg)) * SR), np.float32))
    a = master(np.concatenate(pieces), vcfg.get('lufs', -16.0))
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
