"""独立只读审图助手：下载review ZIP→完整机械核验→平表/联图/待审candidate。
不改renderer、源输入、审核登记或GitHub；不自动批准任何未知图片。
python 在线包核验.py --ids 2024-B1 --archives /path/to/zips --out /workspace/review --allow-locked
python 在线包核验.py --ids 2010-A 2010-B1 --download --run 123 --out /workspace/review
"""
from __future__ import annotations
import argparse,hashlib,json,re,shutil,stat,subprocess,sys,zipfile
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
BATCH=Path(__file__).resolve().parents[2];ROOT=BATCH.parents[2]
sys.path.insert(0,str(BATCH/'tools'))
from 发布汇集 import payload,hash_json,candidate,validate_source_preparation
from 精听数据 import validate,resolve_manual_splits,assert_manual_preserved,audio_protection
from 精听 import engine,states
REPO='AlienCodes/university-entrance-examination';TAG='tem8-listening-review-2009-2024'
LOCKED={'2009-A','2009-B1','2009-B2','2024-A','2024-B1'}
LEGACY_CORE={
 '专八/听力/批量/tools/精听.py':'ff515e1be152ea29844970bca368f64b1dbe1939bd8aeacb075157630aeecf26',
 '专八/听力/批量/tools/精听数据.py':'072c40ec95a6b532e798218d3be84eed68225608f53c1565f1c6c24895ba0d47'}
AAC_CORE={
 '专八/听力/批量/tools/精听.py':'cd766f44cf2075c49331992cb8a2598e48a708d85b2dd873486c494252d03da0',
 '专八/听力/批量/tools/精听数据.py':'11b4ef9c00ef2bae834dcb54026d6905202e3e3c57ace801033b25b080d1bb3e'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def dump(p,d):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def gh(*args):return subprocess.check_output(['gh',*map(str,args)],text=True)
def legacy_projection(now):
 assert all(now['render_sources'].get(k)==v for k,v in AAC_CORE.items()),'只读旧包审计仅支持本次精确AAC core，不接受未知新程序'
 old=json.loads(json.dumps(now));old['render_sources'].update(LEGACY_CORE);return old
def verify_reviewed_payload(row,now,allow_legacy=False):
 if row['payload_sha256']==hash_json(now):
  assert all(row[k]==now[k] for k in ['inputs','render_sources','annotation_source']);return {}
 assert allow_legacy,'输入/依赖指纹已过期'
 old=legacy_projection(now)
 assert row['payload_sha256']==hash_json(old),'旧包不是当前输入仅反投影指定两core的精确版本'
 assert all(row[k]==old[k] for k in ['inputs','render_sources','annotation_source']),'旧包存在未授权输入/依赖差异'
 return {k:{'reviewed_sha256':row['render_sources'][k],'current_sha256':now['render_sources'][k]} for k in LEGACY_CORE}
def unpack(arc,out,digest=None):
 if digest:assert sha(arc)==digest.removeprefix('sha256:'),'ZIP SHA与GitHub digest不符'
 with zipfile.ZipFile(arc) as z:
  names=z.namelist();assert len(names)==len(set(names)),'ZIP重名路径'
  assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names),'ZIP越界路径'
  assert all(not stat.S_ISLNK(x.external_attr>>16) for x in z.infolist()),'ZIP含链接'
  assert z.testzip() is None,'ZIP CRC失败'
  out.mkdir(parents=True,exist_ok=True);z.extractall(out)
 return len(names)
