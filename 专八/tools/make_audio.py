"""生成专八阅读的朗读音频（由六级 make_audio.py 复制，规则完全相同；用户 2026-10-10：专八按常规程序做，之前所有注意事项全部照做）。
四级原说明：生成四级 60 篇的朗读音频（男声 cet4_male：am_fenrir 0.6 + am_onyx 0.4，语速 0.95，用户 2026-10-07 选定）。

    /opt/ttsenv/bin/python 专八/tools/make_audio.py            # 全部
    /opt/ttsenv/bin/python 专八/tools/make_audio.py s01 s02    # 指定篇目

直接复用高考 tools/tts/gaokao_tts.py 的整套流程（分句分段合成、统一电平、压缩限幅、−16 LUFS、
成品 MP3 按 ITU-R BS.1770 独立测量响度，不合格不输出；片头 1.5 秒、句间 0.8 秒、结尾 2 秒），
只把输入换成 四级/仔细阅读/sents.json 和 四级/ann/ 的中文翻译，输出到 四级/audio/。

四级自己的朗读规则（只在这里，不改高考程序）：
- 冒号、分号、破折号的停顿与逗号相同（0.28 秒），无空格的破折号也停顿（2026-10-07）
- 不该停顿的逗号不停顿（2026-10-08，从第二批 c40–c21 起）：并列列举（含牛津逗号）、并列形容词、句末附加语（too、either、for example）、
  句末简短引述（says X），见 pause_free；进出括号处照常停顿。逐条判定结果见 四级/停顿对比/不停顿的逗号清单.txt
- °F/°C 读作 degrees Fahrenheit/Celsius
- 金额缩写 $750m、£12bn 读作 750 million dollars、12 billion pounds；句末金额 $125,000. 的句号不当小数点；and/or 读作 and or
- 铁律：去除电磁音（debuzz.py，用户试听确认），成品 MP3 独立检查
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'tts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(ROOT / '四级' / 'tools'))      # debuzz.py 与四级共用
import gaokao_tts as G  # noqa: E402

C4 = ROOT / '专八'                  # 变量名沿用四级程序
G.ANN = C4 / 'ann'
VOICE = 'cet4_male'


def stem(p):
    return f"{p['id']}_{p['paper'].replace(' ', '_')}_{p['passage'].replace(' ', '')}"


G.file_stem = stem


# 朗读规范化补充：°F/°C 读作 degrees Fahrenheit/Celsius（高考共用的 read_text 不认识度数符号，会报“残留符号”）
_read_text = G.Pronouncer.read_text


ORIG = {}          # 句子编号 → 原文（判断哪些逗号原本是括号）
CUR = {'$': ('dollars', 'dollar'), '£': ('pounds', 'pound'), '€': ('euros', 'euro')}


def read_text(self, original, key=None):
    ORIG[key] = original
    original = G.re.sub(r'\s*°F\b', ' degrees Fahrenheit', original)
    original = G.re.sub(r'\s*°C\b', ' degrees Celsius', original)
    # 六级：数值范围的短横线读作 to（高考共用程序会把它读成破折号停顿，意思就丢了：25–54 → twenty-five—fifty-four）
    original = G.re.sub(r'\$(\d[\d,.]*)–\$(\d[\d,.]*)\s*(billion|million|trillion)', r'\1 to \2 \3 dollars', original)
    original = G.re.sub(r'(?<=\d)–(?=\$?\d)', ' to ', original)
    # 六级：金额缩写 $750m / £12bn 读作 750 million dollars / 12 billion pounds（高考共用程序会读成 dollarsm、poundsbn）；
    # 作复合定语时用单数：a £12bn-a-year industry → twelve billion pound-a-year
    original = G.re.sub(r'([$£€])(\d[\d,.]*)(m|bn)\b(-?)', lambda m: f"{m.group(2)} {'million' if m.group(3) == 'm' else 'billion'} "
                        f"{CUR[m.group(1)][bool(m.group(4))]}{m.group(4)}", original)
    # 句末金额 $125,000. 的句号会被高考共用程序当成小数点（读成 thousand point dollars）：先把这种金额读出来，句号留在后面
    original = G.re.sub(r'([$£€])(\d[\d,]*)\.(?=\s|$|["”’])', lambda m: f"{m.group(2)} {CUR[m.group(1)][0]}.", original)
    # and/or 读作 and or（斜杠不许留在朗读文本里）
    original = G.re.sub(r'\band/or\b', 'and or', original)
    return _read_text(self, original, key)


G.Pronouncer.read_text = read_text

# 四级专用读音修正（叠加在高考词典之上，高考文件不动）
_pron_init = G.Pronouncer.__init__


def pron_init(self, *a, **k):
    _pron_init(self, *a, **k)
    d = json.loads((C4 / 'tools' / '读音修正.json').read_text('utf-8'))
    self.lexicon = {**self.lexicon, **d.get('global', {})}
    for key, v in d.get('sentence', {}).items():
        self.sentence[key] = {**self.sentence.get(key, {}), **v}
    for key, v in d.get('text', {}).items():
        self.text[key] = self.text.get(key, []) + v


G.Pronouncer.__init__ = pron_init


# 用户要求（2026-10-08）：不该停顿的逗号不要停顿——这些逗号不切分合成、不插入静音，整段一口气合成，由模型按自然语调读：
#   1. 并列成分之间的逗号（含牛津逗号）：A, B, and C；VP, VP, and VP —— 用依存句法判定逗号后的成分是前一成分的并列项（conj），
#      且是三项及以上的列举，或是不超过 3 个词的短名词/形容词项；带主语的独立分句（“…, and homelessness remains…”）
#      和两项的长谓语并列（“…both, and ended up enjoying…”）仍然停顿
#   2. 并列形容词：regional, seasonal produce
#   3. 句末附加语：…, too. / …, either. / …, for example. 合成时连逗号也去掉（“I like it, too.” 不要任何停顿语气）
#   4. 句末的简短引述：…, says Bechtoldt. / …, she said.
# 只用于此后生成的音频（第一批 c41–c60 及 c01–c04 已定稿，不重做）。
TAGS = {'too', 'either', 'though', 'as well', 'instead', 'again', 'then', 'please', 'for example', 'for instance',
        'of course', 'indeed', 'after all', 'perhaps'}
REPORT = re.compile(r"\b(says|said|explains|explained|adds|added|notes|noted|writes|wrote|asks|asked|argues|argued|suggests|suggested)\b")
_nlp = None


GROUP = {'VERB': 'V', 'AUX': 'V', 'NOUN': 'N', 'PROPN': 'N', 'PRON': 'N', 'NUM': 'N', 'ADJ': 'A'}


SUBORD = re.compile(r'(if|when|while|although|though|because|since|unless|once|as|whether|after|before)\b', re.I)


def pause_free(read, parts, original=''):
    """返回 [(是否并入上一段, 原因)]，第 0 项无意义。只看逗号；冒号、分号、破折号照常停顿。
    original：原文。朗读文本把括号改成了逗号，进出括号处的逗号一律照常停顿。"""
    global _nlp
    if _nlp is None:
        import spacy
        _nlp = spacy.load('en_core_web_sm')
    doc = _nlp(read)
    rng, pos = [], 0
    for x in parts:
        a = read.index(x, pos)
        rng.append((a, a + len(x)))
        pos = a + len(x)
    where = lambda t: next((m for m, (a, b) in enumerate(rng) if a <= t.idx < b), -1)
    n = len(parts)
    out = [(False, '')] * n
    comma = [bool(re.search(r',["”’)]*$', x)) for x in parts]
    starts_cc = [bool(re.match(r'(and|or|nor|but) ', x)) for x in parts]
    inside = [c for c in re.findall(r'\(([^)]*[A-Za-z][^)]*)\)', original)]
    heads = {re.sub(r'[^a-z]', '', c.split()[0].lower()) for c in inside}
    tails = {re.findall(r'[A-Za-z]+', c)[-1].lower() for c in inside}
    first = lambda m: re.sub(r'[^a-z]', '', parts[m].split()[0].lower())
    last = lambda m: (re.findall(r'[A-Za-z]+', parts[m]) or [''])[-1].lower()
    # 进括号处（括号内容开头那一段之前）和出括号处（括号内容最后一段之后）照常停顿；括号里面的列举照常按规则判断
    locked = {m for m in range(1, n) if first(m) in heads or last(m - 1) in tails}

    def item(m):
        """第 m 段（去掉开头的 and/or/but）的核心词、词数、词类组、是否为带主语的分句或全句主干。"""
        toks = [t for t in doc if where(t) == m and not t.is_punct]
        while toks and toks[0].lower_ in ('and', 'or', 'nor', 'but'):
            toks = toks[1:]
        root = next((t for t in toks if where(t.head) != m or t.head == t), None)
        if root is None:
            return None
        clause = root.dep_ == 'ROOT' or (root.pos_ in ('VERB', 'AUX') and any(
            c.dep_ in ('nsubj', 'nsubjpass', 'expl') for c in root.children))
        return dict(root=root, n=len(toks), g=GROUP.get(root.pos_, root.pos_), clause=clause,
                    inner=any(c.dep_ == 'conj' and where(c) == m for c in root.children))

    # 1. 牛津逗号式列举 A, B, (C,) and/or D：末项与首项并列，中间各项与末项同一词类、都不是分句（小模型常把中间项挂错，所以看标点结构）
    for k in range(2, n):
        if not comma[k - 1] or not starts_cc[k]:
            continue
        last = item(k)
        if not last or last['root'].dep_ != 'conj' or last['clause']:
            continue
        h = last['root'].head
        while h.dep_ == 'conj' and h.head != h:      # 并列项常常一个挂一个（enhance → encourage → cultivate），顺着找到首项
            h = h.head
        i0 = where(h)
        mids = [item(i) for i in range(i0 + 1, k)]
        if 0 <= i0 < k - 1 and all(comma[i] for i in range(i0, k)) and all(
                x and not x['clause'] and x['g'] == last['g'] for x in mids) and not (
                last['g'] == 'V' and SUBORD.match(parts[i0])) and not locked & set(range(i0 + 1, k + 1)):
            for m in range(i0 + 1, k + 1):
                out[m] = (True, '并列')
    for m in range(1, n):
        if out[m][0] or not comma[m - 1] or m in locked:
            continue
        bare = re.sub(r'[^a-z ]', '', parts[m].lower()).strip()
        bw = bare.split()
        # 3. 句末附加语（too / either / for example …）
        if m == n - 1 and bare in TAGS:
            out[m] = (True, '附加语')
            continue
        # 4. 句末简短引述（says Bechtoldt / she said）
        if m == n - 1 and len(bw) <= 3 and (REPORT.fullmatch(bw[0]) or (len(bw) == 2 and REPORT.fullmatch(bw[1]))):
            out[m] = (True, '引述')
            continue
        it = item(m)
        # 2. 不带 and 的并列项（A, B and C 里的 B）：名词/形容词项短或属于三项以上列举；动词项只在很短或本段内还有并列时算
        if it and not starts_cc[m] and it['root'].dep_ == 'conj' and where(it['root'].head) < m and not it['clause']:
            r = it['root']
            if (it['g'] in ('N', 'A') and (it['n'] <= 3 or len(r.conjuncts) >= 2)) or (
                    it['g'] == 'V' and not SUBORD.match(parts[m - 1]) and ((it['n'] <= 2 and len(r.conjuncts) >= 2) or it['inner'])):
                out[m] = (True, '并列')
                continue
        # 列举的最后一项不带 and（breakfast, lunch, dinner）
        if it and m == n - 1 and out[m - 1][1] == '并列' and not starts_cc[m] and it['n'] <= 2 and it['g'] == 'N':
            out[m] = (True, '并列')
            continue
        # 5. 并列形容词（regional, seasonal produce）
        prev = [t for t in doc if where(t) == m - 1 and not t.is_punct]
        if prev and not starts_cc[m] and prev[-1].pos_ == 'ADJ' and prev[-1].dep_ == 'amod' and where(prev[-1].head) == m and any(
                t.dep_ == 'amod' and t.head == prev[-1].head for t in doc if where(t) == m):
            out[m] = (True, '并列形容词')
    return out


# 用户要求（2026-10-08，踩坑 28）：单引号、双引号都不要有任何停顿。语音模型把引号当作停顿符号，
# “right to grow” 前后会拖慢、像停了一下。合成时去掉所有引号（画面文字照旧）；词内撇号（don't、world's）保留。
def strip_quotes(t):
    t = re.sub(r'[“”"]', '', t)
    t = re.sub(r"(?<![A-Za-z])[‘’']|[‘’'](?![A-Za-z])", '', t)
    return re.sub(r' {2,}', ' ', t).strip()


# 用户要求（2026-10-07）：冒号、分号、破折号处的停顿与逗号完全一样（高考版分号、冒号是逗号的 1.4 倍）。
# 复制高考 synth_sentence，只去掉 1.4 倍，其余（分段、补标点、淡入淡出）不变。
def synth_sentence(read, key, engine, pron, style, speed, cfg):
    cp = cfg.get('clause_pause', 0)
    # 原文破折号两侧不留空格（pesticides—in fact），高考的切分规则要求标点后有空格，会漏掉这里的停顿；先补一个空格再切
    read = G.re.sub(r'—(?=\S)', '— ', read)
    read = strip_quotes(read)                       # 引号一律不停顿（踩坑 28）
    parts = [x for x in G.CLAUSE.split(read) if x.strip()] if cp else [read]
    free = pause_free(read, parts, ORIG.get(key, '')) if len(parts) > 1 else []
    merged = []
    for i, x in enumerate(parts):
        if merged and free[i][0] and free[i][1] == '附加语':
            merged[-1] = G.re.sub(r',(["”’)]*)$', r'\1', merged[-1]) + ' ' + x       # 附加语前的逗号在合成时去掉
        elif merged and (len(merged[-1].split()) < 2 or free[i][0]):
            merged[-1] += ' ' + x
        else:
            merged.append(x)
    merged = [x if i == len(merged) - 1 or G.re.search(r'[,;:—.!?]["”’)]*$', x) else x + ','
              for i, x in enumerate(merged)]
    out, spans, t = [], [], 0.0
    for i, x in enumerate(merged):
        if re.search(r'[“”"‘]|(?<![A-Za-z])’', x):    # 检查：送进模型的文字里不得残留引号
            raise RuntimeError(f'{key} 合成文字残留引号：{x}')
        seg = G.fade(G.level(engine.synth(pron.phonemes(x, key), style, speed)))
        spans.append((t, t + len(seg) / G.SR))
        out.append(seg)
        t += len(seg) / G.SR
        if i < len(merged) - 1:
            out.append(np.zeros(int(cp * G.SR), np.float32))          # 逗号、分号、冒号、破折号一律同样长
            t += int(cp * G.SR) / G.SR
    return np.concatenate(out), spans


# 低沉男声的能量集中在低频，按普通电平（RMS）统一各段时，人耳听到的响度（K 加权）仍有起伏，
# 首篇试做短时响度波动 1.17 LU，超过铁律上限 1.0。改为按 K 加权后的有声电平统一每段（只用于四级，
# 不影响已定稿的高考音频），检查标准一项不放宽。
import numpy as np  # noqa: E402
import pyloudnorm as pyln  # noqa: E402
_meter = pyln.Meter(G.SR)
_K = -26.0


def level_k(x, target=None):
    f = x.astype(np.float64)
    for flt in _meter._filters.values():
        f = flt.apply_filter(f)
    g = np.clip(_K - G.active_db(f.astype(np.float32)), -12, 12)
    return (x * 10 ** (g / 20)).astype(np.float32)


G.level = level_k
G.synth_sentence = synth_sentence
_comp = G.compress
_meter48 = pyln.Meter(G.OUT_SR)


def leveler(x, sr, win=1.0, rng=4.0, smooth=0.4):
    """慢速电平控制（类似广播 AGC）：按 1 秒窗的 K 加权电平把有声部分拉到同一水平，
    增益限制在 ±4 dB 并平滑，停顿处保持前值、不放大底噪。"""
    f = x.astype(np.float64)
    for flt in _meter48._filters.values():
        f = flt.apply_filter(f)
    B = int(0.05 * sr)
    n = len(x) // B
    e = np.mean(f[:n * B].reshape(n, B) ** 2, axis=1)
    eb = 10 * np.log10(e + 1e-12)
    on = (eb > np.percentile(eb, 99) - 30).astype(float)       # 只统计有声的 50ms 块，窗口里的停顿不拉低电平
    w = int(win / 0.05)
    num = np.convolve(e * on, np.ones(w), mode='same')
    den = np.convolve(on, np.ones(w), mode='same')
    lv = 10 * np.log10(num / np.maximum(den, 1) + 1e-12)
    act = den >= 0.3 * w                                       # 窗口内有声部分不足 30% 时不调整，保持前值
    ref = np.median(lv[act])
    g = np.zeros(n)
    last = 0.0
    for i in range(n):
        if act[i]:
            last = float(np.clip(ref - lv[i], -rng, rng))
        g[i] = last
    a = int(smooth / 0.05)
    g = np.convolve(np.pad(g, (a, a), mode='edge'), np.ones(2 * a + 1) / (2 * a + 1), mode='valid')
    gs = np.repeat(10 ** (g / 20), B)
    gs = np.concatenate([gs, np.full(len(x) - len(gs), gs[-1])])
    return (x * gs).astype(np.float32)


# 2026-10-08 曾尝试用极窄陷波去掉声码器窄带音（audio_clean.py），用户试听：处理后电磁音反而明显更大
# （高 Q 陷波在每个辅音、字头处“余振”出 65 个频点的细音）。已撤销，恢复原处理链。电磁音的真正来源仍在排查（四级/电磁音排查/）。
# 铁律第 10 条：坚决不能有电磁音（用户 2026-10-08 看 c40 样片确认有效）。
# 压缩之前只在声码器的 9 个固定频点做 60 Hz 带宽的单向陷波（debuzz.py）；成品 MP3 再独立测量，任何频点高出周围就报错、不输出。
import debuzz as D  # noqa: E402

G.compress = lambda x, sr: leveler(_comp(D.debuzz(x, sr), sr), sr)
_verify = G.verify_loudness


def verify_loudness(mp3_bytes, items, target_lufs):
    import io
    import soundfile as sf
    rep, errs = _verify(mp3_bytes, items, target_lufs)
    a, sr = sf.read(io.BytesIO(mp3_bytes), dtype='float32')
    f0, r, e = D.check(a if a.ndim == 1 else a.mean(1), sr, items)
    rep['buzz_hz'], rep['buzz_db'] = f0, round(r, 1)
    return rep, errs + e


G.verify_loudness = verify_loudness


def render_with_fallback(p, vcfg, engine, pron, out_dir):
    """短时响度波动刚好超过 1.0 LU 时（c14：1.01），只对这一篇把慢速电平的调节范围从 ±4 dB 依次放宽到 ±5、±6 dB 再试；
    检查标准一项不放宽，通过的篇目完全不受影响。用了哪一档记在 timings 的 leveler_rng 里。"""
    try:
        r = G.render_passage(p, VOICE, vcfg, engine, pron, out_dir)
        r['leveler_rng'] = 4.0
        return r
    except RuntimeError as e:
        if '短时响度波动' not in str(e) or any(k in str(e) for k in ('整体响度', '句间', '峰值', '电磁音')):
            raise
        first = e
    base = G.compress
    try:
        for rng in (5.0, 6.0):
            G.compress = lambda x, sr, rng=rng: leveler(_comp(D.debuzz(x, sr), sr), sr, rng=rng)
            try:
                r = G.render_passage(p, VOICE, vcfg, engine, pron, out_dir)
                r['leveler_rng'] = rng
                print(f"  {p['id']}：慢速电平放宽到 ±{rng:g} dB 后通过", flush=True)
                return r
            except RuntimeError as e2:
                if '短时响度波动' not in str(e2):
                    raise
        raise first
    finally:
        G.compress = base


def main(ids):
    vcfg = json.loads((G.HERE / 'voices.json').read_text('utf-8'))[VOICE]
    P = json.loads((C4 / '阅读' / 'sents.json').read_text('utf-8'))
    if ids:
        byid = {p['id']: p for p in P}
        P = [byid[i] for i in ids]                 # 按给定顺序生成（用户要求从 2026 年往前做）
    out = C4 / 'audio'
    tpath = out / 'timings.json'
    timings = json.loads(tpath.read_text('utf-8')) if tpath.exists() else {}
    engine, pron = G.Engine(), G.Pronouncer()
    fails = []
    for i, p in enumerate(P, 1):
        t0 = time.time()
        try:
            r = render_with_fallback(p, vcfg, engine, pron, out / VOICE)
        except RuntimeError as e:                 # 检查不通过的不输出文件，记下来最后统一处理
            fails.append(str(e))
            print('未通过：', e, flush=True)
            continue
        r.update(name=f"{p['paper']} {p['passage']}")
        timings.setdefault(VOICE, {})[p['id']] = r
        out.mkdir(parents=True, exist_ok=True)
        tpath.write_text(json.dumps(timings, ensure_ascii=False, indent=1), 'utf-8')
        print(f'[{i}/{len(P)}] {r["file"]}  {r["duration"]:.1f}s，用时 {time.time() - t0:.0f}s', flush=True)
    if fails:
        sys.exit(f'{len(fails)} 篇未通过检查：\n' + '\n'.join(fails))


if __name__ == '__main__':
    main(sys.argv[1:])
