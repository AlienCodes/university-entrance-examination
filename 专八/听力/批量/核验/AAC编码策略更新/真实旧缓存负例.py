"""在真实旧2009-A cache的隔离硬链副本注入失败；不写原件、不上传。"""
import importlib.util,json,hashlib,tempfile,copy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5];p=ROOT/'专八/听力/批量/tools/迁移精听默认AAC缓存.py';s=importlib.util.spec_from_file_location('real_negative_default_aac',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
source=Path('/workspace/tem8-intensive-default-aac-real2009A/cache/0/stage');out=Path(__file__).resolve().parent
sha=m.pub.sha
meta=m.pub.read(source/'meta.json');verification=source/'evidence/工作记录/verification.json';png=next((source/'evidence/已审截图/shots').glob('*.png'))
before={str(x.relative_to(source)):sha(x) for x in [source/'meta.json',verification,png]};proof_sha=sha(m.PROOF);proof=m.validate_proof(proof_sha)
def write(p,b):p=Path(p);p.unlink();p.write_bytes(b)
def changed_json(stage,name,fn):
 p=stage/name;a=m.pub.read(p);fn(a);write(p,(json.dumps(a,ensure_ascii=False,indent=2)+'\n').encode());meta=m.pub.read(stage/'meta.json');meta['evidence'][name]=sha(p);write(stage/'meta.json',(json.dumps(meta,ensure_ascii=False,indent=2)+'\n').encode())
rows=[]
with tempfile.TemporaryDirectory(prefix='aac-real-negative-') as td:
 for case in ['failed_report','changed_PNG_even_inventory_updated','changed_tm_policy']:
  stage=Path(td)/case;m.common.copy_stage(source,stage)
  if case=='failed_report':changed_json(stage,'evidence/工作记录/verification.json',lambda a:a.update(ok=False))
  elif case=='changed_tm_policy':changed_json(stage,'evidence/工作记录/audio/timings.json',lambda a:a['cet4_male']['2009-A'].update(aac_bitrate='256k'))
  else:
   name=str(png.relative_to(source));path=stage/name;b=bytearray(path.read_bytes());b[-1]^=1;write(path,b);a=m.pub.read(stage/'meta.json');a['evidence'][name]=sha(path);write(stage/'meta.json',(json.dumps(a,ensure_ascii=False,indent=2)+'\n').encode())
  try:
   if case=='failed_report':m.pub.validate_stage(stage,'intensive','2009-A',meta['approval_payload_sha256'])
   else:m.inspect(stage,'2009-A',proof,proof_sha,None)
   raise RuntimeError('负例没有被拦：'+case)
  except (AssertionError,m.MigrationError) as ex:rows.append({'case':case,'rejected':True,'reason':str(ex),'scope':'真实成功缓存隔离副本的故意损坏，非新媒体核验'})
after={str(x.relative_to(source)):sha(x) for x in [source/'meta.json',verification,png]};assert before==after
report={'status':'3_real_cache_corruption_negatives_rejected','old_real_MP4_sha256':meta['mp4_sha256'],'source_meta_and_report_and_PNG_unchanged':before==after,'default_proof_sha256_at_test':proof_sha,'cases':rows,'no_video_generated_or_uploaded':True};(out/'真实旧缓存负例结果.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
