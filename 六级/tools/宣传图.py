"""六级学习资料的 B 站商品图（用户 2026-10-21：打包到 B 站卖，需要“资料总览图”和每份文件打开后的样子，全部 1:1）。

    /opt/ttsenv/bin/python 六级/tools/宣传图.py      # → 六级/宣传图/01_资料总览.png … 07_朗读音频.png（1600×1600）

全部由程序生成（零 token）：预览用第 1 篇（s01）真实 PDF 页面（pdftoppm 渲染），音频波形用 s01 朗读音频的真实波形。
“虚拟产品，一旦售出无法退款，谢谢理解”只写在长难句分析那一张（用户要求）。
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
C6 = HERE.parent
ROOT = C6.parent
OUT = C6 / '宣传图'
FOLDER = sorted((C6 / '听写卡').iterdir())[0]
NAME = FOLDER.name[3:]
FONTS = ''.join(f"<link rel='stylesheet' href='{(ROOT / '专八' / 'tools' / 'fonts' / f).as_uri()}'>" for f in ('zh-bold.css', 'zh-regular.css'))
W = 1600
TAG = '大学英语六级 · 仔细阅读真题 60 篇（2021—2026）'

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1600px;height:1600px;overflow:hidden;font-family:'ZH Regular','Noto Sans SC',sans-serif;color:#1d2433;
  background:linear-gradient(160deg,#eef3fb 0%,#f8fafc 55%,#eef6f1 100%)}
.top{height:300px;padding:70px 90px 0;background:linear-gradient(120deg,#123c69,#1f5f9e);color:#fff;position:relative}
.tag{display:inline-block;font-size:30px;letter-spacing:2px;background:rgba(255,255,255,.16);padding:8px 22px;border-radius:30px}
h1{font-family:'ZH Bold',sans-serif;font-size:84px;margin-top:26px;letter-spacing:2px}
.no{position:absolute;right:90px;top:70px;font-family:'ZH Bold',sans-serif;font-size:150px;line-height:1;color:rgba(255,255,255,.18)}
.desc{font-size:38px;color:#2a3a52;padding:36px 90px 0;line-height:1.5}
.desc b{font-family:'ZH Bold',sans-serif;color:#123c69}
.stage{position:absolute;left:90px;right:90px;top:410px;bottom:150px;display:flex;align-items:center;justify-content:center;gap:40px}
.pg{background:#fff;box-shadow:0 18px 50px rgba(18,60,105,.22),0 3px 10px rgba(0,0,0,.08);border-radius:10px;overflow:hidden}
.pg img{display:block;width:100%}
.bot{position:absolute;left:0;right:0;bottom:0;height:150px;display:flex;align-items:center;justify-content:center;gap:26px;font-size:32px;color:#2a3a52}
.chip{background:#fff;border:2px solid #cfdcef;border-radius:40px;padding:12px 28px}
.chip b{font-family:'ZH Bold',sans-serif;color:#123c69}
.notice{position:absolute;left:0;right:0;bottom:0;height:150px;background:#fff4e5;border-top:3px solid #f0a020;display:flex;align-items:center;justify-content:center;
  font-family:'ZH Bold',sans-serif;font-size:44px;color:#b25a00;letter-spacing:2px}
"""


def page(no, title, desc, stage, bottom):
    return (f"<!doctype html><html><head><meta charset='utf-8'>{FONTS}<style>{CSS}</style></head><body>"
            f"<div class='top'><span class='tag'>{TAG}</span><h1>{title}</h1><div class='no'>{no}</div></div>"
            f"<div class='desc'>{desc}</div><div class='stage'>{stage}</div>{bottom}</body></html>")


def chips(*xs):
    return "<div class='bot'>" + ''.join(f"<span class='chip'>{x}</span>" for x in xs) + "</div>"


def render_pages(pdf, pages, dpi, td):
    out = []
    for p in pages:
        stem = td / f'{pdf.stem[-6:]}_{p}'
        subprocess.run(['pdftoppm', '-r', str(dpi), '-png', '-f', str(p), '-l', str(p), '-singlefile', str(pdf), str(stem)], check=True)
        out.append(stem.with_suffix('.png').as_uri())
    return out


def pdf_of(kind):
    return next(FOLDER.glob(f'* - {kind}.pdf'))


