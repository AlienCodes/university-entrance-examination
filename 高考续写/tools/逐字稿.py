"""读后续写讲解：导出给老师改的整片逐字稿（Word）。老师 2026-11-04：“你先把要讲这个视频的逐字稿发给我，我给你修改一下，然后再按照我修改的这个逐字稿去生成。”
按视频顺序分节（小标题 = 这一屏讲什么）；每节先放这一屏的英文（灰色，“画面上的英文，不用改”），下面是配音段落，
每段前面灰色小号 [段 id]；‖ 显示成“／”。英文朗读段也列出（灰色、标“英文朗读，不用改”），导回时不收。字号 14 以上（手机能看清）。
导回：逐字稿导回.py（按 [段 id] 对回，“／”还原成 ‖）。
用法：python3 高考续写/tools/逐字稿.py 讲解目录 [输出.docx]"""
import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

GRAY = RGBColor(0x88, 0x88, 0x88)
CN = '一二三四五六七八九十'
INTRO = ['请直接在下面改文字就行（改说法、加话、删话都可以）。',
         '“／”表示这里停顿一下，可以挪、删、加。',
         '方括号里灰色小字是编号（如 [s1b1]），请别动；灰色的英文是画面上的内容，不用改。']


def title(screen, doc):
    m = re.fullmatch(r's(\d+)', screen)
    if m:
        k = int(m.group(1))
        own = [(pi, si) for pi, p in enumerate(doc['范文']['paragraphs']) for si, s in enumerate(p) if not s.get('given')]
        pi, si = own[k - 1]
        n = sum(1 for a, b in own[:k] if a == pi)
        return f'逐句写：第{CN[pi]}段第{CN[n - 1]}句'
    m = re.fullmatch(r'p(\d)', screen)
    if m:
        return f'读原文：第{CN[int(m.group(1)) - 1]}段'
    m = re.fullmatch(r'para(\d)', screen)
    if m:
        return f'第{CN[int(m.group(1)) - 1]}段连起来读'
    return {'task': '题目要求', 'rubric': '评分标准', 'open': '开头语', 'outline': '列提纲', 'echo': '伏笔与呼应',
            'fail': '常见失分点', 'sum': '方法总结', 'full': '完整范文通读与结束'}[screen]


def english(screen, doc):
    t, fw = doc['题目'], doc['范文']
    m = re.fullmatch(r's(\d+)', screen)
    if m:
        own = [s for p in fw['paragraphs'] for s in p if not s.get('given')]
        return [own[int(m.group(1)) - 1]['en']]
    m = re.fullmatch(r'p(\d)', screen)
    if m:
        return [t['原文'][int(m.group(1)) - 1]]
    if screen in ('task', 'open'):
        return list(t['开头语'])
    return []


def run(p, text, size=14, gray=False, bold=False):
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    r.font.name = 'Microsoft YaHei'
    r._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    if gray:
        r.font.color.rgb = GRAY
    return r


def export(d, out):
    d = Path(d)
    gao = json.loads((d / '稿.json').read_text('utf-8'))
    doc = {'题目': json.loads((d / '题目.json').read_text('utf-8')), '范文': json.loads((d / '范文.json').read_text('utf-8'))}
    W = Document()
    st = W.styles['Normal']
    st.font.size = Pt(14)
    st.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    run(W.add_paragraph(), '读后续写 2026 新课标Ⅰ卷 讲解逐字稿', 20, bold=True)
    for x in INTRO:
        run(W.add_paragraph(), x, 14)
    last = None
    for g in gao['segments']:
        if g['screen'] != last:
            last = g['screen']
            run(W.add_paragraph(), title(last, doc), 17, bold=True)
            en = english(last, doc)
            if en:
                p = W.add_paragraph()
                run(p, '画面上的英文，不用改：', 12, gray=True)
                for e in en:
                    run(p, '\n' + e, 13, gray=True)
        p = W.add_paragraph()
        run(p, f'[{g["id"]}] ', 10, gray=True)
        if g['lang'] == 'Chinese':
            run(p, g['text'].replace('‖', '／'), 14)
        else:
            run(p, '（英文朗读，不用改）' + g['text'], 13, gray=True)
    W.save(out)
    return gao


def syl(t):
    return len(re.findall(r"[一-鿿]|[A-Za-z]+(?:[’'][A-Za-z]+)?", t))


if __name__ == '__main__':
    d = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else d / '逐字稿_v1.docx'
    gao = export(d, out)
    zh = [g for g in gao['segments'] if g['lang'] == 'Chinese']
    print(f'{out}：{len(gao["segments"])} 段（中文 {len(zh)}），中文配音 {sum(len(re.findall("[一-鿿]", g["text"])) for g in zh)} 字，'
          f'音节 {sum(syl(g["text"]) for g in gao["segments"])}')
