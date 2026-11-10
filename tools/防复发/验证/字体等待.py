"""双向验证 + 检查：听力引擎等网页字体不许用 wait_for_function（踩坑 130）。
高考听力 GitHub precheck（run 42918571749）2019-shc、2019-xkb3、2020-shc 在 layout 里
pg.wait_for_function('document.fonts.status === "loaded"') 超时 30 秒；本机实测卡住时 document.fonts.status 早已是 loaded，
慢的是 wait_for_function 本身（偶尔 3—11 秒，GitHub 上 > 30 秒）。改成专八底座 fonts_loaded(pg)：
evaluate 等 document.fonts.ready、再核状态 = loaded（版式结果逐套不变，一套 layout 从 3—4 分钟降到约 1 分钟）。
  ① 专八底座与高考听力引擎里不许出现 wait_for_function 等字体；底座必须有 fonts_loaded 且用 document.fonts.ready；
  ② 旧写法（5ba6f7d 的两个文件）必须报出，现在 0 处。
    python3 tools/防复发/验证/字体等待.py"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILES = ['专八/听力/tools/听力视频.py', '高考听力/tools/听力视频.py']
BAD = re.compile(r"""wait_for_function\(\s*['"][^'"]*document\.fonts\.status""")


def problems(texts):
    out = []
    for name, t in texts.items():
        for n, line in enumerate(t.splitlines(), 1):
            if BAD.search(line) and not line.lstrip().startswith('#'):
                out.append(f'{name}:{n}：用 wait_for_function 等字体（改用底座 fonts_loaded）')
    base = texts.get(FILES[0], '')
    m = re.search(r'\ndef fonts_loaded\(pg\):(.*?)\n(?=\S)', base, re.S)
    if not m or 'document.fonts.ready' not in m.group(1) or "'loaded'" not in m.group(1):
        out.append(f'{FILES[0]}：缺 fonts_loaded（evaluate document.fonts.ready 并核 loaded）')
    return out


def main():
    now = {f: (ROOT / f).read_text('utf-8') for f in FILES}
    old = {f: subprocess.run(['git', '-C', str(ROOT), 'show', f'5ba6f7d:{f}'], capture_output=True, text=True, check=True).stdout
           for f in FILES}
    pn, po = problems(now), problems(old)
    print(f'旧写法（5ba6f7d）{len(po)} 处（应 ≥ 5），现在 {len(pn)} 处（应 0）')
    for p in pn: print('  ', p)
    sys.exit(0 if len(po) >= 5 and not pn else 1)


if __name__ == '__main__':
    main()
