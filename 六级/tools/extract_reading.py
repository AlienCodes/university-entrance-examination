"""从每套六级真题中提取 Section C 仔细阅读的两篇文章（Passage One、Passage Two），只要文章，不要题目。

    python3 六级/tools/extract_reading.py            # 重新生成（文字与封版不一致会报错）
    python3 六级/tools/extract_reading.py --reseal   # 重新精校完成后重新封版

输入：六级/真题/年份/年份年月份/*.pdf（用 pdftotext -layout 重新提取，靠缩进判断分段）
输出：
  六级/仔细阅读/passages.json        与高考 tools/passages.json 同一格式，后续可走同一套流程
  六级/仔细阅读/年份年月 第n套 Passage One.txt 等   每篇一个文本文件，段落之间空一行
  六级/仔细阅读/README.md            目录
任何一篇提取异常（找不到起止、段落为空、字数异常、残留页眉页码）都会报错，不输出。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / '真题'
OUT = ROOT / '仔细阅读'
CJK = re.compile(r'[一-鿿]')
# 2021 年 12 月、2022 年 6 月的几套是扫描件，文字层可能有识别错误，对照页面图片逐字校对后
# 以 “年份年月 第n套 Passage One” 为键整篇替换（六级/tools/人工校对.json）。
HERE = Path(__file__).resolve().parent
# 六级（2026-10-09 用户）：Section C Passage One、Passage Two 按四级同一套流程做；只要 60 篇，从 2026 年开始往下排，
# 最后两篇（2021 年 6 月第 1 套的两篇）不要（真题存档和人工校对稿都保留）。编号 s01 = 2026 年 6 月第 3 套 Passage Two，依次往下。
SKIP = {(2021, 6, 1)}
TOTAL = 60
FIX = json.loads((HERE / '人工校对.json').read_text('utf-8'))
# 原文订正：试卷本身的错误（拼写、语法、标点、括号不配对等）和提取错误，逐条写明类型和理由。
# 每条的原文片段必须在该篇恰好出现一次，否则报错（与高考 tools/sent.py 的 POST 规则相同）。
# 订正记录 仔细阅读/原文订正记录.md 由本文件自动生成，二者永远一致。
EDIT = json.loads((HERE / '原文订正.json').read_text('utf-8'))


def key(f):
    y, m, n = re.search(r'(\d{4})年(\d+)月 英语六级真题 第(\d)套', f.stem).groups()
    return int(y), int(m), int(n)


def blocks(txt):
    """返回 [(篇名, 原始行列表)]：从 “Questions x to y are based on the following passage.” 下一行到第一题之前。"""
    lines = txt.split('\n')
    out = []
    for name in ('Passage One', 'Passage Two'):
        i = next(k for k, l in enumerate(lines) if l.strip() == name)
        # 扫描件的文字层可能有识别错误（如 “46 to SO”“ollowing”），起止标记放宽匹配
        j = next(k for k in range(i, i + 4) if re.search(r'Questions \S+ to \S+ are based on the \S*ollowing passage', lines[k]))
        q = 46 if name == 'Passage One' else 51
        end = next(k for k in range(j + 1, len(lines)) if re.match(rf'\s*{q}\s*[.,，。]', lines[k]))
        out.append((name, lines[j + 1:end]))
    return out


def key_of(tag):
    y, m, n = re.match(r'(\d{4})年(\d+)月 第(\d)套', tag).groups()
    return int(y), int(m), int(n)


def gap_starts(pdf):
    """段首不缩进、靠段间距分段的试卷（如 2026 年 6 月第 1 套）：用 pdftotext -bbox-layout 的行坐标，
    行距明显大于正常行距（> 1.4 倍）的行是段首。返回 {去空白的行文字: 是否段首}。"""
    import html
    xml = subprocess.run(['pdftotext', '-bbox-layout', str(pdf), '-'], capture_output=True, text=True, check=True).stdout
    out = {}
    for page in xml.split('<page ')[1:]:
        prev = None
        lines = re.findall(r'<line xMin="[\d.]+" yMin="([\d.]+)"[^>]*>(.*?)</line>', page, re.S)
        steps = sorted(float(b[0]) - float(a[0]) for a, b in zip(lines, lines[1:]) if float(b[0]) > float(a[0]))
        normal = steps[len(steps) // 4] if steps else 0
        for y, body in lines:
            words = html.unescape(' '.join(re.findall(r'<word[^>]*>(.*?)</word>', body)))
            y = float(y)
            out[re.sub(r'\s', '', words)] = prev is not None and y - prev > 1.4 * normal
            prev = y
    return out


def paragraphs(raw, starts=None):
    """按缩进分段：段首比正文多缩进。去掉页眉（含中文、不在括号注释里）、页码、换页符和空行。"""
    rows = []
    for l in raw:
        l = l.replace('\f', '')
        s = l.strip()
        if not s or re.fullmatch(r'\d+', s):
            continue
        if re.search(r'六级|四级|大学英语|真题|第\s*\d+\s*页|https?:|burningvocabulary|zhenti', s):      # 页眉页脚，如“2023 年 6 月大学英语六级考试真题（第 1 套）”
            continue
        rows.append((len(l) - len(l.lstrip(' ')), s))
    # 段首比正文多缩进 3—5 格；有的试卷续行会整体右移 2 格（2025 年 12 月第 2 套），所以门槛是“多 2 格以上”
    base = min(ind for ind, _ in rows)
    flat = starts is not None and all(ind <= base + 2 for ind, _ in rows)
    paras = []
    for ind, s in rows:
        if not paras or (starts.get(re.sub(r'\s', '', s), False) if flat else ind > base + 2):
            paras.append(s)
        else:
            prev = paras[-1]
            # 行尾连字符：复合词（self-doubt）保留连字符直接相连
            paras[-1] = prev + s if prev.endswith('-') else prev + ' ' + s
    return [re.sub(r'\s{2,}', ' ', p) for p in paras]


def tidy(p):
    """统一排版：中文注释用半角括号、前后各一个空格，如 “stigma (耻辱) and”；破折号统一为 “—”。"""
    p = re.sub(r'\s*[（(]\s*([^（）()]*[一-鿿][^（）()]*?)\s*[）)]\s*', r' (\1) ', p)
    p = re.sub(r' \) ', ') ', p)
    p = re.sub(r'\) ([.,;:!?’”])', r')\1', p)
    p = re.sub(r'(?<=[一-鿿])\s+(?=[一-鿿])', '', p)          # 中文注释里字与字之间的空格，如 (感 知 的)
    p = re.sub(r'(?<=[A-Za-z])\s*[一—–]{1,2}\s*(?=[A-Za-z“‘])', '—', p)
    p = re.sub(r'\s*—\s*', '—', p)                              # 破折号两侧不留空格（全书统一）
    p = re.sub(r'(?<=\d) [-–] (?=\d)', '–', p)                   # 数字范围用短横线：1935–1936
    # 直引号统一为弯引号：词内撇号 ’；双引号按前后位置分左右
    p = re.sub(r"(?<=\w)'(?=\w)|(?<=s)'(?=\s)", '’', p)
    p = re.sub(r'(^|(?<=[\s(—]))"', '“', p).replace('"', '”')
    p = re.sub(r"(^|(?<=[\s(—“]))'", '‘', p).replace("'", '’')
    p = re.sub(r'(?<=\w)“(?=[\s.,;:!?]|$)', '”', p)      # 试卷里错用的左引号，如 “transform“
    return re.sub(r'\s{2,}', ' ', p).strip()


def main():
    OUT.mkdir(exist_ok=True)
    res, rows, errs = [], [], []
    files = sorted(SRC.glob('*/*/*.pdf'), key=key, reverse=True)       # 从新到旧
    for f in files:
        y, m, n = key(f)
        if (y, m, n) in SKIP:
            continue
        txt = subprocess.run(['pdftotext', '-layout', str(f), '-'], capture_output=True, text=True, check=True).stdout
        try:
            bs = blocks(txt)
        except StopIteration:
            errs.append(f'{f.name}：找不到 Passage One/Two 的起止')
            continue
        for name, raw in reversed(bs):                                  # 同一套里 Passage Two 在前（与四级合集顺序一致）
            tag = f'{y}年{m}月 第{n}套 {name}'
            paras = [tidy(p) for p in (FIX.pop(tag) if tag in FIX else paragraphs(raw, gap_starts(f)))]
            text = '\n'.join(paras)
            for e in EDIT.get(tag, []):
                c = text.count(e['old'])
                if c != 1:
                    errs.append(f'{tag}：订正 “{e["old"]}” 匹配到 {c} 处（必须恰好 1 处）')
                text = text.replace(e['old'], e['new'])
            paras = text.split('\n')
            words = len(' '.join(paras).split())
            if any(re.search(r'[一-鿿]', re.sub(r'\([^()]*\)', '', p)) for p in paras):
                errs.append(f'{tag}：括号注释以外还有汉字，疑似识别错误')
            if not (300 <= words <= 600) or len(paras) < 3:
                errs.append(f'{tag}：{len(paras)} 段、{words} 词，疑似提取异常')
            if any(re.search(r'Questions \d|^\d+\.|Section [ABC]|Directions', p) for p in paras):
                errs.append(f'{tag}：混入了题目或说明')
            res.append({'id': f's{len(res) + 1:02d}', 'year': y, 'month': m, 'set': n, 'passage': name,
                        'paper': f'{y}年{m}月 第{n}套', 'part': 'One' if name.endswith('One') else 'Two',
                        'paras': paras, 'words': words, 'source': str(f.relative_to(ROOT))})
    # 同一次考试不同套题偶尔共用文章：标出完全相同的
    seen = {}
    for r in res:
        seen.setdefault(' '.join(r['paras']), []).append(f"{r['paper']} {r['passage']}")
    dups = [v for v in seen.values() if len(v) > 1]
    if len(res) != TOTAL:
        errs.append(f'文章总数 {len(res)} 篇，定题是 {TOTAL} 篇')
    for k in list(FIX):
        if key_of(k) in SKIP:
            del FIX[k]
    for k in list(EDIT):
        if key_of(k) in SKIP:
            del EDIT[k]
    if FIX:
        errs.append(f'人工校对.json 里有未用上的条目：{list(FIX)}')
    tags = {f"{r['paper']} {r['passage']}" for r in res}
    if set(EDIT) - tags:
        errs.append(f'原文订正.json 里有对不上篇目的条目：{sorted(set(EDIT) - tags)}')
    sys.path.insert(0, str(ROOT.parent / '四级' / 'tools'))      # 排版检查与四级共用
    import check_text
    for r in res:
        errs += [f"{r['paper']} {r['passage']} {x}" for x in check_text.check(r)]
    if errs:
        sys.exit('提取有问题，未输出：\n  ' + '\n  '.join(errs))
    # 封版：精校完成后记录每篇文字指纹（仔细阅读/封版.json）。之后文字有任何变化都报错，
    # 必须重新精校并用 --reseal 重新封版，防止未经复核的改动混进定稿。
    import hashlib
    seal_f = OUT / '封版.json'
    fp = {f"{r['id']} {r['paper']} {r['passage']}": hashlib.sha256('\n'.join(r['paras']).encode()).hexdigest()[:16] for r in res}
    if '--reseal' in sys.argv:
        seal_f.write_text(json.dumps({'说明': '六级仔细阅读 60 篇精校定稿的文字指纹。文字一改就必须重新精校、重新封版（--reseal）。',
                                      '指纹': fp}, ensure_ascii=False, indent=1), 'utf-8')
    elif seal_f.exists():
        old = json.loads(seal_f.read_text('utf-8'))['指纹']
        diff = sorted(set(old.items()) ^ set(fp.items()))
        if diff:
            sys.exit('文字与封版不一致（改动未经精校）：\n  ' + '\n  '.join(sorted({k for k, _ in diff})) +
                     '\n确认已重新精校后，用 --reseal 重新封版。')
    (OUT / 'passages.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), 'utf-8')
    for old in OUT.glob('*.txt'):
        old.unlink()
    for r in res:
        (OUT / f"{r['id']} {r['paper']} {r['passage']}.txt").write_text('\n\n'.join(r['paras']) + '\n', 'utf-8')
        first = r['paras'][0][:60].rsplit(' ', 1)[0] + ' …'
        rows.append(f"| {r['id']} | {r['year']} | {r['month']} 月 | 第 {r['set']} 套 | {r['passage']} | {r['words']} | {len(r['paras'])} | {first} |")
    note = ''
    if dups:
        note = '\n> 以下文章在不同套题中完全相同（试卷本身如此），后续加工时只需做一次：\n' + ''.join(f'> - {" ＝ ".join(v)}\n' for v in dups)
    (OUT / 'README.md').write_text(
        f"# 六级仔细阅读文章（Section C）\n\n共 {len(res)} 篇：每套真题的 Passage One 和 Passage Two（只要 60 篇：从 2026 年 6 月往下排，不收 2021 年 6 月第 1 套），只有文章，不含题目。"
        f"每篇一个 `.txt`（段落之间空一行）；`passages.json` 与高考项目 `tools/passages.json` 格式相同，可直接走后续流程。\n{note}\n"
        "\n生成方法：`python3 六级/tools/extract_reading.py`（从 PDF 提取，按缩进分段，去页眉页脚）。"
        "2021 年 6 月、12 月和 2022 年 6 月的 6 套是扫描件，对照试卷页面逐字校对（`六级/tools/人工校对.json`）；"
        "中文注释统一为 “word (中文)”，引号撇号统一为弯引号，试卷本身的错误订正见 原文订正记录.md。\n\n"
        "| 编号 | 年份 | 月份 | 套次 | 篇目 | 词数 | 段数 | 开头 |\n|---|---|---|---|---|---|---|---|\n" + '\n'.join(rows) + '\n', 'utf-8')
    rec = ['# 六级仔细阅读原文订正记录\n',
           '由 `六级/tools/extract_reading.py` 根据 `六级/tools/原文订正.json` 自动生成。'
           '标准与高考部分相同：认真的英语老师或专业编辑会判错的就改，“试卷原文就是这样写的”不是保留错误的理由；'
           '英式拼写和合法的新闻文体不算错。\n',
           '类型：**原文错误**＝试卷本身的拼写、语法、标点错误；**提取错误**＝PDF 文字层或扫描识别造成、与试卷印刷不一致。\n']
    total = 0
    for r in res:
        es = EDIT.get(f"{r['paper']} {r['passage']}", [])
        if es:
            rec.append(f"\n## {r['id']} {r['paper']} {r['passage']}\n\n| 类型 | 原文 | 订正 | 理由 |\n|---|---|---|---|")
            rec += [f"| {e['type']} | {e['old']} | {e['new']} | {e['why']} |" for e in es]
            total += len(es)
    rec.insert(3, f'\n共 {total} 处。\n')
    (OUT / '原文订正记录.md').write_text('\n'.join(rec) + '\n', 'utf-8')
    print(f'{len(res)} 篇，{len(dups)} 组重复，原文订正 {total} 处，排版检查通过')
    for v in dups:
        print('  重复：', ' ＝ '.join(v))


if __name__ == '__main__':
    main()
