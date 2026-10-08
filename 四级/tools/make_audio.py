"""生成四级 60 篇的朗读音频（男声 cet4_male：am_fenrir 0.6 + am_onyx 0.4，语速 0.95，用户 2026-10-07 选定）。

    /opt/ttsenv/bin/python 四级/tools/make_audio.py            # 全部
    /opt/ttsenv/bin/python 四级/tools/make_audio.py c01 c02    # 指定篇目

直接复用高考 tools/tts/gaokao_tts.py 的整套流程（分句分段合成、统一电平、压缩限幅、−16 LUFS、
成品 MP3 按 ITU-R BS.1770 独立测量响度，不合格不输出；片头 1.5 秒、句间 0.8 秒、结尾 2 秒），
只把输入换成 四级/仔细阅读/sents.json 和 四级/ann/ 的中文翻译，输出到 四级/audio/。

四级自己的朗读规则（只在这里，不改高考程序）：
- 冒号、分号、破折号的停顿与逗号相同（0.28 秒），无空格的破折号也停顿（2026-10-07）
- 不该停顿的逗号不停顿（2026-10-08，从第二批 c40–c21 起）：并列列举（含牛津逗号）、并列形容词、句末附加语（too、either、for example）、
  句末简短引述（says X），见 pause_free；进出括号处照常停顿。逐条判定结果见 四级/停顿对比/不停顿的逗号清单.txt
- °F/°C 读作 degrees Fahrenheit/Celsius
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'tts'))
import gaokao_tts as G  # noqa: E402

C4 = ROOT / '四级'
G.ANN = C4 / 'ann'
VOICE = 'cet4_male'


def stem(p):
    return f"{p['id']}_{p['paper'].replace(' ', '_')}_{p['passage'].replace(' ', '')}"


G.file_stem = stem


# 朗读规范化补充：°F/°C 读作 degrees Fahrenheit/Celsius（高考共用的 read_text 不认识度数符号，会报“残留符号”）
_read_text = G.Pronouncer.read_text


ORIG = {}          # 句子编号 → 原文（判断哪些逗号原本是括号）


def read_text(self, original, key=None):
    ORIG[key] = original
    original = G.re.sub(r'\s*°F\b', ' degrees Fahrenheit', original)
    original = G.re.sub(r'\s*°C\b', ' degrees Celsius', original)
    return _read_text(self, original, key)


G.Pronouncer.read_text = read_text


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
    heads = {re.sub(r'[^a-z]', '', c.split()[0].lower()) for c in re.findall(r'\(([^)]*[A-Za-z][^)]*)\)', original)}
    paren = [m > 0 and re.sub(r'[^a-z]', '', parts[m].split()[0].lower()) in heads for m in range(n)]
    locked = {m for m in range(1, n) if paren[m] or paren[m - 1]}      # 进括号、出括号

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


# 用户要求（2026-10-07）：冒号、分号、破折号处的停顿与逗号完全一样（高考版分号、冒号是逗号的 1.4 倍）。
# 复制高考 synth_sentence，只去掉 1.4 倍，其余（分段、补标点、淡入淡出）不变。
def synth_sentence(read, key, engine, pron, style, speed, cfg):
    cp = cfg.get('clause_pause', 0)
    # 原文破折号两侧不留空格（pesticides—in fact），高考的切分规则要求标点后有空格，会漏掉这里的停顿；先补一个空格再切
    read = G.re.sub(r'—(?=\S)', '— ', read)
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


G.compress = lambda x, sr: leveler(_comp(x, sr), sr)


def main(ids):
    vcfg = json.loads((G.HERE / 'voices.json').read_text('utf-8'))[VOICE]
    P = json.loads((C4 / '仔细阅读' / 'sents.json').read_text('utf-8'))
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
            r = G.render_passage(p, VOICE, vcfg, engine, pron, out / VOICE)
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
