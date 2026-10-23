"""双向验证：防复发自检本身（铁律 16）。在内存里改 CLAUDE.md 的文字，核对：
多一条没登记的踩坑 / 铁律必须拦；新坑（≥ 72）没带双向验证必须拦；没有测试的旧坑 / 铁律变多必须拦；铁律登记了却从 CLAUDE.md 删了必须拦；
现在的 CLAUDE.md 与登记必须 0 处。
    python3 tools/防复发/验证/防复发自检.py"""
import copy
import importlib.util
import json
import sys
from pathlib import Path

D = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('zj', D / '防复发自检.py')
zj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zj)
reg = json.loads((D / '踩坑登记.json').read_text('utf-8'))
laws = json.loads((D / '规矩登记.json').read_text('utf-8'))
md = zj.claude_md()
bad = []


def case(name, errs, want, has=''):
    ok = bool(errs) == want and (not want or any(has in e for e in errs))
    print(f"  {'✅' if ok else '❌'} {name}（{len(errs)} 处）")
    if not ok:
        bad.append(f'{name}：{errs[:2]}')


case('现在的踩坑登记 → 0', zj.check_registry(reg, md)[0], False)
case('现在的规矩登记 → 0', zj.check_laws(laws, md)[0], False)
last_pit = md.rindex('\n| 75 |')
md_pit = md[:last_pit] + '\n| 99 | 新踩的坑 | 新做法 | 某检查 |' + md[last_pit:]
case('踩坑表多一行没登记 → 拦', zj.check_registry(reg, md_pit)[0], True, '踩坑 99')
r2 = copy.deepcopy(reg)
r2['rows'].append({'id': '99', 'title': 'x', 'test': {}, 'status': '自动拦截（无双向验证）'})
case('新坑登记了却没带双向验证 → 拦', zj.check_registry(r2, md_pit)[0], True, '必须带双向验证')
r3 = copy.deepcopy(reg)
for r in r3['rows']:
    if zj.tests(r) and zj.num(r['id']) < 72:
        r['test'] = {}
        break
case('旧坑的双向验证被删掉（基线变多）→ 拦', zj.check_registry(r3, md)[0], True, '只许减少')
md_law = md.replace('\n# 踩坑记录', '\n19. **新立的规矩。**\n\n# 踩坑记录', 1)
case('铁律多一条没登记 → 拦', zj.check_laws(laws, md_law)[0], True, '铁律 19')
md_less = md.replace('\n18. **', '\n**', 1)
case('登记的铁律从 CLAUDE.md 删了 → 拦', zj.check_laws(laws, md_less)[0], True, '已经没有')
l2 = copy.deepcopy(laws)
for r in l2['rows']:
    if zj.tests(r):
        r['test'] = []
        break
case('铁律的双向验证被删掉（基线变多）→ 拦', zj.check_laws(l2, md)[0], True, '只许减少')
print('防复发自检双向验证：' + ('全部通过' if not bad else f'{len(bad)} 处失败\n  ' + '\n  '.join(bad)))
sys.exit(1 if bad else 0)
