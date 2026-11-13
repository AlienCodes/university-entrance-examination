"""当前真实输入上的结构/参数等价证明；不编码视频、不自动批准源或截图。"""
import ast,copy,hashlib,importlib.util,json,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5];B=ROOT/'专八/听力/批量';OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(B/'tools'))
import 精听数据 as newdata

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def hjson(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def tree(s):return ast.parse(s)
def same(a,b):return ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False)
class NormalizeDefault(ast.NodeTransformer):
 def __init__(self):self.optional_ifs=0;self.bitrates=0
 def visit_If(self,n):
  if ast.unparse(n.test)=="'aac_bitrate' in d['audio']":self.optional_ifs+=1;return None
  return self.generic_visit(n)
 def visit_Call(self,n):
  if ast.unparse(n)=="tm.get('aac_bitrate', '192k')":self.bitrates+=1;return ast.copy_location(ast.Constant('192k'),n)
  return self.generic_visit(n)

olddata=(OUT/'旧-精听数据.py.txt').read_text();oldcore=(OUT/'旧-精听.py.txt').read_text();newdatas=(B/'tools/精听数据.py').read_text();newcore=(B/'tools/精听.py').read_text()
n=NormalizeDefault();nd=n.visit(tree(newdatas));assert n.optional_ifs==2 and n.bitrates==0 and same(nd,tree(olddata))
n2=NormalizeDefault();nc=n2.visit(tree(newcore));assert n2.optional_ifs==0 and n2.bitrates==2 and same(nc,tree(oldcore))
old=types.ModuleType('aac_old_data_proof');old.__file__=str(B/'tools/精听数据.py');exec(compile(olddata,old.__file__,'exec'),old.__dict__)
# 检查真正生产编码列表中-b:a后面的表达式，不另写一个镜像selector。
expr=[]
for fn in tree(newcore).body:
 if isinstance(fn,ast.FunctionDef) and fn.name in ['audio_check','encode']:
  found=[]
  for x in ast.walk(fn):
   if isinstance(x,ast.List):
    for i,e in enumerate(x.elts[:-1]):
     if isinstance(e,ast.Constant) and e.value=='-b:a':found.append(x.elts[i+1])
  assert len(found)==1;expr.append((fn.name,found[0]))
assert len(expr)==2
params=[]
for name,e in expr:
 for config,want in [(None,'192k'),('192k','192k'),('256k','256k'),('320k','320k')]:
  tm={} if config is None else {'aac_bitrate':config};got=eval(compile(ast.Expression(e),'<actual-production-bitrate-arg>','eval'),{'tm':tm});assert got==want;params.append({'function':name,'explicit_input':config,'actual_argument':got,'pass':True})
base=json.loads((OUT/'2015-A-旧192源输入.json').read_text())
validation=[]
for config in ['192k','256k','320k',None,'128k','256','256K',256,0,True,[],{}]:
 d=copy.deepcopy(base);d['audio']['aac_bitrate']=config
 try:newdata.validate(d,True);accepted=True
 except (AssertionError,TypeError):accepted=False
 assert accepted==(config in ('192k','256k','320k'))
 validation.append({'config':config,'accepted':accepted,'expected':config in ('192k','256k','320k'),'pass':True})

def p_expression(text):
 fn=next(n for n in tree(text).body if isinstance(n,ast.FunctionDef) and n.name=='compile_input')
 return next(n.value for n in fn.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='p' for t in n.targets))
pe0,pe1=p_expression(olddata),p_expression(newdatas);assert same(pe0,pe1)
def passage(d,e):
 flat=[{k:copy.deepcopy(s[k]) for k in ['en','zh','w']} for s in d['sentences']]
 return eval(compile(ast.Expression(e),'<actual-p-dictionary>','eval'),{'d':d,'flat':flat,'TOKEN':newdata.TOKEN})
units=[];explicit=[]
for f in sorted((B/'精听数据').glob('20*.json')):
 d=json.loads(f.read_text());assert 'aac_bitrate' not in d or d['id']=='2015-A'
 p0,p1=passage(d,pe0),passage(d,pe1);assert p0==p1 and p0['title']==d['title']
 if 'aac_bitrate' in d['audio']:explicit.append({'id':d['id'],'rate':d['audio']['aac_bitrate'],'review_status':d.get('review',{}).get('status')});continue
 results=[]
 for mod in [old,newdata]:
  try:mod.validate(copy.deepcopy(d),False);results.append('accepted')
  except AssertionError as ex:results.append('blocked:'+str(ex))
 assert results[0]==results[1]
 units.append({'id':d['id'],'input_file':str(f.relative_to(B)),'input_sha256':sha(f),'aac_field_absent':True,'tm_optional_write_branch_not_entered':True,'effective_precheck_and_encode_bitrate':'192k','old_new_actual_p_dict_equal':True,'p_sha256':hjson(p0),'old_new_validation_identical':True,'current_source_gate':results[1]})
assert len(units)==44 and len(explicit)==1 and explicit[0]['id']=='2015-A' and explicit[0]['rate']=='256k'
assert explicit[0]['review_status'] in ['hold-encoding-policy','approved']
new2015=copy.deepcopy(json.loads((B/'精听数据/2015-A.json').read_text()));new2015['review']['status']='hold-encoding-policy'
try:newdata.validate(new2015,False);raise AssertionError('hold编码策略不应获正式通过')
except AssertionError as ex:assert '译注审校' in str(ex)
report={'status':'minimal_core_default_44_semantics_and_argument_proof_passed_not_media_approval','old_commit':'c87cf30777f324ceabde3a0eba6a1a7ecfd54451','core_files':{str((B/'tools'/n).relative_to(ROOT)):{'old_sha256':sha(OUT/('旧-'+n+'.txt')),'new_sha256':sha(B/'tools'/n)} for n in ['精听.py','精听数据.py']},'module_AST_proof':{'data_only_two_explicit_optional_ifs_added':True,'core_only_two_bitrate_arguments_changed':True,'after_removing_optional_branches_or_resolving_default192_entire_module_AST_identical_to_c87':True,'all_thresholds_raw_audio_processing_visual_layout_states_verify_functions_unchanged':True,'compiled_p_dict_expression_identical':True,'compiled_tm_base_expression_and_all_preexisting_writes_identical':True,'no_default_aac_metadata_added':True},'actual_production_argument_tests':params,'validation_positive_negative_tests':validation,'default_units':units,'explicit_exception':explicit,'2015_hold_blocks_formal_processing':True,'approval_limit':'默认44源没有AAC字段，所以新增两if完全不执行、两处实际FFmpeg参数仍为192k；p/tm/原样PCM/画面函数路径未变。内部代码依赖指纹会变，不等于PNG变化。仍须根显式刷新源/PNG审批；旧5cache迁移另核真实旧meta/MP4/evidence/PNG多重集并保留旧生成来源。此报告不虚称重编码/成品核验或自动批准。'}
(OUT/'默认44路径与真实参数正反例证明.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':report['status'],'defaults':len(units),'argument_cases':len(params),'validation_cases':len(validation),'source_hold':True,'core':report['core_files']},ensure_ascii=False))
