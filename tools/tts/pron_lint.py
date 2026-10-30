"""读音预检的共用函数（各项目 pron_check.py 调用）。

ambiguous_inflections：词典外的派生词（-ed/-s/-ing/-er/-ly），能对应几个词典里的词干、而它的读音与其中某个词干对不上的，列出来人工核对。
踩坑 72：misaki 把 toiled 当成 toile（一种布料，读 twɑl）加 d，读成 twˈɑld；专名读音检查只看词典外的专名，没管这类普通词，
直到语音识别听成 twiled、整篇音频重做才发现。双向验证：去掉 toiled 的读音修正，专八 27 篇报出 toiled；加上修正后不报。"""
import re

SUF = [('ed', ''), ('ed', 'e'), ('d', ''), ('ied', 'y'), ('es', ''), ('s', ''), ('ies', 'y'), ('ing', ''), ('ing', 'e'),
       ('er', ''), ('ers', ''), ('ly', '')]


def _norm(s):
    return re.sub('[ᵻəɪ]', 'ə', re.sub('[ˈˌ]', '', s))      # 弱读元音 ᵻ / ə / ɪ 视为相同，不比重音


def ambiguous_inflections(pron, items):
    """items：[(句子编号, 朗读文本)]。返回 {词: {'音标': 当前读音, '首见': 句子编号, '词干': {词干: 读音}}}。"""
    lex = pron.g2p.lexicon
    gold, silver = lex.golds, lex.silvers
    known = lambda w: any(x in d for x in (w, w.lower()) for d in (gold, silver))
    out = {}
    for key, text in items:
        for w in pron.WORD.findall(text):
            lw = w.lower()
            if w in out or known(w) or (w[0].isupper() and lw not in gold) or w in pron.lexicon or w in pron.sentence.get(key, {}):
                # 已有人工读音修正的词（读音修正.json）已经核对过，不再算歧义
                continue
            stems = [lw[:-len(a)] + b for a, b in SUF if lw.endswith(a) and len(lw) - len(a) >= 3 and lw[:-len(a)] + b in gold]
            if lw.endswith('ed') and len(lw) > 5 and lw[-3] == lw[-4]:
                stems.append(lw[:-3])                          # 双写辅音：unrolled → unroll
            if not stems:
                continue
            ph = pron.phonemes(w, key)
            got = {st: pron.phonemes(st) for st in dict.fromkeys(stems)}
            if not all(_norm(ph).startswith(_norm(b)[:-1] if len(_norm(b)) > 2 else _norm(b)) for b in got.values()):
                out[w] = {'音标': ph, '首见': key, '词干': got}
    return out


def stale_sentence_fixes(pron, items):
    """踩坑 13：按句号登记的读音修正（读音修正.json 的 sentence）重新切句后编号会整体平移，悄悄作用到别的句子上（Ortiz 读两遍）。
    每条逐句修正里的词必须真的出现在那一句的朗读文本里；items：[(句子编号, 朗读文本)]。返回问题列表。"""
    text = dict(items)
    bad = []
    for key, fix in pron.sentence.items():
        if key not in text:
            continue                                   # 别的篇目（不在这次检查范围）
        words = set(pron.WORD.findall(text[key]))
        bad += [f'{key} 逐句读音修正“{w}”在这一句里找不到（切句改过、编号平移了？）' for w in fix if w not in words]
    return bad
