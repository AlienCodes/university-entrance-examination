"""实际Chromium+生产HTML+生产DOM提取器错误注入，不编码或审阅视频。

只验证一个真实题组的DOM门禁；不能替代全部15年修复布局预检、PNG审批或成品核验。
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[5]
ADAPTER=ROOT/'专八/听力/批量/tools/考试视频.py'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--browser',default='/usr/bin/chromium')
    ap.add_argument('--report',type=Path,default=Path(__file__).with_name('实际DOM错误注入结果.json'))
    args=ap.parse_args()
    adapter_sha256=hashlib.sha256(ADAPTER.read_bytes()).hexdigest()
    sp=importlib.util.spec_from_file_location('tem8_actual_group_dom_test',ADAPTER)
    m=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m;sp.loader.exec_module(m)
    assert adapter_sha256==hashlib.sha256(ADAPTER.read_bytes()).hexdigest(),'测试加载期间adapter发生改变，结果无效'
    paper=json.loads((ROOT/'专八/听力/批量/数据/2024/试卷.json').read_text())
    group=paper['groups'][1]
    m.PAPER=paper
    state={'kind':'plist','group':group['id'],'numbers':group['questions'],'display_page':1,'display_pages':1}
    cases=[
      ('完整五题正例','',False),
      ('删去第五题',"document.querySelectorAll('.full-group .qg')[4].remove()",True),
      ('删去一个选项',"document.querySelectorAll('.full-group .opt')[3].remove()",True),
      ('选项文字省略',"document.querySelector('.full-group .option-text').textContent='…'",True),
      ('子文字display_none',"document.querySelector('.full-group .option-text').style.display='none'",True),
      ('子文字visibility_hidden',"document.querySelector('.full-group .option-text').style.visibility='hidden'",True),
      ('子文字opacity0',"document.querySelector('.full-group .option-text').style.opacity='0'",True),
      ('子文字transparent',"document.querySelector('.full-group .option-text').style.color='transparent'",True),
      ('子文字20px',"document.querySelector('.full-group .option-text').style.setProperty('font-size','20px','important')",True),
      ('子文字scale_half',"let e=document.querySelector('.full-group .option-text');e.style.display='inline-block';e.style.transform='scale(.5)'",True),
      ('完整选项改为未批准inline连排',"let box=document.querySelector('.full-group .qg .options');box.style.display='block';for(let e of box.querySelectorAll('.opt')){e.style.display='inline';e.style.paddingRight='16px';for(let x of e.children)x.style.display='inline'}",True),
      ('文字overflow_hidden',"let e=document.querySelector('.full-group .option-text');e.style.display='inline-block';e.style.maxWidth='10px';e.style.overflow='hidden';e.style.whiteSpace='nowrap'",True),
      ('文字overflow_clip',"let e=document.querySelector('.full-group .option-text');e.style.display='inline-block';e.style.maxWidth='10px';e.style.overflow='clip';e.style.whiteSpace='nowrap'",True),
      ('文字clip_path',"document.querySelector('.full-group .option-text').style.clipPath='inset(0 90% 0 0)'",True),
      ('DOM两页',"document.querySelector('.full-group').dataset.pageCount='2'",True),
      ('ASCII分页标题',"document.querySelector('.group-title').append(' (1/2)')",True),
      ('中文括号分页标题',"document.querySelector('.group-title').append(' （1/2）')",True),
    ]
    rows=[]
    with tempfile.TemporaryDirectory(prefix='tem8-group-dom-negative-') as td, sync_playwright() as pw:
      m.OUT=Path(td);f=Path(td)/'actual.html'
      browser=pw.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox'])
      try:
       pg=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
       with m.serving() as base:
        f.write_text(m.page(state).replace(ROOT.as_uri()+'/',base+'/project/'),'utf-8')
        for name,script,want in cases:
         pg.goto(base+'/render/actual.html');m.B.fonts_loaded(pg);fit=m.fit_layout(pg,state)
         baseline=m.group_screen_check(pg,state)
         assert len(baseline['questions'])==5
         if script:pg.evaluate('()=>{'+script+'}')
         rejected=False;error=None
         try:m.group_screen_check(pg,state)
         except (ValueError,KeyError,TypeError,AssertionError) as exc:rejected=True;error=str(exc)
         rows.append({'name':name,'expected_rejection':want,'rejected':rejected,'ok':want==rejected,'error':error,'fit':fit})
      finally:browser.close()
    source_unchanged=adapter_sha256==hashlib.sha256(ADAPTER.read_bytes()).hexdigest()
    result={'status':'PASS' if all(r['ok'] for r in rows) and source_unchanged else 'FAIL','scope':'2024第二组真实生产HTML，实际DOM提取及门禁正反例；不是15年全部修复布局或成品审批。','approved_layout':'固定A/B上行、C/D下行的两栏；题间2px纯黑#000000分隔线。','browser':args.browser,'adapter_sha256':adapter_sha256,'adapter_source_unchanged':source_unchanged,'cases':rows}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'cases':len(rows),'mismatches':[r for r in rows if not r['ok']]},ensure_ascii=False))
    sys.exit(result['status']!='PASS')


if __name__=='__main__':main()
