"""仅迁移c87旧5篇默认192k精听成功缓存；不重编码/不渲染/不自动approval。
2015-A以及任何显式AAC配置永远不走此迁移。保留旧MP4和生成来源，复核新审批fp。
"""
from __future__ import annotations
import argparse,ast,copy,hashlib,importlib.util,json,os,re,shutil,stat,subprocess,sys,tempfile,types,zipfile
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('aac_cache_pub',HERE/'发布汇集.py');pub=importlib.util.module_from_spec(spec);spec.loader.exec_module(pub)
spec=importlib.util.spec_from_file_location('aac_cache_common',HERE/'迁移考试缓存.py');common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
need=common.need;MigrationError=common.MigrationError;ROOT=pub.ROOT;D=pub.D
sys.path.insert(0,str(HERE))
BASELINE='c87cf30777f324ceabde3a0eba6a1a7ecfd54451'
IDS=['2009-A','2009-B1','2009-B2','2024-A','2024-B1']
CORE={'专八/听力/批量/tools/精听.py':('ff515e1be152ea29844970bca368f64b1dbe1939bd8aeacb075157630aeecf26','cd766f44cf2075c49331992cb8a2598e48a708d85b2dd873486c494252d03da0'),'专八/听力/批量/tools/精听数据.py':('072c40ec95a6b532e798218d3be84eed68225608f53c1565f1c6c24895ba0d47','11b4ef9c00ef2bae834dcb54026d6905202e3e3c57ace801033b25b080d1bb3e')}
PROOF=D/'核验/AAC编码策略更新/默认44路径与真实参数正反例证明.json'
OLD_REGISTRY=D/'核验/AAC编码策略更新/旧审核登记.json'
CONTROL=ROOT/'.github/tem8-listening-intensive-aac-cache-migration.json'
def sha_bytes(x):return hashlib.sha256(x).hexdigest()
def git(*args):return subprocess.check_output(['git',*map(str,args)],cwd=ROOT)
def revision():return git('rev-parse','HEAD').decode().strip()
def asts(x):return ast.dump(x,include_attributes=False)
class Defaults(ast.NodeTransformer):
 def __init__(self):self.ifs=0;self.gets=0
 def visit_If(self,n):
  if ast.unparse(n.test)=="'aac_bitrate' in d['audio']":self.ifs+=1;return None
  return self.generic_visit(n)
 def visit_Call(self,n):
  if ast.unparse(n)=="tm.get('aac_bitrate', '192k')":self.gets+=1;return ast.copy_location(ast.Constant('192k'),n)
  return self.generic_visit(n)

def target(ident,d):
 need(ident in IDS and d['id']==ident,'只允许旧5篇，2015-A及其他单元绝不迁移')
 need('aac_bitrate' not in d['audio'],'显式AAC配置不属于旧默认缓存')

def validate_proof(expected_sha):
 need(common.hexsha(expected_sha) and pub.sha(PROOF)==expected_sha,'根最终复验proof SHA已变')
 p=pub.read(PROOF);need(p['status']=='minimal_core_default_44_semantics_and_argument_proof_passed_not_media_approval','默认路径证明未通过')
 need(p['old_commit']==BASELINE and all(p['module_AST_proof'].values()),'证明不是完整默认路径等价')
 need(len(p['default_units'])==44 and {r['id'] for r in p['default_units']}.issuperset(IDS),'44默认单位证明不完整')
 need(len(p['actual_production_argument_tests'])==8 and all(r['pass'] for r in p['actual_production_argument_tests']),'真实编码参数证据不完整')
 need(len(p['validation_positive_negative_tests'])==12 and all(r['pass'] for r in p['validation_positive_negative_tests']),'配置正反例证据不完整')
 for name,(old,new) in CORE.items():
  oldcode=common.old_blob(BASELINE,name);newcode=(ROOT/name).read_bytes();need(sha_bytes(oldcode)==old and sha_bytes(newcode)==new,'核心字节不在批准补丁范围')
  need(p['core_files'][name]=={'old_sha256':old,'new_sha256':new},'proof核心SHA不符')
  n=Defaults();normalized=n.visit(ast.parse(newcode));need(asts(normalized)==asts(ast.parse(oldcode)),'除默认兼容扩展外还有核心语义变化')
  need((n.ifs,n.gets)==((0,2) if name.endswith('/精听.py') else (2,0)),'核心扩展形状不是仅两参数/两显式分支')
 return p

