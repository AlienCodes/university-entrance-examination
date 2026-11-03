"""配音发音（含多音字声调）——铁律 23（用户 2026-11-03：“空格”被读成 kōng，应为 kòng gé；“这些音调的发音一定一定要弄准，千万不要弄错，
让人听着跟 AI 一样”）。所有中文讲解配音共用（高考语法填空、高考续写……），规则只写一处：
  ① 预检 preflight（几秒，合成前）：jieba 分词 + pypinyin 按词标音，讲解稿里每个“易错多音字”（EASY）出现的词都必须登记在
     多音字表.json（人工按讲解场景逐个确认读音），没登记的一次全部列出、退出码 1；
  ② 让模型读对 model_text：读音修正_中文.json 里登记的词，只在送进模型的文字里换成读音无歧义的同音写法（画面文字照旧），逐条写理由；
  ③ 合成后核查 tone_problems：识别对齐（SenseVoice 带时间戳）取出登记字那个音节，pyin 量音高走向（前 1/3 与后 1/3 的半音差 = 降幅），
     只判可靠的对比：应读四声、别的读音不是四声 → 降幅 < FALL4_MIN 报“读成了平/升调”；应读一声或二声、别的读音有四声 → 降幅 > FALL12_MAX
     报“读成了降调”。三声、同调异音（行 xíng / háng、还 hái / huán）测不出，列为缺口（靠 ① ② 和识别）。
用法：python3 多音字.py 稿.json [稿2.json …]          # 预检，列出全部多音字与读音；未登记的报错
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLE = HERE / '多音字表.json'
FIX = HERE / '读音修正_中文.json'
EASY = set('空谓得地了着还重长行调为只种中相处几要看没和便当背差称答')
FALL4_MIN = 2.0      # 半音：应读四声的音节，降幅至少这么多（第 3 轮 r2icl 的“空格”读成一声：0.0；第 2 版正确的四声：8.3）。
#                      后一个字也是四声时不判（四声连读，前一个只降一半，是正常读法：三份样音里“也要用”的“要”都只有 −3—+3）
FALL12_MAX = 4.0     # 半音：应读一声 / 二声的音节，降幅不超过这么多


def _table():
    return json.loads(TABLE.read_text('utf-8'))['words'] if TABLE.exists() else {}


def _fix():
    return json.loads(FIX.read_text('utf-8'))['words'] if FIX.exists() else {}


def readings(text):
    """[(字在 text 里的下标, 字, jieba 词, pypinyin 读音 TONE3)]，只列 EASY 里的字（pypinyin 只作提示，读音以登记表为准）。"""
    import jieba
    from pypinyin import Style, pinyin
    out, pos = [], 0
    for w in jieba.cut(text):
        i0 = text.index(w, pos)
        pos = i0 + len(w)
        if not any(c in EASY for c in w):
            continue
        py = [p[0] for p in pinyin(w, style=Style.TONE3, neutral_tone_with_five=True)]
        for k, c in enumerate(w):
            if c in EASY:
                out.append((i0 + k, c, w, py[k] if len(py) == len(w) else '?'))
    return out


def lookup(text, i, tb=None):
    """登记表里覆盖 text[i] 的最长词条：返回 (词条, 该字读音) 或 (None, None)。词条可以带上下文（如“就得当”），按原文匹配。"""
    tb = _table() if tb is None else tb
    best = (None, None)
    for w, e in tb.items():
        for m in re.finditer(re.escape(w), text):
            if m.start() <= i < m.end():
                py = e['读音'].split()
                if len(py) == len(w) and (best[0] is None or len(w) > len(best[0])):
                    best = (w, py[i - m.start()])
    return best


def preflight(texts):
    """texts：[(段 id, 中文配音文字)]。返回 (全部多音字行, 问题)。问题 = 没登记的（一次全部列出），或登记的读音音节数不对。"""
    tb, rows, errs, seen = _table(), [], [], set()
    for w, e in tb.items():
        if len(e['读音'].split()) != len(w):
            errs.append(f'多音字表：“{w}”的读音音节数不对：{e["读音"]}')
    for sid, t in texts:
        for i, c, w, py in readings(t):
            key, r = lookup(t, i, tb)
            rows.append(f'{sid}  {c}（{t[max(0, i - 3):i + 3]}）登记 {key or "—"} → {r or "—"}（pypinyin {py}）')
            if not key and (w, c) not in seen:
                errs.append(f'{sid}：“{w}”里的多音字“{c}”没登记读音（pypinyin：{py}；上下文：{t[max(0, i - 8):i + 8]}）')
                seen.add((w, c))
    return rows, errs


def model_text(text):
    """送进模型的文字：读音修正_中文.json 里的词换成同音无歧义写法。"""
    for w, e in _fix().items():
        text = text.replace(w, e['送模型'])
    return text


def expected(text):
    """[(字下标, 字, 应读调 1—5, 别的读音的调集合)]：登记了的 EASY 字。"""
    from pypinyin import Style, pinyin
    tb, out = _table(), []
    for i, c, _, _ in readings(text):
        key, py = lookup(text, i, tb)
        if not key:
            continue
        tone = int(py[-1]) if py[-1].isdigit() else 5
        alts = {int(p[-1]) for p in pinyin(c, style=Style.TONE3, heteronym=True, neutral_tone_with_five=True)[0] if p[-1].isdigit()} - {tone}
        out.append((i, c, tone, alts))
    return out


def syllable_fall(y, sr, t0, t1):
    """这个音节的浊音段（[t0, t1] 里从 t0 附近开始的最长一段连续浊音）：前 1/3 基频中位数比后 1/3 高多少半音（正 = 下降）。"""
    import librosa
    import numpy as np
    seg = y[max(0, int(t0 * sr)):int(t1 * sr)].astype(np.float32)
    if len(seg) < int(0.08 * sr):
        return None
    f0, v, _ = librosa.pyin(seg, fmin=60, fmax=300, sr=sr, frame_length=1024, hop_length=int(0.005 * sr))
    ok = v & ~np.isnan(f0)
    runs, s0 = [], None
    for k, o in enumerate(list(ok) + [False]):
        if o and s0 is None:
            s0 = k
        if not o and s0 is not None:
            runs.append((s0, k))
            s0 = None
    runs = [r for r in runs if r[1] - r[0] >= 6]
    if not runs:
        return None
    a, b = max(runs, key=lambda r: r[1] - r[0])
    f = f0[a:b]
    st = 12 * np.log2(f / np.median(f))
    k = max(2, len(st) // 3)
    return float(np.median(st[:k]) - np.median(st[-k:]))


def tone_problems(y, sr, text, aligner, t_off=0.0, sid=''):
    """y：这一段音频；text：这一段稿文字（中文）；aligner：讲解节奏.Aligner。返回 (报告, 问题)。"""
    sys.path.insert(0, str(HERE.parents[1] / '高考语法填空/tools'))
    import 讲解节奏 as NJ
    exp = expected(text)
    if not exp:
        return [], []
    ref_idx, ref = [], []
    for i, t in enumerate(NJ.toks(text)):
        if t not in '？?':
            ref.append(t)
    # 稿文字下标 → toks 下标（只数汉字与英文词）
    pos_map, k = {}, 0
    for m in re.finditer(r"[一-鿿]|[A-Za-z]+(?:['’][A-Za-z]+)?", text):
        pos_map[m.start()] = k
        k += 1
    from pypinyin import Style, pinyin
    pys = [p[0] for p in pinyin(text, style=Style.TONE3, neutral_tone_with_five=True, errors=lambda x: list(x))]
    char_py = dict(enumerate(pys)) if len(pys) == len(text) else {}
    hyp = aligner(y, sr)
    m = NJ.align_index(ref, hyp)
    rep, errs = [], []
    for i, c, tone, alts in exp:
        r = pos_map.get(i)
        if r is None or r not in m:
            continue
        j = m[r]
        if hyp[j][0] != c:
            continue                       # 识别成了别的字：交给识别比对
        t0 = hyp[j][1]
        t1 = min(hyp[j + 1][1] if j + 1 < len(hyp) else t0 + 0.3, t0 + 0.35)
        fall = syllable_fall(y, sr, t0, t1)
        ctx = text[max(0, i - 4):i + 4]
        rep.append({'id': sid, '字': c, '上下文': ctx, '应读调': tone, '降幅': None if fall is None else round(fall, 1)})
        if fall is None:
            continue
        nxt = lookup(text, i + 1)[1] or char_py.get(i + 1, '')
        if tone == 4 and alts and 4 not in alts and nxt.endswith('4'):
            rep[-1]['跳过'] = '后一个字也是四声'
        elif tone == 4 and alts and 4 not in alts and fall < FALL4_MIN:
            errs.append(f'{sid}：“{ctx}”的“{c}”应读四声，实测降幅 {fall:.1f} 半音（下限 {FALL4_MIN}），读成了平调 / 升调（{t_off + t0:.2f}s）')
        elif tone in (1, 2) and 4 in alts and fall > FALL12_MAX:
            errs.append(f'{sid}：“{ctx}”的“{c}”应读{"一" if tone == 1 else "二"}声，实测降幅 {fall:.1f} 半音（上限 {FALL12_MAX}），读成了四声（{t_off + t0:.2f}s）')
    return rep, errs


def check_items(a, sr, items, aligner=None):
    """成品 a 的 timings items（每段 text 为稿文字）逐段核查声调。返回 (报告, 问题)。"""
    sys.path.insert(0, str(HERE.parents[1] / '高考语法填空/tools'))
    import 讲解节奏 as NJ
    aligner = aligner or NJ.Aligner()
    R, E = [], []
    for it in items:
        txt = it['text'].replace('‖', '')
        if not re.search(r'[一-鿿]', txt):
            continue
        y = a[int(it['start'] * sr):int(it['end'] * sr)]
        r, e = tone_problems(y, sr, txt, aligner, it['start'], it['id'])
        R += r
        E += e
    return R, E


def main():
    texts = []
    for p in sys.argv[1:]:
        doc = json.loads(Path(p).read_text('utf-8'))
        texts += [(s['id'], s['text'].replace('‖', '')) for s in doc['segments'] if s.get('lang', 'Chinese') == 'Chinese']
    rows, errs = preflight(texts)
    for r in rows:
        print(r)
    for e in errs:
        print('✗', e)
    print(f'多音字预检：{len(rows)} 处多音字，{len(errs)} 个词没登记')
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
