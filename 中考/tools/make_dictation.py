"""中考学习资料：每篇四份 PDF（仿照高考、四级的听写卡，用户 2026-10-15：“之前那些复习资料，中考的也帮我弄出来，打包 release 下载”）。

    /opt/ttsenv/bin/python 中考/tools/make_dictation.py all          # 全部 40 篇
    /opt/ttsenv/bin/python 中考/tools/make_dictation.py z01 z02 …

每篇一个文件夹：中考/听写卡/26北京 C篇 海洋变暖与南极海冰骤减/（与 40 篇合集里的视频同名，不加序号——用户 2026-10-15 不要序号），四份 PDF：
  … - 0 逐句精读.pdf   与视频画面一模一样（片头一页 + 每屏一页；分屏的句子占两页），16:9；每屏同样跑排版机械检查
  … - 1 汉译英.pdf     左边中文释义，右边横线默写英文
  … - 2 英译汉.pdf     左边英文，右边横线写中文
  … - 3 文章填空.pdf   原文中标注的词换成带编号的空框，下面是整句翻译和每个空的释义（试卷的中文注释去掉，免得泄露答案）
三份听写卡的最后一页是答案。朗读音频不重复入库，由 .github/workflows/release-zk-materials.yml 打包时复制进各文件夹。

复用方式（与四级相同）：听写卡版式直接用高考的 tools/dictation/make_dictation.py（只导入、不改动），逐句精读用中考的 make_video.py 画面函数；
中考不同的地方在这里覆盖：词条只分“单词 / 短语”；页眉“中考英语 2026年 北京 阅读C · 题目”；文件夹、文件名与合集视频文件名一致。
"""
import html
import importlib.util
import re
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent
ROOT = C4.parent
sys.path[:0] = [str(HERE), str(HERE / '封面')]
import make_video as M  # noqa: E402  中考视频画面
from make_post import file_name, bilibili_order  # noqa: E402  文件夹名与合集视频同名；顺序与 B 站 40P 相同
from 画面核查.layoutcheck import screens, problems  # noqa: E402

_spec = importlib.util.spec_from_file_location('gk_dictation', ROOT / 'tools' / 'dictation' / 'make_dictation.py')
GD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(GD)

OUT = C4 / '听写卡'
DATA = json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']
PAGE = '<style>@page{size:1920px 1080px;margin:0}</style>'
esc = lambda s: html.escape(s, quote=False)                                                # noqa: E731


def header(p, kind, note):
    return (f"<h1>{esc(kind)}</h1><div class='sub'>中考英语 {esc(p['paper'])} {esc(p['passage'])} · {esc(p['title'])} · {esc(note)}</div>"
            "<div class='who'><span>姓名：</span><span>日期：</span><span>得分：</span></div>")


GD.TIER = {'core': '单词', 'phr': '短语'}
GD.header = header
_cloze = GD.cloze


def cloze(p):
    """文章填空：空框与紧挨着的标点（前面的左引号、括号，后面的句号、逗号、右引号等）绑在一起不断行
    （样片 z19：“than we do of the [14]” 后面的句号单独掉到下一行）。"""
    return re.sub(r"[“‘(]*<span class='blank'[^>]*><i>\d+</i></span>[.,;:!?’”)\]—]*",
                  lambda m: m.group(0) if m.group(0).startswith('<span') and m.group(0).endswith('</span>')
                  else f"<span style='white-space:nowrap'>{m.group(0)}</span>", _cloze(p))


# 打印版面（A4 去掉左右各 16 mm 页边距 ≈ 673 像素宽）里，英文一行不能以标点开头（空框后的标点被挤到下一行）
LINE_PUNCT = """() => { const out = [];
  for (const el of document.querySelectorAll('.sent .en')) { const items = [];      // 按文档顺序：空框算一个整体，文字逐字
    const w = document.createTreeWalker(el, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) {
      if (n.nodeType === 1) { if (n.classList.contains('blank')) items.push({c: '□', l: n.getBoundingClientRect().left}); continue; }
      if (n.parentElement.closest('.blank')) continue;
      for (let i = 0; i < n.data.length; i++) { if (/\\s/.test(n.data[i])) continue;
        const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1); const rs = r.getClientRects();
        if (rs.length) items.push({c: n.data[i], l: rs[rs.length - 1].left}); } }
    for (let j = 1; j < items.length; j++)
      if (items[j].l < items[j - 1].l - 2 && /[.,;:!?’”)]/.test(items[j].c)) out.push(el.textContent.slice(0, 40)); }
  return out; }"""


