"""四级学习资料：每篇四份 PDF（仿照高考的听写卡，用户 2026-10-08：“像高考那样把所有资料也生成”）。

    /opt/ttsenv/bin/python 四级/tools/make_dictation.py all          # 全部 60 篇
    /opt/ttsenv/bin/python 四级/tools/make_dictation.py c60 c59 …

每篇一个文件夹：四级/听写卡/序号 2026年6月 第3套 Passage Two 题目/，四份 PDF：
  … - 0 逐句精读.pdf   与视频画面一模一样（片头一页 + 每屏一页；分屏的句子占两页），16:9
  … - 1 汉译英.pdf     左边中文释义，右边横线默写英文
  … - 2 英译汉.pdf     左边英文，右边横线写中文
  … - 3 文章填空.pdf   原文中标注的词换成带编号的空框，下面是整句翻译和每个空的释义
三份听写卡的最后一页是答案。序号与 Release 007、B 站合集一致：c60 → c01（从新到旧）。
朗读音频不重复入库，由 .github/workflows/release-cet4-dictation.yml 打包时复制进各文件夹。

复用方式：听写卡版式直接用高考的 tools/dictation/make_dictation.py，逐句精读用四级的 make_video.py 画面函数；
高考程序只导入、不改动（用户指令：高考内容不再改动），四级不同的地方在这里覆盖：
  - 词条分级：四级只分“单词 / 短语”（不分课标、超纲）；
  - 页眉：“大学英语四级 2026年6月 第3套 Passage Two · 题目”；
  - 文件夹、文件名与视频文件名一致。
"""
import html
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent
ROOT = C4.parent
sys.path.insert(0, str(HERE))
import make_video as M  # noqa: E402  四级视频画面（title_slide、sentence_slide、split_parts、FIT）

_spec = importlib.util.spec_from_file_location('gk_dictation', ROOT / 'tools' / 'dictation' / 'make_dictation.py')
GD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(GD)

OUT = C4 / '听写卡'
DATA = json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']
ORDER = sorted((p for p in DATA if p.get('done')), key=lambda p: p['id'], reverse=True)   # c60 → c01
PAGE = '<style>@page{size:1920px 1080px;margin:0}</style>'
esc = lambda s: html.escape(s, quote=False)                                                # noqa: E731


def header(p, kind, note):
    return (f"<h1>{esc(kind)}</h1><div class='sub'>大学英语四级 {esc(p['paper'])} {esc(p['passage'])} · {esc(p['title'])} · {esc(note)}</div>"
            "<div class='who'><span>姓名：</span><span>日期：</span><span>得分：</span></div>")


GD.TIER = {'core': '单词', 'phr': '短语'}
GD.header = header


def base_name(p):
    return M.video_name(p)[:-4]                      # “2026年6月 第3套 Passage Two 题目”，与视频文件名一致


def folder(p):
    return OUT / f'{ORDER.index(p) + 1:02d} {base_name(p)}'


def slides(p):
    """片头 + 每屏一页，与视频的屏完全对应（分屏的句子两页）。"""
    S = [s for para in p['paras'] for s in para]
    out = [(0, M.title_slide(p))]
    for k, s in enumerate(S, 1):
        for part in M.split_parts(p['id'], k, s):
            out.append((k, M.sentence_slide(p, s, k, len(S), part)))
    return out


def reading_pdf(pg, p, td):
    parts = []
    for i, (k, h) in enumerate(slides(p)):
        f = td / f"{p['id']}_{i:03d}.html"
        f.write_text(h.replace('</head>', PAGE + '</head>', 1), 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        if k:
            fs, vs, fits = pg.evaluate(M.FIT)
            if not fits or fs < M.MIN_FS or vs < M.MIN_VS:                    # 与视频同一条可读性下限
                raise SystemExit(f"{p['id']} 第 {k} 句放不下（英文 {fs}px、词汇 {vs}px）")
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
    for name, body in (('1 汉译英', GD.word_list(p, 'zh2en')), ('2 英译汉', GD.word_list(p, 'en2zh')), ('3 文章填空', GD.cloze(p))):
        pg.set_content(f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><style>{GD.CSS}</style></head><body>{body}</body></html>")
        pg.evaluate('document.fonts.ready')
        f = folder(p) / f'{base_name(p)} - {name}.pdf'
        pg.pdf(path=str(f), format='A4', print_background=True,
               display_header_footer=True, header_template='<span></span>',
               footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#999'>"
                               "<span class='pageNumber'></span> / <span class='totalPages'></span></div>",
               margin={'top': '16mm', 'bottom': '18mm', 'left': '16mm', 'right': '16mm'})
        out.append(f)
    return out


def main():
    from playwright.sync_api import sync_playwright
    assert len(ORDER) == 60
    P = {p['id']: p for p in ORDER}
    ids = [p['id'] for p in ORDER] if sys.argv[1:] == ['all'] else sys.argv[1:]
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': M.W, 'height': M.H})
        cards = br.new_page()
        for pid in ids:
            p = P[pid]
            folder(p).mkdir(exist_ok=True)
            dst, n = reading_pdf(pg, p, Path(td))
            fs = card_pdfs(cards, p)
            print(f"{folder(p).name}：逐句精读 {n} 页 + {len(fs)} 份听写卡", flush=True)
        br.close()


if __name__ == '__main__':
    main()
