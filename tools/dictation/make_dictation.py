"""生成听写卡 PDF（每篇三份）：汉译英、英译汉、挖空文章。

    /opt/ttsenv/bin/python tools/dictation/make_dictation.py p01 [p02 …]

输出到 听写卡/：
  pXX 年份 试卷 阅读C 题目 - 1 汉译英.pdf   左边中文释义，右边横线默写英文
  pXX … - 2 英译汉.pdf                     左边英文，右边横线写中文
  pXX … - 3 挖空文章.pdf                   原文中标注的词换成带编号的空框，下面是整句翻译和每个空的释义
每份最后一页是答案。词条来自 data/vocab.json（与网页、视频同一份定稿数据）。
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FONTS = HERE.parent / 'video' / 'fonts'
OUT = ROOT / '听写卡'
TIER = {'core': '课标', 'ext': '超纲', 'phr': '短语'}
FOOTNOTE = re.compile(r'\s*\([^()]*[一-鿿][^()]*\)')   # 试卷里的中文注释，如 (居民)

CSS = f"""
@font-face{{font-family:'SC';src:url('{(FONTS / 'NotoSansSC-Regular.ttf').as_uri()}');font-weight:400}}
@font-face{{font-family:'SC';src:url('{(FONTS / 'NotoSansSC-Bold.ttf').as_uri()}');font-weight:700}}
@font-face{{font-family:'Serif';src:url('{(FONTS / 'SourceSerif4-Regular.otf').as_uri()}');font-weight:400}}
@font-face{{font-family:'Serif';src:url('{(FONTS / 'SourceSerif4-Semibold.otf').as_uri()}');font-weight:600}}
@page{{size:A4;margin:16mm 16mm 18mm}}
*{{box-sizing:border-box}}
body{{font-family:'SC',sans-serif;color:#1d2433;font-size:11pt;margin:0}}
h1{{font-size:17pt;margin:0 0 2mm}}
.sub{{color:#555;font-size:10pt;margin-bottom:3mm}}
.who{{display:flex;gap:10mm;font-size:10.5pt;margin:2mm 0 5mm;padding-bottom:3mm;border-bottom:1.5px solid #1d2433}}
.who span{{flex:1;border-bottom:1px solid #999;padding-bottom:1mm}}
table{{width:100%;border-collapse:collapse}}
td{{padding:2.2mm 1.5mm;vertical-align:bottom;border-bottom:1px dashed #ccc}}
td.n{{width:8mm;color:#888;font-size:9.5pt}}
td.t{{width:11mm;font-size:8pt;color:#777}}
td.q{{width:48%}}
td.a{{border-bottom:1px solid #333}}
.en{{font-family:'Serif',serif;font-size:12pt}}
.ans h2{{font-size:13pt;margin:0 0 3mm}}
.ans{{break-before:page}}
.ans table td{{padding:1.4mm 1.5mm;font-size:10pt}}
.sent{{margin:0 0 5mm;break-inside:avoid}}
.sent .en{{font-size:12.5pt;line-height:2.1}}
.k{{color:#999;font-size:9pt;margin-right:1.5mm}}
.blank{{display:inline-block;border:1.2px solid #1d2433;border-radius:2px;height:7mm;vertical-align:-2mm;
        position:relative;margin:0 .5mm}}
.blank i{{position:absolute;left:1mm;top:-.2mm;font-style:normal;font-family:'SC';font-size:7.5pt;color:#B4231A}}
.zh{{color:#333;font-size:10.5pt;margin-top:1mm}}
.hints{{font-size:10pt;color:#333;margin-top:1mm;display:flex;flex-wrap:wrap;gap:1mm 5mm}}
.hints b{{color:#B4231A;font-weight:700;margin-right:1mm}}
"""


def esc(s):
    return html.escape(s, quote=False)


def entries(p):
    """全文词条，按出现顺序，同一词头 + 同一释义只保留第一次。"""
    seen, out = set(), []
    for k, s in enumerate((s for para in p['paras'] for s in para), 1):
        for w in sorted(s['w'], key=lambda w: w['sp'][0][0]):
            key = (w['h'].lower(), w['m'])
            if key not in seen:
                seen.add(key)
                out.append(w)
    return out


def header(p, kind, note):
    paper = re.sub(r'·[^）]*', '', p['paper'])
    return (f"<h1>{esc(kind)}</h1><div class='sub'>{p['year']} {esc(paper)} 阅读{p['part']} · {esc(p['title'])} · {esc(note)}</div>"
            "<div class='who'><span>姓名：</span><span>日期：</span><span>得分：</span></div>")


def word_list(p, mode):
    E = entries(p)
    rows, ans = [], []
    for i, w in enumerate(E, 1):
        tier = TIER[w['t']]
        if mode == 'zh2en':
            q = f"<td class='q'>{esc(w['m'])}</td>"
            a = f"<span class='en'>{esc(w['h'])}</span>"
        else:
            q = f"<td class='q en'>{esc(w['h'])}</td>"
            a = esc(w['m'])
        rows.append(f"<tr><td class='n'>{i}</td><td class='t'>{tier}</td>{q}<td class='a'></td></tr>")
        ans.append(f"<tr><td class='n'>{i}</td><td class='t'>{tier}</td><td>{esc(w['h']) if mode == 'en2zh' else esc(w['m'])}</td><td>{a}</td></tr>")
    kind, note = (('汉译英听写', f'看中文写英文，共 {len(E)} 个') if mode == 'zh2en' else ('英译汉听写', f'看英文写中文，共 {len(E)} 个'))
    return (header(p, kind, note) + f"<table>{''.join(rows)}</table>"
            f"<div class='ans'><h2>答案</h2><table>{''.join(ans)}</table></div>")


def cloze(p):
    body, ans, n = [], [], 0
    for k, s in enumerate((s for para in p['paras'] for s in para), 1):
        en = s['en']
        spans = sorted(((a, b, w) for w in s['w'] for a, b in w['sp']), key=lambda x: x[0])
        num = {}
        for a, b, w in spans:                       # 同一个词条（分开的短语）共用一个编号
            if id(w) not in num:
                n += 1
                num[id(w)] = n
        parts, pos = [], 0
        for a, b, w in spans:
            parts.append(esc(FOOTNOTE.sub('', en[pos:a])))
            width = max(14, min(60, 2.3 * (b - a) + 6))
            parts.append(f"<span class='blank' style='width:{width:.0f}mm'><i>{num[id(w)]}</i></span>")
            pos = b
        parts.append(esc(FOOTNOTE.sub('', en[pos:])))
        hints, seen = [], set()
        for a, b, w in spans:
            if id(w) in seen:
                continue
            seen.add(id(w))
            hints.append(f"<span><b>{num[id(w)]}</b>{esc(w['m'])}</span>")
            ans.append(f"<tr><td class='n'>{num[id(w)]}</td><td class='en'>{esc(' … '.join(en[x:y] for x, y in w['sp']))}</td><td>{esc(w['m'])}</td></tr>")
        body.append(f"<div class='sent'><div class='en'><span class='k'>{k}</span>{''.join(parts)}</div>"
                    f"<div class='zh'>{esc(s['zh'])}</div><div class='hints'>{''.join(hints)}</div></div>")
    return (header(p, '挖空文章', f'按中文提示填写原文中的单词或短语（注意词形变化），共 {n} 空') + ''.join(body) +
            f"<div class='ans'><h2>答案</h2><table>{''.join(ans)}</table></div>")


def main():
    from playwright.sync_api import sync_playwright
    data = json.loads((ROOT / 'data' / 'vocab.json').read_text('utf-8'))
    P = {p['id']: p for p in data['passages']}
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page()
        for pid in sys.argv[1:]:
            p = P[pid]
            paper = re.sub(r'·[^）]*', '', p['paper'])
            base = f"{pid} {p['year']} {paper} 阅读{p['part']} {p['title']}"
            for name, body in (('1 汉译英', word_list(p, 'zh2en')), ('2 英译汉', word_list(p, 'en2zh')), ('3 挖空文章', cloze(p))):
                pg.set_content(f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>")
                pg.evaluate('document.fonts.ready')
                f = OUT / f'{base} - {name}.pdf'
                pg.pdf(path=str(f), format='A4', print_background=True,
                       display_header_footer=True, header_template='<span></span>',
                       footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#999'>"
                                       "<span class='pageNumber'></span> / <span class='totalPages'></span></div>",
                       margin={'top': '16mm', 'bottom': '18mm', 'left': '16mm', 'right': '16mm'})
                print('已生成', f)
        br.close()


if __name__ == '__main__':
    main()
