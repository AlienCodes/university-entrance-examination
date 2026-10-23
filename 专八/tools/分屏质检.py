"""分屏质检（零 token，铁律 17：中英对应只看文字、由程序打分）：

    DZB_VARIANT=水墨 /opt/ttsenv/bin/python 专八/tools/分屏质检.py t11 … t27

①中英错屏：每屏词条的释义（按 ；，、 分成几个意思，去括注，至少两个字、在整句译文里只出现一次的）应出现在这一屏的中文里；
  落在别的屏的算错。整句 / 重复同一段中文的屏不算。一屏错 ≥ 2 且错多于对 → 列出。
②列举中间切开：下一屏以 or / and 开头、上一屏以逗号结尾、逗号前那一项不超过 3 个词且前面还有逗号（“blind, solo, / or double-amputee”）→ 列出。
只列可疑的句子，人只读这几句的文字。"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_video as M  # noqa: E402

P = {p['id']: p for p in json.loads((M.C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}


def senses(m):
    m = re.sub(r'^(n|v|adj|adv|prep|conj|pron|num|det|int|abbr)\.\s*', '', m)
    m = re.sub(r'[（(][^）)]*[）)]', '', m)
    return [x.strip('…… ') for x in re.split(r'[；，、;,]', m) if len(x.strip('…… ')) >= 2]


out = []
for pid in sys.argv[1:]:
    S = [x for pa in P[pid]['paras'] for x in pa]
    for k in sorted(M.SPLIT.get(pid, {}), key=int):
        s = S[int(k) - 1]
        parts = M.split_parts(pid, int(k), s)
        zhs = [z for _, _, z, _ in parts]
        bad = []
        for j, (lo, hi, zh, _) in enumerate(parts):
            if zhs.count(zh) > 1 or zh == s['zh']:
                continue
            wrong = right = 0
            for w in s['w']:
                if not lo <= w['sp'][0][0] < hi:
                    continue
                for x in senses(w['m']):
                    if s['zh'].count(x) == 1:
                        if x in zh:
                            right += 1
                        else:
                            wrong += 1
                        break
            if wrong >= 2 and wrong > right:
                bad.append(f'第 {j + 1} 屏 错/对 {wrong}/{right}')
        for j in range(1, len(parts)):
            prev, nxt = s['en'][parts[j - 1][0]:parts[j - 1][1]].rstrip(), s['en'][parts[j][0]:parts[j][1]]
            if re.match(r'(or|and)\b', nxt) and prev.endswith(',') and prev.count(',') >= 2 and len(prev.rsplit(',', 2)[-2].split()) <= 3:
                bad.append(f'第 {j}/{j + 1} 屏在列举中间切开：“…{prev[-30:]} / {nxt[:30]}…”')
        if bad:
            out.append(f'{pid} 第 {k} 句：' + '；'.join(bad))
for x in out:
    print(x)
print(f'分屏质检：{len(out)} 句可疑')
