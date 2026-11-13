"""仅迁移已通过、输出等价的十年考试缓存；不渲染、不重编码、不改MP4。

plan只输出待根审核的新候选，不写审核登记。run须专用控制文件、当前有效新审批和冻结证据。
旧报告/来源/生成commit/run保持真实；仅固定registry入口更新，新证据另存旧registry/meta。
"""
from __future__ import annotations
import argparse, ast, copy, hashlib, importlib.util, json, os, re, shutil, stat, subprocess, tempfile, zipfile
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('tem8_migration_pub',HERE/'发布汇集.py');pub=importlib.util.module_from_spec(spec);spec.loader.exec_module(pub)
ROOT=pub.ROOT; D=pub.D
ADAPTER='专八/听力/批量/tools/考试视频.py'; BASE='专八/听力/tools/听力视频.py'
BRANCH='codex/tem8-listening-2009-2024'; REPOSITORY='AlienCodes/university-entrance-examination'
CERTIFICATE=D/'核验/分页短tick修复/15年状态与PNG等价证明.json'
CERT_SHA='37a1cb1b0018e2083b47e2df9c6ffba0ddd3097383c98fb31a256f0cd222bbc9'
OLD_SHA='941779b0e8272331cd89ee1525c4c88c1d0a8711d01e648acee4424382e22ea8'
NEW_SHA='c8c62c657171c13ed67b839d2389e1a44cecf7b1d1343ea92ffa62dca2849c3c'
BEFORE='8d8e22cddc482112e7cc7c653c97b057cd27ff0a'
ALLOWED=[2009,2012,2013,2014,2015,2018,2021,2022,2023,2024]
FORBIDDEN=[2010,2011,2016,2017,2019]
CONTROL=ROOT/'.github/tem8-listening-exam-cache-migration.json'
ROOT_REVIEW=D/'核验/分页短tick修复/root-登记刷新.json'
OLD_REGISTRIES=D/'核验/分页短tick修复/旧登记'
class MigrationError(ValueError):pass
def need(ok,message):
 if not ok:raise MigrationError(message)
def digest_bytes(b):return hashlib.sha256(b).hexdigest()
def hexsha(v):return isinstance(v,str) and re.fullmatch('[a-f0-9]{64}',v) is not None
def git(*args):return subprocess.check_output(['git',*map(str,args)],cwd=ROOT)
def old_blob(commit,path):
 need(re.fullmatch('[a-f0-9]{40}',commit) is not None,'无效Git commit')
 return git('show',commit+':'+path)
def functions(raw):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(raw).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
def revision():return git('rev-parse','HEAD').decode().strip()
def branch_guard():
 branch=os.getenv('GITHUB_REF_NAME') or git('branch','--show-current').decode().strip()
 need(branch==BRANCH,'只允许已审工作分支执行迁移')
 need(os.getenv('GITHUB_REPOSITORY',REPOSITORY)==REPOSITORY and pub.REPO==REPOSITORY,'仓库不匹配')
 if os.getenv('GITHUB_SHA'):need(os.environ['GITHUB_SHA']==revision(),'checkout提交与触发提交不一致')
 return branch

