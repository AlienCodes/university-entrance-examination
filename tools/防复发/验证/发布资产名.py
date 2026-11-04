"""双向验证（踩坑 123）：Release 资产名里的中文会被 GitHub 去掉（2018年12月…mp4 → 2018.12.1.mp4），之后按中文名下载 no assets match。
① .github/cet6-listening-publish.py --自检：ASCII 名 0 处，中文名、空格、重名都报；
② 六级听力发布工作流用这个程序发布（不再直接上传 meta 里的中文 mp4 名）；把旧写法放回去必须报。
    python3 tools/防复发/验证/发布资产名.py"""
import subprocess, sys
from pathlib import Path
R = Path(__file__).resolve().parents[3]
bad = []
p = subprocess.run([sys.executable, str(R / '.github/cet6-listening-publish.py'), '--自检'], capture_output=True, text=True)
print(p.stdout.strip()); bad += [] if p.returncode == 0 else ['发布程序自检']
OLD = 'gh release upload $TAG "$d"/*.mp4'


def wf_problems(s):
    out = []
    if 'cet6-listening-publish.py plan' not in s: out.append('发布没走 cet6-listening-publish.py plan')
    if 'cet6-listening-publish.py verify' not in s: out.append('下载核对没走 cet6-listening-publish.py verify')
    if OLD in s or "/*.mp4 --clobber" in s: out.append('直接上传 meta 里的中文 mp4 名')
    return out


s = (R / '.github/workflows/render-cet6-listening.yml').read_text('utf-8')
for name, txt, want in [('工作流 现在', s, False), ('放回旧写法', s.replace('cet6-listening-publish.py plan', 'x') + '\n' + OLD, True)]:
    got = wf_problems(txt); ok = bool(got) == want
    print(('✅' if ok else '❌'), name, '→', got or '0 处')
    if not ok: bad.append(name)
print('发布资产名双向验证', '通过' if not bad else f'失败 {bad}'); sys.exit(1 if bad else 0)