def base_name(p):
    return file_name(p)[:-4]                          # “26北京 C篇 海洋变暖与南极海冰骤减”


def folder(p):
    return OUT / base_name(p)


def reading_pdf(pg, p, td):
    parts = []
    for i, (label, h, fit) in enumerate(screens(M, p)):                 # 与视频完全相同的每一屏
        f = td / f"{p['id']}_{i:03d}.html"
        f.write_text(h.replace('</head>', PAGE + '</head>', 1), 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        if fit:
            fs, vs, fits = pg.evaluate(M.FIT)
            if not fits or fs < M.MIN_FS or vs < M.MIN_VS:                # 与视频同一条可读性下限
                raise SystemExit(f"{p['id']} {label}放不下（英文 {fs}px、词汇 {vs}px）")
        bad = problems(pg, M.MIN_FS, M.MIN_VS)                           # 与视频同样的排版机械检查
        if bad:
            raise SystemExit(f"{p['id']} {label}排版不合格：{bad}")
        out = td / f"{p['id']}_{i:03d}.pdf"
        pg.pdf(path=str(out), width='1920px', height='1080px', print_background=True,
               margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'}, page_ranges='1')
        parts.append(str(out))
    dst = folder(p) / f'{base_name(p)} - 0 逐句精读.pdf'
    subprocess.run(['pdfunite', *parts, str(dst)], check=True)
    n = int(subprocess.run(['pdfinfo', str(dst)], capture_output=True, text=True, check=True)
            .stdout.split('Pages:')[1].split()[0])
    assert n == len(parts), (dst, n, len(parts))                           # 页数 = 1 + 屏数
    return dst, n


def card_pdfs(pg, p):
    out = []
    for name, body in (('1 汉译英', GD.word_list(p, 'zh2en')), ('2 英译汉', GD.word_list(p, 'en2zh')), ('3 文章填空', cloze(p))):
        pg.set_content(f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><style>{GD.CSS}</style></head><body>{body}</body></html>")
        pg.evaluate('document.fonts.ready')
        if name == '3 文章填空':
            bad = pg.evaluate(LINE_PUNCT)
            if bad:
                raise SystemExit(f"{p['id']} 文章填空有一行以标点开头：{bad}")
        f = folder(p) / f'{base_name(p)} - {name}.pdf'
        pg.pdf(path=str(f), format='A4', print_background=True,
               display_header_footer=True, header_template='<span></span>',
               footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#999'>"
                               "<span class='pageNumber'></span> / <span class='totalPages'></span></div>",
               margin={'top': '16mm', 'bottom': '18mm', 'left': '16mm', 'right': '16mm'})
        out.append(f)
    txt = subprocess.run(['pdftotext', str(out[2]), '-'], capture_output=True, text=True, check=True).stdout
    left = GD.FOOTNOTE.findall(txt)                                           # 试卷的中文注释（半角括号）必须全部去掉，否则泄露答案
    if left:
        raise SystemExit(f"{p['id']} 文章填空里还有试卷的中文注释：{left}")
    return out


def main():
    from playwright.sync_api import sync_playwright
    order = bilibili_order(DATA)
    assert len(order) == 40
    P = {p['id']: p for p in order}
    ids = [p['id'] for p in order] if sys.argv[1:] == ['all'] else sys.argv[1:]
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': M.W, 'height': M.H}, device_scale_factor=2)   # 与生成 4K 视频时同一倍率（倍率不同换行可能不同）
        cards = br.new_page(viewport={'width': 673, 'height': 1000})      # A4 版心宽度，屏幕排版与打印一致，才能在打印前检查换行
        cards.emulate_media(media='print')
        for pid in ids:
            p = P[pid]
            folder(p).mkdir(exist_ok=True)
            dst, n = reading_pdf(pg, p, Path(td))
            fs = card_pdfs(cards, p)
            print(f"{folder(p).name}：逐句精读 {n} 页 + {len(fs)} 份听写卡", flush=True)
        br.close()


if __name__ == '__main__':
    main()
