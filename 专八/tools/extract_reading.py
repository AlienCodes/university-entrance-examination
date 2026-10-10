"""从每套英语专业八级（专八）真题中提取 Part II Reading Comprehension · Section A 的三篇文章（Passage One、Two、Three），只要文章，不要题目。

    python3 专八/tools/extract_reading.py            # 重新生成（封版后文字有变化会报错）
    python3 专八/tools/extract_reading.py --reseal   # 精校完成后封版

用户 2026-10-10：专八只要 Section A 的 Passage One、Passage Two、Passage Three 三篇。
输入：专八/真题/年份年 英语专业八级真题.pdf（2016—2019、2021—2025，2020 年停考），用 pdftotext -layout 提取。
排序：从新到旧（2025 年在前），同一年按 Passage One、Two、Three；编号 t01 = 2025 年 Passage One … t27 = 2016 年 Passage Three。
分段：专八原文每段以 “(1) (2) …” 编号开头，按编号分段并核对编号连续，成稿去掉段号（与四六级一致）。
输出：专八/阅读/passages.json（与六级同一格式）、每篇一个文本文件、README.md 目录。
任何一篇提取异常（找不到起止、段号不连续、字数异常、残留页眉页码、混入题目）都会报错，不输出。
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # 专八/
REPO = ROOT.parent
SRC = ROOT / '真题'
OUT = ROOT / '阅读'
NAMES = ('Passage One', 'Passage Two', 'Passage Three')
HEAD = {'Passage One': r'PASSAGE\s+(?:ONE|1)', 'Passage Two': r'PASSAGE\s+(?:TWO|2)', 'Passage Three': r'PASSAGE\s+(?:THREE|3)'}
NOISE = re.compile(r'tem8app|言回|burningvocabulary|zhenti|https?:|www\.|^\d+\s*/\s*\d+$|^\d+$')
EDIT_F = HERE / '原文订正.json'
EDIT = json.loads(EDIT_F.read_text('utf-8')) if EDIT_F.exists() else {}

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location('cet6_extract_reading', REPO / '六级' / 'tools' / 'extract_reading.py')
_cet6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cet6)
tidy = _cet6.tidy                          # 中文注释、破折号、引号的统一排版与六级相同（模块同名，按路径单独加载）
sys.path.insert(0, str(REPO / '四级' / 'tools'))
import check_text                          # noqa: E402  排版检查与四六级共用


def blocks(txt):
    """Part II 的 Section A 里三篇文章的原始行：从篇名下一行到该篇第一道题之前。"""
    lines = txt.replace('\f', '\n').split('\n')
    p2 = next(k for k, l in enumerate(lines) if re.search(r'PART\s+II\b.*READING', l, re.I))
    sa = next(k for k in range(p2, len(lines)) if re.search(r'SECTION\s+A\b.*MULTIPLE', lines[k], re.I))
    sb = next(k for k in range(sa, len(lines)) if re.search(r'SECTION\s+B\b', lines[k], re.I))
    out = []
    for name in NAMES:
        i = next(k for k in range(sa, sb) if re.fullmatch(HEAD[name], lines[k].strip(), re.I))
        end = next(k for k in range(i + 1, sb) if re.match(r'\s*\d{1,2}\s*[.．]\s*(?=[A-Z])', lines[k]))      # 第一道题（如 11.What；5.5% 不算）
        out.append((name, lines[i + 1:end]))
    return out


JOINS = []        # 行尾连字符拼接记录（逐条人工核对：复合词保留连字符，断词去掉）


def respace(p):
    """2022—2025 年的试卷文字层常丢空格（10%tax、2014.When、&Eating、Association(AMA)urged、St.Louis），按固定规则补回；
    原文的字数统计 “(1023 words)” 去掉；词间用空格隔开的连字符 “ - ” 是破折号。"""
    p = re.sub(r'\s*\(\d+\s*words\)\s*$', '', p)
    p = re.sub(r'(?<=\d)%(?=[A-Za-z])', '% ', p)
    p = re.sub(r'(?<=[a-z]{2})\.(?=[A-Z][a-z])|(?<=\d{4})\.(?=[A-Z][a-z])|(?<=\bSt)\.(?=[A-Z])', '. ', p)
    p = re.sub(r'\s*&\s*', ' & ', p)
    p = re.sub(r'(?<=[A-Za-z])\((?=[A-Za-z])', ' (', p)
    p = re.sub(r'\)(?=[A-Za-z])', ') ', p)
    p = re.sub(r'(?<=[A-Za-z,.;:!?’”)]) - (?=[A-Za-z“‘(])', '—', p)
    return p


def post(p):
    """tidy 之后再补两处：中文注释后的全角逗号（anthropoid (类人猿)，though）、注释后紧接下一句（poplars (杨树).At）。"""
    p = re.sub(r'\s*，\s*(?=[A-Za-z“‘])', ', ', p)
    return re.sub(r'(?<=\))\.(?=[A-Z][a-z])', '. ', p)


def paragraphs(raw):
    """按 “(n)” 段号分段，段号必须从 1 连续递增；去掉页眉页脚、页码和空行。"""
    paras, nums = [], []
    for l in raw:
        s = l.strip()
        if not s or NOISE.search(s):
            continue
        m = re.match(r'\((\d{1,2})\)\s*(.*)$', s)
        if m and int(m.group(1)) == len(nums) + 1:
            nums.append(int(m.group(1)))
            paras.append(m.group(2))
        else:
            if not paras:
                raise ValueError(f'第一段之前有文字：{s[:60]}')
            prev = paras[-1]
            if prev.endswith('-') and re.search(r'[A-Za-z]-$', prev):
                JOINS.append(prev.split()[-1] + s.split()[0])
            paras[-1] = prev + s if prev.endswith('-') else prev + ' ' + s      # 行尾连字符：复合词保留连字符直接相连（逐条核对见 JOINS）
    if nums != list(range(1, len(nums) + 1)):
        raise ValueError(f'段号不连续：{nums}')
    return [respace(re.sub(r'\s{2,}', ' ', p)) for p in paras]


def main():
    OUT.mkdir(exist_ok=True)
    res, errs = [], []
    for f in sorted(SRC.glob('*.pdf'), reverse=True):                 # 从新到旧
        y = int(re.match(r'(\d{4})年', f.name).group(1))
        txt = subprocess.run(['pdftotext', '-layout', str(f), '-'], capture_output=True, text=True, check=True).stdout
        try:
            bs = blocks(txt)
        except StopIteration:
            errs.append(f'{f.name}：找不到 Section A 三篇文章的起止')
            continue
        for name, raw in bs:
            tag = f'{y}年 {name}'
            try:
                paras = [post(tidy(p)) for p in paragraphs(raw)]
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
            if not (500 <= words <= 1700) or len(paras) < 4:
                errs.append(f'{tag}：{len(paras)} 段、{words} 词，疑似提取异常')
            if any(re.search(r'^\d+\.|SECTION [AB]|PASSAGE (ONE|TWO|THREE)|ANSWER SHEET', p) for p in paras):
                errs.append(f'{tag}：混入了题目或说明')
            res.append({'id': f't{len(res) + 1:02d}', 'year': y, 'month': 3, 'set': 1, 'passage': name,
                        'paper': f'{y}年', 'part': name.split()[1], 'paras': paras, 'words': words,
                        'source': str(f.relative_to(ROOT))})
    if len(res) != 27:
        errs.append(f'文章总数 {len(res)} 篇，应为 27 篇（9 套 × 3 篇）')
    tags = {f"{r['paper']} {r['passage']}" for r in res}
    if set(EDIT) - tags:
        errs.append(f'原文订正.json 里有对不上篇目的条目：{sorted(set(EDIT) - tags)}')
    for r in res:
        # 以冒号结尾、引出下一段（引文或分条）的段落是正常写法（2016 年 Passage Three 第 5 段、2017 年 Passage Two 第 3 段），不算“段尾没有句末标点”
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
        seal_f.write_text(json.dumps({'说明': '专八阅读 Section A 27 篇精校定稿的文字指纹。文字一改就必须重新精校、重新封版（--reseal）。',
                                      '指纹': fp}, ensure_ascii=False, indent=1), 'utf-8')
    elif seal_f.exists():
        old = json.loads(seal_f.read_text('utf-8'))['指纹']
        diff = sorted(set(old.items()) ^ set(fp.items()))
        if diff:
            sys.exit('文字与封版不一致（改动未经精校）：\n  ' + '\n  '.join(sorted({k for k, _ in diff})) +
                     '\n确认已重新精校后，用 --reseal 重新封版。')
    (OUT / 'passages.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), 'utf-8')
    for old in OUT.glob('t*.txt'):
        old.unlink()
    rows = []
    for r in res:
        (OUT / f"{r['id']} {r['paper']} {r['passage']}.txt").write_text('\n\n'.join(r['paras']) + '\n', 'utf-8')
        first = r['paras'][0][:60].rsplit(' ', 1)[0] + ' …'
        rows.append(f"| {r['id']} | {r['year']} | {r['passage']} | {r['words']} | {len(r['paras'])} | {first} |")
    (OUT / 'README.md').write_text(
        '# 英语专业八级 阅读理解 Section A（2016—2025，共 27 篇）\n\n'
        '用户 2026-10-10：只要 Part II Reading Comprehension · Section A 的 Passage One、Two、Three。2020 年停考，无真题。\n'
        '从新到旧排列，同一年按 Passage One、Two、Three。原文段号 (1)(2)… 已去掉，段落顺序不变。\n\n'
        '| 编号 | 年份 | 篇目 | 词数 | 段数 | 开头 |\n|---|---|---|---|---|---|\n' + '\n'.join(rows) + '\n', 'utf-8')
    print(f'{len(res)} 篇，共 {sum(r["words"] for r in res)} 词 → {OUT}')


if __name__ == '__main__':
    main()
