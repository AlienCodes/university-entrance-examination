"""多音字预检：稿.json 每段中文，找目标多音字；所在词在 pypinyin 词组词典里 → 读音由词组定（可靠）；
不在 → 单字默认读音，可能读错，列出上下文与 pypinyin 给的读音，人工判断。"""
import json, re, sys
from pypinyin import pinyin, Style
from pypinyin.constants import PHRASES_DICT
from pypinyin.seg.mmseg import seg as mmseg

TARGET = set('空谓得地了着还重长行为调中相处几要看没和便当背差称答觉更教传种分只少数应')
segs = json.load(open(sys.argv[1]))['segments']
seen = {}
for s in segs:
    t = s['text']
    for run in re.findall(r'[一-鿿]+', t):
        for w in mmseg.cut(run):
            hit = [c for c in w if c in TARGET]
            if not hit:
                continue
            py = ' '.join(x[0] for x in pinyin(w, style=Style.TONE))
            src = '词组' if (len(w) > 1 and w in PHRASES_DICT) else '单字'
            key = (w, py, src)
            seen.setdefault(key, []).append(s['id'])
for (w, py, src), ids in sorted(seen.items(), key=lambda kv: (kv[0][2], kv[0][0])):
    print(f'{src}\t{w}\t{py}\t{len(ids)}\t{",".join(ids[:6])}')
