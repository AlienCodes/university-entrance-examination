"""作文讲义「题目译文」检查（四级作文、六级作文的 讲义.py check 都调用这里，规则只写一处）。

用户 2026-10-26：作文题目一定要非常详细地翻译成中文，让学生看懂题目到底什么意思。
检查：题目译文 不能缺、不能空，每条都要有中文；题目里的每个数字（字数上下限、30 分钟、图表数字、年份）
在译文里都要出现；英文引号里的标题 / 首句要在译文里原样出现（放在括号里对照）。
自检：python3 tools/作文题目译文.py --自检（全部篇目 0 处；拿掉字段、清空、删掉一个数字、改掉引号里的原句都要报出）。
"""
import json, re, sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
NUM = re.compile(r'\d+(?:\.\d+)?')


def prompt_of(proj, src):
    """proj = '四级' / '六级'；src = sents.json 里的 src（如 c2026-06-1）→ 英文题目（Directions 全文）。"""
    for f in sorted((R / proj / '作文').glob('20*.json')):
        for x in json.loads(f.read_text('utf-8')):
            if x['id'] == src:
                return x['prompt']
    raise KeyError(f'{proj}/作文 里找不到 {src}')


def check(prompt, lines):
    if not isinstance(lines, list) or not lines:
        return ['题目译文 缺或为空']
    errs = []
    for i, x in enumerate(lines, 1):
        if not isinstance(x, str) or not re.search(r'[一-鿿]', x):
            errs.append(f'题目译文 第 {i} 条没有中文')
    t = ' '.join(x for x in lines if isinstance(x, str))
    have = set(NUM.findall(t))
    miss = sorted(set(NUM.findall(prompt)) - have, key=float)
    if miss:
        errs.append(f'题目译文 漏了题目里的数字 {miss}')
    for q in re.findall(r'“(.+?)”', prompt):
        if q not in t:
            errs.append(f'题目译文 没有原样给出引号里的英文：{q[:40]}')
    return errs


def all_items():
    for proj in ('四级', '六级'):
        P = {p['id']: p for p in json.loads((R / f'{proj}作文/作文/sents.json').read_text('utf-8'))}
        for pid, p in sorted(P.items()):
            d = json.loads((R / f'{proj}作文/讲义/data/{pid}.json').read_text('utf-8'))
            yield f'{proj}/{pid}', prompt_of(proj, p['src']), d.get('题目译文')


def selftest():
    items = list(all_items())
    bad = [(k, e) for k, pr, ls in items for e in check(pr, ls)]
    ok = not bad
    print(f'现有 {len(items)} 篇：{len(bad)} 处', *bad[:5])
    k, pr, ls = next(x for x in items if '“' in x[1])          # 有引号首句 / 标题的一篇
    q = re.search(r'“(.+?)”', pr).group(1)
    bombs = {
        '拿掉字段': None,
        '清空': [],
        '一条没有中文': ls + ['(at least 120 words)'],
        '删掉 30': [x.replace('30', '三十') for x in ls],
        '删掉字数下限': [re.sub(r'\b(120|150)\b', '一百多', x) for x in ls],
        '改掉引号里的原句': [x.replace(q, q[:-3]) for x in ls],
    }
    k2, pr2, ls2 = next(x for x in items if '19.39' in x[1])    # 图表题
    for name, v in bombs.items():
        n = len(check(pr, v))
        print(f'  雷「{name}」（{k}）：{"报出" if n else "漏报！"}')
        ok &= n > 0
    n = len(check(pr2, [x.replace('19.39', '19.4') for x in ls2]))
    print(f'  雷「改图表数字」（{k2}）：{"报出" if n else "漏报！"}')
    ok &= n > 0
    print('自检通过' if ok else '自检失败')
    return 0 if ok else 1


if __name__ == '__main__':
    if '--自检' in sys.argv:
        sys.exit(selftest())
    errs = [f'{k} {e}' for k, pr, ls in all_items() for e in check(pr, ls)]
    print('\n'.join(errs) or '题目译文检查全部通过')
    sys.exit(1 if errs else 0)