def validate_year_certificate(cert,year,current_inputs):
 need(year in ALLOWED and year not in FORBIDDEN,'受影响五年或非许可年份绝不迁移')
 found=[r for r in cert['years'] if r['year']==year];need(len(found)==1,'年度证据缺失/重复');r=found[0]
 need(r.get('safe_to_migrate') is True and r.get('all_states_and_PNG_identical') is True,'本年不安全')
 need(not r.get('removed') and not r.get('PNG_key_set_removed') and not r.get('new_PNG_keys'),'本年有状态/图片变化')
 need(r.get('audio_contract_equal') is True and r['old']==r['new'],'状态/帧/HTML/图片/音频契约不完全等价')
 data=r['old'];need(all(hexsha(data.get(k)) for k in ['states_sha256','fr_sha256','audio_contract_sha256']),'证据摘要缺失')
 html=data.get('html_by_state');need(isinstance(html,list) and bool(html),'缺完整逐state HTML证据')
 frames=[x['frame'] for x in html];need(frames[0]==0 and all(isinstance(x,int) and x>=0 for x in frames) and frames==sorted(set(frames)),'证据帧序列不合法')
 need(len(html)==r['old_states']==r['new_states'],'证据状态数量不符')
 need(all(hexsha(x.get('state_sha256')) and hexsha(x.get('html_sha256')) and re.fullmatch('[a-f0-9]{12}',x.get('png_key','')) for x in html),'不完整state/HTML/PNG key')
 need(data['png_keys_multiset']==sorted(x['png_key'] for x in html),'PNG key多重集不符')
 need(data['png_keys_unique']==sorted(set(data['png_keys_multiset'])),'PNG key唯一集不符')
 need(data['fr_sha256']==pub.hash_json([[x['frame'],x['png_key']] for x in html]),'帧表摘要不符')
 ac={**r['audio_contract_evidence'],'LEAD':1.5,'FPS':30}
 need(data['audio_contract_sha256']==pub.hash_json(ac),'音频调用/T/总帧数契约摘要不符')
 need(ac['ORIGINAL'] is True and ac['CUT_END'] is None and ac['INSERTS']==[] and ac['nfr']>frames[-1],'不是不变原声音频契约')
 need(ac['nfr']==round((ac['total']+1.5)*30) and ac['T']['trim_start']==ac['CUT_START'] and abs(ac['T']['source_duration']-ac['CUT_START']-ac['T']['audioEnd'])<1e-8,'总帧/时长/剪头契约自相矛盾')
 required={f'专八/听力/批量/数据/{year}/'+name for name in ['试卷.json','时间轴.json']}
 need(set(r['source_inputs'])==required,'年度输入证据集合不符')
 need(all(current_inputs.get(p)==s for p,s in r['source_inputs'].items()),'证据已过期：年度input SHA变化')
 return r

def validate_certificate(path=CERTIFICATE,expected_sha=CERT_SHA):
 path=Path(path);need(path.resolve()==CERTIFICATE.resolve(),'不允许替换冻结证据路径')
 need(expected_sha==CERT_SHA and pub.sha(path)==expected_sha,'冻结certificate SHA已变')
 c=pub.read(path)
 need(c.get('schema_version')==2 and c.get('before_commit')==BEFORE,'certificate版本/旧提交不符')
 need(c.get('old_sha256')==OLD_SHA and c.get('new_sha256')==NEW_SHA,'旧新adapter证据不符')
 need(c.get('allowed_migration_years')==ALLOWED and c.get('forbidden_migration_years')==FORBIDDEN,'许可/禁迁移范围变化')
 need(c.get('unchanged_years')==ALLOWED and c.get('only_changed_years')==FORBIDDEN,'等价分组不一致')
 need(sorted(r['year'] for r in c['years'])==sorted(pub.YEARS),'证据不是完整15年')
 need(c.get('changed_functions')==['states'] and c.get('new_pure_function')=='suppress_short_pagination_ticks','修改范围超出短tick修复')
 need(subprocess.run(['git','merge-base','--is-ancestor',BEFORE,'HEAD'],cwd=ROOT).returncode==0,'旧证据提交不在当前历史')
 old=old_blob(BEFORE,ADAPTER);new=(ROOT/ADAPTER).read_bytes()
 need(digest_bytes(old)==OLD_SHA and digest_bytes(new)==NEW_SHA,'证据已过期：当前/旧adapter不是冻结字节')
 oldf,newf=functions(old),functions(new)
 need(set(newf)-set(oldf)=={'suppress_short_pagination_ticks'} and set(oldf)-set(newf)==set(),'新增/删除函数超范围')
 need([n for n in oldf if oldf[n]!=newf[n]]==['states'],'除states还有函数改变')
 bases=[old_blob(BEFORE,BASE),(ROOT/BASE).read_bytes()];bf=[functions(x) for x in bases]
 required={('adapter',n) for n in oldf if n!='states'}|{('shared_base',n) for n in ['audio_track','decoded','orig_match','audio_check','video','verify','key']}
 fs=c['function_equivalence'];need(len(fs)==len(required) and {(x['module'],x['name']) for x in fs}==required,'函数AST证据不完整/重复')
 for x in fs:
  a,b=(oldf,newf) if x['module']=='adapter' else bf
  h1,h2=digest_bytes(a[x['name']].encode()),digest_bytes(b[x['name']].encode())
  need(h1==h2==x['old_ast_sha256']==x['new_ast_sha256'],'音频/编码/核验/HTML函数AST不等价')
 for y in ALLOWED:
  current=pub.payload('exam',str(y))['inputs'];validate_year_certificate(c,y,current)
 return c