def transition(old,current):
 need(old.get('status')=='approved' and old.get('shots'),'旧审批无成功全图')
 keys=['kind','id','inputs','render_sources','annotation_source'];need(old['payload_sha256']==pub.hash_json({k:old[k] for k in keys}),'旧审批payload不自洽')
 need(old['inputs']==current['inputs'] and old['annotation_source']==current['annotation_source'],'旧新输入/源语义已变')
 a,b=old['render_sources'],current['render_sources'];need(set(a)==set(b),'依赖集合变了')
 need({k for k in a if a[k]!=b[k]}==set(CORE),'除两核心以外依赖改变')
 need(all(a[k]==v[0] and b[k]==v[1] for k,v in CORE.items()),'核心旧新SHA不符')
 return old['payload_sha256'],pub.hash_json(current)

def load_core_pair():
 def module(name,text,path):
  m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m;exec(compile(text,str(path),'exec'),m.__dict__);return m
 datapath=HERE/'精听数据.py';corepath=HERE/'精听.py'
 olddata=module('aac_old_data',common.old_blob(BASELINE,pub.relative(datapath)),datapath)
 oldkey=sys.modules.get('精听数据');sys.modules['精听数据']=olddata
 try:oldcore=module('aac_old_core',common.old_blob(BASELINE,pub.relative(corepath)),corepath)
 finally:
  if oldkey is None:sys.modules.pop('精听数据',None)
  else:sys.modules['精听数据']=oldkey
 import 精听 as newcore
 return oldcore,newcore

def bitrate_argv(coretext,fn,env):
 f=next(n for n in ast.parse(coretext).body if isinstance(n,ast.FunctionDef) and n.name==fn)
 lists=[n for n in ast.walk(f) if isinstance(n,ast.List) and any(isinstance(e,ast.Constant) and e.value=='-b:a' for e in n.elts)]
 need(len(lists)==1,'实际AAC命令列表不唯一')
 return eval(compile(ast.Expression(lists[0]),'<actual-encoding-argv-from-frozen-code>','eval'),env)

