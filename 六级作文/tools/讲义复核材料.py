#!/usr/bin/env python3
"""讲义内容复核材料：把 讲义/data/cNN.json 转成只读文字的复核稿（每个字段带位置标签，审阅员按标签报问题）。

  python3 六级作文/tools/讲义复核材料.py A --篇 c01-c10 [--雷 埋雷.json] [--总论] > 稿.md   # 考官/教研：全部内容
  python3 六级作文/tools/讲义复核材料.py B --篇 c01-c31 [--雷 埋雷.json] > 稿.md            # 母语编辑：只看英文（例句、替换、升格、词汇）
  python3 六级作文/tools/讲义复核材料.py F --篇 c01-c31 [--雷 埋雷.json] > 稿.md            # 只看句式卡（公式与原句、例句是否对得上）
  python3 六级作文/tools/讲义复核材料.py apply 修改.json                                     # 按位置标签改数据（old 必须恰好出现一次）

埋雷 / 修改 文件：[{"篇": "c30", "位置": "句式[0].例句[1].en", "old": "…", "new": "…"}, …]
埋雷只改内存里的副本，不动数据文件；每颗雷 old 必须在该字段恰好出现一次，否则报错（雷必须真的埋进去）。
"""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
C = ROOT / '六级作文'
DATA = C / '讲义' / 'data'


def ids(spec):
    out = []
    for part in spec.split(','):
        a, _, b = part.partition('-')
        b = b or a
        out += [f'c{i:02d}' for i in range(int(a[1:]), int(b[1:]) + 1)]
    return out


def get_ref(d, path):
    """位置标签 → (容器, 键)。"""
    keys = re.findall(r'([^.\[\]]+)|\[(\d+)\]', path)
    cur, last = d, None
    seq = [(int(i) if i else k) for k, i in keys]
    for k in seq[:-1]:
        cur = cur[k]
    return cur, seq[-1]


def patch(d, path, old, new, who):
    cur, k = get_ref(d, path)
    v = cur[k]
    if not isinstance(v, str) or v.count(old) != 1:
        sys.exit(f'{who} {path}：“{old}”出现 {v.count(old) if isinstance(v, str) else "?"} 次（必须恰好一次）')
    cur[k] = v.replace(old, new)


def prompts():
    out = {}
    for f in sorted((ROOT / '六级' / '作文').glob('20*.json')):
        for x in json.load(open(f)):
            out[x['id']] = x
    return out


def essay():
    return {p['id']: p for p in json.load(open(C / '作文' / 'sents.json'))}


def render(v, path, lines, depth=0):
    pad = '  ' * depth
    if isinstance(v, dict):
        for k, x in v.items():
            p = f'{path}.{k}' if path else k
            if isinstance(x, list) and all(isinstance(y, int) for y in x):
                lines.append(f'{pad}- 【{p}】 {x}')
            elif isinstance(x, (dict, list)):
                lines.append(f'{pad}- 【{p}】')
                render(x, p, lines, depth + 1)
            else:
                lines.append(f'{pad}- 【{p}】 {x}')
    elif isinstance(v, list):
        for i, x in enumerate(v):
            render(x, f'{path}[{i}]', lines, depth) if isinstance(x, (dict, list)) else lines.append(f'{pad}- 【{path}[{i}]】 {x}')


def head(pid, E, PR, prompt=True):
    p = E[pid]
    pr = PR.get(p['src'], {})
    S = [s for pa in p['sents'] for s in pa]
    out = [f'# {pid}　{p["paper"]}', '']
    if prompt:
        out += [f'**题目**（{pr.get("type", "")}，{pr.get("limit", "")}）：{pr.get("prompt", "")}', '']
    out += ['**范文（定稿，不许改；句号即“第 N 句”）**：']
    out += [f'{i}. {s}' for i, s in enumerate(S, 1)]
    return out + ['']


def english_only(d):
    """B 稿：只留英文——句式卡的公式、例句和替换的英文，升格的每一步写法，词汇的词和替代说法（位置标签与数据一致）。"""
    out = {'句式': [], '升格': [], '词汇': []}
    for x in d.get('句式', []):
        out['句式'].append({'名称': x.get('名称', ''), '公式': x.get('公式', ''),
                          '例句': [{'en': y['en']} for y in x.get('例句', [])],
                          '替换': [{'en': y['en']} for y in x.get('替换', [])]})
    for x in d.get('升格', []):
        out['升格'].append({'原句': x['原句'], '步骤': [{'写法': y['写法']} for y in x['步骤']]})
    out['词汇'] = [{'词': y['词'], '替代': y['替代']} for y in d.get('词汇', [])]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['A', 'B', 'F', 'apply'])
    ap.add_argument('file', nargs='?')
    ap.add_argument('--篇', default='c01-c31')
    ap.add_argument('--雷')
    ap.add_argument('--总论', action='store_true')
    a = ap.parse_args()
    if a.mode == 'apply':
        n = 0
        for x in json.load(open(a.file)):
            f = DATA / f'{x["篇"]}.json'
            d = json.load(open(f))
            patch(d, x['位置'], x['old'], x['new'], x['篇'])
            json.dump(d, open(f, 'w'), ensure_ascii=False, indent=1)
            open(f, 'a').write('\n')
            n += 1
        print(f'已改 {n} 处')
        return
    mines = json.load(open(a.雷)) if a.雷 else []
    E, PR = essay(), prompts()
    lines = []
    todo = ids(a.篇)
    if a.总论:
        z = json.load(open(DATA / '总论.json'))
        for m in mines:
            if m['篇'] == '总论':
                patch(z, m['位置'], m['old'], m['new'], '雷')
        lines += ['# 总论（六级写作总攻略）', '']
        render(z, '', lines)
        lines.append('')
    for pid in todo:
        d = copy.deepcopy(json.load(open(DATA / f'{pid}.json')))
        for m in mines:
            if m['篇'] == pid:
                patch(d, m['位置'], m['old'], m['new'], '雷')
        lines += head(pid, E, PR, a.mode == 'A') if a.mode != 'F' else [f'# {pid}', '']
        d.pop('id', None)
        if a.mode == 'F':      # 只看句式卡：公式与原句、例句、替换说法是否对得上
            d = {'句式': d.get('句式', [])}
        render(d if a.mode in ('A', 'F') else english_only(d), '', lines)
        lines.append('')
    used = {m['篇'] for m in mines}
    miss = used - set(todo) - ({'总论'} if a.总论 else set())
    if miss:
        sys.exit(f'雷埋在本稿之外的篇目：{sorted(miss)}')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
