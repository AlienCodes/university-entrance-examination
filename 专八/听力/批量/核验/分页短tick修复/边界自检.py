import sys,types,json,hashlib,copy,ast,subprocess,tempfile,argparse
from pathlib import Path
root=Path(__file__).resolve().parents[5];path=root/'专八/听力/批量/tools/考试视频.py';before_commit='8d8e22cddc482112e7cc7c653c97b057cd27ff0a';before=subprocess.check_output(['git','show',before_commit+':专八/听力/批量/tools/考试视频.py'],cwd=root).decode();after=path.read_text();batch=path.parents[1];work=Path(tempfile.mkdtemp(prefix='tem8-tick-equivalence-'))
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def snapshot(module,L,total,T):
 fr=[(round((t+module.B.LEAD)*module.B.FPS),module.B.key(s)) for t,s in L]
 html=[{'frame':f,'state_sha256':digest(state),'html_sha256':hashlib.sha256(module.B.page(state).encode()).hexdigest(),'png_key':k} for (f,k),(t,state) in zip(fr,L)]
 ac={'total':total,'T':T,'nfr':round((total+module.B.LEAD)*module.B.FPS),'CUT_START':module.B.CUT_START,'CUT_END':module.B.CUT_END,'INSERTS':module.B.INSERTS,'ORIGINAL':module.B.ORIGINAL,'LEAD':module.B.LEAD,'FPS':module.B.FPS}
 return {'states_sha256':digest(L),'fr_sha256':digest(fr),'html_by_state':html,'png_keys_multiset':sorted(k for f,k in fr),'png_keys_unique':sorted(set(k for f,k in fr)),'audio_contract_sha256':digest(ac)}
def load(name,text):
 m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m;exec(compile(text,str(path),'exec'),m.__dict__);return m
old=load('tem8_tick_old',before);new=load('tem8_tick_new',after)
rows=[];removedyears=[]
for y in [2009,2010,2011,2012,2013,2014,2015,2016,2017,2018,2019,2021,2022,2023,2024]:
 old.configure(batch/'数据'/str(y),work/'before'/str(y));o,total0,T0=old.states()
 new.configure(batch/'数据'/str(y),work/'after'/str(y));n,total1,T1=new.states()
 of=[(round((t+old.B.LEAD)*old.B.FPS),old.B.key(s)) for t,s in o];nf=[(round((t+new.B.LEAD)*new.B.FPS),new.B.key(s)) for t,s in n]
 extra=[{'frame':f,'key':k,'state':o[i][1]} for i,(f,k) in enumerate(of) if (f,k) not in nf];missing=[r for r in nf if r not in of]
 assert not missing
 assert total0==total1 and T0==T1
 assert all({k:v for k,v in x.__dict__.items() if k in ['CUT_START','CUT_END','INSERTS','ORIGINAL','LEAD','FPS']}=={k:v for k,v in old.B.__dict__.items() if k in ['CUT_START','CUT_END','INSERTS','ORIGINAL','LEAD','FPS']} for x in [new.B])
 if extra:removedyears.append(y);assert len(extra)==1
 else:assert o==n and of==nf
 # All retained render HTML is identical; both modules use the same original path/font sources.
 oldhtml={s[0]:old.B.page(s[1]) for s in o};newhtml={s[0]:new.B.page(s[1]) for s in n};assert all(oldhtml[t]==h for t,h in newhtml.items())
 previous_total=round((total0+old.B.LEAD)*old.B.FPS);assert previous_total==round((total1+new.B.LEAD)*new.B.FPS)
 rows.append({'year':y,'old_states':len(o),'new_states':len(n),'removed':extra,'all_retained_frame_and_HTML_keys_identical':True,'original_page_flip_frame_preserved_in_state_plan':True,'PNG_key_set_removed':sorted(set(k for _,k in of)-set(k for _,k in nf)),'new_PNG_keys':sorted(set(k for _,k in nf)-set(k for _,k in of)),'audio_contract_equal':True,'old':snapshot(old,o,total0,T0),'new':snapshot(new,n,total1,T1),'safe_to_migrate':not extra,'source_inputs':{str((batch/'数据'/str(y)/name).relative_to(root)):hashlib.sha256((batch/'数据'/str(y)/name).read_bytes()).hexdigest() for name in ['试卷.json','时间轴.json']},'audio_contract_evidence':{'total':total1,'T':T1,'nfr':previous_total,'CUT_START':new.B.CUT_START,'CUT_END':new.B.CUT_END,'INSERTS':new.B.INSERTS,'ORIGINAL':new.B.ORIGINAL},'all_states_and_PNG_identical':not extra})
