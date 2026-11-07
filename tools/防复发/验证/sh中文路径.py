"""双向验证 + 检查：git 输出的中文路径被转义（踩坑 92）。
git 默认 core.quotepath=true：ls-tree / ls-files / diff --name-only / status 输出里的中文路径变成 "\\344\\273\\273…"，
同一行再 grep 中文就永远匹配不上——样片56.sh / 用户声音.sh 等合成结果的循环因此空等（2026-10-30，结果 16:33 就到了）。
  ① 仓库里所有 *.sh：同一行里 git ls-tree / ls-files / diff --name-only / status / log --name-only 的输出用 grep 匹配非 ASCII 文字，
     却没写 -c core.quotepath=false（或 -z）→ 报；
  ② 旧写法必须报出，新写法不报。
    python3 tools/防复发/验证/sh中文路径.py"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GIT = re.compile(r'\bgit\b(?:\s+-c\s+\S+)*\s+(ls-tree|ls-files|diff\b[^|]*--name-only|status|log\b[^|]*--name-only|show\b[^|]*--name-only)')
GREP_NA = re.compile(r'\|\s*grep\b[^|]*[^\x00-\x7f]')


def problems(text, name='?'):
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith('#'):
            continue
        if GIT.search(line) and GREP_NA.search(line) and 'quotepath=false' not in line and ' -z' not in line:
            out.append(f'{name}:{n}：git 输出的中文路径默认被转义，grep 中文匹配不上（加 -c core.quotepath=false）')
    return out


def main():
    bad = []
    old = "  R=$(git ls-tree --name-only origin/gram-tts-out runs/ 2>/dev/null | grep '任务_用户声音-' | sort -V | tail -1 || true)\n"
    new = "  R=$(git -c core.quotepath=false ls-tree --name-only origin/gram-tts-out runs/ 2>/dev/null | grep '任务_用户声音-' | tail -1)\n"
    po, pn = problems(old), problems(new)
    print(f'② 旧写法 {len(po)} 处（应 1），新写法 {len(pn)} 处（应 0）')
    if len(po) != 1 or pn:
        bad.append('双向验证')
    files = [f for f in subprocess.run(['git', 'ls-files', '*.sh'], cwd=ROOT, capture_output=True, text=True).stdout.split('\n') if f]
    rep = []
    for f in files:
        if (ROOT / f).exists():
            rep += problems((ROOT / f).read_text('utf-8', 'replace'), f)
    print(f'① 仓库 {len(files)} 个 .sh：{len(rep)} 处')
    for x in rep:
        print('  ✗', x)
    bad += rep
    print('git 中文路径检查', '通过' if not bad else '失败')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
