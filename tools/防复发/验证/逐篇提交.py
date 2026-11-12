"""双向验证（踩坑 87 ①）：批量生成视频时，没通过核查的 MP4 不许被下一篇一起提交。
在临时 git 仓库里造一个假项目（假的 make_video.py / verify_all.py，不生成真视频）：
  z01：引擎把成品写进 最终视频/ 后退出码 1（提前 SystemExit / check 抛异常）；
  z02：正常通过；
  z03：引擎通过，独立核查 verify_all.py 不通过；
  开跑前 最终视频/ 里还留着上次被杀掉的半成品 z00.mp4。
旧的 batch_video.sh（提交前的版本，推送改成不推）必须重现漏洞：z02 的提交里带着 z01 / z00；
新的 tools/video/batch_commit.sh：每个提交只有这一篇的一个 MP4，z00 / z01 / z03 一个都没提交，跑完 最终视频/ 干净。
    python3 tools/防复发/验证/逐篇提交.py"""
import subprocess
import sys
import tempfile
from pathlib import Path

R = Path(__file__).resolve().parents[3]
ENGINE = '''import sys
from pathlib import Path
pid = sys.argv[1]
out = Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else Path(__file__).resolve().parents[1] / '最终视频'
out.mkdir(exist_ok=True)
(out / f'{pid}.mp4').write_bytes(pid.encode())
sys.exit(1 if pid == 'z01' else 0)
'''
VERIFY = 'import sys\nsys.exit(1 if "z03" in sys.argv[1:] else 0)\n'
OLD = '中考/tools/batch_video.sh'
# 改之前（42f6885）的 中考/tools/batch_video.sh 原文（GitHub 浅克隆取不到旧提交，所以抄在这里）
OLD_SRC = '#!/bin/bash\n# 按给定顺序逐篇生成中考 4K 视频（make_video.py 内含全部成品核查），每篇完成即提交推送（铁律 9）。\ncd "$(dirname "$0")/../.." || exit 1\nfor id in "$@"; do\n  /opt/ttsenv/bin/python 中考/tools/make_video.py "$id" || { echo "视频未通过：$id"; continue; }\n  git add 中考/最终视频 && git commit -q -m "中考视频：$id\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01Bo2nvX3EdvyJhDdDqVayNH" && git push -q -u origin claude/epic-edison-4gkcfb\ndone\necho 全部完成\n'


def git(d, *a):
    return subprocess.run(['git', '-C', str(d), '-c', 'core.quotepath=off', *a], capture_output=True, text=True, check=True).stdout


def sandbox(td, script_name, script_src):
    d = Path(td)
    git(d, 'init', '-q')
    git(d, 'config', 'user.email', 't@t')
    git(d, 'config', 'user.name', 't')
    (d / '中考' / 'tools').mkdir(parents=True)
    (d / '中考' / '最终视频').mkdir()
    (d / '中考' / 'tools' / 'make_video.py').write_text(ENGINE, 'utf-8')
    (d / '中考' / 'tools' / 'verify_all.py').write_text(VERIFY, 'utf-8')
    (d / '中考' / '最终视频' / '旧.mp4').write_bytes(b'old')
    (d / 'tools' / 'video').mkdir(parents=True)
    (d / script_name).parent.mkdir(parents=True, exist_ok=True)
    (d / script_name).write_text(script_src, 'utf-8')
    git(d, 'add', '-A')
    git(d, 'commit', '-qm', 'init')
    (d / '中考' / '最终视频' / 'z00.mp4').write_bytes(b'half')       # 上次被杀掉留下的半成品
    (d / '中考' / '最终视频' / '旧.mp4').write_bytes(b'tampered')    # 已登记的成品被改了一半
    return d


def commits(d):
    """每个提交（除 init）→ 改动的文件。"""
    out = {}
    for h in git(d, 'rev-list', 'HEAD').split()[:-1]:
        msg = git(d, 'log', '-1', '--format=%s', h).strip()
        out[msg] = sorted(x for x in git(d, 'show', '--name-only', '--format=', h).split('\n') if x)
    return out


def run_old(td):
    src = OLD_SRC.replace('/opt/ttsenv/bin/python', 'python3')
    src = src.split(' && git push')[0] + '\ndone\n' if ' && git push' in src else src
    d = sandbox(td, OLD, src)
    subprocess.run(['bash', str(d / OLD), 'z01', 'z02'], cwd=d, capture_output=True, text=True)
    return commits(d), d


def run_new(td):
    d = sandbox(td, 'tools/video/batch_commit.sh', (R / 'tools/video/batch_commit.sh').read_text('utf-8'))
    (d / OLD).write_text((R / OLD).read_text('utf-8'), 'utf-8')
    git(d, 'add', '-A')
    git(d, 'commit', '-qm', 'script')
    p = subprocess.run(['bash', str(d / OLD), 'z01', 'z02', 'z03'], cwd=d, capture_output=True, text=True,
                       env={'PATH': '/usr/bin:/bin', 'BATCH_PY': sys.executable, 'BATCH_NO_PUSH': '1', 'HOME': td})
    c = commits(d)
    c.pop('script', None)
    left = git(d, 'status', '--porcelain', '--', '中考/最终视频').strip()
    return c, left, p.returncode, p.stdout + p.stderr


def main():
    bad = []

    def case(name, ok, detail):
        print(f"  {'✅' if ok else '❌'} {name}：{detail}")
        if not ok:
            bad.append(name)

    with tempfile.TemporaryDirectory() as td:
        c, _ = run_old(td)
        leak = [f for files in c.values() for f in files if f.endswith(('z00.mp4', 'z01.mp4', '旧.mp4'))]
        case('旧 batch_video.sh：z01 没通过、z00 半成品，却被 z02 的提交一起带走 → 重现漏洞', bool(leak), c)
    with tempfile.TemporaryDirectory() as td:
        c, left, rc, out = run_new(td)
        want = {'中考视频：z02': ['中考/最终视频/z02.mp4']}
        case('新 batch_commit.sh：只有 z02 一个提交、只含 z02.mp4', c == want, c)
        case('新：z00 / z01 / z03 / 被改的旧.mp4 一个都没提交，跑完 最终视频/ 干净', not left, left or '干净')
        case('新：有篇目没通过 → 退出码非 0', rc != 0, f'退出码 {rc}')
    if bad:
        sys.exit(f'逐篇提交双向验证失效：{bad}')
    print('逐篇提交双向验证：全部通过')


if __name__ == '__main__':
    main()