assert removedyears==[2010,2011,2016,2017,2019]
# Real old/new audio code is unchanged; only L is unused by audio sample assembly.
def funcs(text):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
a,b=funcs(before),funcs(after);assert [k for k in a if a[k]!=b[k]]==['states'];assert set(b)-set(a)=={'suppress_short_pagination_ticks'}
base={'kind':'sheet','page':0,'display_page':1,'display_pages':2,'st':'预览答题卡','cdl':'预览'}
def case(span=1,kind='sheet'):
 p={**base,'kind':kind,'cd':16};s={**base,'kind':kind,'cd':15};z={**base,'kind':kind,'page':1,'display_page':2,'cd':15};return [(0,p),(1,s),(1+span/30,z)]
tests=[]
def expect(name,raw,removed=None,raises=False):
 try:
  kept,rm=new.suppress_short_pagination_ticks(raw)
  assert not raises and len(rm)==removed
  tests.append({'name':name,'pass':True,'removed':len(rm)})
 except ValueError:
  assert raises;tests.append({'name':name,'pass':True,'rejected':True})
expect('1帧冗余旧页tick',case(1),1);expect('2帧冗余旧页tick',case(2),1);expect('3帧保留',case(3),0);expect('0帧明确拒绝',case(0),raises=True)
expect('单题绝不删除',case(1,'q'),0);expect('说明绝不删除',case(1,'instr'),0)
x=case();x[0][1]['st']='别的内容';expect('前态内容不同保留',x,0)
x=case();x[2][1]['cd']=14;expect('下一页倒计时不同保留',x,0)
x=case();x[2][1]['display_page']=1;expect('没有真正翻页保留',x,0)
x=case();x[2][1]['st']='新说明';expect('下一逻辑段内容不同保留',x,0)
x=case();x[1][1].update(kind='plist',group='part1',numbers=[1,2]);x[0][1].update(kind='plist',group='part1',numbers=[1,2]);x[2][1].update(kind='plist',group='part2',numbers=[3,4]);expect('不同采访group保留',x,0)
x=case();x[0][1]['cd']=18;expect('非连续倒计时保留',x,0)
function_equivalence=[]
for module_name,old_text,new_text,names in [('adapter',before,after,[k for k in a if k!='states']),('shared_base',subprocess.check_output(['git','show',before_commit+':专八/听力/tools/听力视频.py'],cwd=root).decode(),(root/'专八/听力/tools/听力视频.py').read_text(),['audio_track','decoded','orig_match','audio_check','video','verify','key'])]:
 old_f,new_f=funcs(old_text),funcs(new_text)
 for name in names:
  os=hashlib.sha256(old_f[name].encode()).hexdigest();ns=hashlib.sha256(new_f[name].encode()).hexdigest();assert os==ns
  function_equivalence.append({'module':module_name,'name':name,'old_ast_sha256':os,'new_ast_sha256':ns})
for row in rows:
 for file,h in row['source_inputs'].items():assert hashlib.sha256(subprocess.check_output(['git','show',before_commit+':'+file],cwd=root)).hexdigest()==h
 if row['safe_to_migrate']:assert row['old']==row['new']
report={'schema_version':2,'before_commit':before_commit,'allowed_migration_years':[r['year'] for r in rows if r['safe_to_migrate']],'forbidden_migration_years':removedyears,'function_equivalence':function_equivalence,'old_sha256':hashlib.sha256(before.encode()).hexdigest(),'new_sha256':hashlib.sha256(after.encode()).hexdigest(),'changed_functions':['states'],'new_pure_function':'suppress_short_pagination_ticks','only_changed_years':removedyears,'unchanged_years':[r['year'] for r in rows if r['all_states_and_PNG_identical']],'audio_proof_scope':'audio_track与所有音频源/增益/窗/总帧数/采样率声道代码未改；15年T/total/CUT_START/CUT_END/INSERTS/ORIGINAL相同，因此同源样本拼接契约一致。未声称重新逐字节生成全部15条音轨。','tests':tests,'years':rows,'concat_quantization_limitation':'底座PNG输入默认25fps转30fps，派生页切点实际解码可能±1帧。真实2017局部编码前后逐帧证据单列；不声称两版编码MP4或5年受影响边界逐帧相同。'}
out=batch/'核验/分页短tick修复';out.mkdir(parents=True,exist_ok=True);(out/'15年状态与PNG等价证明.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['old_sha256','new_sha256','only_changed_years','unchanged_years','tests']},ensure_ascii=False,indent=2))
