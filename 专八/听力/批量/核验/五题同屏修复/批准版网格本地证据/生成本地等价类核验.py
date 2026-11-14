from pathlib import Path
import importlib.util,json,sys
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[6];adapter=root/'专八/听力/批量/tools/考试视频.py'
spec=importlib.util.spec_from_file_location('A',adapter);A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
years=[int(x) for x in sys.argv[1:]] or [2009,2010,2011,2012,2013,2014,2015,2016,2017,2018,2019,2021,2022,2023,2024]
report=[]
with sync_playwright() as pw:
 br=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 pager=A.B.Pager(br,viewport={'width':1920,'height':1080},device_scale_factor=2)
 for year in years:
  out=Path(__file__).resolve().parent/'临时本地输出'/str(year);A.configure(root/f'专八/听力/批量/数据/{year}',out)
  raw,total,meta=A.states();chosen={}
  for _,s in raw:
   if s['kind'] not in ['plist','q']:continue
   shape=(s['kind'],s['group'],s.get('n'),s.get('st'),s.get('cdl'),bool('cd'in s))
   if shape not in chosen or s.get('cd',0)>chosen[shape].get('cd',0):chosen[shape]=s
  checks=[]
  with A.serving() as base:
   for i,s in enumerate(chosen.values()):
    htm=A.page(s);url=base+'/render/'+str(i)+'.html';htm=htm.replace(root.as_uri()+'/',base+'/project/')
    (out/(str(i)+'.html')).write_text(htm)
    pg=pager.load(url);fit=A.fit_layout(pg,s);sp=pg.evaluate(A.SPACING_JS)
    bad=pg.evaluate(A.CHECK_JS)+A.B.font_check(pg,pager.cdp)+A.leak_check(s,htm)+sp['errors'];snap=None
    try:snap=A.group_screen_check(pg,s)
    except Exception as e:bad.append(str(e))
    checks.append({'state':s,'fit':fit,'spacing':sp,'group_snapshot':snap,'errors':bad})
    if i==0 or bad or s.get('n')in[1,5,6,10]:pg.screenshot(path=str(out/(f'{i}-{s["kind"]}-{s.get("n",s["group"])}'+'.png')))
    if bad:print(year,i,s['kind'],s.get('n',s['group']),'FAIL',bad[:3],flush=True)
  A.dump(out/'全部组状态DOM核验.json',{'adapter_sha256':A.sha(adapter),'year':year,'states_total':len(raw),'equivalence_classes':len(checks),'checks':checks})
  fails=[c for c in checks if c['errors']];report.append({'year':year,'classes':len(checks),'errors':len(fails),'fonts':sorted(set(c['fit'].get('font_size',0) for c in checks))})
  print(json.dumps(report[-1]),flush=True)
 br.close()
(Path(__file__).resolve().parent/'临时本地输出/summary.json').write_text(json.dumps(report,indent=2))
if any(c['errors']for c in report):sys.exit(1)
