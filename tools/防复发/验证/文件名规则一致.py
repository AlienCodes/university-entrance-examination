"""踩坑 108：各项目 verify_all.py 的成品文件名规则必须与引擎 PROJECTS 里同项目的 name_re 一致（规则只写一处）。

高考续写精读的 verify_all.py 由考研复制，文件名正则还是考研的，把正确的“2026 新课标Ⅰ卷 读后续写 …mp4”判成不合格（GitHub 试跑 x01 查出）；
同一个坑在考研、六级作文、四级作文复制时已经犯过（注释“由专八复制时漏改了文件名规则”）。

检查（纯 AST，不 import 引擎）：凡目录对应引擎 PROJECTS 里某个项目的 */tools/verify_all.py，里面的 re.fullmatch 文件名判断
要么直接用引擎的 PJ['name_re']，要么字面正则 = 该项目的 name_re；找不到文件名判断也报。中考、四级用各自的旧引擎，不在 PROJECTS 里，不查。

双向验证：现在的仓库 0 处；把考研式正则放回高考续写精读（= 修之前的写法）报出；把 PJ['name_re'] 换成别的项目的 name_re 报出；
删掉文件名判断报出；旧正则把 x01 的正确文件名判错、引擎 name_re 判对、考研式文件名被引擎 name_re 拒绝。
    python3 tools/防复发/验证/文件名规则一致.py            # 自检（双向验证）
"""
import ast
import re
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
warnings.filterwarnings('ignore', category=SyntaxWarning)      # 被解析的源码里旧写法的 '\S' 转义，不是本检查的事
ENGINE = ROOT / '专八' / 'tools' / 'make_video.py'


def projects(src):
    """引擎源码里 PROJECTS 字典：{项目: (目录, name_re)}。"""
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PROJECTS' for t in node.targets):
            out = {}
            for k, v in zip(node.value.keys, node.value.values):
                name = ast.literal_eval(k)
                d = {ast.literal_eval(kk): vv for kk, vv in zip(v.keys, v.values) if kk is not None}
                out[name] = (ast.literal_eval(d['dir']) if 'dir' in d else name,
                             ast.literal_eval(d['name_re']) if 'name_re' in d else None)
            return out
    raise SystemExit('引擎里找不到 PROJECTS')


def _is_pj_name_re(node):
    return (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'PJ'
            and isinstance(node.slice, ast.Constant) and node.slice.value == 'name_re')


def problems(engine_src, files):
    """files：{verify_all 所在项目目录（相对仓库根，如 '高考续写/精读'）: 源码}。返回问题列表，空 = 合格。"""
    P = projects(engine_src)
    bydir = {d: (name, rx) for name, (d, rx) in P.items()}
    out = []
    for d, src in sorted(files.items()):
        if d not in bydir:
            continue
        name, rx = bydir[d]
        calls = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == 'fullmatch' and isinstance(n.func.value, ast.Name) and n.func.value.id == 're' and n.args]
        if not calls:
            out.append(f'{d}/tools/verify_all.py：找不到文件名判断 re.fullmatch（项目 {name}）')
        for c in calls:
            a = c.args[0]
            if _is_pj_name_re(a):
                continue
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                if a.value != rx:
                    out.append(f'{d}/tools/verify_all.py 第 {c.lineno} 行：文件名正则 {a.value!r} ≠ 引擎 PROJECTS[{name!r}][\'name_re\'] {rx!r}')
                continue
            out.append(f'{d}/tools/verify_all.py 第 {c.lineno} 行：文件名正则既不是 PJ[\'name_re\'] 也不是字面正则，无法核对')
    return out


def repo_files():
    return {str(f.parent.parent.relative_to(ROOT)): f.read_text('utf-8') for f in ROOT.glob('**/tools/verify_all.py')
            if '.git' not in f.parts}


def selftest():
    eng = ENGINE.read_text('utf-8')
    files = repo_files()
    P = projects(eng)
    bad = []
    now = problems(eng, files)
    print(('  ✅' if not now else '  ❌'), '现在的仓库：', now or '0 处')
    bad += now
    xu = files['高考续写/精读']
    ky_rx = P['考研'][1]
    assert "re.fullmatch(PJ['name_re'], mp4.name)" in xu, '高考续写精读 verify_all 应直接用 PJ[\'name_re\']'
    cases = {
        '放回考研式正则（修之前的写法）': xu.replace("re.fullmatch(PJ['name_re'], mp4.name)", f're.fullmatch({ky_rx!r}, mp4.name)'),
        '换成六级的 name_re': xu.replace("re.fullmatch(PJ['name_re'], mp4.name)", f're.fullmatch({P["六级"][1]!r}, mp4.name)'),
        '删掉文件名判断': xu.replace("re.fullmatch(PJ['name_re'], mp4.name)", 'True'),
        '考研 verify_all 正则改一个字': ('考研', files['考研'].replace('Text [1-4]', 'Text [1-3]', 1)),
    }
    for label, src in cases.items():
        d, s = src if isinstance(src, tuple) else ('高考续写/精读', src)
        r = problems(eng, {**files, d: s})
        ok = bool(r)
        print(('  ✅' if ok else '  ❌'), label, '→', '报出' if ok else '没报出', r[:1])
        if not ok:
            bad.append(label)
    good = '2026 新课标Ⅰ卷 读后续写 雪夜被困获好心夫妇相助.mp4'
    good_latin = '2026 新课标I卷 读后续写 雪夜被困获好心夫妇相助.mp4'
    kyname = '2026年考研英语一 Text 1 雪夜被困获好心夫妇相助.mp4'
    xrx = P['高考续写'][1]
    checks = [('旧正则把 x01 的正确文件名判错', not re.fullmatch(ky_rx, good)),
              ('引擎 name_re 判对 x01 文件名（Ⅰ 与拉丁 I）', bool(re.fullmatch(xrx, good)) and bool(re.fullmatch(xrx, good_latin))),
              ('考研式文件名被引擎 name_re 拒绝', not re.fullmatch(xrx, kyname))]
    for label, ok in checks:
        print(('  ✅' if ok else '  ❌'), label)
        if not ok:
            bad.append(label)
    print('文件名规则一致 双向验证：' + ('全部通过' if not bad else f'失败：{bad}'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(selftest())