def inspect(stage,ident,proof,proof_sha,current_registry=None):
 stage=Path(stage);d=pub.read(D/'精听数据'/f'{ident}.json');target(ident,d)
 baseline=common.old_blob(BASELINE,f'专八/听力/批量/精听数据/{ident}.json');need(sha_bytes(baseline)==pub.sha(D/'精听数据'/f'{ident}.json'),'输入不再与c87字节相同')
 rows=[r for r in proof['default_units'] if r['id']==ident];need(len(rows)==1 and rows[0]['input_sha256']==pub.sha(D/'精听数据'/f'{ident}.json') and rows[0]['aac_field_absent'],'根proof对此输入已过期')
 meta=pub.read(stage/'meta.json');fp=meta['approval_payload_sha256'];pub.validate_stage(stage,'intensive',ident,fp)
 oldrow=pub.read(stage/'evidence/审核登记.json');current=pub.payload('intensive',ident);transition(oldrow,current)
 saved=pub.read(OLD_REGISTRY)['entries']['intensive:'+ident];need(saved['payload_sha256']==fp and saved['inputs']==oldrow['inputs'] and saved['render_sources']==oldrow['render_sources'] and Counter(saved['shots'].values())==Counter(oldrow['shots'].values()),'cache不属于根保存的旧5登记')
 need(meta.get('source_commit') and meta.get('run_id'),'缺真实旧生成来源')
 for path,(old,new) in CORE.items():need(sha_bytes(common.old_blob(meta['source_commit'],path))==old,'实际生成提交不是c87等价旧核心')
 work=stage/'evidence/工作记录'
 required=['prepared.json','data/vocab.json','audio/timings.json','states.json','screens.json','approved-screens.json','audio-precheck.json','verification.json','meta.json']
 need(all('evidence/工作记录/'+n in meta['evidence'] for n in required),'旧完整编译/截图/原音/成品记录缺失')
 prepared=pub.read(work/'prepared.json');p=pub.read(work/'data/vocab.json')['passages'][0];tm=pub.read(work/'audio/timings.json')['cet4_male'][ident];states=pub.read(work/'states.json');screens=pub.read(work/'screens.json');approved=pub.read(work/'approved-screens.json');audio=pub.read(work/'audio-precheck.json');verification=pub.read(work/'verification.json');inner=pub.read(work/'meta.json')
 need(prepared['draft'] is False and prepared['input_sha256']==pub.sha(D/'精听数据'/f'{ident}.json'),'旧编译为草稿或输入不符')
 need('aac_bitrate' not in tm and tm.get('aac_bitrate','192k')=='192k','旧tm不是未配置192默认')
 need(prepared['source_sha256']==tm['source_sha256']==meta['source_sha256']==d['audio']['sha256'],'原音SHA不一致')
 need(prepared['audio_sha256']==tm['audio_sha256']==audio['audio_sha256'],'原样编译PCM摘要不一致')
 need(tm['window']==d['audio']['window'] and len(tm['sentences'])==len(d['sentences']),'源窗/句数改变')
 need(all(t['text']==s['en'] and t['read']==s['en'] and t['orig']==[s['start'],s['end']] for t,s in zip(tm['sentences'],d['sentences'])),'真实原句/原时刻不同')
 need(audio.get('ok') is True and audio.get('raw_exact_before_encoding') is True and audio['source_sha256']==tm['source_sha256'],'旧原音AAC预演未过')
 need(verification.get('ok') is True and verification.get('draft') is False and verification['sha256']==meta['mp4_sha256'],'旧成品核验未过')
 need(not screens['problems'] and screens['fingerprint']==approved['fingerprint']==verification['fingerprint']==inner['fingerprint'],'旧全图/审批/成品原始fingerprint不同')
 need(approved['screens_sha256']==pub.sha(work/'screens.json') and len(approved['review_note'].strip())>=10,'旧截图审批不真实')
 need(inner['kind']=='text' and inner['input_sha256']==prepared['input_sha256'] and inner['mp4_sha256']==meta['mp4_sha256'],'旧内层meta来源不一致')
 pngroot=stage/'evidence/已审截图';pngs={f.relative_to(pngroot).as_posix():pub.sha(f) for f in sorted(pngroot.rglob('*.png'))};need(pngs,'无真实PNG')
 common.require_png_multiset(pngs,oldrow['shots'],'旧PNG与旧registry不同')
 need({r['file']:r['sha256'] for r in screens['shots']}=={Path(k).name:v for k,v in pngs.items()},'实际PNG与screens逐图SHA不一致')
 if current_registry is not None:
  need(current_registry==pub.gate('intensive',ident),'当前registry无效');common.require_png_multiset(pngs,current_registry['shots'],'新审批PNG多重集改变')
 oldcore,newcore=load_core_pair()
 # 仅读取真实缓存数据；states切点使用实际word_alignment/parts，不伪造时间或生成音轨。
 with tempfile.TemporaryDirectory(prefix='tem8-default-aac-proof-') as td:
  runtime=Path(td)/'work';shutil.copytree(work,runtime)
  oldm=oldcore.engine(runtime);newm=newcore.engine(runtime)
  oldstates=oldcore.states(oldm,p,tm,runtime);newstates=newcore.states(newm,p,tm,runtime);need(oldstates==newstates==states,'旧新实际帧/分屏时刻不相同')
  oldhtml=oldm.screens(p);newhtml=newm.screens(p);need(oldhtml==newhtml and len(oldhtml)==len(states)==len(screens['shots']),'完整逐屏HTML/帧数量不同')
  # 当前真实输入按生产p字典表达式重建；词、中文、词注/标题均完整，不作替换。
  source=common.old_blob(BASELINE,pub.relative(HERE/'精听数据.py')).decode();fn=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef) and x.name=='compile_input');pe=next(x.value for x in fn.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='p' for t in x.targets));flat=[{k:copy.deepcopy(s[k]) for k in ['en','zh','w']} for s in d['sentences']];import 精听数据 as currentdata
  actualp=eval(compile(ast.Expression(pe),'<actual-p-expression>','eval'),{'d':d,'flat':flat,'TOKEN':currentdata.TOKEN});need(actualp==p,'缓存p不等于当前真实输入')
  need(oldm.video_name(p)==newm.video_name(p)==meta['label'],'成品中文标签路径变了')
  env={'out':runtime,'tm':tm,'encoded':runtime/'audio-precheck.m4a','listing':runtime/'concat.txt','mp4':runtime/meta['label'],'frames':round(tm['duration']*30),'FPS':30,'os':os}
  commands={}
  for function in ['audio_check','encode']:
   a=bitrate_argv(common.old_blob(BASELINE,pub.relative(HERE/'精听.py')).decode(),function,env);b=bitrate_argv((HERE/'精听.py').read_text(),function,env);need(a==b and a[a.index('-b:a')+1]=='192k','实际完整编码参数不再等价192');commands[function]={'old_argv':a,'new_argv':b,'identical':True}
  html=[{'screen':i+1,'label':r[0],'html_sha256':sha_bytes(r[1].encode()),'old_equals_new':True} for i,r in enumerate(oldhtml)]
  image_by_key={Path(k).stem:v for k,v in pngs.items()};need(set(k for _,k in states)==set(image_by_key),'states可达PNG与完整截图不同')
  perframe=[{'frame':f,'online_png_key':k,'png_sha256':image_by_key[k]} for f,k in states]
 result={'id':ident,'status':'old_successful_default192_cache_output_equivalence_checked_not_reencoded','old_payload_sha256':fp,'new_payload_sha256':pub.hash_json(current),'mp4_sha256':meta['mp4_sha256'],'mp4_bytes':meta['mp4_bytes'],'original_source_commit':meta['source_commit'],'original_run_id':meta['run_id'],'default_proof_sha256':proof_sha,'input_sha256':prepared['input_sha256'],'compiled_p_actual_old_equals_current':True,'compiled_p_sha256':pub.sha(work/'data/vocab.json'),'compiled_tm_sha256':pub.sha(work/'audio/timings.json'),'compiled_tm_new_equivalence_basis':'同输入/同源SHA，新增显式分支不执行，其余整模块AST归一后与c87相同；复用真实旧tm，不声称重新生成或估算时间。','aac_bitrate':'192k','real_states_exact_old_new_cached':True,'states_sha256':pub.sha(work/'states.json'),'complete_actual_html_old_new':html,'real_online_PNGs_sha_multiset':sorted(pngs.values()),'real_online_frames_and_PNGs':perframe,'actual_AAC_and_video_encoding_commands':commands,'commands_derived_from_actual_function_AST_not_executed':True,'old_reports_preserved_with_old_fingerprints':True,'current_registry_images_checked':current_registry is not None,'no_new_media_verification_claim':True}
 return result

