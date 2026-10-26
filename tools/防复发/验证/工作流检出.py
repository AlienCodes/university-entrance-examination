"""踩坑 84 双向验证：GitHub 生成工作流的 sparse-checkout 必须覆盖引擎运行时读的全部目录。
做法：取工作流 render 任务的 sparse-checkout 路径，在本机按同样的路径建稀疏工作树（git worktree，当前 HEAD），在里面试排一篇原题屏
（四级作文/tools/原题屏试排.py），必须 0 处、退出码 0；再拿掉题目数据目录（/四级/作文/、/六级/作文/）重建，必须失败。
（本机完整检出时一切正常，只有 GitHub 的稀疏检出会缺目录——cet4w-2 整批 KeyError 就是这样漏过去的。）
用法：python3 tools/防复发/验证/工作流检出.py（只查已提交的 HEAD）"""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
import yaml

R = Path(__file__).resolve().parents[3]
PY = '/opt/ttsenv/bin/python'
CASES = [('render-cet4-writing.yml', '四级作文', 'c30', '/四级/作文/'), ('render-cet6-writing.yml', '六级作文', 'c31', '/六级/作文/')]


def patterns(wf):
    job = yaml.safe_load((R / '.github/workflows' / wf).read_text('utf-8'))['jobs']['render']
    for st in job['steps']:
        w = st.get('with') or {}
        if 'sparse-checkout' in w:
            return [x.strip() for x in w['sparse-checkout'].splitlines() if x.strip()]
    raise SystemExit(f'{wf} 的 render 任务没有 sparse-checkout')


def trial(pats, proj, pid):
    td = Path(tempfile.mkdtemp(prefix='wfco_'))
    wt = td / 'wt'
    try:
        subprocess.run(['git', '-C', str(R), 'worktree', 'add', '-q', '--no-checkout', '--detach', str(wt), 'HEAD'], check=True)
        subprocess.run(['git', '-C', str(wt), 'sparse-checkout', 'set', '--no-cone', *pats], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(wt), 'checkout', '-q'], check=True)
        r = subprocess.run([PY, str(wt / '四级作文/tools/原题屏试排.py'), proj, str(td / 'out'), pid], capture_output=True, text=True, timeout=900)
        tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or ['']
        return r.returncode, tail[0][:160]
    finally:
        subprocess.run(['git', '-C', str(R), 'worktree', 'remove', '--force', str(wt)], capture_output=True)
        shutil.rmtree(td, ignore_errors=True)


ok = True
for wf, proj, pid, data in CASES:
    pats = patterns(wf)
    rc, msg = trial(pats, proj, pid)
    print(f'{wf}（{proj} {pid}）按工作流的检出：退出码 {rc}  {msg}'); ok &= rc == 0
    rc, msg = trial([p for p in pats if p != data], proj, pid)
    print(f'  雷「拿掉 {data}」：退出码 {rc}  {msg}'); ok &= rc != 0
print('自检通过' if ok else '自检失败')
sys.exit(0 if ok else 1)