def payload_transition(old_row,new_payload,cert):
 old_fp=old_row['payload_sha256'];need(old_row.get('status')=='approved' and old_row.get('shots'),'旧审批未通过/缺截图')
 need(old_fp==pub.hash_json({k:old_row[k] for k in ['kind','id','inputs','render_sources']}),'旧审批payload自洽失败')
 need(old_row['inputs']==new_payload['inputs'],'当前输入SHA与旧成品不同')
 before,after=old_row['render_sources'],new_payload['render_sources']
 need(set(before)==set(after),'渲染依赖集合发生变化')
 diffs={k for k in before if before[k]!=after[k]}
 need(diffs=={ADAPTER},'仅允许考试adapter一个依赖变化')
 need(before[ADAPTER]==cert['old_sha256'] and after[ADAPTER]==cert['new_sha256'],'adapter旧新SHA不在冻结证据')
 return old_fp,pub.hash_json(new_payload)

def validate_success_reports(layout,final,fingerprints,video_sha):
 need(layout.get('sample') is False and layout.get('draft') is False and layout.get('problems')==[],'旧排版报告失败/样片/草稿')
 need(final.get('问题')==[] and final.get('原音模式') is True and final.get('成品sha256')==video_sha,'旧成品报告未通过')
 need(layout.get('source_fingerprints')==final.get('source_fingerprints')==fingerprints,'旧报告真实来源指纹不符')

def actual_pngs(stage):
 base=Path(stage)/'evidence/已审截图'
 paths=sorted(base.rglob('*.png'));need(bool(paths),'旧stage缺实际PNG')
 need(all(p.is_file() and p.resolve().is_relative_to(base.resolve()) for p in paths),'PNG路径越界')
 data={p.relative_to(base).as_posix():pub.sha(p) for p in paths}
 keys={p.stem:pub.sha(p) for p in paths};need(len(keys)==len(paths),'PNG key冲突')
 need(all(re.fullmatch('[a-f0-9]{12}',k) for k in keys),'旧PNG key不是实际HTML key')
 return data,keys

