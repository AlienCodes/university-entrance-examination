"""Read all release assets, including pages beyond GitHub's first hundred."""
from functools import lru_cache
import argparse
import hashlib
import json
import os
import random
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import quote


def is_rate_limited(reason):
    return any(part in reason.lower() for part in ("api rate limit", "secondary rate limit", "http 429"))


def rate_limit_delay(reason, attempt):
    if not is_rate_limited(reason):
        return None
    # Look up the core reset time only after GitHub actually reports a limit.
    # Secondary limits do not provide a reset in /rate_limit; back off in minutes.
    delay = 60 * (2 ** attempt)
    try:
        core = json.loads(subprocess.check_output(
            ["gh", "api", "rate_limit", "--jq", ".resources.core"],
            text=True, stderr=subprocess.PIPE, timeout=15))
        if core["remaining"] == 0:
            delay = max(1, core["reset"] - time.time() + 1)
    except (subprocess.SubprocessError, ValueError, KeyError, TypeError):
        pass
    return delay + random.uniform(1, 5)


def transient_read_error(error):
    reason = (error.stderr or '').lower()
    return is_rate_limited(reason) or any(part in reason for part in (
        'http 500', 'http 502', 'http 503', 'http 504', 'timed out', 'unexpected eof',
        'unexpected end of json input', 'connection reset'))


def read_github(command, destination=None):
    for attempt in range(3):
        try:
            if destination is None:
                return subprocess.check_output(command, text=True, stderr=subprocess.PIPE)
            with destination.open("wb") as output:
                subprocess.run(command, stdout=output, text=True, stderr=subprocess.PIPE, check=True)
            return
        except subprocess.CalledProcessError as exc:
            if attempt == 2 or not transient_read_error(exc):
                if exc.stderr:
                    sys.stderr.write(exc.stderr)
                raise
            delay = rate_limit_delay(exc.stderr or "", attempt)
            if delay is not None:
                print(f"GitHub read limit reached; retrying in {delay:.0f}s", file=sys.stderr, flush=True)
            time.sleep(delay if delay is not None else (2, 8)[attempt])


@lru_cache(maxsize=12)
def inventory(tag,repo=None):
    repository = repo or os.getenv("GH_REPO") or os.getenv("GITHUB_REPOSITORY") or "{owner}/{repo}"
    route = f"repos/{repository}/releases/tags/{quote(tag, safe='')}"
    endpoint = read_github(["gh", "api", route, "--jq", ".url"]).strip()
    lines=read_github(['gh','api','--paginate','--jq','.[] | @json',endpoint+'/assets?per_page=100']).splitlines()
    assets=[json.loads(line) for line in lines if line.strip()]
    return {asset['name']:asset for asset in assets if asset['state']=='uploaded'}


def fetch(asset,folder):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    dest=folder/asset['name']
    tmp=dest.with_suffix(dest.suffix+'.partial')
    read_github(['gh','api','-H','Accept: application/octet-stream',asset['url']], destination=tmp)
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
