"""四级翻译与生词标注的公共函数：读句子、解析标注文件、匹配高亮、中文排版检查。

标注文件格式与高考 tools/ann/pXX.txt 完全相同（T:/G:/S: 三行，然后每句“n 中文”与“= 词条 | 词条”）。
词条前缀：无前缀＝单词，~＝短语。按用户要求不区分四级词和超纲词，每句里需要记住的生词全部标注，不加 * 前缀。
匹配高亮的规则直接复用高考 tools/build.py 里的 parse/find，保证两边一致。
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                     # 四级/
REPO = ROOT.parent
ANN = ROOT / 'ann'

_src = (REPO / 'tools' / 'build.py').read_text('utf-8')
_ns = {'re': re, 'json': json}
exec(_src[_src.index('IRR={'):_src.index('out=[];errs=0')], _ns)
parse, find = _ns['parse'], _ns['find']

# 覆盖检查：句子里不属于基础词（初中词表 基础词.txt 及其规则变形）的词都必须被标注（用户要求：如 participant、interact 这类词一个都不能漏）。
# 专有名词（句中大写）、数字、缩写不算。
BASIC = set((HERE / '基础词.txt').read_text('utf-8').split())
_BV = set()
for _w in BASIC:
    _BV |= _ns['variants'](_w)
SUF = [('ly', ''), ('ly', 'le'), ('ily', 'y'), ('ness', ''), ('er', ''), ('er', 'e'), ('ing', ''), ('ing', 'e'), ('ed', ''), ('ed', 'e'), ('ied', 'y'),
       ('s', ''), ('es', ''), ('ies', 'y'), ('est', ''), ('ier', 'y'), ('iest', 'y'), ('n', ''), ('ful', '')]


def is_basic(tok):
    w = tok.lower().replace('’', "'")
    if w in _BV or w.split("'")[0] in _BV:
        return True
    for x, y in SUF:
        if w.endswith(x) and len(w) - len(x) >= 2:
            b = w[:-len(x)] + y
            if b in BASIC or (len(b) > 3 and b[-1] == b[-2] and b[:-1] in BASIC):
                return True
    return False


def _stems(w):
    w = re.sub(r"['’]s$", '', w.lower())
    out = {w}
    for x, y in (('ies', 'y'), ('es', ''), ('es', 'e'), ('s', ''), ('ed', ''), ('ed', 'e'), ('ing', ''), ('ing', 'e')):
        if w.endswith(x) and len(w) - len(x) >= 3:
            out.add(w[:-len(x)] + y)
    return out


def uncovered(en, spans, names=()):
    """返回句中没有被任何高亮覆盖、又不是基础词的词。names：本篇在句中位置出现过的大写词（专有名词），句首出现也不算漏标。"""
    out = []
    toks = list(re.finditer(r"[A-Za-z]+(?:['’][a-z]+)?", en))
    done = set()
    for m in toks:
        if any(x <= m.start() and m.end() <= y for x, y in spans):
            done |= _stems(m.group(0))
    for m in toks:
        a, b = m.span()
        if any(x <= a and b <= y for x, y in spans) or _stems(m.group(0)) & done:     # 同一句里重复出现的词（含单复数等变形），标一次即可
            continue
        tok = m.group(0)
        if re.sub(r"['’]s$", '', tok) in names:
            continue
        if is_basic(tok):
            continue
        if tok[0].isupper() and a > 0 and not re.search(r'[.!?“"‘(]\s*$', en[:a]):     # 句中大写：专有名词
            continue
        if tok.isupper() and len(tok) <= 5:            # 缩写 DNA、AI、IT
            continue
        if re.fullmatch(r"[A-Za-z]{1,2}", tok):        # s、t 等残片
            continue
        out.append(tok)
    return out


def load_sents():
    R = json.loads((ROOT / '仔细阅读' / 'sents.json').read_text('utf-8'))
    return {r['id']: r for r in R}


def flat(r):
    return [s for para in r['sents'] for s in para]


def zh_problems(z, whole=False):
    probs = []
    if re.search(r'[一-鿿][,;:?!]|[,;:?!][一-鿿]', z):
        probs.append('半角标点')
    if re.search(r'[一-鿿]\.(?!\d)|(?<![\w.])\.(?=[一-鿿])', z):
        probs.append('半角句点')
    if whole and z.count('“') != z.count('”'):
        probs.append('引号不配对')
    if re.search(r'[，。；：！？、]{2,}|，。|。，', z):
        probs.append('重复标点')
    if re.search(r'[一-鿿] +[一-鿿]', z):
        probs.append('汉字间空格')
    if '"' in z:
        probs.append('直引号')
    if re.search(r'([\u4e00-\u9fff，、]{4,})\1', z):
        probs.append('连续重复字串')
    return probs


def check(pid, path, R=None):
    """返回 (错误列表, 备用列表, 词条数)。错误必须为零。"""
    R = R or load_sents()
    sents = flat(R[pid])
    meta, ann = parse(str(path))
    names = set()
    for en in sents:
        for m in re.finditer(r"(?<=[a-z,;:] )[A-Z][a-z]+", en):
            names.add(m.group(0))
    errs, tiers = [], []
    for line in Path(path).read_text('utf-8').split('\n'):
        if line.startswith('='):
            for e in line[1:].split(' | '):
                if e.strip() and not _ns['ENT'].match(e.strip()):
                    errs.append(f'词条格式错误：{e.strip()}')
    for k in ('T', 'G', 'S'):
        if not meta.get(k):
            errs.append(f'缺少 {k}: 行')
    for k in ('T', 'S'):
        if meta.get(k) and zh_problems(meta[k], True):
            errs.append(f'{k} 中文排版：{zh_problems(meta[k], True)}')
    if sorted(ann) != list(range(1, len(sents) + 1)):
        errs.append(f'句数不对：标注 {len(ann)} 句，原文 {len(sents)} 句（编号必须是 1..{len(sents)}）')
    allzh = ''
    for k, en in enumerate(sents, 1):
        a = ann.get(k)
        if not a:
            continue
        allzh += a['zh']
        if not a['zh'].strip():
            errs.append(f'第{k}句 缺中文翻译')
        if re.search(r'[一-鿿]', en) is None and re.search(r'[A-Za-z]{4,}', a['zh']) and not re.search(r'[一-鿿]', a['zh']):
            errs.append(f'第{k}句 中文里没有汉字')
        p = zh_problems(a['zh'])
        if p:
            errs.append(f'第{k}句 中文排版：{p}：{a["zh"][:40]}')
        if not a['w']:
            errs.append(f'第{k}句 没有标注任何单词（铁律：每句至少一个）')
        taken = []
        for e in sorted(a['w'], key=lambda e: -len(e['h'])):
            sp = find(e, en, taken)
            if sp is None:
                errs.append(f'第{k}句 找不到：{e["h"]}' + (f'{{{e["surf"]}}}' if e.get('surf') else '') + f'  ||  {en}')
                continue
            taken += sp
        miss = uncovered(en, taken, names)
        if miss:
            errs.append(f'第{k}句 漏标（不是基础词，必须标注）：{", ".join(dict.fromkeys(miss))}')
        seen = set()
        for e in a['w']:
            if e['t'] != 'phr' and not re.match(r'^(n|v|adj|adv|prep|conj|pron|num|det|int|abbr|pref|suf)\.', e['m']):
                errs.append(f'第{k}句 单词 {e["h"]} 的释义缺少词性：{e["m"]}')
            if e['t'] == 'phr' and re.match(r'^(n|v|adj|adv|prep|conj)\. ', e['m']):
                errs.append(f'第{k}句 短语 {e["h"]} 的释义不应带词性：{e["m"]}')
            if e['t'] == 'phr' and ' ' not in e['h'].strip() and '…' not in e['h']:
                errs.append(f'第{k}句 短语 {e["h"]} 只有一个词，应作单词标注')
            if zh_problems(e['m']):
                errs.append(f'第{k}句 释义 {e["h"]} 中文排版：{zh_problems(e["m"])}')
            if (e['h'].lower(), e['m']) in seen:
                errs.append(f'第{k}句 重复词条：{e["h"]}')
            seen.add((e['h'].lower(), e['m']))
            if e['t'] == 'ext':
                errs.append(f'第{k}句 {e["h"]} 加了 * 前缀：不区分超纲词，单词一律不加前缀')
    if allzh.count('“') != allzh.count('”'):
        errs.append(f'全文中文引号不配对（“ {allzh.count("“")} 个，” {allzh.count("”")} 个）')
    n = sum(len(a['w']) for a in ann.values())
    return errs, tiers, n