def inspect_stage(stage,year,cert,current_payload,new_registry=None):
 stage=Path(stage);meta=pub.read(stage/'meta.json');old_fp=meta['approval_payload_sha256']
 # 此调用保留原生产验证，不以迁移证明豁免失败成品或来源核验。
 pub.validate_stage(stage,'exam',str(year),old_fp)
 old_registry=pub.read(stage/'evidence/审核登记.json')
 need(old_registry['payload_sha256']==old_fp,'旧registry与meta不符')
 payload_transition(old_registry,current_payload,cert)
 row=validate_year_certificate(cert,year,current_payload['inputs'])
 need(meta.get('source_commit') and meta.get('run_id'),'旧生成commit/run_id缺失')
 need(digest_bytes(old_blob(meta['source_commit'],ADAPTER))==OLD_SHA,'旧成品生成提交不是冻结旧adapter')
 root=stage/'evidence/工作记录'
 framefile=root/'帧表.json';need(framefile.is_file() and 'evidence/工作记录/帧表.json' in meta['evidence'],'旧成品缺真实帧表归档')
 fr=pub.read(framefile);need(isinstance(fr,list) and fr,'真实帧表为空')
 need(all(isinstance(x,list) and len(x)==2 and isinstance(x[0],int) and isinstance(x[1],str) for x in fr),'真实帧表格式不符')
 frames=[x[0] for x in fr];expected=[x['frame'] for x in row['old']['html_by_state']]
 need(frames==expected,'真实帧表帧号与冻结证据不相同')
 pngs,keys=actual_pngs(stage)
 need(Counter(pngs.values())==Counter(old_registry['shots'].values()),'旧实际PNG与旧已审多重集不同')
 need(set(k for _,k in fr)==set(keys),'真实帧表可达PNG集合与实际完整截图不同')
 if new_registry is not None:
  need(new_registry.get('status')=='approved' and new_registry.get('shots'),'当前审批未批准完整截图')
  need(Counter(new_registry['shots'].values())==Counter(pngs.values()),'旧/新实际PNG多重集不一致')
 fps={'paper':old_registry['inputs'][f'专八/听力/批量/数据/{year}/试卷.json'],'timeline':old_registry['inputs'][f'专八/听力/批量/数据/{year}/时间轴.json'],'adapter':OLD_SHA,'base':old_registry['render_sources'][BASE]}
 required_reports={'核验/排版核验.json','核验/核查报告.json'}
 for name in required_reports:
  need('evidence/工作记录/'+name in meta['evidence'],'必要成功报告未列入原evidence')
  r=pub.read(root/name);need(r.get('source_fingerprints')==fps,'旧报告真实来源指纹不符')
 layout=pub.read(root/'核验/排版核验.json');final=pub.read(root/'核验/核查报告.json');validate_success_reports(layout,final,fps,meta['mp4_sha256'])
 timing=pub.read(root/'核验/画面时间轴核验.json');ac=row['audio_contract_evidence']
 need(timing['frame_count']==ac['nfr'] and timing['events']==len(fr),'旧总帧/状态数与证据不符')
 need(timing['source_duration']==ac['T']['source_duration'] and timing['trim_start']==ac['CUT_START'],'原音时长/剪头契约改变')
 if '画面状态' in final:need(final['画面状态']==len(fr),'成品报告状态数不符')
 # 不拿local key冒充runner key；仅按真实frame逐个配对，保留全部在线key和实际PNG字节。
 pairings=[{'frame':f,'online_png_key':k,'online_png_sha256':keys[k],'state_sha256':e['state_sha256'],'html_sha256_old_equals_new':e['html_sha256']} for (f,k),e in zip(fr,row['old']['html_by_state'])]
 return {'year':year,'old_payload_sha256':old_fp,'new_payload_sha256':pub.hash_json(current_payload),'mp4_sha256':meta['mp4_sha256'],'mp4_bytes':meta['mp4_bytes'],'source_commit':meta['source_commit'],'run_id':meta['run_id'],'certificate_sha256':CERT_SHA,'true_frame_table_sha256':pub.sha(framefile),'true_online_png_sha_multiset':sorted(pngs.values()),'true_online_per_frame_png_sha_multiset':sorted(keys[k] for _,k in fr),'frame_pairings':pairings,'checks':{'old_pub_validate_stage':True,'inputs_identical':True,'only_frozen_adapter_changed':True,'certificate_old_new_states_fr_all_HTML_audio_equal':True,'actual_online_frame_numbers_match_certificate':True,'all_actual_PNG_match_old_registry':True,'all_actual_PNG_match_current_registry':new_registry is not None,'old_reports_success_and_original_fingerprints_preserved':True},'proof_scope':'不重新编码/伪称新视频verify；复用已通过成品，冻结证明保证本年输出不变，原source_commit/run_id和旧报告来源保持真实。'}

def migration_context(proof):return {k:proof[k] for k in ['certificate_sha256','old_payload_sha256','mp4_sha256']}
def validate_current_registry(year,proof):
 r=pub.gate('exam',str(year));need(r['payload_sha256']==proof['new_payload_sha256'],'当前gate指纹不符')
 review=pub.read(ROOT_REVIEW);need(review.get('status')=='approved' and review.get('certificate')==pub.relative(CERTIFICATE),'缺根实际登记刷新批准')
 rows=[x for x in review['records'] if x['id']==str(year)];need(len(rows)==1,'根批准年度不唯一');x=rows[0]
 need(x['old_payload_sha256']==proof['old_payload_sha256'] and x['new_payload_sha256']==proof['new_payload_sha256'] and x['certificate_sha256']==CERT_SHA,'根批准指纹/证据不匹配')
 need(x['changed_render_sources']==[ADAPTER] and x['must_reencode'] is False and not x['removed_shots'] and x['new_image_bytes_approved'] is False,'根登记不允许本年等价缓存迁移')
 need(x['previous_shots']==x['current_shots']==len(r['shots']),'根批准截图数量不一致')
 return r

def old_registry_entry(path,year):
 path=Path(path);row=pub.read(path/f'{year}.json' if path.is_dir() else path)
 return row['entries']['exam:'+str(year)] if 'entries' in row else row