def download(ident,fp,dest):
 rel=pub.release(pub.CACHE_TAG);assets={r['name']:r for r in rel['assets']};pairs=pub.cache_pairs(rel,'intensive',ident,fp);need(pairs,'旧精听cache无MP4/evidence配对');dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
 errors=[]
 for i,(v,e) in enumerate(pairs):
  try:
   sub=dest/str(i);sub.mkdir(exist_ok=True);pub.gh('release','download',pub.CACHE_TAG,'-R',common.REPOSITORY,'-p',v,'-p',e,'-D',sub,'--clobber')
   for n in [v,e]:need(assets[n].get('digest')=='sha256:'+pub.sha(sub/n) and assets[n]['size']==(sub/n).stat().st_size,'旧Release资产SHA/大小不符')
   with zipfile.ZipFile(sub/e) as z:need(z.testzip() is None and len(z.namelist())==len(set(z.namelist())) and not any(stat.S_ISLNK(x.external_attr>>16) for x in z.infolist()),'证据ZIP CRC/条目失败')
   stage=sub/'stage';pub.unpack_evidence(sub/e,stage);m=pub.read(stage/'meta.json');need(m['kind']=='intensive' and m['id']==ident and m['approval_payload_sha256']==fp,'旧下载meta错配');need(assets[v]['digest']=='sha256:'+m['mp4_sha256'],'旧MP4 digest不匹配');os.link(sub/v,stage/m['mp4']);pub.validate_stage(stage,'intensive',ident,fp)
   return stage,{'release':pub.CACHE_TAG,'MP4':v,'evidence':e,'video_server_digest':assets[v]['digest'],'evidence_zip_sha256':pub.sha(sub/e),'CRC_all':True}
  except (MigrationError,AssertionError,KeyError,zipfile.BadZipFile) as ex:errors.append(str(ex))
 raise MigrationError('旧cache未通过：'+str(errors[:3]))

