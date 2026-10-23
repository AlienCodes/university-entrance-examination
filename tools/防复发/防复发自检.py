"""防复发自检（用户 2026-10-23：“要有一个机制，保证踩过的坑不能再踩；方法要不断进化”）。

    python3 tools/防复发/防复发自检.py               # 登记核对 + 复盘核对（不到 1 秒；提交前钩子自动跑）
    python3 tools/防复发/防复发自检.py --测试        # 再跑全部双向验证（埋雷）测试，heavy 的除外（几分钟）
    python3 tools/防复发/防复发自检.py --测试 --全部  # 连 heavy 的一起跑（截图回归，十几分钟）
    python3 tools/防复发/防复发自检.py --更新基线     # 补上缺口后，把“没有测试的旧坑”基线调低（只许调低）

机制（tools/防复发/README.md 有完整说明）：
1. 踩坑登记.json：CLAUDE.md 踩坑表的每一行都要登记（阶段、哪段程序拦住、双向验证命令、状态、缺口）。表里出现没登记的行 → 失败。
2. 从踩坑 72 起（防复发机制建立之后）新增的坑，必须带双向验证命令（故意把这个错误放回去，检查必须报出来）→ 没有就失败。
   72 以前的旧坑里没有测试的，数量记在基线里，只许减少、不许增加（每补一条测试就 --更新基线）。
3. --测试：逐条跑双向验证命令，任何一条失效（检查不再报出埋的雷）→ 失败。改了任何检查程序都要跑。
4. 复盘：每个项目的生成清单（.github/*-render.txt 第一行标签）换新批次时，上一批必须在 方法进化记录.md 里有“## 复盘 <标签>”
   （返工统计、根因、新增的检查、方法改进），否则失败——上一批不复盘，下一批不能开工。"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[2]
D = R / 'tools' / '防复发'
REG = D / '踩坑登记.json'
LOG = D / '方法进化记录.md'
NEW_FROM = 72                     # 从这一条起，新坑必须带双向验证


def tests(r):
    t = r.get('test') or []
    return [x for x in (t if isinstance(t, list) else [t]) if x.get('cmd')]


def table_ids():
    ids = []
    for line in (R / 'CLAUDE.md').read_text('utf-8').splitlines():
        m = re.match(r'\|\s*(\d+[a-z]?)\s*\|', line)
        if m:
            ids.append(m.group(1))
    return ids


def num(i):
    return int(re.match(r'\d+', i).group(0))


def check_registry(reg):
    errs = []
    rows = {r['id']: r for r in reg['rows']}
    ids = table_ids()
    for i in ids:
        if i not in rows:
            errs.append(f'踩坑 {i} 在 CLAUDE.md 里，却没在 踩坑登记.json 登记（要写：哪个阶段、哪段程序拦住、双向验证命令）')
        elif num(i) >= NEW_FROM and not tests(rows[i]) and rows[i].get('status') != '已不适用':
            errs.append(f'踩坑 {i} 是防复发机制建立之后的新坑，必须带双向验证命令（故意放回这个错误，检查必须报出来）')
    legacy = [i for i in ids if i in rows and num(i) < NEW_FROM and not tests(rows[i]) and rows[i].get('status') != '已不适用']
    base = reg.get('_没有测试的旧坑基线')
    if base is not None and len(legacy) > base:
        errs.append(f'没有双向验证的旧坑从 {base} 条增加到 {len(legacy)} 条（只许减少）')
    return errs, legacy, ids


EXEMPT = set()


def check_retro():
    """每个生成清单换批次时，上一批要有复盘。"""
    errs, text = [], LOG.read_text('utf-8') if LOG.exists() else ''
    for f in sorted((R / '.github').glob('*-render.txt')):
        rel = str(f.relative_to(R))
        revs = subprocess.run(['git', '-C', str(R), 'log', '--format=%H', '--', rel], capture_output=True, text=True).stdout.split()
        tags = []
        for h in reversed(revs):
            first = subprocess.run(['git', '-C', str(R), 'show', f'{h}:{rel}'], capture_output=True, text=True).stdout.split('\n', 1)[0].strip()
            if first and not first.startswith('#') and first not in tags:
                tags.append(first)
        cur = f.read_text('utf-8').split('\n', 1)[0].strip()
        if cur and not cur.startswith('#') and cur not in tags:
            tags.append(cur)
        proj = f.stem.replace('-render', '')
        for t in tags[:-1]:
            key = f'{proj} {t}'
            if re.match(r'(test|probe)', t) or key in EXEMPT:
                continue
            if f'## 复盘 {key}' not in text:
                errs.append(f'{rel}：上一批 {t} 还没复盘（方法进化记录.md 里写“## 复盘 {key}”：返工统计、根因、新增的检查、方法改进），新批次 {tags[-1]} 不能开工')
    return errs


def run_tests(reg, heavy):
    cmds = {}
    for r in reg['rows']:
        for t in tests(r):
            if heavy or t.get('needs') != 'heavy':
                cmds.setdefault(t['cmd'], (t.get('expect') or 'exit 0', []))[1].append(r['id'])
    bad = []
    for cmd, (expect, ids) in cmds.items():
        t0 = time.time()
        p = subprocess.run(cmd, shell=True, cwd=R, capture_output=True, text=True)
        out = p.stdout + p.stderr
        ok = p.returncode == 0 if expect == 'exit 0' else (expect in out)
        print(f"  {'✅' if ok else '❌'} 踩坑 {','.join(ids)}：{cmd}（{time.time() - t0:.0f} 秒）", flush=True)
        if not ok:
            bad.append(f'踩坑 {",".join(ids)} 的双向验证失效：{cmd}\n      ' + '\n      '.join(out.strip().splitlines()[-6:]))
    return bad


def main():
    a = sys.argv[1:]
    reg = json.loads(REG.read_text('utf-8'))
    EXEMPT.update(reg.get('_复盘豁免', []))
    errs, legacy, ids = check_registry(reg)
    if '--更新基线' in a:
        old = reg.get('_没有测试的旧坑基线')
        if old is not None and len(legacy) > old:
            sys.exit(f'没有测试的旧坑 {len(legacy)} 条，比基线 {old} 多，不能调高')
        reg['_没有测试的旧坑基线'] = len(legacy)
        REG.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + '\n', 'utf-8')
        print(f'基线 {old} → {len(legacy)}')
        return
    if '--不查复盘' not in a:                       # GitHub 上是浅克隆、没有历史，复盘核对只在本机（提交前钩子）做
        errs += check_retro()
    print(f'踩坑表 {len(ids)} 条，登记 {len(reg["rows"])} 条；没有双向验证的旧坑 {len(legacy)} 条（基线 {reg.get("_没有测试的旧坑基线")}，只许减少）')
    if '--测试' in a:
        errs += run_tests(reg, '--全部' in a)
    for e in errs:
        print('❌ ' + e)
    print('防复发自检：通过' if not errs else f'防复发自检：{len(errs)} 处不通过')
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
