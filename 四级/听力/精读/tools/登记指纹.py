"""把 GitHub mode=stills 推到 cet4lt-fp 分支的截图指纹登记进 截图审阅通过.json（零 token，不从日志抄）。

    git fetch origin cet4lt-fp
    /opt/ttsenv/bin/python 四级/听力/精读/tools/登记指纹.py <运行标签> 202206-1 [202512-1 …]

只登记：分支上有这一套的指纹文件、问题 0 处、指纹 = 本机用现在的程序和数据算出的 M.fingerprint（截图之后程序或数据改过就不登记）。
有一套不能登记就退出码 1（其余照常登记）。
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
os.environ['DZB_PROJECT'] = '四级听力'
sys.path.insert(0, str(ROOT / '专八' / 'tools'))
import make_video as M  # noqa: E402

M.set_project('四级听力')
LOOK = M.PJ['look']


def main():
    tag, ids = sys.argv[1], sys.argv[2:]
    reg = json.loads(M.SAMPLE_REG.read_text('utf-8')) if M.SAMPLE_REG.exists() else {}
    bad = []
    for pid in ids:
        r = subprocess.run(['git', '-c', 'core.quotepath=false', 'show', f'FETCH_HEAD:{tag}/截图指纹_{pid}.json'],
                           cwd=ROOT, capture_output=True)
        if r.returncode:
            r = subprocess.run(['git', 'show', f'origin/cet4lt-fp:{tag}/截图指纹_{pid}.json'], cwd=ROOT, capture_output=True)
        if r.returncode:
            bad.append(f'{pid}：cet4lt-fp 分支上没有 {tag}/截图指纹_{pid}.json')
            continue
        j = json.loads(r.stdout.decode('utf-8'))
        why = ('程序检查有问题' if j['问题'] else '没有截图' if not j['截图'] else
               f'指纹 {j["指纹"]} ≠ 本机现在的 {M.fingerprint(pid, LOOK)}（截图之后程序或数据改过）' if j['指纹'] != M.fingerprint(pid, LOOK) else '')
        if why:
            bad.append(f'{pid}：{why}')
            continue
        reg[f'{pid}@{LOOK}'] = {'指纹': j['指纹'], '截图': j['截图'], '登记时间': time.strftime('%Y-%m-%d %H:%M:%S'),
                                '来源': f'GitHub {tag}（{len(j["截图"])} 屏，程序检查 0 处）'}
    M.SAMPLE_REG.write_text(json.dumps(dict(sorted(reg.items())), ensure_ascii=False, indent=1) + '\n', 'utf-8')
    print(f'已登记 {len(ids) - len(bad)} 套')
    if bad:
        print('没有登记：\n  ' + '\n  '.join(bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
