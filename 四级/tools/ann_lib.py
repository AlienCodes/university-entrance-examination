"""四级翻译与生词标注的公共函数：读句子、解析标注文件、匹配高亮、判断词级、中文排版检查。

标注文件格式与高考 tools/ann/pXX.txt 完全相同（T:/G:/S: 三行，然后每句“n 中文”与“= 词条 | 词条”）。
词条前缀：无前缀＝四级词（在 词表/ 的初中+高中+四级并集里），*＝超纲词，~＝短语。
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

SCOPE = set()
for _f in ('初中', '高中', '四级'):
    SCOPE |= set((HERE / '词表' / f'{_f}.txt').read_text('utf-8').split())
_ov = HERE / '词级已核.json'
TIER_OK = json.loads(_ov.read_text('utf-8')) if _ov.exists() else {}   # 词头 -> 'core'/'ext'，人工裁定

BRIT = [('isation', 'ization'), ('ise', 'ize'), ('our', 'or'), ('tre', 'ter'), ('ence', 'ense'), ('lled', 'led'), ('lling', 'ling'), ('ogue', 'og')]
SUF = [('ly', ''), ('ly', 'le'), ('ily', 'y'), ('ally', ''), ('ness', ''), ('iness', 'y'), ('ment', ''), ('er', ''), ('er', 'e'), ('or', ''), ('or', 'e'),
       ('ing', ''), ('ing', 'e'), ('ed', ''), ('ed', 'e'), ('ied', 'y'), ('s', ''), ('es', ''), ('ies', 'y'), ('ful', ''), ('less', ''), ('al', ''), ('ally', 'al')]


def in_scope(h):
    """词头是否在四级范围：本身在表里，或是表中词的规则派生（-ly/-ness/-ment/-er/-ing/-ed/-ful/-less/-al）或英式拼写。"""
    w = h.lower().strip()
    if w in TIER_OK:
        return TIER_OK[w] == 'core'
    cands = {w}
    for a, b in BRIT:
        if a in w:
            cands.add(w.replace(a, b))
    for c in list(cands):
        if c in SCOPE:
            return True
        for s, r in SUF:
            if c.endswith(s) and len(c) - len(s) >= 3:
                base = c[:-len(s)] + r
                if base in SCOPE:
                    return True
                if len(base) > 3 and base[-1] == base[-2] and base[:-1] in SCOPE:     # running -> run
                    return True
    if '-' in w:                                    # 复合词：每一部分都在范围内才算四级词
        return all(in_scope(x) for x in w.split('-') if x)
    return False


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
    """返回 (错误列表, 词级不符列表, 词条数)。错误必须为零；词级不符要么改前缀，要么人工裁定写进 词级已核.json。"""
    R = R or load_sents()
    sents = flat(R[pid])
    meta, ann = parse(str(path))
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
        seen = set()
        for e in a['w']:
            if e['t'] != 'phr' and not re.match(r'^(n|v|adj|adv|prep|conj|pron|num|det|int|abbr)\.', e['m']):
                errs.append(f'第{k}句 单词 {e["h"]} 的释义缺少词性：{e["m"]}')
            if e['t'] == 'phr' and re.match(r'^(n|v|adj|adv|prep|conj)\. ', e['m']):
                errs.append(f'第{k}句 短语 {e["h"]} 的释义不应带词性：{e["m"]}')
            if e['t'] == 'phr' and ' ' not in e['h'].strip() and '…' not in e['h']:
                errs.append(f'第{k}句 短语 {e["h"]} 只有一个词，应作单词标注')
            if zh_problems(e['m']):
                errs.append(f'第{k}句 释义 {e["h"]} 中文排版：{zh_problems(e["m"])}')
            if e['h'].lower() in seen:
                errs.append(f'第{k}句 重复词条：{e["h"]}')
            seen.add(e['h'].lower())
            if e['t'] in ('core', 'ext'):
                want = 'core' if in_scope(e['h']) else 'ext'
                if want != e['t']:
                    tiers.append(f'第{k}句 {e["h"]} 标为{"四级词" if e["t"] == "core" else "超纲词"}，按词表应为{"四级词" if want == "core" else "超纲词（加 *）"}')
    if allzh.count('“') != allzh.count('”'):
        errs.append(f'全文中文引号不配对（“ {allzh.count("“")} 个，” {allzh.count("”")} 个）')
    n = sum(len(a['w']) for a in ann.values())
    return errs, tiers, n
