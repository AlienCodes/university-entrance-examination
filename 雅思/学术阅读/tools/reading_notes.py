"""Export the complete bilingual text and the same contextual glosses as the video."""
import html
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright
from lesson import ROOT, load
from pilot_video import engine, visible_words

def main(destination):
    p=load()
    rows=[]
    for n,s in enumerate((s for group in p['paras'] for s in group),1):
        parts=engine.split_parts(p['id'],n,s)
        for i,(lo,hi,zh,_) in enumerate(parts,1):
            words=visible_words(s,lo,hi)
            gloss='　·　'.join(f'<b>{html.escape(w["h"])}</b> {html.escape(w["m"])}' for w in words)
            part=f'<small>{i}/{len(parts)}</small>' if len(parts)>1 else ''
            rows.append(f'<article><aside>{n:02d}{part}</aside><section><p class="en">{html.escape(s["en"][lo:hi].strip())}</p>'
                        f'<p lang="zh-CN">{html.escape(zh)}</p><p class="gl">{gloss}</p></section></article>')
    css=(ROOT/'四级/tools/fonts/fonts.css').as_uri()
    head=(f'<meta charset="utf-8"><link rel="stylesheet" href="{css}"><style>'
          '@page{size:A4;margin:16mm 16mm 15mm}*{box-sizing:border-box}body{color:#142a25;font:11pt/1.5 "Inter","Noto Serif SC",serif}'
          'header{border-bottom:3px solid #1f5246;padding-bottom:12px;margin-bottom:14px}h1{font-size:23pt;margin:0}header p{margin:0;color:#345d52}'
          'article{display:flex;gap:13px;break-inside:avoid;border-bottom:1px solid #b3c5be;padding:7px 0}'
          'aside{color:#3d7161;font-weight:700;min-width:27px}aside small{display:block;font-weight:400;font-size:8pt}section{min-width:0}p{margin:0 0 4px}.en{font-size:12pt;font-weight:650}'
          '.gl{color:#345d52;font-size:9.5pt;line-height:1.5}.gl b{font-weight:700}</style>')
    body=('<header><p>剑桥雅思 20　学术类阅读　Test 1 · Passage 1</p>'
          '<h1>The kākāpō　鸮鹦鹉</h1><p>逐句原文、中文译文与语境词汇</p></header>'+''.join(rows))
    with tempfile.TemporaryDirectory() as tmp,sync_playwright() as pw:
        path=Path(tmp)/'notes.html';path.write_text('<!doctype html><html lang="zh-CN"><head>'+head+'</head><body>'+body+'</body></html>')
        br=pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg=br.new_page();pg.goto(path.as_uri());pg.evaluate('document.fonts.ready')
        assert pg.locator('article').count()==len(rows)
        pg.pdf(path=str(destination),prefer_css_page_size=True,print_background=True)
        br.close()

if __name__=='__main__':main(Path(sys.argv[1]))
