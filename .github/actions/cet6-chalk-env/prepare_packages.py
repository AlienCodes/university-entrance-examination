"""Install only missing packages from the pinned Chromium dependency plan."""
import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


def browser_packages(plan):
    shell = shlex.split(plan.strip().splitlines()[-1])
    command = shell[shell.index('-c') + 1]
    args = shlex.split(command.replace('&&', ' && '))
    start = args.index('--no-install-recommends')
    if args[start-3:start] != ['apt-get', 'install', '-y']:
        raise ValueError('Unexpected Playwright dependency plan')
    packages = args[start+1:]
    if not packages or any(not re.fullmatch(r'[a-z0-9][a-z0-9.+:-]*', p) for p in packages):
        raise ValueError('Invalid package list from the pinned Playwright release')
    return packages


def missing_packages(wanted):
    table = subprocess.check_output(['dpkg-query', '-W', '-f=${binary:Package}\t${Status}\n'], text=True)
    installed = set()
    for row in table.splitlines():
        package, status = row.split('\t', 1)
        if status.endswith(' ok installed'):
            installed.add(package.split(':')[0])
    return sorted(set(wanted) - installed)


def apt(args, deadline, sources=None):
    options = ['-q', '-o', 'Acquire::Retries=1', '-o', 'Acquire::http::Timeout=15',
               '-o', 'Acquire::https::Timeout=15', '-o', 'DPkg::Lock::Timeout=25',
               '-o', 'Dpkg::Use-Pty=0', '-o', 'Acquire::Languages=none']
    if sources:
        options += ['-o', 'Dir::Etc::sourcelist='+str(sources), '-o', 'Dir::Etc::sourceparts=-',
                    '-o', 'APT::Update::Error-Mode=any']
    command = ['sudo', '-n', 'env', 'DEBIAN_FRONTEND=noninteractive', 'NEEDRESTART_MODE=a',
               'timeout', '--kill-after=10s', str(deadline), 'apt-get', *options, *args]
    print(f"Running apt-get {' '.join(args)} (limit {deadline}s)", flush=True)
    return subprocess.run(command).returncode


def ubuntu_sources(folder):
    release = {}
    for row in Path('/etc/os-release').read_text().splitlines():
        if '=' in row:
            k, v = row.split('=',1)
            release[k] = v.strip('"')
    if release.get('ID') != 'ubuntu':
        return None
    suite = release['VERSION_CODENAME']
    if not re.fullmatch('[a-z]+', suite): raise ValueError('Invalid Ubuntu suite')
    arch = subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()
    archive = 'https://archive.ubuntu.com/ubuntu' if arch in ('amd64','i386') else 'https://ports.ubuntu.com/ubuntu-ports'
    security = 'https://security.ubuntu.com/ubuntu' if arch in ('amd64','i386') else archive
    template = ('Types: deb\nURIs: {url}\nSuites: {suites}\nComponents: main restricted universe multiverse\n'
                'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n')
    path = folder/'ubuntu.sources'
    path.write_text(template.format(url=archive,suites=f'{suite} {suite}-updates')+'\n'
                    +template.format(url=security,suites=suite+'-security'))
    path.chmod(0o644)
    return path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('browser',choices=['141','153'])
    parser.add_argument('--plan-file',type=Path)
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--decoder-only',action='store_true')
    args=parser.parse_args()
    required=['ffmpeg']
    if not args.decoder_only:
        plan = args.plan_file.read_text() if args.plan_file else subprocess.check_output(
            ['/tmp/pw156/bin/python','-m','playwright','install-deps','--dry-run','chromium'],text=True,timeout=30)
        required.extend(browser_packages(plan))
        if args.browser=='153': required.append('fonts-inter')
    missing = missing_packages(required)
    print(f'{len(set(required))} required browser, font and encoding packages; missing: {missing}',flush=True)
    if not missing or args.check_only: return
    install = ['install','-y','--no-install-recommends',*missing]
    if apt(install,150):
        audit = subprocess.check_output(['dpkg','--audit'],text=True,timeout=20).strip()
        if audit:
            print(audit,flush=True)
            subprocess.run(['sudo','-n','env','DEBIAN_FRONTEND=noninteractive',
                            'timeout','--kill-after=10s','90','dpkg','--configure','-a'],check=True)
        with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as temp:
            folder=Path(temp)
            folder.chmod(0o755)
            sources=ubuntu_sources(folder)
            if apt(['update'],150,sources) or apt(install,180,sources):
                raise SystemExit('Renderer system package setup failed. See the timed apt commands above.')
    remaining=missing_packages(required)
    if remaining: raise SystemExit('Missing declared renderer packages: '+', '.join(remaining))


if __name__=='__main__': main()
