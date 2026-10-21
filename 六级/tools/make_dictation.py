"""六级学习资料（用户 2026-10-21：像四级那样做听写卡等资料，另外每篇多一份“长难句分析”）。

    /opt/ttsenv/bin/python 六级/tools/make_dictation.py all          # 全部 60 篇
    /opt/ttsenv/bin/python 六级/tools/make_dictation.py s01 s02 …

每篇一个文件夹：六级/听写卡/序号 视频文件名（不含 .mp4）/，五份 PDF：
  … - 0 逐句精读.pdf   直接用视频画面（教室黑板大字版）：已登记审阅通过的截图（六级/样片/截图/<篇目>/），先逐张核对哈希与
                        六级/tools/画面核查/截图审阅通过.json 相同（与发布的视频逐字节一致），再一屏一页拼成 PDF（不重画、不花 token）
  … - 1 汉译英.pdf     左边中文释义，右边横线默写英文（高考听写卡版式，tools/dictation/make_dictation.py）
  … - 2 英译汉.pdf     左边英文，右边横线写中文
  … - 3 文章填空.pdf   原文中标注的词换成带编号的空框，下面是整句翻译和每个空的释义
  … - 4 长难句分析.pdf  六级/tools/长难句.py 生成（挑句由程序、分析由模型、检查由程序）
序号与六级黑板视频 Release（cet6-chalk）的顺序一致：s01 → s60。朗读音频由发布工作流打包时复制进各文件夹。
高考、四级程序只导入、不改动。
"""
import html
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
C6 = HERE.parent
ROOT = C6.parent
sys.path.insert(0, str(ROOT / '专八' / 'tools'))
import make_video as M  # noqa: E402  六级与专八共用引擎（video_name）
M.set_project('六级')

_spec = importlib.util.spec_from_file_location('gk_dictation', ROOT / 'tools' / 'dictation' / 'make_dictation.py')
GD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(GD)

OUT = C6 / '听写卡'
STILLS = C6 / '样片' / '截图'
REG = json.loads((HERE / '画面核查' / '截图审阅通过.json').read_text('utf-8'))
ORDER = [p for p in json.loads((C6 / 'data' / 'vocab.json').read_text('utf-8'))['passages'] if p.get('done')]   # s01 → s60，与视频 Release 相同
esc = lambda s: html.escape(s, quote=False)                                                # noqa: E731


def header(p, kind, note):
    return (f"<h1>{esc(kind)}</h1><div class='sub'>大学英语六级 {esc(p['paper'])} {esc(p['passage'])} · {esc(p['title'])} · {esc(note)}</div>"
            "<div class='who'><span>姓名：</span><span>日期：</span><span>得分：</span></div>")


GD.TIER = {'core': '单词', 'phr': '短语'}
GD.header = header


def base_name(p):
    return M.video_name(p)[:-4]


def folder(p):
    return OUT / f'{ORDER.index(p) + 1:02d} {base_name(p)}'


def reading_pdf(pg, p):
    """逐句精读：已登记的视频截图一屏一页。截图缺失或哈希与登记不同（不是发布的视频画面）就报错。"""
    reg = REG[f"{p['id']}@3"]['截图']
    d = STILLS / p['id']
    got = {x.name: M.file_hash(x) for x in M.still_files(d)}
    bad = sorted(k for k in set(reg) | set(got) if reg.get(k) != got.get(k))
    if bad:
        raise SystemExit(f"{p['id']} 截图与审阅登记不一致（{len(bad)} 张，如 {bad[:3]}）：先 六级/tools/大字版.py --stills {p['id']}")
    from PIL import Image                      # 无损截图直接嵌进 PDF 每篇 65 MB；转成 JPEG（质量 80，文字清晰）约 9 MB，Chromium 原样嵌入
    tmp = Path(tempfile.mkdtemp(prefix=f"cet6_{p['id']}_"))
    for k in sorted(reg):
        Image.open(d / k).convert('RGB').save(tmp / (Path(k).stem + '.jpg'), 'JPEG', quality=80, optimize=True)
    imgs = ''.join(f"<img src='{(tmp / (Path(k).stem + '.jpg')).as_uri()}'>" for k in sorted(reg))
    page = tmp / 'reading.html'      # 本地截图要用 file:// 页面才能加载（set_content 的页面加载不了）
    page.write_text("<!doctype html><html><head><meta charset='utf-8'><style>@page{size:1920px 1080px;margin:0}"
                    "html,body{margin:0}img{display:block;width:1920px;height:1080px;break-after:page}</style></head>"
                    f"<body>{imgs}</body></html>", 'utf-8')
    pg.goto(page.as_uri())
    pg.wait_for_function('[...document.images].every(i => i.complete && i.naturalWidth === 1920)')
    dst = folder(p) / f'{base_name(p)} - 0 逐句精读.pdf'
    pg.pdf(path=str(dst), width='1920px', height='1080px', print_background=True, margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'})
    n = int(subprocess.run(['pdfinfo', str(dst)], capture_output=True, text=True, check=True).stdout.split('Pages:')[1].split()[0])
    assert n == len(reg), (dst, n, len(reg))                     # 页数 = 屏数（片头 + 每屏一页）
    shutil.rmtree(tmp, ignore_errors=True)
    return n


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
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': 1920, 'height': 1080})
        cards = br.new_page()
        for pid in ids:
            p = P[pid]
            folder(p).mkdir(exist_ok=True)
            n = reading_pdf(pg, p)
            fs = card_pdfs(cards, p)
            print(f"{folder(p).name}：逐句精读 {n} 页 + {len(fs)} 份听写卡", flush=True)
        br.close()


if __name__ == '__main__':
    main()
