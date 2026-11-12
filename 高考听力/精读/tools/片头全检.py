"""一次核对50套已确认片头：年份卷名、主次字号、字体、边界和重叠。"""
import argparse
import json
import os
from pathlib import Path
import tempfile
from 数据 import C,ROOT,load_text,sha,dump
from 项目 import engine
from 片头检查 import problems


def main():
    from playwright.sync_api import sync_playwright
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,default=C/'大字版/片头全检')
    args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if os.environ.get('GK_HTTP'):
        from 本机预览 import enable
        enable([ROOT,out,Path(tempfile.gettempdir())],os.environ.get('GK_BROWSER','/usr/bin/chromium'))
    m=engine();rows=[]
    with sync_playwright() as pw:
        br=pw.chromium.launch(executable_path=os.environ.get('GK_BROWSER','/opt/pw-browsers/chromium'))
        pg=br.new_page(viewport={'width':1920,'height':1080},device_scale_factor=2)
        for src in sorted((C/'定稿').glob('*.json')):
            d,p,_=load_text(src.stem);m.NAMES=d['names']
            html=out/'cover.html';html.write_text(m.title_slide(p))
            pg.goto(html.as_uri());pg.evaluate('document.fonts.ready');pg.evaluate(m.GK_COVER_FIT)
            bad=problems(pg,m,p['paper_title']);shot=out/(src.stem+'.png');pg.screenshot(path=str(shot))
            rows.append({'id':src.stem,'title':p['paper_title'],'problems':bad,'sha256':sha(shot)})
        br.close()
    report={'ok':not any(r['problems'] for r in rows),'covers':rows};dump(out/'report.json',report)
    assert report['ok'],[r for r in rows if r['problems']]
    print(f'{len(rows)}套片头：文字、字号层级、边界、字体、无重叠检查全部通过')


if __name__=='__main__':main()
