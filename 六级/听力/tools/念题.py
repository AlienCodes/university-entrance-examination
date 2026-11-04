"""念题校对材料：各套念题（Question N: …）在 otter 底稿里的词位 + 解析里的英文题干，并排列出。
定稿.py 只拿解析原文比对正文，念题部分解析原文里没有，转写错（断句、漏 Question、人名不一致）比不到。
校对结果写进 <套>/待核裁定.json 的 "改 a:b"（定稿.py 整段改写），题目.py 的题干随之变。
用法：python 念题.py <套> …   打印 TSV：套  题号  a:b  念题（otter 原样）  解析题干（OCR）"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import 定稿 as G
import 题目 as T

NUM = {w: i + 1 for i, w in enumerate('one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty twenty-one twenty-two twenty-three twenty-four twenty-five'.split())}


def stems(sid):
    sd = G.D / sid
    W = [w for _, _, ws in G.otter((sd / 'otter.txt').read_text('utf-8')) for w in ws]
    out = {}
    i = 0
    while i < len(W):
        w = W[i]
        a = None
        if re.fullmatch(r'[Qq]uestion', w) and i + 1 < len(W):
            k = re.sub(r'\W+$', '', W[i + 1]).lower()
            if k.isdigit() or k in NUM: a, num = i, int(k) if k.isdigit() else NUM[k]
        elif re.fullmatch(r'(2[0-5]|1\d|[1-9]):', w) and (i == 0 or W[i - 1].endswith(('?', '.'))):
            a, num = i, int(w[:-1])                          # 漏了 Question 的
        if a is None or num in out:
            i += 1; continue
        j = a + (1 if W[a].endswith(':') and W[a][0].isdigit() else 2)
        while j < len(W) and not (re.fullmatch(r'[Qq]uestions?', W[j]) and j + 1 < len(W) and re.match(r'\w', W[j + 1]) and (W[j + 1].strip(':.,').lower() in NUM or W[j + 1].strip(':.,').isdigit())) \
                and not (re.match(r"(That|This)('s)?$", W[j]) and j + 2 < len(W) and W[j + 1] in ('is', 'the', 'end')) \
                and not re.fullmatch(r'(2[0-5]|1\d|[1-9]):', W[j]) \
                and not (W[j].lower() in ('section', 'passage', 'recording', 'conversation') and j > a + 3
                         and j + 1 < len(W) and W[j + 1].strip('.,:').lower() in set(NUM) | {'a', 'b', 'c', '1', '2', '3'}):
            j += 1
        out[num] = (a, j, ' '.join(W[a:j]))
        i = j
    return out


if __name__ == '__main__':
    for sid in sys.argv[1:]:
        ocr = (G.D / sid / '解析原文.txt').read_text('utf-8')
        st = stems(sid)
        for n in range(1, 26):
            a, b, t = st.get(n, (0, 0, '（找不到）'))
            print(f'{sid}\t{n}\t{a}:{b}\t{t}\t{T.ocr_stem(ocr, n)}')
