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
        drv = wt / '四级作文/tools/原题屏试排.py'          # 试排驱动本身不是工作流的依赖：六级作文的检出里没有，复制进去
        drv.parent.mkdir(parents=True, exist_ok=True)
        if not drv.exists():
            shutil.copy(R / '四级作文/tools/原题屏试排.py', drv)
        r = subprocess.run([PY, str(drv), proj, str(td / 'out'), pid], capture_output=True, text=True, timeout=900)
        tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or ['']
        return r.returncode, tail[0][:160]
    finally:
        subprocess.run(['git', '-C', str(R), 'worktree', 'remove', '--force', str(wt)], capture_output=True)
        shutil.rmtree(td, ignore_errors=True)


def trial_cmds(pats, cmds):
    """按检出路径建稀疏工作树，依次跑 cmds（在工作树里），返回第一个失败的（退出码, 末行）或 (0, 末行)"""
    td = Path(tempfile.mkdtemp(prefix='wfco_'))
    wt = td / 'wt'
    try:
        subprocess.run(['git', '-C', str(R), 'worktree', 'add', '-q', '--no-checkout', '--detach', str(wt), 'HEAD'], check=True)
        subprocess.run(['git', '-C', str(wt), 'sparse-checkout', 'set', '--no-cone', *pats], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(wt), 'checkout', '-q'], check=True)
        env = dict(os.environ, CET6_OUT=str(td / 'out'))
        last = ''
        for c in cmds:
            r = subprocess.run(c.replace('{TD}', str(td)), shell=True, cwd=wt, capture_output=True, text=True, timeout=900, env=env)
            last = ((r.stdout + r.stderr).strip().splitlines()[-1:] or [''])[0][:160]
            if r.returncode: return r.returncode, last
        return 0, last
    finally:
        subprocess.run(['git', '-C', str(R), 'worktree', 'remove', '--force', str(wt)], capture_output=True)
        shutil.rmtree(td, ignore_errors=True)


# 六级听力练习视频（2026-11-04 复发：稀疏检出漏了 六级/真题 的试卷文字，19 套死在关口）：关口 → 取字体 → 时间轴（假时长）→ 版式
LISTEN = ('render-cet6-listening.yml', '202606-1', '六级/真题/**/*.txt', [
    'python3 六级/听力/tools/定稿.py {S} > /dev/null', 'python3 六级/听力/tools/题目.py {S}',
    f'{PY} 专八/听力/tools/取字体.py',
    f'{PY} -c "import soundfile as sf, numpy as np; sf.write(\'{{TD}}/f.wav\', np.zeros(8000 * 2400, dtype=np.int16), 8000)"',
    f'{PY} 六级/听力/tools/听力视频.py {{S}} timeline {{TD}}/f.wav', f'{PY} 六级/听力/tools/听力视频.py {{S}} layout'])

ok = True
wf, sid, data, cmds = LISTEN
pats = patterns(wf)
cmds = [c.replace('{S}', sid) for c in cmds]
rc, msg = trial_cmds(pats, cmds)
print(f'{wf}（{sid}）按工作流的检出：退出码 {rc}  {msg}'); ok &= rc == 0
rc, msg = trial_cmds([p for p in pats if p != data], cmds)
print(f'  雷「拿掉 {data}」：退出码 {rc}  {msg}'); ok &= rc != 0
for wf, proj, pid, data in CASES:
    pats = patterns(wf)
    rc, msg = trial(pats, proj, pid)
    print(f'{wf}（{proj} {pid}）按工作流的检出：退出码 {rc}  {msg}'); ok &= rc == 0
    rc, msg = trial([p for p in pats if p != data], proj, pid)
    print(f'  雷「拿掉 {data}」：退出码 {rc}  {msg}'); ok &= rc != 0
print('自检通过' if ok else '自检失败')
sys.exit(0 if ok else 1)
