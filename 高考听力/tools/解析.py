#!/usr/bin/env python3
"""从试卷 / 解析文字里抽听力题：题号、题干、选项、分组、答案、原文。
用法：python3 -I 解析.py <文字文件> → JSON（stdout）；--表 <清单.json> <文字目录> 打印每套抽取情况。"""
import json, re, sys
from pathlib import Path

OPT = re.compile(r'(?<![A-Za-z])([A-D])\s*[\.．]\s*')
QNUM = re.compile(r'^\s*(\d{1,2})\s*[\.．、]\s*(.*)$')


def listening(s):
    """只取听力部分：从开头到“阅读理解”/“第二部分”/“II. Grammar” 之前。"""
    a = re.search(r'第一节|Section\s*A', s)
    s = s[a.start():] if a else s
    m = re.search(r'第二部分|阅读理解\s*[（(]|第一部分\s*阅读|I\s*I\.\s*Grammar|Ⅱ\.\s*Grammar|II\.\s*Vocabulary|Grammar and Vocabulary', s)
    return s[:m.start()] if m else s


def norm(t):
    t = t.replace('　', ' ').replace('\t', ' ').replace('﻿', '')
    t = t.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    return re.sub(r' {2,}', ' ', t).strip()


def parse(s):
    s = listening(s)
    lines = [norm(l) for l in s.split('\n')]
    qs, cur, want, groups, ans, orig = {}, None, 1, [], {}, {}
    mode, otext = None, []
    for l in lines:
        if not l:
            continue
        g = re.search(r'听第\s*\d+\s*段材料[，,]\s*回答第\s*(\d+)\s*(?:[、,，]|至|到|-|—|~)\s*(\d+)\s*题', l) or \
            re.search(r'Questions\s+(\d+)\s+(?:through|to|and)\s+(\d+)', l)
        if g:
            groups.append([int(g.group(1)), int(g.group(2))])
        a = re.match(r'^【答案】\s*(.*)', l)
        if a:
            mode = None
            body = a.group(1)
            multi = re.findall(r'(\d{1,2})\s*[\.．、]?\s*([A-D])\b', body)
            if multi:
                for n, x in multi:
                    ans[int(n)] = x
                if len(multi) > 1:
                    groups.append([int(multi[0][0]), int(multi[-1][0])])
            elif cur and re.match(r'^[A-D]\b', body):
                ans[cur] = body[0]
            continue
        if l.startswith('【原文】'):
            mode = cur; otext = orig.setdefault(cur, [])
            l = l[4:].strip()
            if l:
                otext.append(l)
            continue
        m = QNUM.match(l)
        if m and int(m.group(1)) in (want, want + 1) and mode is None:
            cur = int(m.group(1)); want = cur + 1
            qs[cur] = {'stem': '', 'opts': {}}
            l = m.group(2)
        elif m and int(m.group(1)) in (want, want + 1) and mode is not None:
            mode = None; cur = int(m.group(1)); want = cur + 1
            qs[cur] = {'stem': '', 'opts': {}}
            l = m.group(2)
        if mode is not None:
            if re.match(r'^(【|第[一二]节|听下面)', l):
                mode = None
            else:
                otext.append(l)
                continue
        if cur is None or l.startswith('【'):
            continue
        l = re.sub(r'【此处可播放相关音频，请去附件查看】', '', l).strip()
        q = qs[cur]
        parts = OPT.split(l)
        head = parts[0].strip()
        if head and not q['opts']:
            q['stem'] = (q['stem'] + ' ' + head).strip()
        for i in range(1, len(parts) - 1, 2):
            q['opts'][parts[i]] = parts[i + 1].strip()
    return {'qs': qs, 'groups': groups, 'ans': ans, 'orig': {k: ' '.join(v) for k, v in orig.items()}}


if __name__ == '__main__':
    if sys.argv[1] == '--表':
        L = json.loads(Path(sys.argv[2]).read_text('utf-8')); T = Path(sys.argv[3])
        for k, v in L.items():
            if not v.get('音频'):
                continue
            row = [k]
            for c in ('空白卷', '解析', '听力试题', '原文'):
                for it in v.get(c, []):
                    p = parse((T / (Path(it['文件']).stem + '.txt')).read_text('utf-8', 'replace'))
                    nq = len(p['qs']); no = sum(1 for q in p['qs'].values() if len(q['opts']) >= 3)
                    row.append(f"{c}:{nq}题/{no}全选项/组{len(p['groups'])}/答{len(p['ans'])}/原{len(p['orig'])}")
            print(' | '.join(row))
    else:
        print(json.dumps(parse(Path(sys.argv[1]).read_text('utf-8', 'replace')), ensure_ascii=False, indent=1))