def main():
    from playwright.sync_api import sync_playwright
    OUT.mkdir(exist_ok=True)
    td = Path(tempfile.mkdtemp(prefix='cet6promo_'))
    imgs = {}
    # 1 资料总览：资料包最外层（历年真题 + 60 个篇目文件夹）+ 一个篇目文件夹打开后的样子
    names = [x.name for x in sorted((C6 / '听写卡').iterdir())]
    root = [('dir hl', '六级历年真题套卷 + 答案解析（2021—2026 全部）')] + [('dir', n) for n in names[:3]] + [('more', f'…… 共 {len(names)} 个篇目文件夹，2026—2021 年从新到旧')]
    files = [('PDF', '0 逐句精读.pdf', '片头 + 每屏一页，英文高亮、中文翻译、生词编号注释'),
             ('PDF', '1 汉译英.pdf', '看中文写英文，最后一页是答案'),
             ('PDF', '2 英译汉.pdf', '看英文写中文，最后一页是答案'),
             ('PDF', '3 文章填空.pdf', '原文挖空，附整句翻译和每空释义'),
             ('PDF', '4 长难句分析.pdf', '找主干、层层拆解、怎么读懂、怎么翻译、知识点'),
             ('MP3', '朗读音频.mp3', '男声逐句朗读')]
    rr = ''.join(f"<div class='r {c}'><span class='fo'></span><span>{t}</span></div>" if c != 'more' else f"<div class='r more'>{t}</div>" for c, t in root)
    rows = ''.join(f"<div class='f'><span class='ic {t.lower()}'>{t}</span><span class='fn'>{n}</span><span class='fd'>{d}</span></div>" for t, n, d in files)
    win = ("<div style='display:flex;flex-direction:column;gap:30px;width:1420px'>"
           f"<div class='win'><div class='bar'><i></i><i></i><i></i><span>六级阅读真题60篇学习资料</span></div>{rr}</div>"
           f"<div class='win'><div class='bar'><i></i><i></i><i></i><span>01 {NAME}</span></div>{rows}</div></div>"
           "<style>.win{background:#fff;border-radius:18px;box-shadow:0 18px 50px rgba(18,60,105,.22);overflow:hidden}"
           ".bar{height:58px;background:#e9eef6;display:flex;align-items:center;padding:0 24px;gap:10px;font-size:26px;color:#3b4a60}"
           ".bar i{width:16px;height:16px;border-radius:50%;background:#f26b5e}.bar i+i{background:#f6be4f}.bar i+i+i{background:#5ac05a}.bar span{margin-left:16px}"
           ".r{display:flex;align-items:center;gap:22px;padding:12px 32px;border-top:1px solid #edf1f7;font-size:30px;color:#26364d}"
           ".r.hl{background:#fff6dc;font-family:'ZH Bold',sans-serif;color:#9a5b00}.r.more{color:#7b8aa0;font-size:26px;padding-left:96px}"
           ".fo{flex:none;width:52px;height:40px;border-radius:6px;background:#f2b84b;position:relative}.fo:before{content:'';position:absolute;left:0;top:-8px;width:22px;height:10px;border-radius:4px 4px 0 0;background:#f2b84b}"
           ".f{display:flex;align-items:center;gap:22px;padding:11px 32px;border-top:1px solid #edf1f7}"
           ".ic{flex:none;width:58px;height:66px;border-radius:8px;display:flex;align-items:flex-end;justify-content:center;padding-bottom:8px;"
           "font-family:'ZH Bold',sans-serif;font-size:19px;color:#fff;background:#d64541}.ic.mp3{background:#2e9e5b}"
           ".fn{flex:none;width:330px;font-family:'ZH Bold',sans-serif;font-size:30px;color:#123c69}.fd{font-size:25px;color:#5b6b80}</style>")
    imgs['01_资料总览'] = page('01', '资料总览', '<b>历年真题套卷 + 答案解析</b> + <b>60 个篇目文件夹</b>，每个文件夹里都是下面这 6 个文件', win,
                             chips('<b>历年真题</b>套卷+解析', '<b>60</b> 篇精读', '<b>300</b> 份 PDF', '<b>256</b> 个长难句', '<b>60</b> 段音频'))
    # 2 长难句分析（只有这一张写“虚拟产品……”）
    p = render_pages(pdf_of('4 长难句分析'), [1, 2], 110, td)
    imgs['02_长难句分析'] = page('02', '长难句分析', '挑出每篇<b>又长又复杂</b>的句子：找主干 → 层层拆解 → 怎么读懂 → 怎么翻译 → 知识点',
                              ''.join(f"<div class='pg' style='width:670px'><img src='{u}'></div>" for u in p),
                              "<div class='notice'>虚拟产品，一旦售出无法退款，谢谢理解</div>")
    # 3 逐句精读
    p = render_pages(pdf_of('0 逐句精读'), [1, 6, 14], 60, td)
    imgs['03_逐句精读'] = page('03', '逐句精读', '与视频画面<b>一模一样</b>：片头 + 每屏一页，英文高亮、中文翻译、生词编号注释',
                             f"<div style='display:flex;flex-direction:column;gap:30px;align-items:center'><div class='pg' style='width:1220px'><img src='{p[1]}'></div>"
                             f"<div style='display:flex;gap:30px'><div class='pg' style='width:595px'><img src='{p[0]}'></div><div class='pg' style='width:595px'><img src='{p[2]}'></div></div></div>",
                             chips('<b>16:9</b> 横版', '单词 · 短语 分色高亮', '生词编号对应注释'))
    # 4—6 听写卡
    for no, kind, desc in (('04', '1 汉译英', '看<b>中文</b>写<b>英文</b>：本篇全部生词与短语，按单词 / 短语分组默写'),
                           ('05', '2 英译汉', '看<b>英文</b>写<b>中文</b>：本篇全部生词与短语，按单词 / 短语分组默写'),
                           ('06', '3 文章填空', '<b>原文挖空</b>，下面附整句翻译和每空释义，检验在语境里会不会用')):
        pdf = pdf_of(kind)
        n = int(subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True, check=True).stdout.split('Pages:')[1].split()[0])
        p = render_pages(pdf, [1, n], 110, td)
        imgs[f'{no}_{kind[2:]}'] = page(no, kind[2:], desc,
                                         f"<div class='pg' style='width:700px'><img src='{p[0]}'></div><div style='display:flex;flex-direction:column;align-items:center;gap:14px'>"
                                         f"<div class='pg' style='width:560px'><img src='{p[1]}'></div><div style='font-size:30px;color:#5b6b80'>最后一页：答案</div></div>",
                                         chips('A4 打印', '最后一页是答案', '可反复默写'))
    # 7 朗读音频：真实波形
    import numpy as np
    import soundfile as sf
    T = json.loads((C6 / 'audio' / 'timings.json').read_text('utf-8'))['cet4_male']['s01']
    a, sr = sf.read(str(C6 / 'audio' / T['file']), dtype='float32')
    a = a if a.ndim == 1 else a.mean(1)
    n = 96                                         # 响度包络（均方根），按 98% 分位归一、加大对比：句间停顿看得出来
    env = np.array([np.sqrt(np.mean(c ** 2)) for c in np.array_split(a, n)])
    env = np.clip(env / np.percentile(env, 98), 0, 1) ** 1.6
    bars = ''.join(f"<i style='height:{max(6, int(v * 300))}px'></i>" for v in env)
    dur = len(a) / sr
    player = (f"<div class='pl'><div class='ttl'>{NAME} - 朗读音频.mp3</div><div class='wave'>{bars}</div>"
              f"<div class='ctl'><span class='btn'>▶</span><div class='prog'><div></div></div><span>00:00 / {int(dur // 60):02d}:{int(dur % 60):02d}</span></div></div>"
              "<style>.pl{width:1420px;background:#fff;border-radius:22px;box-shadow:0 18px 50px rgba(18,60,105,.22);padding:56px 60px}"
              ".ttl{font-family:'ZH Bold',sans-serif;font-size:36px;color:#123c69}.wave{height:320px;display:flex;align-items:center;gap:6px;margin:40px 0}"
              ".wave i{flex:1;background:linear-gradient(#3f86d6,#123c69);border-radius:4px}"
              ".ctl{display:flex;align-items:center;gap:30px;font-size:32px;color:#5b6b80}.btn{width:96px;height:96px;border-radius:50%;background:#123c69;color:#fff;"
              "display:flex;align-items:center;justify-content:center;font-size:44px}.prog{flex:1;height:12px;background:#e3eaf4;border-radius:6px}"
              ".prog div{width:0;height:12px}</style>")
    imgs['07_朗读音频'] = page('07', '朗读音频', '<b>男声逐句朗读</b>，与视频是同一份朗读：句与句之间停顿 0.8 秒，方便跟读、听写', player,
                             chips('MP3', '每篇一段', '逐句停顿'))
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': W, 'height': W})
        for k, h in imgs.items():
            f = td / f'{k}.html'
            f.write_text(h, 'utf-8')
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            pg.wait_for_timeout(300)
            pg.screenshot(path=str(OUT / f'{k}.png'))
            print(OUT / f'{k}.png', flush=True)
        br.close()
    shutil.rmtree(td, ignore_errors=True)


if __name__ == '__main__':
    main()
