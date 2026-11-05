"""关卡 4：答案两个独立来源一致才写 <套>/答案裁定.json。
  来源 A：解析 PDF（解析答案.py：按左右半栏 OCR、按题号就近配）→ <套>/解析答案.json；字母抽不到 / 与做题不一致的题，
         子代理只读该题解析讲解、按内容对应到我们的选项 → <套>/解析判读.json（埋雷 3/3）；
         2024-12—2025-12 六套的解析是选项顺序不同的版本（字母大多对不上），这六套全部按内容判读
  来源 B：子代理只看定稿原文 + 选项自己做题（不看解析）→ <套>/做题.json
  没有官方解析的 6 套（2023-06、2023-12、2024-06 的解析讲的是别的版本的试卷，题干对上 ≤ 4 道）：来源 A 换成第二次独立做题 <套>/做题2.json，汇报写明。
  人看过的（看解析原图 / 讲解）登记 <套>/答案人核.json {"题号": {"答案": "X", "理由": "…"}}，优先于两个来源。
  另查：正确选项的实词在本段原文里有没有出现（0 个的列出，推断题可以没有）。
用法：python3 答案.py ALL [--写]       不一致、缺的一次全部列出；--写 时把一致的写进 答案裁定.json（保留 题干 / 题干已核）"""
import json, re, sys
from pathlib import Path
H = Path(__file__).resolve().parents[1]
SHIFT = {'202412-1', '202412-2', '202506-1', '202506-2', '202512-1', '202512-2'}    # 解析用的试卷版本选项顺序不同：解析的字母不能直接用，只认按内容判读的
NOJX = {'202306-1', '202306-2', '202312-1', '202312-2', '202406-1', '202406-2'}


def load(p):
    return json.loads(p.read_text('utf-8')) if p.exists() else {}


def run(sid, write=False):
    sd = H / sid
    if sid in NOJX: a = load(sd / '做题2.json').get('答案', {})
    else:
        # 解析判读.json：子代理只读解析讲解、按内容对应到我们的选项（字母可能是别的版本的）——有就优先；版本不同的套只认它
        a = {} if sid in SHIFT else dict(load(sd / '解析答案.json').get('答案') or {})
        a.update({k: v for k, v in load(sd / '解析判读.json').items() if v in tuple('ABCD')})
    b = load(sd / '做题.json').get('答案', {})
    c = load(sd / '做题3.json').get('答案', {})
    maj = []
    hum = load(sd / '答案人核.json')
    rule = load(sd / '答案裁定.json')
    out, bad = {}, []
    for n in map(str, range(1, 26)):
        if n in hum: out[n] = hum[n]['答案']; continue
        x, y = a.get(n), b.get(n)
        z = c.get(n)          # 第三来源：第三次独立做题（只对两来源定不了的题做）
        if x and x == y: out[n] = x
        elif z and [v for v in (x, y, z) if v].count(z) >= 2: out[n] = z; maj.append(n)
        elif not x: bad.append((n, '来源 A 没有' + (f'，做题 {y} ≠ 做题3 {z}' if z else ''), y))
        else: bad.append((n, f'来源 A {x} ≠ 做题 {y}' + (f' ≠ 做题3 {z}' if z else ''), y))
    if write:
        keep = {k: v for k, v in rule.items() if not re.fullmatch(r'\d+', k)}
        keep.update(out); keep['_来源'] = '两个独立来源一致（' + ('两次独立做题' if sid in NOJX else '解析 PDF × 做题') + '）+ 答案人核.json' + (f'；第 {"、".join(maj)} 题两来源定不了，按三来源（加第三次独立做题 做题3.json）多数' if maj else '')
        (sd / '答案裁定.json').write_text(json.dumps(keep, ensure_ascii=False, indent=0), 'utf-8')
    return out, bad


if __name__ == '__main__':
    ids = [x for x in sys.argv[1:] if not x.startswith('--')]
    if ids == ['ALL']: ids = sorted(json.loads((H / '对照.json').read_text('utf-8'))['choice'])
    tot = 0
    for s in ids:
        o, b = run(s, '--写' in sys.argv)
        tot += len(b)
        if b: print(s, f'一致 {len(o)}', '；'.join(f'{n}:{w}' for n, w, _ in b))
    print(f'待定 {tot} 题'); sys.exit(1 if tot else 0)
