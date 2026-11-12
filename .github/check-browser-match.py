#!/usr/bin/env python3
"""踩坑 78：本机截图用的浏览器必须与 GitHub 上生成视频用的浏览器相同，否则截图不能逐字节重现，GitHub 上一张也对不上、整批白跑。

  python3 .github/check-browser-match.py .github/workflows/render-cet6-writing.yml      # 不一致就退出码 1
  python3 .github/check-browser-match.py 工作流.yml --local "Google Chrome for Testing 153.0.8010.12"   # 双向验证用：指定本机版本

GitHub 一侧：工作流里 cet6-chalk-env 的 browser 输入（不写 = 141）。本机一侧：/opt/pw-browsers/chromium --version。
（2026-10-26 六级作文：新容器的 /opt/pw-browsers/chromium 是 Chrome 153，环境动作默认装 Chromium 141，c30 试跑 15 屏全部对不上。）
"""
import re
import subprocess
import sys
from pathlib import Path

VERSIONS = {'141': 'Chromium 141.0.7390.37', '153': 'Google Chrome for Testing 153.0.8010.12'}


def workflow_browser(text):
    """工作流里每一处 cet6-chalk-env 用的浏览器（不写 browser = 141）。"""
    out = []
    for m in re.finditer(r'uses: \./\.github/actions/cet6-chalk-env[ \t]*\n((?:[ \t]+with:[ \t]*\n(?:[ \t]{10,}\S.*\n)+)?)', text):
        b = re.search(r"browser:\s*'?(\d+)'?", m.group(1))
        out.append(b.group(1) if b else '141')
    return out


def check(text, local):
    uses = workflow_browser(text)
    if not uses:
        return ['工作流里没有用 cet6-chalk-env']
    errs = []
    for b in sorted(set(uses)):
        want = VERSIONS.get(b)
        if want is None:
            errs.append(f'工作流的 browser={b} 不认识（只有 {"、".join(VERSIONS)}）')
        elif want not in local:
            errs.append(f'GitHub 上用 {want}（browser={b}），本机是 {local.strip()}：本机画的截图在 GitHub 上不能逐字节重现。'
                        f'把工作流的 browser 改成本机的版本（{"、".join(k for k, v in VERSIONS.items() if v in local) or "无对应，先在环境动作里加上"}）')
    if len(set(uses)) > 1:
        errs.append(f'同一个工作流里浏览器不一致：{uses}')
    return errs


def main():
    a = sys.argv[1:]
    wf = Path(a[0])
    local = a[a.index('--local') + 1] if '--local' in a else subprocess.run(['/opt/pw-browsers/chromium', '--version'], capture_output=True, text=True).stdout
    errs = check(wf.read_text('utf-8'), local)
    for e in errs:
        print('浏览器不一致：' + e)
    if not errs:
        print(f'浏览器一致：{local.strip()}')
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
