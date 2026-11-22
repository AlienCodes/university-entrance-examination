"""Read all release assets, including pages beyond GitHub's first hundred."""
from functools import lru_cache
import json
from pathlib import Path
import subprocess


@lru_cache(maxsize=12)
def inventory(tag,repo=None):
    flags=['--repo',repo] if repo else []
    endpoint=subprocess.check_output(['gh','release','view',tag,*flags,'--json','apiUrl','--jq','.apiUrl'],text=True).strip()
    lines=subprocess.check_output(['gh','api','--paginate','--jq','.[] | @json',endpoint+'/assets?per_page=100'],text=True).splitlines()
    assets=[json.loads(line) for line in lines if line.strip()]
    return {asset['name']:asset for asset in assets if asset['state']=='uploaded'}


def fetch(asset,folder):
    dest=Path(folder)/asset['name']
    tmp=dest.with_suffix(dest.suffix+'.partial')
    with tmp.open('wb') as f:
        subprocess.run(['gh','api','-H','Accept: application/octet-stream',asset['url']],stdout=f,check=True)
    if tmp.stat().st_size!=asset['size']:
        raise ValueError('Incomplete GitHub asset download: '+asset['name'])
    tmp.replace(dest)
    return dest
