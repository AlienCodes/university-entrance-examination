#!/usr/bin/env python3
"""给抽题子代理做精简材料包：每套 空白卷 + 解析 的听力部分（到第 21 题之前），删掉【解析】【详解】等讲解段，只留题目、说明、【答案】、【原文】。
用法：python3 -I 材料包.py <文字目录> <输出目录> <每包套数>  → 包01.txt …（另写 包清单.json）"""
import json, re, sys
from pathlib import Path

DROP = re.compile(r'^\s*【(解析|详解|分析|点睛|考点|导语|点评|解答|名师点睛|试题解析|考点定位|方法|总结)')
KEEP = re.compile(r'^\s*【(答案|原文|听力原文|录音原文)')
QLINE = re.compile(r'^\s*(\d{1,2})\s*[\.．、]')


def cut(s):
    a = re.search(r'第一节|Section\s*A|SECTION\s*A|听力', s)
    s = s[a.start():] if a else s
    m = None
    for mm in re.finditer(r'(?m)^\s*21\s*[\.．、]|第二部分|阅读理解|II\.\s*Grammar|Ⅱ\.\s*Grammar|Grammar and Vocabulary', s):
        if mm.start() > 800:
            m = mm; break
    rest = s[m.start():] if m else ''
    s = s[:m.start()] if m else s
    q20 = list(re.finditer(r'(?m)^\s*20\s*[\.．、]', s))
    if q20 and len(s) - q20[-1].start() > 3000:      # 结尾标记没找到：第 20 题之后最多留 3000 字
        rest = s[q20[-1].start() + 3000:] + rest
        s = s[:q20[-1].start() + 3000]
    k = re.search(r'1\s*[-~—–至]\s*5\s*[:：]?\s*[A-D]{3}|(?<!\d)1\s*[\.．、]\s*[A-D]\s+2\s*[\.．、]\s*[A-D]', rest)
    if k:                                            # 卷尾答案表（江苏、上海老版）
        s += '\n【卷尾答案表】\n' + rest[max(0, k.start() - 100):k.start() + 700]
    out, drop = [], False
    for l in s.split('\n'):
        l = l.replace('　', ' ').strip()
        if not l:
            continue
        if DROP.match(l):
            drop = True; continue
        if KEEP.match(l) or QLINE.match(l) or re.match(r'^(第[一二三]节|听第|Section|SECTION|Questions|Directions|[A-D][\.．])', l):
            drop = False
        if not drop:
            out.append(re.sub(r'\s{2,}', '  ', l))
    return '\n'.join(out)


def slim(srcs):
    """瘦身版（省 token）：一份题目来源（空白卷优先，其次听力试题、解析）全文 + 其余来源只留答案行；题目由 核题.py 拿其余来源原文逐字核。"""
    order = sorted(srcs, key=lambda x: (not x[0].startswith('空白卷'), not x[0].startswith('听力试题')))
    t0, b0 = order[0]
    out = [(t0, b0)]
    for t, b in order[1:]:
        keep = [l for l in b.split('\n') if re.match(r'^\s*【答案】', l) or re.search(r'1\s*[-~—–至]\s*5\s*[:：]?\s*[A-D]{3}', l)]
        i = b.find('【卷尾答案表】')
        if i >= 0: keep.append(b[i:])
        out.append((t + '·只留答案', '\n'.join(keep)))
    return out


if __name__ == '__main__':
    SLIM = '--瘦' in sys.argv
    sys.argv = [a for a in sys.argv if a != '--瘦']
    ONLY = sys.argv[4:]
    src, dst, n = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
    dst.mkdir(parents=True, exist_ok=True)
    sets = {}
    for f in sorted(src.glob('*.txt')):
        k, t = f.stem.split('__')
        if '天津' in k or '北京' in k:
            continue
        sets.setdefault(k, []).append((t, cut(f.read_text('utf-8'))))
    keys = [k for k in sets if not ONLY or k in ONLY]
    if SLIM:
        sets = {k: slim(v) for k, v in sets.items()}
    plan = {}
    for i in range(0, len(keys), n):
        name = f'包{i // n + 1:02d}'
        buf = []
        for k in keys[i:i + n]:
            for t, body in sets[k]:
                buf.append(f'\n######## 套={k}  来源={t}  ({len(body)} 字)\n{body}')
        (dst / f'{name}.txt').write_text('\n'.join(buf), 'utf-8')
        plan[name] = keys[i:i + n]
    (dst / '包清单.json').write_text(json.dumps(plan, ensure_ascii=False, indent=1), 'utf-8')
    for name, ks in plan.items():
        print(name, len((dst / f'{name}.txt').read_text('utf-8')), ks)
