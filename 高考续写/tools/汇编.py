"""读后续写 Word 汇编：一次生成总汇编 + 三本分册（高考真题 / T8联考 / 九省联考），并做程序检查。
每册：封面（篇数、套数、范文数由数据算）→ 按年份统计 → 可点击目录 → 每篇一页起（标题 = 出自哪套卷，下面一行原卷标题）。
用法: python3 -I 汇编.py 续写题汇总.json 输出目录"""
import sys, os, json, re, collections
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SRC, OUT = sys.argv[1], sys.argv[2]
D = json.load(open(SRC))
RECS = D['续写题']
VOLS = [  # (文件名, 册名, 类别；None = 全部)
    ('续写题汇编.docx', '高考英语读后续写汇编（全部）', None),
    ('续写题汇编_高考真题.docx', '高考英语读后续写汇编 · 高考真题', '高考'),
    ('续写题汇编_T8联考.docx', '高考英语读后续写汇编 · T8联考', 'T8联考'),
    ('续写题汇编_九省联考.docx', '高考英语读后续写汇编 · 九省联考', '九省联考'),
]
GREY, BLUE, RED = (0x66, 0x66, 0x66), (0x1F, 0x4E, 0x79), (0xA0, 0x30, 0x30)
OCR_NOTE = '扫描件识别，可能有个别错字。'
MISS_NOTE = '原卷开头语缺失，待补。'

def setfont(run, east='宋体'):
    run.font.name = 'Times New Roman'
    rpr = run._element.get_or_add_rPr()
    rpr.get_or_add_rFonts().set(qn('w:eastAsia'), east)

def para(doc, text='', bold=False, size=11, color=None, indent=False, align=None, east='宋体', after=4, italic=False):
    p = doc.add_paragraph()
    if text:
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        r.font.size = Pt(size)
        setfont(r, east)
        if color:
            r.font.color.rgb = RGBColor(*color)
    if indent:
        p.paragraph_format.first_line_indent = Pt(22)
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.25
    return p

def bookmark(p, name, bid):
    s = OxmlElement('w:bookmarkStart'); s.set(qn('w:id'), str(bid)); s.set(qn('w:name'), name)
    e = OxmlElement('w:bookmarkEnd'); e.set(qn('w:id'), str(bid))
    p._p.insert(0, s); p._p.append(e)

def link(p, text, anchor, size=10.5):
    h = OxmlElement('w:hyperlink'); h.set(qn('w:anchor'), anchor)
    r = OxmlElement('w:r'); rpr = OxmlElement('w:rPr')
    f = OxmlElement('w:rFonts'); f.set(qn('w:ascii'), 'Times New Roman'); f.set(qn('w:hAnsi'), 'Times New Roman'); f.set(qn('w:eastAsia'), '宋体')
    c = OxmlElement('w:color'); c.set(qn('w:val'), '1F4E79')
    sz = OxmlElement('w:sz'); sz.set(qn('w:val'), str(int(size * 2)))
    rpr.extend([f, c, sz]); r.append(rpr)
    t = OxmlElement('w:t'); t.text = text; t.set(qn('xml:space'), 'preserve'); r.append(t)
    h.append(r); p._p.append(h)

def page_number(doc):
    p = doc.sections[0].footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    for tag, val in (('begin', None), (None, 'PAGE'), ('end', None)):
        if tag:
            el = OxmlElement('w:fldChar'); el.set(qn('w:fldCharType'), tag)
        else:
            el = OxmlElement('w:instrText'); el.set(qn('xml:space'), 'preserve'); el.text = val
        r._r.append(el)

def heading(doc, text, size, color=BLUE, after=6):
    p = para(doc, text, bold=True, size=size, color=color, east='黑体', after=after)
    p.paragraph_format.keep_with_next = True
    return p

