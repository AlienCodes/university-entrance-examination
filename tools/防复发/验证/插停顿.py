"""双向验证：202606-1 插作答停顿（六级/听力/tools/听力视频.gap_identical）。插入段之外必须与原音逐样本相同、插入段必须是数字 0。
    /opt/ttsenv/bin/python tools/防复发/验证/插停顿.py"""
import ast, sys
from pathlib import Path
import numpy as np
src = (Path(__file__).resolve().parents[3] / '六级/听力/tools/听力视频.py').read_text('utf-8')
fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'gap_identical')
ns = {}; exec(compile(ast.Module([fn], []), 'gap', 'exec'), ns); chk = ns['gap_identical']
rng = np.random.default_rng(0); a = rng.uniform(-0.5, 0.5, (48000, 2)); cuts = [(1000, 300), (20000, 500), (47000, 10)]


def build(a, cuts):
    out, prev = [], 0
    for k, z in cuts: out += [a[prev:k], np.zeros((z, 2))]; prev = k
    return np.concatenate(out + [a[prev:]])


bad = []
y = build(a, cuts)
for name, yy, want in [('正常', y, False), ('改原音一个样本', None, True), ('插入段里有一个非 0', None, True), ('少插一个样本', None, True)]:
    if name == '改原音一个样本': yy = y.copy(); yy[30000, 1] += 1e-6
    if name == '插入段里有一个非 0': yy = y.copy(); yy[1100, 0] = 1e-9
    if name == '少插一个样本': yy = np.delete(y, 1001, axis=0)
    got = chk(a, yy, cuts)
    ok = bool(got) == want
    print(('✅' if ok else '❌'), name, '→', got or '0 处')
    if not ok: bad.append(name)
print('插停顿双向验证', '通过' if not bad else f'失败 {bad}'); sys.exit(1 if bad else 0)
