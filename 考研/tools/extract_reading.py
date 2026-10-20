"""从每份考研英语真题（全国硕士研究生招生考试英语一、英语二）中提取 Section II Reading Comprehension · Part A 的四篇文章（Text 1—4），只要文章，不要题目。

    /opt/ttsenv/bin/python 考研/tools/extract_reading.py            # 重新生成（封版后文字有变化会报错）
    /opt/ttsenv/bin/python 考研/tools/extract_reading.py --reseal   # 精校完成后封版

用户 2026-10-20：考研真题每份试卷的 Text 1、Text 2、Text 3、Text 4 四篇，做法与专八晴空校园版完全相同。
输入：考研/真题/年份年考研英语一.pdf、年份年考研英语二.pdf（2021—2026，共 12 份），用 pdftotext -layout 提取。
排序：从新到旧（2026 年在前），同一年英语一在前、英语二在后，各按 Text 1—4；编号 k01 = 2026 年考研英语一 Text 1 … k48 = 2021 年考研英语二 Text 4。
分段：段首比正文多缩进（与六级相同；门槛“多 2 格以上”）；换页符所在行先去掉换页符再量缩进。
输出：考研/阅读/passages.json（与六级、专八同一格式）、每篇一个文本文件、README.md 目录。
任何一篇提取异常（找不到起止、字数异常、残留页眉页码、混入题目）都会报错，不输出。
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # 考研/
REPO = ROOT.parent
SRC = ROOT / '真题'
OUT = ROOT / '阅读'
NOISE = re.compile(r'考研|研究生|真题|第\s*\d+\s*页|https?:|www\.|^\d+\s*/\s*\d+$|^\d+$')
EDIT_F = HERE / '原文订正.json'
EDIT = json.loads(EDIT_F.read_text('utf-8')) if EDIT_F.exists() else {}

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location('cet6_extract_reading', REPO / '六级' / 'tools' / 'extract_reading.py')
_cet6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cet6)
tidy = _cet6.tidy                          # 中文注释、破折号、引号的统一排版与六级相同（模块同名，按路径单独加载）
sys.path.insert(0, str(REPO / '四级' / 'tools'))
import check_text                          # noqa: E402  排版检查与四六级共用


def key(f):
    y, n = re.match(r'(\d{4})年考研英语([一二])', f.name).groups()
    return int(y), '一二'.index(n) + 1


def blocks(txt):
    """Section II Part A 的四篇文章的原始行：从 “Text N” 下一行到该篇第一道题之前。"""
    lines = txt.split('\n')
    s2 = next(k for k, l in enumerate(lines) if re.search(r'Section\s+II\b.*Reading', l, re.I))
    pa = next(k for k in range(s2, len(lines)) if re.fullmatch(r'Part\s+A', lines[k].replace('\f', '').strip()))
    pb = next(k for k in range(pa, len(lines)) if re.fullmatch(r'Part\s+B', lines[k].replace('\f', '').strip()))
    out = []
    for n in range(1, 5):
        i = next(k for k in range(pa, pb) if re.fullmatch(rf'Text\s+{n}', lines[k].replace('\f', '').strip()))
        q = 21 + 5 * (n - 1)                                          # 每篇 5 题：Text 1 从第 21 题开始
        end = next(k for k in range(i + 1, pb) if re.match(rf'\s*{q}\s*[.．]', lines[k].replace('\f', '')))
        out.append((f'Text {n}', lines[i + 1:end]))
    return out


JOINS = []        # 行尾连字符拼接记录（逐条人工核对：复合词保留连字符，断词去掉）


def paragraphs(raw):
    """按缩进分段：段首比正文多缩进 2 格以上。去掉页眉页脚、页码、换页符和空行。"""
    rows = []
    for l in raw:
        l = l.replace('\f', '')
        s = l.strip()
        if not s or NOISE.search(s):
            continue
        rows.append((len(l) - len(l.lstrip(' ')), s))
    base = min(ind for ind, _ in rows)
    paras = []
    for ind, s in rows:
        if not paras or ind > base + 2:
            paras.append(s)
        else:
            prev = paras[-1]
            if prev.endswith('-') and re.search(r'[A-Za-z]-$', prev):
                JOINS.append(prev.split()[-1] + s.split()[0])
            paras[-1] = prev + s if prev.endswith('-') else prev + ' ' + s      # 行尾连字符：复合词保留连字符直接相连（逐条核对见 JOINS）
    if rows and rows[0][0] <= base + 2:
        raise ValueError('第一行不是段首（缩进不够），分段规则可能不适用')
    return [re.sub(r'\s{2,}', ' ', p) for p in paras]


def main():
    OUT.mkdir(exist_ok=True)
    res, errs = [], []
    for f in sorted(SRC.glob('*.pdf'), key=lambda f: (-key(f)[0], key(f)[1])):       # 从新到旧，同一年英语一在前
        y, n = key(f)
        paper = f'{y}年考研英语{"一二"[n - 1]}'
        txt = subprocess.run(['pdftotext', '-layout', str(f), '-'], capture_output=True, text=True, check=True).stdout
        try:
            bs = blocks(txt)
        except StopIteration:
            errs.append(f'{f.name}：找不到 Part A 四篇文章的起止')
            continue
        for name, raw in bs:
            tag = f'{paper} {name}'
            try:
                paras = [tidy(p) for p in paragraphs(raw)]
            except ValueError as e:
                errs.append(f'{tag}：{e}')
                continue
            text = '\n'.join(paras)
            for e in EDIT.get(tag, []):
                c = text.count(e['old'])
                if c != 1:
                    errs.append(f'{tag}：订正 “{e["old"]}” 匹配到 {c} 处（必须恰好 1 处）')
                text = text.replace(e['old'], e['new'])
            paras = text.split('\n')
            words = len(' '.join(paras).split())
            if any(re.search(r'[一-鿿]', re.sub(r'\([^()]*\)', '', p)) for p in paras):
                errs.append(f'{tag}：括号注释以外还有汉字，疑似页眉页脚或识别错误')
            if not (300 <= words <= 700) or len(paras) < 3:
                errs.append(f'{tag}：{len(paras)} 段、{words} 词，疑似提取异常')
            if any(re.search(r'^\d+\.|Section I|Part [AB]\b|Text [1-4]\b|ANSWER SHEET', p) for p in paras):
                errs.append(f'{tag}：混入了题目或说明')
            res.append({'id': f'k{len(res) + 1:02d}', 'year': y, 'month': 12, 'set': n, 'passage': name,
                        'paper': paper, 'part': name.split()[1], 'paras': paras, 'words': words,
                        'source': str(f.relative_to(ROOT))})
    if len(res) != 48:
        errs.append(f'文章总数 {len(res)} 篇，应为 48 篇（12 份 × 4 篇）')
    tags = {f"{r['paper']} {r['passage']}" for r in res}
    if set(EDIT) - tags:
        errs.append(f'原文订正.json 里有对不上篇目的条目：{sorted(set(EDIT) - tags)}')
    for r in res:
        colon = {f'第{k}段' for k, p in enumerate(r['paras'][:-1], 1) if re.search(r'[:：][”’)]*$', p)}
        errs += [f"{r['paper']} {r['passage']} {x}" for x in check_text.check(r)
                 if not (x.split(' ')[0] in colon and '段尾没有句末标点' in x)]
    if '--joins' in sys.argv:
        print('行尾连字符拼接：', JOINS)
    if errs:
        sys.exit('提取有问题，未输出：\n  ' + '\n  '.join(errs))
    seal_f = OUT / '封版.json'
    fp = {f"{r['id']} {r['paper']} {r['passage']}": hashlib.sha256('\n'.join(r['paras']).encode()).hexdigest()[:16] for r in res}
    if '--reseal' in sys.argv:
        seal_f.write_text(json.dumps({'说明': '考研英语阅读 Part A 48 篇精校定稿的文字指纹。文字一改就必须重新精校、重新封版（--reseal）。',
                                      '指纹': fp}, ensure_ascii=False, indent=1), 'utf-8')
    elif seal_f.exists():
        old = json.loads(seal_f.read_text('utf-8'))['指纹']
        diff = sorted(set(old.items()) ^ set(fp.items()))
        if diff:
            sys.exit('文字与封版不一致（改动未经精校）：\n  ' + '\n  '.join(sorted({k for k, _ in diff})) +
                     '\n确认已重新精校后，用 --reseal 重新封版。')
    (OUT / 'passages.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), 'utf-8')
    for old in OUT.glob('k*.txt'):
        old.unlink()
    rows = []
    for r in res:
        (OUT / f"{r['id']} {r['paper']} {r['passage']}.txt").write_text('\n\n'.join(r['paras']) + '\n', 'utf-8')
        first = r['paras'][0][:60].rsplit(' ', 1)[0] + ' …'
        rows.append(f"| {r['id']} | {r['paper']} | {r['passage']} | {r['words']} | {len(r['paras'])} | {first} |")
    (OUT / 'README.md').write_text(
        '# 考研英语 阅读理解 Part A（2021—2026，英语一、英语二，共 48 篇）\n\n'
        '用户 2026-10-20：每份试卷 Section II Reading Comprehension · Part A 的 Text 1—4。\n'
        '从新到旧排列，同一年英语一在前、英语二在后，各按 Text 1—4。\n\n'
        '| 编号 | 试卷 | 篇目 | 词数 | 段数 | 开头 |\n|---|---|---|---|---|---|\n' + '\n'.join(rows) + '\n', 'utf-8')
    print(f'{len(res)} 篇，共 {sum(r["words"] for r in res)} 词 → {OUT}')


if __name__ == '__main__':
    main()