def migrate(source,target_dir,ident,proof,proof_sha,current,download_record):
 result=inspect(source,ident,proof,proof_sha,current);source=Path(source);target_dir=Path(target_dir);old=pub.read(source/'meta.json');old_meta_bytes=(source/'meta.json').read_bytes();common.copy_stage(source,target_dir);extra=target_dir/'evidence/AAC默认兼容迁移';extra.mkdir(exist_ok=True)
 def replace(p,data):p=Path(p);p.unlink(missing_ok=True);p.write_bytes(data)
 (extra/'旧meta.json').write_bytes(old_meta_bytes);(extra/'旧审核登记.json').write_bytes((source/'evidence/审核登记.json').read_bytes());shutil.copyfile(PROOF,extra/'根默认44路径证明.json')
 result.update(revalidated_commit=revision(),revalidation_run_id=os.getenv('GITHUB_RUN_ID'),download=download_record)
 pub.dump(extra/'真实缓存等价核验.json',result);replace(target_dir/'evidence/审核登记.json',(json.dumps(current,ensure_ascii=False,indent=2)+'\n').encode())
 new=copy.deepcopy(old);new['approval_payload_sha256']=result['new_payload_sha256'];new['revalidated_commit']=revision();new['revalidation_run_id']=os.getenv('GITHUB_RUN_ID');new['current_registry']=current;new['approval_migration']={'schema':1,'type':'unchanged_default192_AAC_compatibility','default_proof_sha256':proof_sha,'old_payload_sha256':old['approval_payload_sha256'],'new_payload_sha256':result['new_payload_sha256'],'old_meta_sha256':sha_bytes(old_meta_bytes),'old_registry_path':'evidence/AAC默认兼容迁移/旧审核登记.json','reason':'此旧5输入无AAC字段，compiled p/tm/真实帧表/逐屏HTML/全部PNG/实际编码参数与默认192均不变；只迁移审批，不冒充重新渲染或新成品核验。','no_new_video_verification_claim':True}
 new['evidence']={p.relative_to(target_dir).as_posix():pub.sha(p) for p in sorted((target_dir/'evidence').rglob('*')) if p.is_file()};replace(target_dir/'meta.json',(json.dumps(new,ensure_ascii=False,indent=2)+'\n').encode())
 for n,h in old['evidence'].items():
  if n!='evidence/审核登记.json':need(pub.sha(target_dir/n)==h,'旧报告/可视数据/时刻/截图字节变化')
 need((source/'meta.json').read_bytes()==old_meta_bytes and pub.sha(target_dir/new['mp4'])==old['mp4_sha256'] and (target_dir/new['mp4']).stat().st_size==old['mp4_bytes'],'原meta或MP4字节变化')
 need(new['source_commit']==old['source_commit'] and new['run_id']==old['run_id'],'旧生成来源被改写');pub.validate_stage(target_dir,'intensive',ident,new['approval_payload_sha256']);return new,result

def control(path):
 c=pub.read(path);need(c.get('schema')==1 and c.get('status')=='approved','控制未根批准');need(c.get('branch')==common.branch_guard() and c.get('repository')==common.REPOSITORY and c.get('target_release')==pub.CACHE_TAG,'分支/仓库/目标Release错误')
 need(c.get('proof_file')==pub.relative(PROOF) and c.get('registry_sha256')==pub.sha(pub.REGISTRY) and c.get('old_registry_sha256')==pub.sha(OLD_REGISTRY),'控制所审证明/registry已变')
 ids=c.get('ids');need(isinstance(ids,list) and ids and len(ids)==len(set(ids)) and all(x in IDS for x in ids),'目标含2015-A/非旧5/重复')
 need(set(c.get('old_fingerprints',{}))==set(ids) and set(c.get('old_mp4_sha256',{}))==set(ids) and all(common.hexsha(v) for v in [*c['old_fingerprints'].values(),*c['old_mp4_sha256'].values()]),'控制未绑定旧成品SHA')
 need(len(c.get('evidence','').strip())>=10,'缺实际根审核说明');return c

