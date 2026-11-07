"""检查一篇六级标注：python3 六级/tools/check_ann.py sNN 标注文件路径
输出 OK，或逐条列出错误（必须清零）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ann_lib  # noqa: E402

pid, path = sys.argv[1], sys.argv[2]
errs, tiers, n = ann_lib.check(pid, path)
if errs or tiers:
    print('\n'.join(errs + tiers))
    sys.exit(1)
print(f'OK  {len(ann_lib.flat(ann_lib.load_sents()[pid]))} 句，{n} 个词条')
