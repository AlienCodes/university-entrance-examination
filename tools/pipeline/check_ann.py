"""检查一篇标注草稿：python3 check_ann.py pXX 草稿路径
与 tools/build.py 用同一套匹配规则。输出 OK 或逐条错误。"""
import os
import re
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pid, path = sys.argv[1], sys.argv[2]
src = open(f'{TOOLS}/build.py').read()
head = src[:src.index('out=[];errs=0')]
os.chdir(TOOLS)
ns = {}
exec(head, ns)
S = {o['id']: [s for para in o['sents'] for s in para] for o in ns['S']}
flat = S[pid]
meta, ann = ns['parse'](os.path.abspath(path) if not os.path.isabs(path) else path)
errs = []
for k in ('T', 'G', 'S'):
    if not meta.get(k):
        errs.append(f'缺少 {k}: 行')
if sorted(ann) != list(range(1, len(flat) + 1)):
    errs.append(f'句数不对：草稿 {len(ann)} 句，原文 {len(flat)} 句（编号必须是 1..{len(flat)}）')
for k, en in enumerate(flat, 1):
    a = ann.get(k)
    if not a:
        continue
    if not a['zh'].strip():
        errs.append(f'第{k}句 缺中文翻译')
    if not a['w']:
        errs.append(f'第{k}句 没有标注任何单词（铁律：每句至少一个）')
    taken = []
    for e in sorted(a['w'], key=lambda e: -len(e['h'])):
        sp = ns['find'](e, en, taken)
        if sp is None:
            errs.append(f'第{k}句 找不到：{e["h"]}' + (f'{{{e["surf"]}}}' if e.get('surf') else '') + f'  ||  {en}')
            continue
        taken += sp
    for e in a['w']:
        if e['t'] != 'phr' and not re.match(r'^(n|v|adj|adv|prep|conj|pron|num|det|int|abbr)\.', e['m']):
            errs.append(f'第{k}句 单词 {e["h"]} 的释义缺少词性：{e["m"]}')
        if e['t'] == 'phr' and re.match(r'^(n|v|adj|adv|prep)\. ', e['m']):
            errs.append(f'第{k}句 短语 {e["h"]} 的释义不应带词性：{e["m"]}')
n = sum(len(a['w']) for a in ann.values())
print('\n'.join(errs) if errs else f'OK  {len(flat)} 句，{n} 个词条')
