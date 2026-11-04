"""读后续写讲解：把老师改过的逐字稿（逐字稿.py 导出的 docx）导回讲稿。老师的用词优先。
按 [段 id] 对回中文配音（英文朗读段不收），“／”还原成 ‖；列出改了哪些段（新旧对照）。
朗读规则 / 程序检查（阿拉伯数字、讲解推理、中文地道、口语停顿）碰到的只列出来、不自动改——按老师的写法保留，交协调会话定。
--写入：把改动写回源头（文字在 稿源.py 里恰好出现一次就改 稿源.py；在 逐块翻译稿.json 的 say 里恰好出现一次就改那里），再跑 稿源.py；
  对不上（文字是拼出来的，或出现不止一次）的段列为“要手改”，不写。
用法：python3 高考续写/tools/逐字稿导回.py 讲解目录 老师改过.docx [--写入]
      python3 高考续写/tools/逐字稿导回.py --自检      # 双向验证：导出 → 不改直接导回 = 0 处；改一个字 → 恰好报这一段"""
import copy
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / '高考语法填空/tools'), str(Path(__file__).parent)]
TAG = re.compile(r'^\s*\[([A-Za-z0-9]+)\]\s*(.*)$', re.S)


def read_docx(p):
    out = {}
    for para in Document(p).paragraphs:
        m = TAG.match(para.text)
        if m:
            out[m.group(1)] = m.group(2).strip().replace('／', '‖').replace('/', '‖')
    return out


def diff(d, docx):
    gao = json.loads((Path(d) / '稿.json').read_text('utf-8'))
    got = read_docx(docx)
    ch, miss = [], []
    for g in gao['segments']:
        if g['lang'] != 'Chinese':
            continue
        if g['id'] not in got:
            miss.append(g['id'])
        elif got[g['id']] != g['text']:
            ch.append((g['id'], g['text'], got[g['id']]))
    return gao, ch, miss


def rule_notes(gao, ch):
    import 中文地道 as ZD
    import 讲解推理 as TL
    import 稿检查 as GK
    new = copy.deepcopy(gao)
    m = {i: n for i, _, n in ch}
    for g in new['segments']:
        if g['id'] in m:
            g['text'] = m[g['id']]
    ids = set(m)
    E = [f'{i}：有阿拉伯数字（朗读规则：中文段写汉字数字）' for i, n in m.items() if re.search(r'\d', n)]
    E += [x for x in TL.problems(new) + ZD.problems(ZD.doc_items(new)) + GK.talk_problems(new) if any(re.search(rf'\b{i}\b', x) for i in ids)]
    return E


def write_back(d, ch):
    d = Path(d)
    src_p, zk_p = d / '稿源.py', d / '逐块翻译稿.json'
    src, zk = src_p.read_text('utf-8'), zk_p.read_text('utf-8')
    hand = []
    for i, old, new in ch:
        if src.count(old) == 1 and "'" not in new and '\\' not in new:
            src = src.replace(old, new)
            continue
        jo, jn = json.dumps(old, ensure_ascii=False)[1:-1], json.dumps(new, ensure_ascii=False)[1:-1]
        if zk.count(jo) == 1:
            zk = zk.replace(jo, jn)
            continue
        hand.append(i)
    src_p.write_text(src, 'utf-8')
    zk_p.write_text(zk, 'utf-8')
    subprocess.run([sys.executable, str(d / '稿源.py')], check=True, cwd=d)
    return hand


def selftest():
    import shutil
    import 逐字稿 as Z
    from docx import Document as D
    ok = True
    real = ROOT / '高考续写/讲解/2026_新课标Ⅰ卷'
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        for f in ('稿.json', '题目.json', '范文.json'):
            shutil.copy(real / f, t / f)
        Z.export(t, t / 'a.docx')
        _, ch, miss = diff(t, t / 'a.docx')
        print(f'  导出后不改直接导回：{len(ch)} 处变化、缺 {len(miss)} 段（应 0、0）')
        ok &= not ch and not miss
        w = D(t / 'a.docx')
        for p in w.paragraphs:
            if p.text.startswith('[s1b2]'):
                p.runs[-1].text = p.runs[-1].text.replace('附近', '旁边', 1)
        w.save(t / 'b.docx')
        _, ch, _ = diff(t, t / 'b.docx')
        print(f'  改 s1b2 一个词：报 {[c[0] for c in ch]}（应 [s1b2]）')
        ok &= [c[0] for c in ch] == ['s1b2']
    print('逐字稿导回 自检', '通过' if ok else '失败')
    return ok


if __name__ == '__main__':
    if sys.argv[1] == '--自检':
        sys.exit(0 if selftest() else 1)
    d, docx = sys.argv[1], sys.argv[2]
    gao, ch, miss = diff(d, docx)
    for i, old, new in ch:
        print(f'■ {i}\n  旧：{old}\n  新：{new}')
    if miss:
        print('✗ 逐字稿里找不到这些段（编号被改了？）：', ' '.join(miss))
    notes = rule_notes(gao, ch) if ch else []
    for x in notes:
        print('  ⚠ 检查碰到（保留老师写法，列给协调会话）：', x)
    print(f'改了 {len(ch)} 段；检查碰到 {len(notes)} 处；缺 {len(miss)} 段')
    if '--写入' in sys.argv and ch:
        hand = write_back(d, ch)
        print('已写回；要手改的段：', ' '.join(hand) or '无')
