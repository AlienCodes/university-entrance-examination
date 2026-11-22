"""Read all release assets, including pages beyond GitHub's first hundred."""
from functools import lru_cache
import json
from pathlib import Path
import subprocess


@lru_cache(maxsize=12)
def inventory(tag,repo=None):
    flags=['--repo',repo] if repo else []
    endpoint=subprocess.check_output(['gh','release','view',tag,*flags,'--json','apiUrl','--jq','.apiUrl'],text=True).strip()
    pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',endpoint+'/assets?per_page=100']))
    return {asset['name']:asset for page in pages for asset in page if asset['state']=='uploaded'}


def fetch(asset,folder):
    dest=Path(folder)/asset['name']
    tmp=dest.with_suffix(dest.suffix+'.partial')
    with tmp.open('wb') as f:
        subprocess.run(['gh','api','-H','Accept: application/octet-stream',asset['url']],stdout=f,check=True)
    if tmp.stat().st_size!=asset['size']:
        raise ValueError('Incomplete GitHub asset download: '+asset['name'])
    tmp.replace(dest)
    return dest