def download_old(year,fp,dest):
 need(hexsha(fp),'旧fingerprint不合法');dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
 rel=pub.release(pub.CACHE_TAG);assets={a['name']:a for a in rel['assets']};pairs=pub.cache_pairs(rel,'exam',str(year),fp)
 need(pairs,'持久cache无该旧指纹的MP4/evidence配对');errors=[]
 for index,(video,ev) in enumerate(pairs):
  sub=dest/str(index);sub.mkdir(exist_ok=True)
  try:
   pub.gh('release','download',pub.CACHE_TAG,'-R',REPOSITORY,'-p',ev,'-p',video,'-D',sub,'--clobber')
   for n in [video,ev]:need(assets[n].get('digest')=='sha256:'+pub.sha(sub/n) and assets[n]['size']==(sub/n).stat().st_size,'Release资产digest/size不符')
   with zipfile.ZipFile(sub/ev) as z:
    names=z.namelist();need(len(names)==len(set(names)) and z.testzip() is None,'证据ZIP重复项/CRC失败')
    need(not any(stat.S_ISLNK(x.external_attr>>16) for x in z.infolist()),'证据ZIP含符号链接')
   stage=sub/'stage';pub.unpack_evidence(sub/ev,stage);m=pub.read(stage/'meta.json')
   need(m['kind']=='exam' and m['id']==str(year) and m['approval_payload_sha256']==fp,'下载cache meta不匹配')
   need(assets[video]['digest']=='sha256:'+m['mp4_sha256'] and assets[video]['size']==m['mp4_bytes'],'原MP4远端SHA不符')
   os.link(sub/video,stage/m['mp4']);pub.validate_stage(stage,'exam',str(year),fp)
   return stage,{'release':pub.CACHE_TAG,'video_asset':video,'evidence_asset':ev,'video_server_digest':assets[video]['digest'],'evidence_zip_sha256':pub.sha(sub/ev),'evidence_zip_crc_all':True}
  except (MigrationError,AssertionError,KeyError,ValueError,zipfile.BadZipFile) as ex:errors.append(str(ex))
 raise MigrationError('所有旧cache配对均未通过：'+str(errors[:3]))

def copy_stage(source,target):
 need(not Path(target).exists(),'目标stage已存在，拒绝覆盖')
 def link_or_copy(a,b):
  try:os.link(a,b)
  except OSError:shutil.copyfile(a,b)
 shutil.copytree(source,target,copy_function=link_or_copy)

def migrate(source,target,year,cert,current_registry,download_record=None):
 payload=pub.payload('exam',str(year));proof=inspect_stage(source,year,cert,payload,current_registry)
 need(current_registry==validate_current_registry(year,proof),'调用者审批与当前registry不同')
 source=Path(source);target=Path(target);old=pub.read(source/'meta.json');oldbytes=(source/'meta.json').read_bytes()
 copy_stage(source,target);extra=target/'evidence/审批迁移';extra.mkdir(exist_ok=True)
 # copytree会硬链，因此替换registry/meta前先unlink，绝不能改写旧stage的inode。
 def replace_bytes(path,data):
  p=Path(path);p.unlink(missing_ok=True);p.write_bytes(data)
 (extra/'旧meta.json').write_bytes(oldbytes)
 (extra/'旧审核登记.json').write_bytes((source/'evidence/审核登记.json').read_bytes())
 shutil.copyfile(CERTIFICATE,extra/'冻结等价证明.json')
 shutil.copyfile(ROOT_REVIEW,extra/'根登记刷新批准.json')
 replace_bytes(target/'evidence/审核登记.json',(json.dumps(current_registry,ensure_ascii=False,indent=2)+'\n').encode())
 proof.update(status='approval_migration_revalidated_not_rerendered',revalidated_commit=revision(),revalidation_run_id=os.getenv('GITHUB_RUN_ID'),download=download_record)
 pub.dump(extra/'迁移核验.json',proof)
 meta=copy.deepcopy(old);meta['approval_payload_sha256']=proof['new_payload_sha256'];meta['revalidated_commit']=revision();meta['revalidation_run_id']=os.getenv('GITHUB_RUN_ID');meta['current_registry']=current_registry
 meta['approval_migration']={**migration_context(proof),'schema':1,'new_payload_sha256':proof['new_payload_sha256'],'old_meta_sha256':digest_bytes(oldbytes),'old_registry_path':'evidence/审批迁移/旧审核登记.json','current_registry_path':'evidence/审核登记.json','certificate_path':'evidence/审批迁移/冻结等价证明.json','root_review_path':'evidence/审批迁移/根登记刷新批准.json','root_review_sha256':pub.sha(ROOT_REVIEW),'report_path':'evidence/审批迁移/迁移核验.json','reason':'该年states/帧表/逐state HTML/音轨与编码函数完全等价；保留原MP4字节及生成来源，仅迁移审批指纹。','no_new_video_verification_claim':True}
 meta['evidence']={p.relative_to(target).as_posix():pub.sha(p) for p in sorted((target/'evidence').rglob('*')) if p.is_file()}
 replace_bytes(target/'meta.json',(json.dumps(meta,ensure_ascii=False,indent=2)+'\n').encode())
 for name,h in old['evidence'].items():
  if name!='evidence/审核登记.json':need(pub.sha(target/name)==h,'旧机械报告/截图/来源字节改变')
 need((source/'meta.json').read_bytes()==oldbytes and pub.sha(target/meta['mp4'])==old['mp4_sha256'] and (target/meta['mp4']).stat().st_size==old['mp4_bytes'],'源stage或MP4字节改变')
 pub.validate_stage(target,'exam',str(year),proof['new_payload_sha256'])
 need(Counter(actual_pngs(source)[0].values())==Counter(actual_pngs(target)[0].values()),'复制后PNG多重集改变')
 return meta,proof