def build(fname, title, cat):
    recs = [r for r in RECS if cat is None or r['类别'] == cat]
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(2.2)
    sec.top_margin = sec.bottom_margin = Cm(2.0)
    page_number(doc)
    papers = sum(len(r['试卷']) for r in recs)
    essays = sum(1 for r in recs if r['范文'])
    # 封面
    para(doc, after=60)
    para(doc, title, bold=True, size=24, color=BLUE, east='黑体', align=WD_ALIGN_PARAGRAPH.CENTER, after=18)
    para(doc, f'本册共 {len(recs)} 篇读后续写，对应 {papers} 套试卷；{essays} 篇附参考范文。',
         size=13, align=WD_ALIGN_PARAGRAPH.CENTER, after=6)
    para(doc, '按年份从新到旧排列；同一篇被几套试卷共用时写在同一处，只算一篇。',
         size=11, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER, after=24)
    # 按年份统计
    cats = [cat] if cat else ['高考', 'T8联考', '九省联考']
    by = collections.defaultdict(collections.Counter)
    for r in recs:
        by[r['年份']][r['类别']] += 1
    t = doc.add_table(rows=1, cols=len(cats) + 2)
    t.style = 'Light Grid Accent 1'
    t.alignment = 1
    for i, h in enumerate(['年份'] + [f'{c}（篇）' for c in cats] + ['合计']):
        t.rows[0].cells[i].text = h
    for y in sorted(by, reverse=True):
        row = t.add_row().cells
        row[0].text = str(y)
        for i, c in enumerate(cats):
            row[i + 1].text = str(by[y].get(c, 0))
        row[-1].text = str(sum(by[y].values()))
    row = t.add_row().cells
    row[0].text = '合计'
    for i, c in enumerate(cats):
        row[i + 1].text = str(sum(1 for r in recs if r['类别'] == c))
    row[-1].text = str(len(recs))
    # 目录
    doc.add_page_break()
    heading(doc, '目　录（点击标题跳转）', 16, after=10)
    for i, r in enumerate(recs, 1):
        p = para(doc, after=2)
        link(p, f'第 {i} 篇　{r["标题"]}', f'p{i}')
        extra = ('（附范文）' if r['范文'] else '') + ('（开头语待补）' if not r['开头语'] else '')
        if extra:
            x = p.add_run(extra); x.font.size = Pt(9); x.font.color.rgb = RGBColor(*GREY); setfont(x)
    # 正文
    for i, r in enumerate(recs, 1):
        doc.add_page_break()
        h = heading(doc, f'第 {i} 篇　{r["标题"]}', 15, after=2)
        bookmark(h, f'p{i}', i)
        para(doc, f'原卷标题：{r["原卷标题"]}', size=9.5, color=GREY, after=2)
        meta = [f'类别：{r["类别"]}']
        if r['题号']:
            meta.append(f'第 {r["题号"]} 题')
        if r['分值']:
            meta.append(f'{r["分值"]} 分')
        prov = '；'.join(e['适用省份'] for e in r['试卷'] if e['适用省份'])
        if prov:
            meta.append(f'适用省份：{prov}')
        para(doc, '　'.join(meta), size=9.5, color=GREY, after=10)
        para(doc, r['说明'], bold=True, size=11)
        for x in r['原文']:
            para(doc, x, indent=True)
        for x in r['注意']:
            para(doc, x, size=10)
        ops = r['开头语'] or [None, None]
        for k, o in enumerate(ops, 1):
            para(doc, f'Paragraph {k}:', bold=True, after=2)
            para(doc, o if o else MISS_NOTE, indent=True, color=None if o else RED, bold=not o)
            for _ in range(3):
                para(doc, '_' * 62, color=(0xBB, 0xBB, 0xBB), after=0)
        if 'OCR' in (r.get('备注') or ''):
            para(doc, '注：' + OCR_NOTE, size=9.5, color=RED, after=4)
        if r['范文']:
            heading(doc, '参考范文（来自原解析卷）', 12.5, after=4)
            for x in r['范文']:
                para(doc, x, indent=True)
    doc.save(os.path.join(OUT, fname))
    return recs

made = {fn: build(fn, title, cat) for fn, title, cat in VOLS}

# ---------- 程序检查 ----------
bad = []
parts = [made[fn] for fn, _, cat in VOLS if cat]
ids = [r['编号'] for recs in parts for r in recs]
if len(ids) != len(RECS) or sorted(ids) != sorted(r['编号'] for r in RECS):
    bad.append(f'三本分册合计 {len(ids)} 篇，汇总里 {len(RECS)} 篇，或有重复/遗漏')
for fn, _, cat in VOLS:
    if cat and any(r['类别'] != cat for r in made[fn]):
        bad.append(f'{fn} 混进了别的类别')
    for r in made[fn]:
        if not r['标题'] or not r['原卷标题']:
            bad.append(f'{fn} #{r["编号"]} 标题为空')
        if not r['开头语'] and MISS_NOTE.rstrip('。') not in json.dumps(r, ensure_ascii=False) + MISS_NOTE:
            bad.append(f'{fn} #{r["编号"]} 缺开头语却没标待补')
    # 目录链接数 = 书签数 = 篇数
    d = Document(os.path.join(OUT, fn))
    xml = d.element.xml
    nl, nb = len(re.findall(r'<w:hyperlink [^>]*w:anchor="p\d+"', xml)), len(re.findall(r'<w:bookmarkStart [^>]*w:name="p\d+"', xml))
    if not nl == nb == len(made[fn]):
        bad.append(f'{fn}：目录链接 {nl}、书签 {nb}、篇数 {len(made[fn])} 不一致')
    if MISS_NOTE in xml and not any(not r['开头语'] for r in made[fn]):
        bad.append(f'{fn}：多出“开头语待补”')
for fn, _, cat in VOLS:
    print(fn, len(made[fn]), '篇', sum(len(r['试卷']) for r in made[fn]), '套')
print('检查', len(bad), '处'); [print(' ', b) for b in bad]
sys.exit(1 if bad else 0)