def main():
 a=argparse.ArgumentParser(description=__doc__);s=a.add_subparsers(dest='command',required=True)
 p=s.add_parser('plan');p.add_argument('--id',choices=IDS,default='2009-A');p.add_argument('--proof-sha256',required=True);p.add_argument('--source',type=Path);p.add_argument('--out',type=Path,required=True)
 p=s.add_parser('run');p.add_argument('--control',type=Path,default=CONTROL);p.add_argument('--out',type=Path,required=True)
 a=a.parse_args();common.branch_guard();a.out.mkdir(exist_ok=True,parents=True)
 if a.command=='plan':
  proof=validate_proof(a.proof_sha256);ident=a.id;old=pub.read(OLD_REGISTRY)['entries']['intensive:'+ident]
  with tempfile.TemporaryDirectory(prefix='aac-default-plan-',dir=a.out) as td:
   stage,rec=(a.source,None) if a.source else download(ident,old['payload_sha256'],Path(td))
   current=None
   try:current=pub.gate('intensive',ident)
   except AssertionError:pass
   result=inspect(stage,ident,proof,a.proof_sha256,current);result['download']=rec;pub.dump(a.out/f'{ident}-真实默认缓存只读等价.json',result)
  print(ident,'只读等价通过；未批准/迁移/上传。')
 else:
  c=control(a.control);proof=validate_proof(c['proof_sha256']);frozen=[Path(__file__),a.control,PROOF,OLD_REGISTRY,pub.REGISTRY,*pub.dependencies('intensive'),*[p for i in c['ids'] for p in pub.input_paths('intensive',i)]];need(subprocess.run(['git','diff','--quiet','HEAD','--',*[pub.relative(p) for p in frozen]],cwd=ROOT).returncode==0,'相关源/控制未提交，不能伪记revalidated_commit');need(subprocess.run(['git','ls-files','--error-unmatch','--',pub.relative(a.control),pub.relative(PROOF),pub.relative(OLD_REGISTRY),pub.relative(pub.REGISTRY),pub.relative(Path(__file__))],cwd=ROOT,capture_output=True).returncode==0,'代码/控制/证明必须已提交')
  results=[]
  for ident in c['ids']:
   with tempfile.TemporaryDirectory(prefix='aac-default-'+ident+'-',dir=a.out) as td:
    source,rec=download(ident,c['old_fingerprints'][ident],Path(td)/'download');need(pub.read(source/'meta.json')['mp4_sha256']==c['old_mp4_sha256'][ident],'控制旧MP4 SHA与真实资产不符');current=pub.gate('intensive',ident);dest=Path(td)/'new';m,r=migrate(source,dest,ident,proof,c['proof_sha256'],current,rec);pub.store_stage(dest)
    assets={x['name']:x for x in pub.release(pub.CACHE_TAG)['assets']};v=pub.asset('intensive',ident,m['approval_payload_sha256'],m['mp4_sha256']);e=pub.cache_evidence('intensive',ident,m['approval_payload_sha256'],m['mp4_sha256']);need(assets[v]['digest']=='sha256:'+m['mp4_sha256'] and assets[v]['size']==m['mp4_bytes'] and assets[e]['digest']=='sha256:'+pub.sha(dest/e),'迁移后服务端SHA/大小不符')
    results.append({k:r[k] for k in ['id','old_payload_sha256','new_payload_sha256','mp4_sha256','mp4_bytes','original_source_commit','original_run_id']});results[-1].update(video_asset=v,evidence_asset=e,evidence_sha256=pub.sha(dest/e),revalidated_commit=revision());pub.dump(a.out/'迁移进行中.json',results)
  name='TEM8-intensive-default192-migration-'+pub.sha(a.control)[:16]+'.json';pub.dump(a.out/name,{'status':'old_five_default192_successful_caches_migrated_not_reencoded','proof_sha256':c['proof_sha256'],'control_sha256':pub.sha(a.control),'revalidated_commit':revision(),'results':results});pub.upload(pub.CACHE_TAG,a.out/name);print('旧默认192精听缓存迁移完成',len(results))
if __name__=='__main__':
 try:main()
 except (MigrationError,AssertionError,KeyError,FileNotFoundError) as e:raise SystemExit('拒绝迁移：'+str(e))