def load_control(path=CONTROL):
 c=pub.read(path);need(c.get('schema')==1 and c.get('status')=='approved','迁移control未批准')
 need(c.get('branch')==branch_guard() and c.get('repository')==REPOSITORY,'control仓库/分支不符')
 need(c.get('target_release')==pub.CACHE_TAG,'只准写持久缓存Release')
 need(c.get('certificate_sha256')==CERT_SHA and c.get('certificate')==pub.relative(CERTIFICATE),'control证据过期')
 need(c.get('registry_sha256')==pub.sha(pub.REGISTRY),'control所审registry已变')
 need(c.get('root_review_sha256')==pub.sha(ROOT_REVIEW),'control所审根等价迁移批准已变')
 need(isinstance(c.get('evidence'),str) and len(c['evidence'].strip())>=10,'control无根实际审核说明')
 years=c.get('years');need(isinstance(years,list) and years and len(years)==len(set(years)) and all(y in ALLOWED for y in years),'control年份非法/重复/含受影响年')
 need(set(c.get('old_fingerprints',{}))=={str(y) for y in years},'control旧指纹未逐年固定')
 need(set(c.get('old_mp4_sha256',{}))=={str(y) for y in years},'control旧MP4 SHA未逐年固定')
 need(all(hexsha(v) for v in [*c['old_fingerprints'].values(),*c['old_mp4_sha256'].values()]),'control SHA不合法')
 return c

