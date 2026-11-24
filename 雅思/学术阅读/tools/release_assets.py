"""Read all release assets, including pages beyond GitHub's first hundred."""
from functools import lru_cache
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


@lru_cache(maxsize=12)
def inventory(tag,repo=None):
    flags=['--repo',repo] if repo else []
    endpoint=subprocess.check_output(['gh','release','view',tag,*flags,'--json','apiUrl','--jq','.apiUrl'],text=True).strip()
    lines=subprocess.check_output(['gh','api','--paginate','--jq','.[] | @json',endpoint+'/assets?per_page=100'],text=True).splitlines()
    assets=[json.loads(line) for line in lines if line.strip()]
    return {asset['name']:asset for asset in assets if asset['state']=='uploaded'}


def fetch(asset,folder):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    dest=folder/asset['name']
    tmp=dest.with_suffix(dest.suffix+'.partial')
    with tmp.open('wb') as f:
        subprocess.run(['gh','api','-H','Accept: application/octet-stream',asset['url']],stdout=f,stderr=subprocess.PIPE,check=True)
    if tmp.stat().st_size!=asset['size']:
        raise ValueError('Incomplete GitHub asset download: '+asset['name'])
    digest=asset.get('digest')
    if digest and digest.startswith('sha256:'):
        with tmp.open('rb') as stream:
            actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=digest.removeprefix('sha256:'):
            raise ValueError('GitHub asset checksum differs: '+asset['name'])
    tmp.replace(dest)
    return dest


def upload(tag, file, *, replace=False):
    """Recover a timed-out transfer without replacing an immutable asset."""
    path=Path(file)
    command=['gh','release','upload',tag,str(path)]
    if replace:
        command.append('--clobber')
    for delay in (0,3,12,30):
        if delay:
            time.sleep(delay)
        attempt=subprocess.run(command, capture_output=True, text=True)
        inventory.cache_clear()
        if attempt.returncode==0:
            return
        # GitHub can finish writing the file even when the response is lost.
        try:
            remote=inventory(tag).get(path.name,{})
        except subprocess.CalledProcessError:
            remote={}
        if remote.get('size')==path.stat().st_size:
            with path.open('rb') as stream:
                expected='sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()
            if remote.get('digest')==expected:
                return
        reason=attempt.stderr.casefold()
        if not any(s in reason for s in ('timeout','timed out','connection reset','unexpected eof',
                                          'http 500','http 502','http 503','http 504','tls handshake')):
            break
    raise subprocess.CalledProcessError(attempt.returncode,command,stderr=attempt.stderr)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('tag')
    parser.add_argument('asset')
    parser.add_argument('folder',type=Path)
    parser.add_argument('--if-present',action='store_true')
    args=parser.parse_args()
    asset=inventory(args.tag).get(args.asset)
    if asset is not None:
        fetch(asset,args.folder)
    elif not args.if_present:
        raise SystemExit('Missing GitHub release asset: '+args.asset)
