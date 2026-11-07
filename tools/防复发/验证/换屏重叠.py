"""双向验证 踩坑 126（六级听力精读 mode=video 运行 41922681259：成品核查两项系统性不过，视频本身对）：
① 换屏在两句之间（原音）：raw6 音轨里两句之间没有低于门限的停顿时，上一句的 end 与下一句的 start 互相伸进对方（≤ 0.3 秒，都在两句的词之间），
   引擎把换屏放在重叠里，旧检查要求 end ≤ 换屏 ≤ start，永远不过（30 套 2741 处）。
   - 旧检查（提交 0f9b2a9）在 30 套真实时间轴上必须报出（> 2000 处），新检查 0 处；
   - 新检查对放错的换屏照样报：落在重叠之前 0.1 秒、之后 0.1 秒、没有重叠时早于上一句读完；
② 成品体积：六级听力 22 分钟 4K 约 330 MB，旧上限 95 MB（成品进 git 的项目）一律不过 → 引擎 PROJECTS['六级听力']['max_mb'] 与打包程序的上限同值，
   且 ≤ 每包上限 < 2 GB；别的项目仍是 95 MB。

    /opt/ttsenv/bin/python tools/防复发/验证/换屏重叠.py
"""
import ast
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / '专八' / 'tools'))
import make_video as M  # noqa: E402

M.set_project('六级听力')
errs = []


def old_cut_check():
    src = subprocess.run(['git', 'show', '0f9b2a9:专八/tools/make_video.py'], capture_output=True, text=True, check=True).stdout
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'cut_check')
    g = {}
    exec(compile(ast.Module([node], []), 'old', 'exec'), g)
    return g['cut_check']


def engine_cuts(S):
    """与引擎 render 里原音句间换屏同一公式（停顿 ≥ 0.8 秒读完停 0.5 秒，更短按 0.5/0.8 比例）。"""
    cuts, owner = [], []
    for i in range(1, len(S)):
        e, s = S[i - 1]['end'], S[i]['start']
        g = s - e
        cuts.append(e + (0.5 if g >= 0.8 else g * 0.5 / 0.8))
        owner.append((i, 0, None))
    return cuts, owner


OLD = old_cut_check()
T = json.loads((ROOT / '六级/听力/精读/audio/timings.json').read_text('utf-8'))['cet4_male']
n_old = n_new = 0
for pid, tm in sorted(T.items()):
    S = tm['sentences']
    cuts, owner = engine_cuts(S)
    n_old += len(json.loads(OLD(cuts, owner, S, 0)[2].split('第 ', 1)[1].rsplit(' 句', 1)[0])) if not OLD(cuts, owner, S, 0)[1] else 0
    r = M.cut_check(cuts, owner, S, 0)
    if not r[1]:
        n_new += 1
        errs.append(f'① 新检查在 {pid} 的真实时间轴上报 {r[2][:80]}')
if n_old < 2000:
    errs.append(f'① 旧检查在 30 套真实时间轴上应报 > 2000 处，实际 {n_old}')

S = [{'start': 0.0, 'end': 2.0}, {'start': 1.8, 'end': 4.0}, {'start': 5.0, 'end': 7.0}]       # 第 1、2 句重叠 0.2 秒；第 2、3 句之间停 1 秒
own = [(1, 0, None), (2, 0, None)]
for cuts, want in [([1.9, 4.5], True), ([1.7, 4.5], False), ([2.1, 4.5], False), ([1.9, 3.9], False), ([1.9, 5.1], False)]:
    if M.cut_check(cuts, own, S, 0)[1] != want:
        errs.append(f'① 人造时间轴 换屏 {cuts}：应{"通过" if want else "报出"}，实际相反')

mx = M.PJ.get('max_mb')
P = {}
exec(compile(ast.Module([n for n in ast.parse((ROOT / '.github/cet6-listening-text-pack.py').read_text('utf-8')).body
                         if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'CFG'], []), 'pack', 'exec'),
     {'PROJECT': '六级听力'}, P)
cfg = P['CFG']
if not mx or mx != cfg.get('max_mb') or not cfg.get('zip_mb') or mx > cfg['zip_mb'] or cfg['zip_mb'] >= 2048:
    errs.append(f'② 体积上限不一致：引擎 {mx}，打包 {cfg.get("max_mb")}，每包 {cfg.get("zip_mb")}（要求相等、≤ 每包、每包 < 2048 MB）')
M.set_project('六级')
if M.PJ.get('max_mb', 95) != 95:
    errs.append('② 六级阅读的体积上限应仍是 95 MB')
src = (ROOT / '专八/tools/make_video.py').read_text('utf-8')
if "PJ.get('max_mb', 95)" not in src or "'成品体积 ≤ 95 MB', size <= 95 * 2**20" in src:
    errs.append('② 引擎的成品体积检查没有按项目取上限')

print('\n'.join(errs) or f'换屏重叠 / 体积上限 双向验证通过：旧检查在 30 套报 {n_old} 处、新检查 0；人造错位 4 种都报；体积上限 {mx} MB（引擎 = 打包 ≤ 每包 {cfg["zip_mb"]} MB）')
sys.exit(1 if errs else 0)