def main():
 ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
 p=sub.add_parser('plan');p.add_argument('--years',type=int,nargs='+',default=ALLOWED);p.add_argument('--old-registry',type=Path,default=OLD_REGISTRIES);p.add_argument('--source',type=Path);p.add_argument('--out',type=Path,required=True)
 p=sub.add_parser('run');p.add_argument('--control',type=Path,default=CONTROL);p.add_argument('--out',type=Path,required=True)
 a=ap.parse_args();branch_guard();cert=validate_certificate();a.out.mkdir(parents=True,exist_ok=True)
 if a.command=='plan':
  need(len(a.years)==len(set(a.years)) and all(y in ALLOWED for y in a.years),'plan含禁迁移年/重复')
  need(a.source is None or len(a.years)==1,'--source只对应一个年份');results=[]
  for year in a.years:
   with tempfile.TemporaryDirectory(prefix='tem8migration-plan-',dir=a.out) as td:
    if a.source:stage,download=a.source,None
    else:stage,download=download_old(year,old_registry_entry(a.old_registry,year)['payload_sha256'],Path(td))
    payload=pub.payload('exam',str(year));proof=inspect_stage(stage,year,cert,payload)
    current=validate_current_registry(year,proof);proof=inspect_stage(stage,year,cert,payload,current)
    candidate=pub.candidate('exam',str(year));candidate['shots']=pub.read(stage/'evidence/审核登记.json')['shots'];candidate['approval_migration']=migration_context(proof);candidate['evidence']='待根实际审查：冻结等价证据、原成品成功报告、逐帧与PNG字节完全等价后填写批准说明。'
    pub.dump(a.out/f'exam-{year}-待批准候选.json',candidate);pub.dump(a.out/f'exam-{year}-只读迁移核验.json',{**proof,'download':download,'status':'ready_for_root_registry_approval_not_migrated'})
    results.append({k:proof[k] for k in ['year','old_payload_sha256','new_payload_sha256','mp4_sha256','mp4_bytes','source_commit','run_id']})
  pub.dump(a.out/'待根审批迁移汇总.json',{'status':'pending_root_approval_no_control_created','certificate_sha256':CERT_SHA,'years':results});print('只读plan通过',len(results),'年；未批准/迁移/上传。')
 else:
  c=load_control(a.control);results=[]
  frozen=[Path(__file__),a.control,CERTIFICATE,ROOT_REVIEW,pub.REGISTRY,*pub.dependencies('exam'),*[p for y in c['years'] for p in pub.input_paths('exam',str(y))]]
  need(subprocess.run(['git','diff','--quiet','HEAD','--',*[pub.relative(p) for p in frozen]],cwd=ROOT).returncode==0,'run拒绝未提交的源/审批/控制文件，revalidated_commit必须真实对应当前字节')
  need(subprocess.run(['git','ls-files','--error-unmatch','--',*[pub.relative(p) for p in [Path(__file__),a.control,CERTIFICATE,ROOT_REVIEW,pub.REGISTRY]]],cwd=ROOT,capture_output=True).returncode==0,'run要求迁移代码/控制/证据/registry均已提交')
  for year in c['years']:
   with tempfile.TemporaryDirectory(prefix=f'tem8migration-{year}-',dir=a.out) as td:
    source,download=download_old(year,c['old_fingerprints'][str(year)],Path(td)/'download');need(pub.read(source/'meta.json')['mp4_sha256']==c['old_mp4_sha256'][str(year)],'control旧MP4 SHA与实际下载不同')
    payload=pub.payload('exam',str(year));proof=inspect_stage(source,year,cert,payload);current=validate_current_registry(year,proof)
    target=Path(td)/'migrated';meta,proof=migrate(source,target,year,cert,current,download);pub.store_stage(target)
    rel=pub.release(pub.CACHE_TAG);assets={r['name']:r for r in rel['assets']};v=pub.asset('exam',str(year),meta['approval_payload_sha256'],meta['mp4_sha256']);e=pub.cache_evidence('exam',str(year),meta['approval_payload_sha256'],meta['mp4_sha256'])
    need(assets[v].get('digest')=='sha256:'+meta['mp4_sha256'] and assets[v]['size']==meta['mp4_bytes'],'迁移MP4上传后服务端SHA不同')
    need(assets[e].get('digest')=='sha256:'+pub.sha(target/e),'迁移证据上传后服务端SHA不同')
    results.append({'year':year,'status':'migrated_identical_mp4_bytes','old_payload_sha256':proof['old_payload_sha256'],'new_payload_sha256':proof['new_payload_sha256'],'mp4_sha256':meta['mp4_sha256'],'mp4_bytes':meta['mp4_bytes'],'original_source_commit':meta['source_commit'],'original_run_id':meta['run_id'],'revalidated_commit':meta['revalidated_commit'],'video_asset':v,'evidence_asset':e,'evidence_sha256':pub.sha(target/e)})
    pub.dump(a.out/'迁移进行中.json',results)
  summary={'schema':1,'status':'selected_unaffected_exam_cache_migrated_not_full_batch_release','control_sha256':pub.sha(a.control),'registry_sha256':pub.sha(pub.REGISTRY),'certificate_sha256':CERT_SHA,'revalidated_commit':revision(),'revalidation_run_id':os.getenv('GITHUB_RUN_ID'),'results':results}
  name='TEM8-exam-cache-migration-'+pub.sha(a.control)[:16]+'.json';pub.dump(a.out/name,summary);pub.upload(pub.CACHE_TAG,a.out/name);print('持久迁移完成',len(results),'年，MP4字节全部保持。')
if __name__=='__main__':
 try:main()
 except (MigrationError,AssertionError,KeyError,FileNotFoundError) as e:raise SystemExit('拒绝迁移：'+str(e))
