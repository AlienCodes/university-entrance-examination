"""生产精听engine片头ONLY真实浏览器检查，不改题名/正文、不需要原音。

完整p字段与精听数据.compile_input的passage构造相同；直接运行生产title_slide/page、
layout片头分支的TITLE_JS/SUB_FIT_JS及screen_checks。绝无题名替换/缩短或虚构音频时间。
"""
from __future__ import annotations
import argparse,copy,json,hashlib,tempfile,shutil,sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from 精听 import engine,load_module
from 精听数据 import ROOT,HERE,TOKEN
BATCH=HERE.parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p=Path(p);p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def passage(d):
 flat=[{k:copy.deepcopy(s[k]) for k in ['en','zh','w']} for s in d['sentences']]
 return {'id':d['id'],'year':d['year'],'month':0,'set':1,'part':'L','paper':f"{d['year']}年专八听力",'passage':d['section'],'title':d['title'],'genre':d.get('genre','听力原文'),'summary':d.get('summary',''),'done':True,'words':sum(len(TOKEN.findall(s['en'])) for s in flat),'nv':sum(len(s['w']) for s in flat),'paras':[flat]}

MEASURE="""() => {
 const h=document.querySelector('.ttl h1'),r=document.createRange();r.selectNodeContents(h);
 const boxes=[...r.getClientRects()].map(x=>({x:x.x,y:x.y,width:x.width,height:x.height}));
 const ys=[];for(const b of boxes)if(!ys.some(y=>Math.abs(y-b.y)<2))ys.push(b.y);
 const s=getComputedStyle(h),br=h.getBoundingClientRect();
 return {title_text:h.textContent,title_lines:ys.length,font_family:s.fontFamily,font_size:s.fontSize,line_height:s.lineHeight,
 title_rect:{x:br.x,y:br.y,width:br.width,height:br.height},text_rects:boxes,font_faces:[...document.fonts].map(f=>({family:f.family,style:f.style,status:f.status})),fonts_ready:document.fonts.status};
}"""

def check(job):
 from playwright.sync_api import sync_playwright
 d,out,origin,export,synthetic=job;out=Path(out);out.mkdir(exist_ok=True,parents=True)
 for name in ['tools','data','shots']:(out/name).mkdir(exist_ok=True)
 p=passage(d);assert p['title']==d['title'],'母稿title与生产passage title不逐字一致'
 dump(out/'source.json',d);dump(out/'data/vocab.json',{'passages':[p]});dump(out/'tools/人名.json',{'names':d.get('names',[])});dump(out/'tools/分屏_水墨.json',{d['id']:{}})
 helper=load_module('tem8_real_cover_http',ROOT/'高考听力/精读/tools/本机预览.py');helper.enable([ROOT,out,Path(tempfile.gettempdir())],'/usr/bin/chromium')
 m=engine(out);m.P_CUR=p;before=json.dumps(p,ensure_ascii=False,sort_keys=True)
 html=m.title_slide(p);page=out/'page.html';page.write_text(html)
 with sync_playwright() as pw:
  br=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);pg=br.new_page(viewport={'width':1920,'height':1080},device_scale_factor=2)
  pg.goto(page.as_uri());pg.evaluate('document.fonts.ready');pg.wait_for_timeout(150);pg.evaluate(m.TITLE_JS)
  if m.PJ.get('sub_fit'):pg.evaluate(m.SUB_FIT_JS)
  problems=m.screen_checks(pg,'片头',False,None);measurement=pg.evaluate(MEASURE);pg.screenshot(path=str(out/'shots/cover.png'));br.close()
 assert json.dumps(p,ensure_ascii=False,sort_keys=True)==before,'生产题名快检不得变更passage数据'
 assert p['title']==d['title']
 if export and export.get('title_equal_to_mother') is False:problems.append('源一致性：当前导出title与母稿title不逐字相同，须owner刷新后生产')
 result={'id':d['id'],'status':'passed' if not problems else 'blocked','scope':'生产精听engine真实封面ONLY；不涉及音频或正文/换屏批准','synthetic_test_only':synthetic,'mother_title':d['title'],'actual_passage_title':p['title'],'mother_title_literal_equal_p_title':True,'origin':origin,'production_export':export,'source_snapshot_sha256':sha(out/'source.json'),'passage_sha256':hashlib.sha256(before.encode()).hexdigest(),'html_sha256':sha(page),'png_sha256':sha(out/'shots/cover.png'),'dimensions':[3840,2160],'measurement':measurement,'problems':problems,'engines':{str(f.relative_to(ROOT)):sha(f) for f in [Path(__file__),HERE/'精听.py',HERE/'精听数据.py',ROOT/'专八/tools/make_video.py']},'actual_production_functions':['精听.engine','make_video.title_slide','精听.engine包装后的m.page','make_video.TITLE_JS','make_video.SUB_FIT_JS（PJ要求时）','make_video.screen_checks(pg,片头,False,None)']}
 dump(out/'封面核验.json',result);print(d['id'],result['status'],'lines',measurement['title_lines'],repr(d['title']),problems,flush=True)
 return {'id':d['id'],'status':result['status'],'title':d['title'],'title_lines':measurement['title_lines'],'problems':problems,'report':str(out/'封面核验.json')}

def worker(job):
 try:return check(job)
 except BaseException as e:
  result={'id':job[0]['id'],'status':'error','error':type(e).__name__+': '+str(e)};dump(Path(job[1])/'封面核验.json',result);print(result,flush=True);return result

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--ids',nargs='+');ap.add_argument('--out',type=Path,required=True);ap.add_argument('--workers',type=int,default=3);ap.add_argument('--selftest',action='store_true');a=ap.parse_args();a.out.mkdir(exist_ok=True,parents=True)
 units={};origins={}
 for f in sorted((BATCH/'译注草稿').glob('*.json')):
  obj=json.loads(f.read_text())
  for u in obj['units']:units[u['id']]={'year':obj['year'],**u};origins[u['id']]={'file':str(f.relative_to(BATCH)),'sha256':sha(f)}
 jobs=[]
 if a.selftest:
  for label,title in [('normal','讲座：语言与交流'),('long','讲座：语言的副语言特征（新题型优化版所供原文）')]:
   d=copy.deepcopy(units['2010-A']);d['title']=title;jobs.append((d,a.out/label,origins['2010-A'],None,True))
 else:
  assert a.ids and len(a.ids)==len(set(a.ids))
  for uid in a.ids:
   d=units[uid];f=BATCH/'精听数据'/f'{uid}.json';export=None
   if f.exists():
    fd=json.loads(f.read_text());export={'file':str(f.relative_to(BATCH)),'sha256':sha(f),'title':fd['title'],'title_equal_to_mother':fd['title']==d['title']}
   jobs.append((d,a.out/uid,origins[uid],export,False))
 results=[]
 with ProcessPoolExecutor(max_workers=max(1,min(3,a.workers))) as pool:
  for f in as_completed([pool.submit(worker,j) for j in jobs]):
   results.append(f.result());dump(a.out/'汇总.json',{'scope':'production_engine_cover_only_no_title_rewrite','expected':len(jobs),'completed':len(results),'results':results})
 if a.selftest:
  normal=next(r for r in results if r['report'].endswith('/normal/封面核验.json'));long=next(r for r in results if r['report'].endswith('/long/封面核验.json'));assert normal['status']=='passed' and long['status']=='blocked';print('真实浏览器短题名正例通过、超长题名反例被拦。')
 return 0 if a.selftest or all(x['status']=='passed' for x in results) else 1
if __name__=='__main__':raise SystemExit(main())
