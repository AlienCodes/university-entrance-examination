"""大字版打包（六级黑板 render-cet6-chalk.yml、专八校园 render-tem8-campus.yml、考研校园 render-kaoyan-campus.yml 的最后一个任务；环境变量 PROJECT=六级|专八|考研，默认六级，下面以六级为例）。
六级黑板（render-cet6-chalk.yml 最后一个任务）：汇总 60 个视频 → 逐个核对 → 每 20 个打一个 zip（不压缩）→ Python zipfile 逐个核对 → 写发布说明。

视频来源（按优先级）：
  ① 本次运行生成的：artifacts/cet6-chalk-<篇目>/（视频、_核查.json、meta.json、核查报告、日志）
  ② 仓库里已提交的：六级/最终视频_黑板/<文件名>（核查结果 六级/样片/成品核查/<文件名>_核查.json，同时提交的；指纹与现在的审阅登记不同就不用，
     如 s47 是 07:18 重新审阅登记之前 03:40 做的样片）
  ③ 以前运行留下、还没过期的 artifact cet6-chalk-<篇目>（最新的优先）：某几篇失败、修好后只重跑那几篇时，其余的不用重做
每一个都核对：核查结果全部通过、指纹 = 截图审阅登记（截图审阅通过.json）的指纹（登记之后程序、样式、数据都没改过）、体积与核查时相同、≤ 95 MB；
artifact 另核 sha256 和 verify_all 结果。

打包用 Python zipfile（不压缩，ZIP_STORED）：Info-ZIP 的 zip -0 不给中文文件名打 UTF-8 标记（本机实测 flag_bits=0），
Python zipfile 读出来是乱码，中文 Windows 解压也会乱码；Python 写的 zip 对非 ASCII 文件名自动打 UTF-8 标记。
打完逐个核对（踩坑 43：一律用 Python zipfile）：文件名与顺序、不压缩、每个文件大小、CRC（testzip）、每包 < 2 GB（Release 单个附件上限）。

环境变量：TAG（运行标签，以 test 开头 = 试跑：缺的、不能用的篇目只提示，用现有的打包核对，不发布；本次生成的核对不通过一律报错）、GITHUB_REPOSITORY、GITHUB_RUN_ID、GH_TOKEN。
输出：videos/、CET6-chalkboard-videos-partN-of-M.zip、zips.txt、notes.md、timing.md（本次每篇用时）。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

TAG = os.environ['TAG']
TEST = TAG.startswith('test')
REPO = os.environ['GITHUB_REPOSITORY']
RUN = os.environ.get('GITHUB_RUN_ID', '')
LIMIT = 95 * 2**20
MAN = json.loads(Path('manifest/manifest.json').read_text('utf-8'))
PROJECT = os.environ.get('PROJECT', '六级')
CFG = {
    '六级': {'look': '3', 'work': '样片', 'videos': '最终视频_黑板', 'art': 'cet6-chalk', 'zip': 'CET6-chalkboard-videos', 'n': 60,
             'head': ['大学英语六级 仔细阅读（Section C）逐句精读视频 · 教室黑板大字版，共 {n} 个（分 {parts} 个压缩包，每包 20 个，解压即可）。',
                      '4K（3840×2160）、30 帧/秒恒定；英文 Inter 加粗、中文黑体，生词黄色、短语粉色；男声朗读（已去电磁音），句与句之间停顿 0.8 秒；每个视频 ≤ 95 MB。']},
    '专八': {'look': '1', 'work': '大字版', 'videos': '最终视频_校园', 'art': 'tem8-campus', 'zip': 'TEM8-campus-videos', 'n': 10,
             'head': ['英语专业八级 阅读理解（Section A）逐句精读视频 · 晴空校园大字版，共 {n} 个（{parts} 个压缩包，解压即可）。',
                      '4K（3840×2160）、30 帧/秒恒定；片头 985 教学楼；英文全部加粗，生词晴空蓝、短语草绿（黄色底纹）；男声朗读（已去电磁音），句与句之间停顿 0.8 秒；每个视频 ≤ 95 MB。']},
    '考研': {'look': '1', 'work': '大字版', 'videos': '最终视频_校园', 'art': 'kaoyan-campus', 'zip': 'KAOYAN-campus-videos', 'n': 48,
             'head': ['考研英语（英语一、英语二）阅读理解 Part A（Text 1—4，2021—2026 年）逐句精读视频 · 晴空校园大字版，共 {n} 个（分 {parts} 个压缩包，每包 20 个，解压即可）。',
                      '4K（3840×2160）、30 帧/秒恒定；片头 985 教学楼；英文、中文全部加粗，生词晴空蓝、短语草绿（黄色底纹）；男声朗读（已去电磁音），句与句之间停顿 0.8 秒；每个视频 ≤ 95 MB。']},
}[PROJECT]
LOOK = CFG['look']
REG = json.loads(Path(f'{PROJECT}/tools/画面核查/截图审阅通过.json').read_text('utf-8'))
REP = Path(PROJECT) / CFG['work'] / '成品核查'
ART, OLD, VID = Path('artifacts'), Path('old-artifacts'), Path('videos')
VID.mkdir(exist_ok=True)


def sha256(f):
    h = hashlib.sha256()
    with open(f, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def report_problem(pid, name, rep, size):
    """核查结果是否可用：全部通过、指纹与审阅登记相同、体积相同。返回问题（空字符串 = 可用）。"""
    if not rep.exists():
        return f'没有核查结果 {rep}'
    r = json.loads(rep.read_text('utf-8'))
    fp = REG.get(f'{pid}@{LOOK}', {}).get('指纹')
    if r.get('video') != name:
        return f'核查结果里的文件名是 {r.get("video")}'
    if not r.get('ok') or not all(c.get('ok') for c in r.get('checks', [])) or not r.get('checks'):
        return '核查结果不是全部通过'
    if not fp or r.get('指纹') != fp:
        return f'指纹 {r.get("指纹")} ≠ 截图审阅登记 {fp}（登记之后程序、样式或数据改过）'
    if r.get('size') != size:
        return f'体积 {size} ≠ 核查时 {r.get("size")}'
    if size > LIMIT:
        return f'体积 {size / 2**20:.1f} MB > 95 MB'
    return ''


def from_artifact(pid, name, d):
    f, meta = d / name, d / 'meta.json'
    if not f.exists() or not meta.exists():
        return f'{d} 里没有视频或 meta.json'
    m = json.loads(meta.read_text('utf-8'))
    if m.get('verify_all') != '全部通过':
        return 'verify_all 没有通过'
    if m.get('sha256') != sha256(f):
        return 'sha256 与生成时不同'
    why = report_problem(pid, name, d / (Path(name).stem + '_核查.json'), f.stat().st_size)
    if not why:
        shutil.move(str(f), VID / name)
    return why


def committed():
    out = subprocess.run(['git', '-c', 'core.quotepath=off', 'ls-files', '-z', '--', f'{PROJECT}/{CFG["videos"]}'],
                         capture_output=True, text=True, check=True).stdout
    return set(x for x in out.split('\0') if x)


def from_repo(pid, name):
    path = f'{PROJECT}/{CFG["videos"]}/{name}'
    with open(VID / name, 'wb') as fh:              # 稀疏检出 + blob:none：这里才按需下载这一个视频
        subprocess.run(['git', 'cat-file', 'blob', f'HEAD:{path}'], stdout=fh, check=True)
    why = report_problem(pid, name, REP / (Path(name).stem + '_核查.json'), (VID / name).stat().st_size)
    if why:
        (VID / name).unlink()
    return why


def from_old_runs(pid, name):
    """以前运行留下的 artifact（还没过期、最新的优先），逐个试，第一个核对通过的就用。返回 (来源说明, 问题列表)。"""
    r = subprocess.run(['gh', 'api', '-X', 'GET', f'repos/{REPO}/actions/artifacts', '-f', f'name={CFG["art"]}-{pid}', '-f', 'per_page=100'],
                       capture_output=True, text=True, check=True)
    arts = sorted((a for a in json.loads(r.stdout)['artifacts'] if not a['expired'] and str(a['workflow_run']['id']) != RUN),
                  key=lambda a: a['created_at'], reverse=True)
    whys = []
    for a in arts[:5]:
        d = OLD / f'{pid}-{a["id"]}'
        d.mkdir(parents=True, exist_ok=True)
        z = d / 'a.zip'
        with open(z, 'wb') as fh:
            subprocess.run(['gh', 'api', f'repos/{REPO}/actions/artifacts/{a["id"]}/zip'], stdout=fh, check=True)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(d)
        z.unlink()
        why = from_artifact(pid, name, d)
        shutil.rmtree(d, ignore_errors=True)
        if not why:
            return f'以前的运行 {a["workflow_run"]["id"]}（{a["created_at"]}）', whys
        whys.append(f'artifact {a["id"]}：{why}')
    return None, whys


def main():
    rendered = set(MAN['render'])
    tracked = committed()
    got, missing, bad, stale, timing = [], [], [], [], []
    for e in MAN['passages']:
        pid, name = e['id'], e['name']
        if pid in rendered:
            d = ART / f'{CFG["art"]}-{pid}'
            m = json.loads((d / 'meta.json').read_text('utf-8')) if (d / 'meta.json').exists() else {}
            why = from_artifact(pid, name, d)
            if why:
                bad.append(f'{pid}（本次生成）：{why}')
                continue
            got.append((pid, name, '本次生成'))
            timing.append(f'| {pid} | {m.get("秒", {}).get("截图", "")} | {m.get("秒", {}).get("视频", "")} | {m.get("秒", {}).get("verify_all", "")} '
                          f'| {m.get("size", 0) / 2**20:.1f} | {m.get("cpu", "")} |')
            continue
        whys = []
        if f'{PROJECT}/{CFG["videos"]}/{name}' in tracked:            # 仓库里的不能用（如 s47 是重新审阅登记之前做的样片）就接着找以前运行留下的
            why = from_repo(pid, name)
            if not why:
                got.append((pid, name, '仓库'))
                continue
            whys.append(f'仓库里的：{why}')
        src, old = from_old_runs(pid, name)
        if src:
            got.append((pid, name, src))
        else:
            missing.append(pid)
            stale.extend(f'{pid}：{w}' for w in whys + old)
    for pid, name, src in got:
        print(f'✅ {pid} {name}（{src}，{(VID / name).stat().st_size / 2**20:.1f} MB）', flush=True)
    for x in bad:
        print(f'❌ {x}', flush=True)
    for x in stale:
        print(f'{"⚠️" if TEST else "❌"} 不能用：{x}', flush=True)
    if missing:
        print(f'{"⚠️" if TEST else "❌"} 没有可用视频的篇目（{len(missing)} 篇）：{" ".join(missing)}', flush=True)
    if bad or (missing and not TEST):
        sys.exit('本次生成的视频核对不通过，不打包、不发布' if bad else '缺视频，不打包、不发布（标签以 test 开头才允许缺）')
    order = [e['name'] for e in MAN['passages']]
    names = [n for n in order if (VID / n).exists()]
    assert names == [n for _, n, _ in got], '顺序与篇目顺序（vocab.json）不一致'
    assert len(set(names)) == len(names), '文件名重复'
    if not TEST:
        assert names == order and len(names) == CFG['n'], f'应有 {CFG["n"]} 个，实有 {len(names)} 个'
    n = len(names)
    parts = (n + 19) // 20
    zips = []
    for p in range(parts):
        z = Path(f'{CFG["zip"]}-part{p + 1}-of-{parts}.zip')
        sl = names[p * 20:(p + 1) * 20]
        with zipfile.ZipFile(z, 'w', zipfile.ZIP_STORED, allowZip64=True) as zf:
            for x in sl:
                zf.write(VID / x, x)
        with zipfile.ZipFile(z) as zf:                     # 踩坑 43：一律用 Python zipfile 核对
            infos = zf.infolist()
            assert [i.filename for i in infos] == sl, f'{z}：文件名或顺序不对'
            for i in infos:
                assert i.flag_bits & 0x800, f'{z}：{i.filename} 没有 UTF-8 标记'
                assert i.compress_type == zipfile.ZIP_STORED, f'{z}：{i.filename} 被压缩了'
                assert i.file_size == (VID / i.filename).stat().st_size, f'{z}：{i.filename} 大小不对'
            assert zf.testzip() is None, f'{z}：CRC 不对'
        assert z.stat().st_size < 2 * 2**30, f'{z} 超过 2 GB'
        zips.append(z.name)
        print(f'📦 {z.name}：{len(sl)} 个，{z.stat().st_size / 2**20:.0f} MB，zipfile 核对通过（文件名、顺序、UTF-8 标记、不压缩、大小、CRC）', flush=True)
    Path('zips.txt').write_text('\n'.join(zips) + '\n', 'utf-8')
    lines = [CFG['head'][0].format(n=n, parts=parts), '', CFG['head'][1], '',
             '每个视频都通过了全部成品核查（分辨率、流畅度、声画等长、片头 1.5 秒 / 结尾 2 秒静音、句间停顿、响度、无电磁音、朗读与画面逐句一致、逐屏与审过的截图一致、体积），并单独复测（verify_all）。', '',
             '| # | 文件名 | 压缩包 |', '|---|---|---|']
    lines += [f'| {i} | {x} | part{(i - 1) // 20 + 1} |' for i, x in enumerate(names, 1)]
    Path('notes.md').write_text('\n'.join(lines) + '\n', 'utf-8')
    Path('timing.md').write_text('| 篇目 | 截图（秒） | 视频（秒） | verify_all（秒） | 体积（MB） | CPU |\n|---|---|---|---|---|---|\n'
                                 + '\n'.join(timing) + '\n', 'utf-8')
    print(f'共 {n} 个视频、{parts} 个压缩包' + (f'；试跑（{TAG}）：缺 {len(missing)} 篇，不发布' if TEST else ''), flush=True)


if __name__ == '__main__':
    main()
