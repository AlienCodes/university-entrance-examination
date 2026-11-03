"""双向验证（踩坑 98）：合成机中途被停时 collect 照样发布、少一个 take，下游等待脚本不能悄悄收下。
  ① 真实数据：runs/任务_续写_样片-16（2026-11-03，synth(0) exit 143，只有 take2、take3）的文件列表——
     旧写法（找到运行号就收）收下；新检查 合成齐全.missing 报出 take1；补上 take1 后 0；
  ② 续写全片.sh 的等待循环必须调用 合成齐全.py、缺了不 break。
    python3 tools/防复发/验证/合成齐全.py"""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('合成齐全', ROOT / '高考续写/tools/合成齐全.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

RUN, VOICE, TAKES = 'runs/任务_续写_样片-16', 'r2icl', [1, 2, 3]
paths = (Path(__file__).parent / '数据/合成缺take_样片16.txt').read_text('utf-8').split('\n')
bad = []
old_accepts = any(p.startswith(RUN + '/') for p in paths)          # 旧写法：运行号出现就收
miss = m.missing(paths, RUN, VOICE, TAKES)
full = m.missing(paths + [f'{RUN}/{VOICE}/take1/meta_part0.json'], RUN, VOICE, TAKES)
print(f'① 旧写法收下缺片结果：{old_accepts}（应 True）；新检查缺 {miss}（应 [take1]）；补齐后 {full}（应 []）')
if not old_accepts or miss != ['take1'] or full:
    bad.append('①')
sh = (ROOT / '高考续写/tools/续写全片.sh').read_text('utf-8')
ok = re.search(r'miss=\$\(python3 高考续写/tools/合成齐全\.py[^\n]*\n\s*\[ -z "\$miss" \] && RUN=\$r && break', sh)
print(f'② 续写全片.sh 等待循环接上检查：{bool(ok)}')
if not ok:
    bad.append('②')
print('合成齐全：' + ('失败 ' + ' '.join(bad) if bad else '通过'))
sys.exit(1 if bad else 0)
