"""Publish one PDF-only archive and verify remote size and every downloaded byte."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen

TAG='ielts-academic-study-21-14-by-video'
REPO='AlienCodes/university-entrance-examination'
TITLE='剑桥雅思第21–14册学术阅读讲义 · 按视频全名分类 · 三份PDF'

def gh(*args):
    return subprocess.check_output(['gh',*map(str,args)],text=True).strip()

def release():
    return json.loads(gh('api',gh('release','view',TAG,'--json','apiUrl','--jq','.apiUrl')))

def main(folder):
    proof=json.loads((folder/'actual.json').read_text())
    pack=folder/proof['zip_name']
    if (proof['files'],proof['passages'])!=(288,96) or pack.stat().st_size!=proof['zip_bytes']:
        raise ValueError('Unexpected ZIP to publish')
    sha=proof['zip_sha256']
    with pack.open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=sha: raise ValueError('Local SHA-256 differs')
    url='https://github.com/'+REPO+'/releases/download/'+TAG+'/'+pack.name
    note=folder/'notes.md'
    note.write_text(f"""[下载全部 PDF 讲义（一个 ZIP）]({url})

剑桥雅思学术阅读第 21–14 册。每个 B 站视频对应一个文件夹，共 96 个文件夹、288 份 PDF。文件夹按第 21 册到第 14 册排列，每册依照原书 Test 和 Passage 的顺序。标注年份为该册出版年份。

第一个文件夹为「{proof['contents'][0]['folder']}」，最后一个文件夹为「{proof['contents'][-1]['folder']}」。

每个文件夹只放三份 PDF。

- **视频逐屏讲义.pdf**　保留对应精读视频的实际画面，原句、译文及语境词义逐屏对应。
- **逐题解析.pdf**　按原书题号查找答案、证据句和推理过程。
- **长难句与写作句式.pdf**　拆解原句，附写作场景、英文例句和中译。

ZIP 文件为 {pack.stat().st_size:,} 字节。SHA-256 为 `{sha}`。
""")
    result=subprocess.run(['gh','release','view',TAG],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if result.returncode:
        gh('release','create',TAG,'--draft','--target',os.environ['GITHUB_SHA'],'--title',TITLE,'--notes-file',note)
    data=release();asset=next((a for a in data['assets'] if a['name']==pack.name),{})
    def matches(a):
        return (a.get('digest'),a.get('size'),a.get('state'))==('sha256:'+sha,pack.stat().st_size,'uploaded')
    if not matches(asset):
        if not data['draft']:raise ValueError('The public edition has a different archive')
        gh('release','upload',TAG,pack,'--clobber')
    data=release()
    def verified(record):
        if len(record['assets'])!=1 or not matches(record['assets'][0]):raise ValueError('Expected one verified GitHub asset')
    verified(data)
    if data['draft']:gh('release','edit',TAG,'--draft=false','--latest=false','--title',TITLE,'--notes-file',note)
    data=release();verified(data)
    if data['draft'] or data['prerelease']:raise ValueError('Formal release is not visible')
    for attempt in range(4):
        try:
            h=hashlib.sha256();size=0
            with urlopen(Request(url,headers={'User-Agent':'IELTS-public-download-check','Accept-Encoding':'identity'}),timeout=100) as net:
                for b in iter(lambda:net.read(4<<20),b''): h.update(b);size+=len(b)
            if (size,h.hexdigest())!=(pack.stat().st_size,sha):raise ValueError('Returned archive differs')
            break
        except OSError:
            if attempt==3:raise
            time.sleep(3*(attempt+1))
    print(json.dumps(dict(release=data['html_url'],asset=url,bytes=size,sha256=sha,folders=96,pdfs=288),ensure_ascii=False))

if __name__=='__main__':main(Path(sys.argv[1]))
