"""六级听力原文精读：GitHub 生成之后的每一步在本机预演一遍（踩坑 126：video / publish 从没在本机跑过，一次运行一次暴露一个问题）。

在临时目录里按工作流的路径摆好文件，**原样**抽出工作流里的 Python 运行（踩坑 61），视频用按比例缩小的假文件（PACK_SCALE）：
  ① prep：核对审阅登记、写 manifest（30 套）；
  ② render「整理要上传的文件」：每套一个假 mp4（约 330 MB × SCALE）+ 全部通过的核查结果（指纹 = 当前程序算的）→ out/ → artifacts/cet6lt-<套>/；
  ③ publish「汇总、核对、打包」：.github/cet6-listening-text-pack.py（按体积分包、中文名 UTF-8、不压缩、CRC、发布说明、zips.txt）；
  ④ publish「发布后核对」：先记 sha256、删本地，再拿“下载回来”的副本比；
  ⑤ 雷：一个假视频超过上限（× SCALE）必须被 ② 或 ③ 拒收；核查结果有一项不过必须被拒收。
全部 0 处才算通过。

    /opt/ttsenv/bin/python tools/防复发/验证/精读发布预演.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WF = yaml.safe_load((ROOT / '.github/workflows/render-cet6-listening-text.yml').read_text('utf-8'))
SCALE = 0.001
C = '六级/听力/精读'
errs = []


def step(job, name_start):
    st = [s for s in WF['jobs'][job]['steps'] if str(s.get('name', '')).startswith(name_start)]
    assert len(st) == 1, f'{job} 里找不到步骤 {name_start}'
    return st[0]


def heredocs(run):
    return re.findall(r"<<'PY'\n(.*?)\nPY", run, re.S)


def py(code, cwd, env, exe=sys.executable):
    r = subprocess.run([exe, '-'], input=code, text=True, capture_output=True, cwd=cwd, env={**os.environ, **env})
    return r.returncode, (r.stdout + r.stderr).strip()


def setup(W):
    for x in ('专八', 'tools', '.github', '四级'):
        (W / x).symlink_to(ROOT / x)
    (W / C).mkdir(parents=True)
    for x in ('data', 'audio', 'tools', 'ann'):
        (W / C / x).symlink_to(ROOT / C / x)
    (W / 'manifest').mkdir()                     # 工作流在 prep 的 Python 之前 mkdir -p manifest
    for x in ('最终视频', '大字版/成品核查', '大字版/日志', 'artifacts'):
        (W / (C if x != 'artifacts' else '') / x).mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', '-q', str(W)], check=True)


def run_all(W, bomb=None):
    """返回 (问题, 打包输出)。bomb：('big', 套) 视频超上限；('fail', 套) 核查有一项不过。"""
    out = []
    ids = [l for l in (ROOT / '.github/cet6-listening-text-render.txt').read_text('utf-8').split('\n')[2:] if l.strip() and not l.startswith('#')]
    env = {'IDS': json.dumps(ids), 'MODE': 'video', 'TAG': 'cet6lt-video-dryrun', 'RELEASE_TAG': 'cet6-listening-text'}
    rc, o = py(heredocs(step('prep', '核对审阅登记')['run'])[0], W, env, '/opt/ttsenv/bin/python')
    if rc:
        return [f'① prep：{o[-300:]}'], ''
    sys.path.insert(0, str(ROOT / '专八' / 'tools'))
    import make_video as M
    M.set_project('六级听力')
    vocab = {p['id']: p for p in json.loads((ROOT / C / 'data/vocab.json').read_text('utf-8'))['passages']}
    tidy = heredocs(step('render', '整理要上传的文件')['run'])[0]
    T = json.loads((ROOT / C / 'audio/timings.json').read_text('utf-8'))['cet4_male']
    import hashlib
    for k, pid in enumerate(ids):
        name = M.video_name(vocab[pid])
        size = int((300 + k) * 2**20 * SCALE)
        if bomb == ('big', pid):
            size = int(1901 * 2**20 * SCALE)
        mp4 = W / C / '最终视频' / name
        mp4.write_bytes(os.urandom(size))
        checks = [{'item': '逐屏画面与截图一致', 'ok': True, 'detail': ''}, {'item': f'成品体积 ≤ {M.PJ["max_mb"]} MB', 'ok': size <= M.PJ['max_mb'] * 2**20, 'detail': ''}]
        if bomb == ('fail', pid):
            checks.append({'item': '换屏在两句之间（原音）', 'ok': False, 'detail': '雷'})
        ok = all(c['ok'] for c in checks)
        (W / C / '大字版/成品核查' / (Path(name).stem + '_核查.json')).write_text(json.dumps(
            {'video': name, 'style': '3', '指纹': M.fingerprint(pid, '3'), 'ok': ok, 'size': size, 'checks': checks}, ensure_ascii=False), 'utf-8')
        (W / C / '大字版/日志' / f'{pid}.log').write_text('dryrun', 'utf-8')
        asha = hashlib.sha256((ROOT / C / 'audio' / T[pid]['file']).read_bytes()).hexdigest()
        shutil.rmtree(W / 'out', ignore_errors=True)
        (W / 'out').mkdir()                          # 工作流在这段 Python 之前 mkdir -p out
        rc, o = py(tidy, W, {'ID': pid, 'AUDIO_SHA': asha, 'STILLS_S': '1', 'VIDEO_S': '2', 'GITHUB_SERVER_URL': 'https://github.com',
                             'GITHUB_REPOSITORY': 'AlienCodes/university-entrance-examination', 'GITHUB_RUN_ID': '0'}, '/opt/ttsenv/bin/python')
        mp4.unlink()
        if rc:
            out.append(f'② 整理 {pid}：{o.splitlines()[-1][:200]}')
            continue
        shutil.move(str(W / 'out'), str(W / 'artifacts' / f'cet6lt-{pid}'))
    if out:
        return out, ''
    r = subprocess.run([sys.executable, str(ROOT / '.github/cet6-listening-text-pack.py')], cwd=W, text=True, capture_output=True,
                       env={**os.environ, 'TAG': 'cet6lt-video-dryrun', 'GITHUB_REPOSITORY': 'AlienCodes/university-entrance-examination',
                            'GITHUB_RUN_ID': '0', 'PACK_SCALE': str(SCALE)})
    po = (r.stdout + r.stderr).strip()
    if r.returncode:
        return [f'③ 打包退出码 {r.returncode}：{po[-300:]}'], po
    zips = (W / 'zips.txt').read_text('utf-8').split()
    names = []
    for z in zips:
        assert (W / z).stat().st_size < 2 * 2**30 * SCALE
        with zipfile.ZipFile(W / z) as zf:
            for i in zf.infolist():
                if not i.flag_bits & 0x800 or i.compress_type != zipfile.ZIP_STORED:
                    out.append(f'③ {z} {i.filename}：没有 UTF-8 标记或被压缩')
                names.append(i.filename)
    want = [M.video_name(vocab[p]) for p in ids]
    if names != want:
        out.append(f'③ 包里的文件名 / 顺序与 30 套不一致（{len(names)} 个）')
    notes = (W / 'notes.md').read_text('utf-8')
    if len(re.findall(r'^\| \d+ \|', notes, re.M)) != 30 or any(f'part{i}' not in notes for i in range(1, len(zips) + 1)):
        out.append('③ 发布说明的对照表不对')
    v1, v2 = heredocs(step('publish', '发布后核对')['run'])
    rc, o = py(v1, W, {})
    if rc:
        out.append(f'④ 记 sha256：{o[-200:]}')
    (W / 'dl').mkdir()
    for z in zips:
        shutil.copy(W / z, W / 'dl' / z)
    rc, o = py(v2, W, {'RELEASE_TAG': 'cet6-listening-text'})
    if rc:
        out.append(f'④ 下载回来核对：{o[-200:]}')
    with open(W / 'dl' / zips[0], 'r+b') as fh:          # 雷：下载回来的被改了一个字节，核对必须报
        fh.seek(100)
        b = fh.read(1)
        fh.seek(100)
        fh.write(bytes([b[0] ^ 1]))
    if py(v2, W, {'RELEASE_TAG': 'cet6-listening-text'})[0] == 0:
        out.append('④ 下载回来的 zip 被改了一个字节，核对没报')
    return out, po


with tempfile.TemporaryDirectory() as d:
    W = Path(d)
    setup(W)
    probs, po = run_all(W)
    errs += probs
    parts = re.findall(r'📦 (\S+)：(\d+) 个，(\d+) MB', po)
for bomb in [('big', '202312-2'), ('fail', '201812-1')]:
    with tempfile.TemporaryDirectory() as d:
        W = Path(d)
        setup(W)
        probs, _ = run_all(W, bomb)
        if not probs:
            errs.append(f'⑤ 雷 {bomb} 没有被拒收')



def tidy_full_size(wf_text):
    """⑥ 真实体积（330 MB 稀疏文件）走一遍「整理」：返回退出码。"""
    wf = yaml.safe_load(wf_text)
    code = heredocs([s for s in wf['jobs']['render']['steps'] if str(s.get('name', '')).startswith('整理要上传的文件')][0]['run'])[0]
    with tempfile.TemporaryDirectory() as d:
        W = Path(d)
        setup(W)
        sys.path.insert(0, str(ROOT / '专八' / 'tools'))
        import hashlib
        import make_video as M
        M.set_project('六级听力')
        pid = '202312-2'
        p = next(x for x in json.loads((ROOT / C / 'data/vocab.json').read_text('utf-8'))['passages'] if x['id'] == pid)
        name = M.video_name(p)
        size = 330 * 2**20
        with open(W / C / '最终视频' / name, 'wb') as fh:
            fh.truncate(size)
        (W / C / '大字版/成品核查' / (Path(name).stem + '_核查.json')).write_text(json.dumps(
            {'video': name, '指纹': M.fingerprint(pid, '3'), 'ok': True, 'size': size, 'checks': [{'item': 'x', 'ok': True}]}, ensure_ascii=False), 'utf-8')
        (W / C / '大字版/日志' / f'{pid}.log').write_text('dryrun', 'utf-8')
        (W / 'out').mkdir()
        tm = json.loads((ROOT / C / 'audio/timings.json').read_text('utf-8'))['cet4_male'][pid]
        asha = hashlib.sha256((ROOT / C / 'audio' / tm['file']).read_bytes()).hexdigest()
        return py(code, W, {'ID': pid, 'AUDIO_SHA': asha, 'STILLS_S': '1', 'VIDEO_S': '2', 'GITHUB_SERVER_URL': 'x',
                            'GITHUB_REPOSITORY': 'x', 'GITHUB_RUN_ID': '0'}, '/opt/ttsenv/bin/python')[0]


if tidy_full_size((ROOT / '.github/workflows/render-cet6-listening-text.yml').read_text('utf-8')):
    errs.append('⑥ 330 MB 的真实体积过不了「整理要上传的文件」')
old = subprocess.run(['git', '-C', str(ROOT), 'show', 'c4a7328:.github/workflows/render-cet6-listening-text.yml'], capture_output=True, text=True).stdout
if old and tidy_full_size(old) == 0:
    errs.append('⑥ 旧工作流（c4a7328，写死 95 MB）应拒收 330 MB，却放过了（这条验证失效）')

print('\n'.join(errs) or f'精读发布预演通过：prep → 整理 30 套 → 打包 {len(parts)} 包（每包 {"、".join(n for _, n, _ in parts)} 个，< 2 GB × {SCALE}）→ 发布核对；超上限、核查不过、下载被改 3 颗雷都拦下')
sys.exit(1 if errs else 0)
