import datetime,hashlib,importlib.util,json,pathlib,subprocess,urllib.request,zipfile
import argparse
a=argparse.ArgumentParser(description='正式考试Release服务器摘要及ZIP真实回下载逐成员核验');a.add_argument('--state',type=pathlib.Path,required=True);a.add_argument('--run',required=True);a.add_argument('--production-commit',required=True);a.add_argument('--producer-register',type=pathlib.Path,required=True);args=a.parse_args()
root=pathlib.Path(__file__).resolve().parents[5];monitor=args.state;s=importlib.util.spec_from_file_location('pub',root/'专八/听力/批量/tools/发布汇集.py');p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
tag='tem8-listening-exam-2009-2024';rel=p.release(tag);assets={a['name']:a for a in rel['assets']};dest=monitor/'final-download';dest.mkdir(exist_ok=True)
def fetch(name):
 a=assets[name];file=dest/name
 if not file.exists() or p.sha(file)!=''.join(a['digest'].split(':')[1:]):
  req=urllib.request.Request(a['browser_download_url'],headers={'User-Agent':'tem8-exam-publication-verifier'})
  with urllib.request.urlopen(req,timeout=120) as source,file.open('wb') as out:
   while True:
    block=source.read(1<<20)
    if not block:break
    out.write(block)
 assert file.stat().st_size==a['size'] and a['digest']=='sha256:'+p.sha(file),(name,'server SHA mismatch')
 return file
manifest=p.read(fetch('TEM8-manifest.json'));report=p.read(fetch('发布回下载核验.json'));sums={}
for line in fetch('SHA256SUMS').read_text().splitlines():
 h,name=line.split('  ',1);sums[name]=h
fetch('TEM8-filenames.txt')
assert manifest['mode']==report['mode']=='complete_exam' and manifest['tag']==report['tag']==tag
assert report['videos']==15 and report['server_digest'] is True and report['download_sha_crc_utf8'] is True
videos=manifest['videos'];assert len(videos)==15 and [m['id'] for m in videos]==list(map(str,p.YEARS))
allowed={str(r['run_id']):r for r in p.read(args.producer_register)['runs']}
cache={r['id']:r for r in p.read(root/'专八/听力/批量/核验/考试正式发布/生产15缓存核验.json')['rows']}
rows=[]
for m in videos:
 g=p.gate('exam',m['id']);a=assets[m['mp4']]
 assert m['approval_payload_sha256']==g['payload_sha256']
 assert m['verification']['ok'] is True and m['verification']['draft'] is False
 assert a['digest']=='sha256:'+m['mp4_sha256'] and a['size']==m['mp4_bytes'] and a['label']==m['label']
 assert sums[m['mp4']]==m['mp4_sha256']
 producer=allowed[str(m['run_id'])]
 assert m['id'] in producer['target_ids'] and m['source_commit']==producer['source_commit']
 assert m['mp4_sha256']==cache[m['id']]['mp4_sha256'] and m['mp4_bytes']==cache[m['id']]['mp4_bytes']
 rows.append({'id':m['id'],'approval_payload_sha256':g['payload_sha256'],'mp4_sha256':m['mp4_sha256'],'bytes':m['mp4_bytes'],'label':m['label'],'source_commit':m['source_commit'],'production_run_id':m['run_id']})
expected={'专八听力考试/'+m['label']:m for m in videos};members=[];archives=[]
for archive in report['archives']:
 file=fetch(archive['file']);assert p.sha(file)==archive['sha256']==sums[file.name] and file.stat().st_size==archive['bytes']
 with zipfile.ZipFile(file) as z:
  assert z.testzip() is None
  for info in z.infolist():
   assert info.filename in expected and info.filename not in members
   assert info.flag_bits&0x800 and info.compress_type==zipfile.ZIP_STORED and info.date_time==p.DATE
   h=hashlib.sha256()
   with z.open(info) as f:
    for block in iter(lambda:f.read(1<<20),b''):h.update(block)
   m=expected[info.filename];assert h.hexdigest()==m['mp4_sha256'] and info.file_size==m['mp4_bytes'];members.append(info.filename)
 archives.append({**archive,'download_url':assets[file.name]['browser_download_url'],'server_and_download_verified':True})
 print('archive verified',file.name,len(members),'videos',flush=True)
assert members==list(expected) and len(members)==15
allowed={m['mp4'] for m in videos}|{m['mp4'][:-4]+'-evidence.zip' for m in videos}|{x['file'] for x in archives}|{'TEM8-manifest.json','TEM8-filenames.txt','SHA256SUMS','发布回下载核验.json'}
extra=sorted(set(assets)-allowed)
audit={'status':'PASS','release_url':rel['html_url'],'tag':tag,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'mode':'complete_exam','videos':15,'manifest_source_commit':manifest['source_commit'],'server_digest_verified':True,'actual_download_zip_crc_utf8_member_sha256_verified':True,'rows':rows,'archives':archives,'unexpected_assets':extra,'release_report_sha256':p.sha(dest/'发布回下载核验.json'),'manifest_sha256':p.sha(dest/'TEM8-manifest.json')}
p.dump(root/'专八/听力/批量/核验/考试正式发布/正式Release独立回下载核验.json',audit)
print(json.dumps({'status':'PASS','url':rel['html_url'],'videos':15,'archives':archives,'unexpected_assets':extra},ensure_ascii=False),flush=True)
