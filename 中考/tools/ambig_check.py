"""列出同一句里高亮词还出现在别处的词条（匹配程序取第一处空闲的位置）：逐条人工核对高亮是否落在释义对应的那一处（专八、六级的踩坑 #24 同类）。 /opt/ttsenv/bin/python 中考/tools/ambig_check.py z01 …"""
import re, sys, json
sys.path.insert(0, '/home/user/university-entrance-examination/中考/tools')
import ann_lib as A
R = A.load_sents()
ids = sys.argv[1:] or sorted(R)
for pid in ids:
    meta, ann = A.parse(str(A.ANN / f'{pid}.txt'))
    S = A.flat(R[pid])
    for k, en in enumerate(S, 1):
        a = ann.get(k, {'w': []})
        taken = []
        for w in sorted(a['w'], key=lambda w: -len(w['h'])):
            sp = A.find(w, en, taken)
            if not sp:
                continue
            taken += sp
            for (x, y) in sp:
                word = en[x:y]
                others = [m.start() for m in re.finditer(r'(?<![\w-])' + re.escape(word) + r'(?![\w-])', en, re.I) if m.start() != x]
                if others and '[' not in (w.get('surf') or ''):
                    print(f"{pid} [{k}] {w['h']!r} -> '{word}'@{x} also @{others} | {w['m'][:30]} || {en[max(0,x-30):x]}<<{word}>>{en[y:y+30]}")
