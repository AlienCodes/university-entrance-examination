"""把专八翻译复核中最终采用的修改写回 专八/ann/sNN.txt（由高考 tools/pipeline/apply3.py 改写）。

输入 decisions3.json：[{pid, sent, field, headword, current, proposed}]
- zh       : 第 sent 句中文整行替换（current 必须与现有整行完全一致）
- gloss    : 第 sent 句里 headword 的释义替换
- headword : 第 sent 句里 headword 改成 proposed（proposed 可带 {原文} 和 ~/* 标记）
- tier     : 第 sent 句里 headword 的分级改为 proposed（单词/短语）
- title/genre : T:/G: 整行替换
- summary  : S: 行里把 current 子串换成 proposed
- entry    : 整条词条替换（current/proposed 都是 ann 原始写法，如 "~for the better{for better}=变得更好"）
- add      : 在第 sent 句末尾追加词条（proposed 为 ann 原始写法）
- drop     : 删除第 sent 句里 headword 这一条
任何一条匹配不到都报错（踩坑：修正静默失效）。
英文原文的修改（field=en）不在这里处理，写进 sent.py 的 FIX。
"""
import json
import re
import sys
from pathlib import Path

ANN = Path(__file__).resolve().parents[1] / 'ann'      # 专八/ann
TIER = {'单词': '', '短语': '~'}


def parse_entry(e):
    m = re.match(r'^([~*]?)(.+?)(\{[^}]*\})?=(.*)$', e.strip())
    if not m:
        raise ValueError(f'无法解析词条：{e}')
    return {'mark': m.group(1), 'head': m.group(2), 'surf': m.group(3) or '', 'mean': m.group(4)}


def fmt(x):
    return f"{x['mark']}{x['head']}{x['surf']}={x['mean']}"


def apply(decisions):
    by = {}
    for d in decisions:
        by.setdefault(d['pid'], []).append(d)
    errs = []
    for pid, ds in by.items():
        f = ANN / f'{pid}.txt'
        lines = f.read_text('utf-8').split('\n')
        # 定位每句：中文行下标、词条行下标
        zh_at, wl_at = {}, {}
        for i, ln in enumerate(lines):
            m = re.match(r'^(\d+) (.*)$', ln)
            if m:
                zh_at[int(m.group(1))] = i
                wl_at[int(m.group(1))] = i + 1
        for d in ds:
            fld, k = d['field'], d.get('sent', 0)
            try:
                if fld in ('title', 'genre'):
                    tag = 'T: ' if fld == 'title' else 'G: '
                    i = next(i for i, ln in enumerate(lines) if ln.startswith(tag))
                    if lines[i][3:] != d['current']:
                        raise ValueError(f'现有 {lines[i][3:]!r} ≠ {d["current"]!r}')
                    lines[i] = tag + d['proposed']
                elif fld == 'summary':
                    i = next(i for i, ln in enumerate(lines) if ln.startswith('S: '))
                    if lines[i].count(d['current']) != 1:
                        raise ValueError(f'概要里找不到（或不唯一）{d["current"]!r}')
                    lines[i] = lines[i].replace(d['current'], d['proposed'])
                elif fld == 'zh':
                    i = zh_at[k]
                    cur = lines[i].split(' ', 1)[1]
                    if cur != d['current']:
                        raise ValueError(f'现有 {cur!r} ≠ {d["current"]!r}')
                    lines[i] = f'{k} {d["proposed"]}'
                else:
                    i = wl_at[k]
                    assert lines[i].startswith('= '), lines[i]
                    ents = [parse_entry(e) for e in lines[i][2:].split(' | ')]
                    if fld == 'add':
                        ents.append(parse_entry(d['proposed']))
                    elif fld == 'entry':
                        j = [n for n, e in enumerate(ents) if fmt(e) == d['current']]
                        if len(j) != 1:
                            raise ValueError(f'找不到词条 {d["current"]!r}')
                        ents[j[0]] = parse_entry(d['proposed'])
                    else:
                        j = [n for n, e in enumerate(ents) if e['head'] == d['headword']]
                        if len(j) != 1:
                            raise ValueError(f'词条 {d["headword"]!r} 匹配到 {len(j)} 条')
                        e = ents[j[0]]
                        if fld == 'gloss':
                            if e['mean'] != d['current']:
                                raise ValueError(f'现有释义 {e["mean"]!r} ≠ {d["current"]!r}')
                            e['mean'] = d['proposed']
                        elif fld == 'tier':
                            e['mark'] = TIER[d['proposed']]
                        elif fld == 'headword':
                            n = parse_entry(d['proposed'] + '=x')
                            e['head'], e['surf'] = n['head'], n['surf'] or e['surf']
                            if n['mark']:
                                e['mark'] = n['mark']
                        elif fld == 'drop':
                            ents.pop(j[0])
                        else:
                            raise ValueError(f'未知字段 {fld}')
                    lines[i] = '= ' + ' | '.join(fmt(e) for e in ents)
            except Exception as ex:  # noqa: BLE001
                errs.append(f'{pid}:{k} {fld} {d.get("headword", "")}: {ex}')
        f.write_text('\n'.join(lines), 'utf-8')
    return errs


if __name__ == '__main__':
    errs = apply(json.load(open(sys.argv[1])))
    for e in errs:
        print('❌', e)
    print('errors', len(errs))
    sys.exit(1 if errs else 0)