def audit(arc,out,digest=None,run=None,head=None,contacts=False,allow_legacy=False):
 from PIL import Image,ImageDraw,ImageFont
 entries=unpack(arc,out,digest);row=read(out/'审核候选.json');ident=row['id'];now=payload('intensive',ident)
 legacy_delta=verify_reviewed_payload(row,now,allow_legacy)
 for n,h in row['inputs'].items():assert sha(out/'实际输入'/Path(n).name)==h,'实际输入附件损坏：'+n
 source=validate(read(BATCH/'精听数据'/f'{ident}.json'))
 assert read(out/'实际输入'/f'{ident}.json')==source
 work=out/'工作记录';link=work/'shots'
 if not link.exists():link.symlink_to('../shots',target_is_directory=True)
 assert link.resolve()==(out/'shots').resolve(),'工作目录shots未绑定本包'
 prepared=read(work/'prepared.json');screens=read(work/'screens.json');audio=read(work/'audio-precheck.json')
 assert prepared['input_sha256']==sha(out/'实际输入'/f'{ident}.json') and prepared['draft'] is False
 assert not screens['problems'] and audio['ok'] and audio['raw_exact_before_encoding']
 assert audio['audio_sha256']==prepared['audio_sha256'] and audio['source_sha256']==source['audio']['sha256']==prepared['source_sha256']
 assert audio['raw_match']['snr_db']>=30 and abs(audio['raw_match']['gain_db'])<=.05 and audio['raw_match']['sec_db']<=1
 sourceprep=read(work/'源音频准备.json');native=validate_source_preparation(sourceprep,source['year'],audio['source_sha256'])
 assert audio['sample_rate']==sourceprep['canonical']['sample_rate'] and audio['channels']==sourceprep['canonical']['channels']
 p=read(work/'data/vocab.json')['passages'][0];flat=[s for para in p['paras'] for s in para]
 assert flat==[{k:s[k] for k in ['en','zh','w']} for s in source['sentences']]
 tm=read(work/'audio/timings.json')['cet4_male'][ident]
 assert tm['audio_sha256']==audio['audio_sha256'] and tm['source_sha256']==audio['source_sha256']
 protected,protection=audio_protection(source)
 assert prepared.get('protected_source_intervals',[])==tm.get('protected_source_intervals',[])==protected
 assert prepared.get('audio_protection')==tm.get('audio_protection')==protection
 assert not any(u<y and v>x for x,y in protected for u,v in tm['compressed_gaps']),'保护原音被压缩'
 m=engine(work);manual=resolve_manual_splits(source);bound=prepared.get('manual_splits',{});derived=read(work/'tools/分屏_水墨.json').get(ident,{})
 assert all(k in bound and all(bound[k][x]==v[x] for x in ['at','zh']) for k,v in manual.items())
 assert_manual_preserved(bound,derived);assert_manual_preserved(bound,read(work/'tools/分屏手定_水墨.json').get(ident,{}))
 assert states(m,p,tm,work)==read(work/'states.json'),'真实词首换屏/帧数与在线记录不一致'
 shotrows=screens['shots'];pngs=sorted((out/'shots').glob('*.png'));assert len(pngs)==len(shotrows)==len(row['shots'])==len(m.screens(p))
 assert set(x.name for x in pngs)=={x['file'] for x in shotrows}
 for r in shotrows:
  f=out/'shots'/r['file'];assert sha(f)==r['sha256']==row['shots']['shots/'+r['file']]
  with Image.open(f) as im:assert im.size==(3840,2160)
  if r['sizes'] is not None:
   fs,vs,fit=r['sizes'];assert fit and fs>=m.MIN_FS and vs>=m.MIN_VS,'实际字号/几何门禁失败'
 index=[];multi=[]
 for k,s in enumerate(flat,1):
  parts=m.split_parts(ident,k,s)
  if len(parts)>1:multi.append(k)
  assert ''.join(s['en'][a:b] for a,b,_,_ in parts)==s['en']
  zs=[z for _,_,z,_ in parts];ded=[z for j,z in enumerate(zs) if j==0 or z!=zs[j-1]]
  assert zs==[s['zh']]*len(zs) or ''.join(ded)==s['zh'],'跨屏中文丢字或重排未登记'
  for j,(a,b,zh,tag) in enumerate(parts,1):
   label=f'第 {k} 句'+(f' 第 {j} 屏' if len(parts)>1 else '');r=next(x for x in shotrows if x['label']==label)
   vocab=[w['h'] for w in s['w'] if any(a<=x and y<=b for x,y in w['sp'])];assert vocab,'实际分屏无可见词注'
   index.append({'file':r['file'],'sha256':r['sha256'],'k':k,'part':j,'parts':len(parts),'role':source['sentences'][k-1].get('role'),'en':s['en'][a:b],'zh':zh,'vocabulary':vocab})
 dump(out/'逐屏ENZH索引.json',index)
 (out/'逐屏ENZH平表.tsv').write_text('file\tk\tpart\tparts\trole\ten\tzh\tvocabulary\n'+'\n'.join('\t'.join(str(r.get(k,'' ) or '').replace('\t',' ').replace('\n',' ') for k in ['file','k','part','parts','role','en','zh'])+'\t'+' / '.join(r['vocabulary']) for r in index)+'\n')
 selected={shotrows[0]['file'],shotrows[-1]['file']};selected.update(r['file'] for r in index if r['parts']>1 or r['role'])
 if contacts:
  # 联图保留所有完整4K来源。实际已看名单须由审阅员另填，脚本不假批。
  font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',23);folder=out/'完整联图';folder.mkdir(exist_ok=True)
  for start in range(0,len(shotrows),4):
   canvas=Image.new('RGB',(1920,1144),'#e8e8e8');draw=ImageDraw.Draw(canvas)
   for j,r in enumerate(shotrows[start:start+4]):
    x=j%2*960;y=j//2*572;draw.text((x+12,y+5),r['file'],font=font,fill='#101010')
    with Image.open(out/'shots'/r['file']) as im:canvas.paste(im.resize((960,540)),(x,y+32))
   canvas.save(folder/f'contact-{start//4+1:02d}.jpg',quality=97)
 report={'id':ident,'status':'mechanical_pass_visual_pending','run_id':run,'head':head,'archive':arc.name,'archive_sha256':sha(arc),'zip_entries':entries,'crc':'PASS','payload_sha256':row['payload_sha256'],'screens':len(shotrows),'source_sentences':len(flat),'vocabulary_entries':sum(len(s['w']) for s in flat),'all_png_sha_dimensions_font_checks':'PASS','state_and_real_word_first_guard':'PASS','unit_input_sha256':prepared['input_sha256'],'annotation_source':now['annotation_source'],'audio_precheck':audio,'native_source':native,'multi_sentence_numbers':multi,'critical_png_files':sorted(selected),'work':str(work),'actual_viewed_png_files':[],'warning':'只有完整机械关卡通过；实际看图名单和语义发现须人工填写，candidate仍pending，不自动改登记/批准/触发GitHub。'}
 report.update(current_payload_sha256=hash_json(now),reviewed_legacy_core_delta=legacy_delta,current_dependency_revalidation_required=bool(legacy_delta))
 dump(out/'下载机械核验.json',report)
 c=json.loads(json.dumps(row)) if legacy_delta else candidate('intensive',ident,work)
 assert c['payload_sha256']==row['payload_sha256'] and c['shots']==row['shots']
 if legacy_delta:
  c['status']='pending';c['evidence']='只读核验原在线版本；仅指定两core与当前AAC版本不同。必须实际选图并由root另作等价复核/重绑，不自动批准当前指纹。'
 dump(out/'待审候选.json',c)
 return {k:report[k] for k in ['id','status','screens','payload_sha256','work']}
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--ids',nargs='+',required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--archives',type=Path);ap.add_argument('--download',action='store_true');ap.add_argument('--run',type=int);ap.add_argument('--workers',type=int,default=3);ap.add_argument('--contacts',action='store_true');ap.add_argument('--allow-locked',action='store_true');ap.add_argument('--review-legacy-aac-core',action='store_true');a=ap.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
 assert len(a.ids)==len(set(a.ids)) and all(re.fullmatch(r'20\d\d-(?:A|B1|B2)',i) for i in a.ids)
 assert a.allow_locked or not set(a.ids)&LOCKED,'本轮不覆盖已锁五篇，验证工具需显式--allow-locked'
 assets=json.loads(gh('api',f'repos/{REPO}/releases/tags/{TAG}'))['assets'] if a.download else [];head=None
 if a.run:head=json.loads(gh('api',f'repos/{REPO}/actions/runs/{a.run}'))['head_sha']
 arcdir=a.archives.resolve() if a.archives else a.out/'archives';arcdir.mkdir(parents=True,exist_ok=True);jobs=[];results=[]
 for ident in a.ids:
  try:
   now=payload('intensive',ident);fp=hash_json(now);name=f'TEM8-review-intensive-{ident}-{fp[:16]}.zip';asset=next((r for r in assets if r['name']==name),None);arc=arcdir/name
   if a.review_legacy_aac_core and not arc.exists() and asset is None:
    fp=hash_json(legacy_projection(now));name=f'TEM8-review-intensive-{ident}-{fp[:16]}.zip';asset=next((r for r in assets if r['name']==name),None);arc=arcdir/name
   if not arc.exists():
    assert a.download and asset,'缺少当前指纹在线包：'+name
    jobs.append((ident,arc,asset));continue
   jobs.append((ident,arc,asset))
  except Exception as ex:results.append({'id':ident,'status':'not_ready','error':str(ex)})
 def fetch(job):
  ident,arc,asset=job
  if not arc.exists():gh('release','download',TAG,'-R',REPO,'-p',arc.name,'-D',arcdir)
  return job
 with ThreadPoolExecutor(max_workers=min(max(a.workers,1),4)) as pool:
  tasks={pool.submit(fetch,j):j[0] for j in jobs};ready=[]
  for fut in as_completed(tasks):
   try:ready.append(fut.result())
   except Exception as ex:results.append({'id':tasks[fut],'status':'download_error','error':str(ex)})
 for ident,arc,asset in sorted(ready):
  try:results.append(audit(arc,a.out/ident,asset.get('digest') if asset else None,a.run,head,a.contacts,a.review_legacy_aac_core))
  except Exception as ex:results.append({'id':ident,'status':'rejected_mechanical','error':type(ex).__name__+': '+str(ex)})
 dump(a.out/'批量机械核验汇总.json',{'requested':a.ids,'results':results,'visual_approval_automatic':False});print(json.dumps(results,ensure_ascii=False,indent=2))
 if any(r['status']!='mechanical_pass_visual_pending' for r in results):raise SystemExit(1)
if __name__=='__main__':main()
