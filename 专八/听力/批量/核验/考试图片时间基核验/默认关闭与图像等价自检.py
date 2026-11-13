import sys,types,ast,json,hashlib,tempfile,copy,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[5];base=root/'专八/听力/tools/听力视频.py';adapter=root/'专八/听力/批量/tools/考试视频.py';before=subprocess.check_output(['git','cat-file','blob','a7fd86387b8d0b528fdfb92a5d35f69d0349f2d7'],cwd=root).decode();after=base.read_text();out=Path(tempfile.mkdtemp(prefix='tem8-default-compat-'));(out/'shots').mkdir();[(out/'shots'/f'{k}.png').touch() for k in ['a','b','c','d']]
def load(name,s,p):
 m=types.ModuleType(name);m.__file__=str(p);sys.modules[name]=m;exec(compile(s,str(p),'exec'),m.__dict__);return m
old=load('clock_base_before',before,base);new=load('clock_base_after',after,base)
def run(m,fast,original,exact='default'):
 calls=[];m.OUT=out;m.NAME='fixture.mp4';m.ORIGINAL=original;m.key=lambda s:s['key'];m.audio_track=lambda wav:([(-m.LEAD,{'key':'a'}),(17/30-m.LEAD,{'key':'b'}),(18/30-m.LEAD,{'key':'c'}),(20/30-m.LEAD,{'key':'d'})],90/30-m.LEAD,{'audioEnd':1},90,44100);m.verify=lambda *a:None
 class Spy:
  def run(self,args,**kw):
   calls.append((args,kw))
   if args[0]=='ffprobe':return types.SimpleNamespace(stdout=' '.join(str(i/30) for i in range(90)) if 'packet=pts_time' in args else '3.0')
   return types.SimpleNamespace(returncode=0)
 m.subprocess=Spy()
 if exact=='default':m.video('fixture.wav',fast)
 else:m.video('fixture.wav',fast,exact_image_fps=exact)
 return {'calls':calls,'concat':(out/'list.txt').read_text(),'frames':(out/'帧表.json').read_text()}
tests=[]
for fast in [False,True]:
 for original in [False,True]:
  a=run(old,fast,original);b=run(new,fast,original);assert a==b;tests.append({'name':f'default_none_fast={fast}_original={original}','pass':True,'command_concat_frames_identical':True})
for fast in [False,True]:
 r=run(new,fast,True,30);assert r['concat'].count('option framerate 30')==6;cmd=next(c for c,k in r['calls'] if c[0]=='ffmpeg');vf=cmd[cmd.index('-vf')+1];assert vf==('scale=480:270,fps=30:start_time=0:round=near' if fast else 'fps=30:start_time=0:round=near');tests.append({'name':f'exact30_fast={fast}','pass':True,'filter':vf})
try:run(new,False,True,24)
except SystemExit:tests.append({'name':'different_fps_rejected','pass':True})
else:raise AssertionError('应拒不同输入/输出帧率')
def funcs(s):return {x.name:ast.dump(x,include_attributes=False) for x in ast.parse(s).body if isinstance(x,ast.FunctionDef)}
a,b=funcs(before),funcs(after);assert [k for k in a if a[k]!=b[k]]==['video']
adold=subprocess.check_output(['git','cat-file','blob','deb970bb0cda3fe39df9ea55d1b066c53baa7ace'],cwd=root).decode();adnew=adapter.read_text();aa,ab=funcs(adold),funcs(adnew);assert [k for k in aa if aa[k]!=ab[k]]==['main'];assert set(ab)-set(aa)=={'fast_frame_check','require_fast_frame_check'}
# Compare all actual per-year state plans and every rendered HTML under the old/new code.
modold=types.ModuleType('clock_adapter_before');modold.__file__=str(adapter);modold.BASE_BEFORE_SOURCE=before;sys.modules[modold.__name__]=modold;exec(compile(adold.replace('spec.loader.exec_module(B)',"exec(compile(BASE_BEFORE_SOURCE,str(BASE_FILE),'exec'),B.__dict__)"),str(adapter),'exec'),modold.__dict__)
modnew=load('clock_adapter_after',adnew,adapter);years=[]
for year in [2009,2010,2011,2012,2013,2014,2015,2016,2017,2018,2019,2021,2022,2023,2024]:
 pairs=[]
 for label,m in [('old',modold),('new',modnew)]:
  m.configure(root/'专八/听力/批量/数据'/str(year),out/label/str(year));L,total,T=m.states();htmlhash=hashlib.sha256();keys=[]
  for t,s in L:
   html=m.page(s);htmlhash.update(html.encode());keys.append(m.B.key(s))
  pairs.append({'states_sha256':hashlib.sha256(json.dumps([L,total,T],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'HTML_aggregate_sha256':htmlhash.hexdigest(),'PNG_keys_multiset':sorted(keys),'count':len(L)})
 assert pairs[0]==pairs[1];years.append({'year':year,'old':pairs[0],'new':pairs[1],'identical':True})
report={'status':'PASS','base_old_sha256':hashlib.sha256(before.encode()).hexdigest(),'base_new_sha256':hashlib.sha256(after.encode()).hexdigest(),'adapter_old_sha256':hashlib.sha256(adold.encode()).hexdigest(),'adapter_new_sha256':hashlib.sha256(adnew.encode()).hexdigest(),'tests':tests,'base_only_changed_function':'video','adapter_changed_function':'main','adapter_added_functions':['fast_frame_check','require_fast_frame_check'],'all_other_functions_AST_identical':True,'years':years,'warning':'此证明只用于保留已审实际PNG与旧2025默认调用行为；明确不能迁移本批15旧MP4，全部重编码。'}
p=root/'专八/听力/批量/核验/考试图片时间基核验/默认关闭兼容与15年PNG不变证明.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('PASS',len(tests),'tests',len(years),'state/HTML/PNG unchanged years')
