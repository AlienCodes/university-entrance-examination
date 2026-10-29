"""发布前核对音频合格证（踩坑 87；只用标准库，发布工作流不用装 numpy）。
    python3 .github/check-audio-cert.py <音频目录>...        # 如 中考/audio 四级/audio audio
每个音频目录：
  ① timings.json 每一条（所有音色）都必须是旧成品（响度旧成品清单）/ 专八听力考试原声，或者带 clause-v1 合格证：
     合格证的上限是标准值、测量值都在上限内、与 timings 的测量一致，MP3 旁边有 *.loudness.json 且与之完全相同，
     MP3 在仓库里时 sha256 与合格证一致（规则在 tools/tts/合格证.py，只写一处）；
  ② 目录里的每个 MP3（git 登记的 + 磁盘上的）都必须被 timings 的某一条引用（打包的就是这些 MP3）。
视频发布：视频都是用本目录 timings 的条目生成的，全部条目合格才发布。有一处不合格就退出码 1，不发布。
    python3 .github/check-audio-cert.py --自检              # 双向验证（造一个临时音频目录：合格 0 处，各种不合格都报出）"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'tts'))
import 合格证 as C  # noqa: E402

# 已知的、没被 timings 引用的旧文件（不会被打包；只许减少）：路径 → 理由
ORPHANS = {
    '考研作文/audio/cet4_male/w02_2026年考研英语一_写作PartB.mp3': 'w02 改名（写作_PartB）前的旧文件，2026-10-29 核对时发现，没有发布工作流打包它',
}


def git_mp3s(d):
    try:
        out = subprocess.run(['git', '-c', 'core.quotepath=off', 'ls-files', '-z', '--', str(d)], cwd=ROOT,
                             capture_output=True, check=True).stdout.decode('utf-8').split('\0')
        return {ROOT / x for x in out if x.lower().endswith('.mp3')}
    except (OSError, subprocess.CalledProcessError):
        return set()


def git_blob(path):
    try:
        rel = Path(path).resolve().relative_to(ROOT).as_posix()
        return subprocess.run(['git', 'show', f'HEAD:{rel}'], cwd=ROOT, capture_output=True, check=True).stdout
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def mp3_problems(tm, mp3, ci=False):
    """MP3 在磁盘上：核旁证 + sha256。不在（本机按需下载 / GitHub 自检不检出 MP3）：本机从 git 取回再核；ci=True 只核旁证 JSON。"""
    if Path(mp3).exists():
        return C.problems(tm, mp3)
    side = C.sidecar_of(mp3)
    if not side.exists():
        return C.problems(tm) + [f'缺少合格证文件 {side.name}']
    data = None if ci else git_blob(mp3)
    if data is None and not ci:
        return C.problems(tm, sidecar=json.loads(side.read_text('utf-8'))) + [f'找不到 MP3 {Path(mp3).name}（磁盘和 git 里都没有），无法核对 sha256']
    return C.problems(tm, sidecar=json.loads(side.read_text('utf-8')), mp3_bytes=data)


def check_dir(d, ci=False):
    d = Path(d)
    if not d.is_absolute():
        d = ROOT / d
    tp = d / 'timings.json'
    if not tp.exists():
        return [f'{d}：没有 timings.json']
    errs, used = [], set()
    for v, pid, tm in C.timings_entries(json.loads(tp.read_text('utf-8'))):
        mp3 = d / tm['file']
        used.add(mp3.resolve())
        e = [] if C.is_legacy(tm) else mp3_problems(tm, mp3, ci)
        errs += [f'{d.name}/{v}/{pid}（{tm["file"]}）：{x}' for x in e]
    for m in sorted(git_mp3s(d) | set(d.rglob('*.mp3'))):
        if m.resolve() not in used and not (m.is_relative_to(ROOT) and m.relative_to(ROOT).as_posix() in ORPHANS):
            errs.append(f'{m.relative_to(d) if m.is_relative_to(d) else m}：timings.json 里没有这个 MP3 的条目（来路不明，不许打包）')
    return errs


def selftest():
    """双向验证：用合格证.py 的规则造一个临时目录。"""
    import hashlib
    bad = []

    def case(name, errs, want):
        ok = (not errs) if want is None else any(want in e for e in errs)
        print(f"  {'✅' if ok else '❌'} {name}：{errs[:2] or '0 处'}")
        if not ok:
            bad.append(name)

    mp3 = b'ID3' + bytes(range(256)) * 20
    L = {'integrated_lufs': -16.02, 'sentence_max_dev_lu': 1.1, 'short_term_std_lu': 0.6, 'peak_dbfs': -1.6,
         'clause_nb_min_lu': -0.9, 'clause_tail_min_db': -2.5}
    cert = {'chain': C.CHAIN, 'passed': True, 'mp3_sha256': hashlib.sha256(mp3).hexdigest(), 'loudness': L,
            'limits': dict(C.STD_LIMITS), 'date': '2026-10-29'}
    tm = {'file': 'v/x.mp3', 'duration': 9.9, 'loudness': L, 'clause_check': C.CHAIN, 'certificate': cert, 'sentences': []}

    def build(td, tm=tm, side=cert, data=mp3, extra=False, ci=False):
        d = Path(td) / 'audio'
        (d / 'v').mkdir(parents=True)
        if data is not None:
            (d / 'v' / 'x.mp3').write_bytes(data)
        if side is not None:
            (d / 'v' / 'x.loudness.json').write_text(json.dumps(side), 'utf-8')
        if extra:
            (d / 'v' / '别的.mp3').write_bytes(b'x')
        (d / 'timings.json').write_text(json.dumps({'cet4_male': {'a01': tm}}), 'utf-8')
        return check_dir(d, ci)

    def run(name, want, **kw):
        with tempfile.TemporaryDirectory() as td:
            case(name, build(td, **kw), want)

    run('合格的新音频 → 0', None)
    run('没有合格证（旧处理链）→ 报', '不是当前处理链', tm={k: v for k, v in tm.items() if k not in ('clause_check', 'certificate')})
    mini = {'chain': C.CHAIN, 'passed': True}
    run('手写最小合格证 → 报', '缺少测量值', tm=dict(tm, certificate=mini), side=mini)
    hi = dict(cert, loudness=dict(L, clause_nb_min_lu=-1.9))
    run('合格证里写超标值 → 报', '超标', tm=dict(tm, certificate=hi, loudness=hi['loudness']), side=hi)
    run('旁证 passed=False、timings 写 True → 报', '不一致', side=dict(cert, passed=False))
    run('上限被改宽 → 报', '不是标准值', tm=dict(tm, certificate=dict(cert, limits=dict(C.STD_LIMITS, clause_nb=9))),
        side=dict(cert, limits=dict(C.STD_LIMITS, clause_nb=9)))
    run('缺合格证文件 → 报', '缺少合格证文件', side=None)
    run('MP3 检查后被改过 → 报', '被改过', data=mp3[:-5] + b'00000')
    run('目录里有没登记的 MP3 → 报', '来路不明', extra=True)
    run('GitHub 上没检出 MP3（--ci）：只核旁证 → 0', None, data=None, ci=True)
    run('GitHub 上没检出 MP3（--ci）、旁证 passed=False → 报', '不一致', data=None, ci=True, side=dict(cert, passed=False))
    run('本机磁盘和 git 里都没有 MP3 → 报', '找不到 MP3', data=None)
    run('自己写 source=原音 → 报', '不是当前处理链', tm={'file': 'v/x.mp3', 'source': '原音', 'duration': 1, 'sentences': [{'parts': []}]})
    # 命令行退出码（协调会话复核补）：发布工作流靠退出码停下，不合格必须非 0、合格必须 0
    for name, want_bad, kw in (('命令行：不合格的目录 → 退出码非 0', True, {'side': dict(cert, passed=False)}), ('命令行：合格的目录 → 退出码 0', False, {})):
        with tempfile.TemporaryDirectory() as td:
            build(td, **kw)
            rc = subprocess.run([sys.executable, str(Path(__file__).resolve()), str(Path(td) / 'audio')], capture_output=True, text=True).returncode
        ok = (rc != 0) == want_bad
        print(f"  {'✅' if ok else '❌'} {name}：退出码 {rc}")
        if not ok:
            bad.append(name)
    if bad:
        sys.exit(f'check-audio-cert 自检失效：{bad}')
    print('check-audio-cert 自检：全部通过')


def main():
    args = sys.argv[1:]
    if args == ['--自检']:
        return selftest()
    if not args:
        sys.exit(__doc__)
    ci = '--ci' in args
    errs = [e for d in args if d != '--ci' for e in check_dir(d, ci)]
    for e in errs[:50]:
        print('❌', e)
    if errs:
        sys.exit(f'音频合格证核对未通过（{len(errs)} 处），不发布')
    print(f'音频合格证核对通过：{" ".join(x for x in args if x != "--ci")}')


if __name__ == '__main__':
    main()
