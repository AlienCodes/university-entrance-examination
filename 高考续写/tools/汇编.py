"""把 续写题汇总.json 排成 Word 汇编（按年份从新到旧，每篇标明来源；有范文放题后）。
用法: python3 -I 汇编.py 续写题汇总.json 续写题汇编.docx"""
import sys, json
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

d = json.load(open(sys.argv[1]))
doc = Document()
st = doc.styles['Normal']
st.font.name = 'Times New Roman'
st.font.size = Pt(11)
st.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
for s in ('Heading 1', 'Heading 2', 'Title'):
    doc.styles[s].element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'), '黑体')

def para(text, bold=False, italic=False, size=None, color=None, indent=False, align=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold, r.italic = bold, italic
    if size:
        r.font.size = Pt(size)
    if color:
        r.font.color.rgb = RGBColor(*color)
    if indent:
        p.paragraph_format.first_line_indent = Pt(22)
    if align:
        p.alignment = align
    p.paragraph_format.space_after = Pt(4)
    return p

stat = d['统计']
cats = ['高考', '八省/九省联考', '其他（T8 等联考）']
doc.add_heading('高考英语读后续写汇编', 0)
para(f"去重后共 {stat['续写题（去重后）']} 篇（同一篇被几套试卷共用只算一篇）；"
     + '、'.join(f"{c} {stat['按类别'].get(c, 0)} 篇" for c in cats)
     + f"；{stat['有范文']} 篇附原解析卷参考范文。按年份从新到旧排列。")
t = doc.add_table(rows=1, cols=len(cats) + 2)
t.style = 'Light Grid Accent 1'
for i, h in enumerate(['年份'] + cats + ['合计']):
    t.rows[0].cells[i].text = h
for y, c in stat['按年份'].items():
    row = t.add_row().cells
    row[0].text = y
    for i, k in enumerate(cats):
        row[i + 1].text = str(c.get(k, 0))
    row[-1].text = str(sum(c.values()))
row = t.add_row().cells
row[0].text = '合计'
for i, k in enumerate(cats):
    row[i + 1].text = str(stat['按类别'].get(k, 0))
row[-1].text = str(stat['续写题（去重后）'])

for r in d['续写题']:
    doc.add_page_break()
    doc.add_heading(f"{r['编号']}. {r['来源']}", 1)
    meta = [f"类别：{r['类别']}"]
    if r['题号']:
        meta.append(f"题号：第 {r['题号']} 题")
    if r['分值']:
        meta.append(f"分值：{r['分值']} 分")
    for e in r['试卷']:
        if e['适用省份']:
            meta.append(f"适用省份：{e['适用省份']}")
    para('　'.join(meta), size=9.5, color=(0x55, 0x55, 0x55))
    if r.get('备注'):
        para('备注：' + r['备注'], size=9.5, color=(0xA0, 0x30, 0x30))
    para(r['说明'], bold=True)
    for x in r['原文']:
        para(x, indent=True)
    for x in r['注意']:
        para(x, size=10)
    for i, o in enumerate(r['开头语'] or ['（原文件缺开头语）', '（原文件缺开头语）'], 1):
        para(f'Paragraph {i}:', bold=True)
        para(o, indent=True)
        para('_' * 60, color=(0xAA, 0xAA, 0xAA))
    if r['范文']:
        doc.add_heading('参考范文（来自原解析卷）', 2)
        for x in r['范文']:
            para(x, indent=True)
doc.save(sys.argv[2])
print('ok', len(d['续写题']))
