"""踩坑 73①：分屏定稿一次列全要人工指定的句子。去掉 t11—t27 的人工指定，必须一次列出全部 21 句、退出码 1、不写方案；
用现在的人工指定表必须退出码 0（只在临时副本上跑，不动仓库里的方案）。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

R = Path(__file__).resolve().parents[3]
src = (R / '专八/tools/分屏定稿.py').read_text('utf-8')
H = json.loads((R / '专八/tools/分屏手定_水墨.json').read_text('utf-8'))
res = []
for label, hand, want in [('去掉 t11—t27 人工指定', {p: d for p, d in H.items() if p.startswith('_') or int(p[1:]) <= 10}, 21), ('现在的人工指定表', H, 0)]:
    td = Path(tempfile.mkdtemp())
    (td / 'hand.json').write_text(json.dumps(hand, ensure_ascii=False), 'utf-8')
    shutil.copy(R / '专八/tools/分屏_水墨.json', td / 'plan.json')
    code = (src.replace("HAND = HERE / (f'分屏手定_{VAR}.json' if VAR else '分屏手定.json')", f"HAND = Path({str(td / 'hand.json')!r})")
               .replace("PLAN = HERE / (f'分屏_{VAR}.json' if VAR else '分屏.json')", f"PLAN = Path({str(td / 'plan.json')!r})")
               .replace("HERE = Path(__file__).resolve().parent", f"HERE = Path({str(R / '专八/tools')!r})"))
    (td / 'x.py').write_text(code, 'utf-8')
    r = subprocess.run([sys.executable, str(td / 'x.py'), str(R / '专八/大字版水墨/分屏方案_t11-t27.json')] + [f't{i}' for i in range(11, 28)],
                       capture_output=True, text=True, env=dict(os.environ, DZB_VARIANT='水墨'))
    n = sum(1 for x in r.stdout.splitlines() if x.startswith('  t'))
    good = (r.returncode == 1 and n == want) if want else r.returncode == 0
    res.append(good)
    print(f"{'✅' if good else '❌'} {label}：退出码 {r.returncode}，列出 {n} 句（应 {want}）")
    shutil.rmtree(td)
print('分屏定稿：双向通过' if all(res) else '分屏定稿：不通过')
sys.exit(0 if all(res) else 1)
