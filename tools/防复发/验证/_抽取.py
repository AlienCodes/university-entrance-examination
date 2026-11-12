"""从源文件里只抽出要测的函数和常量（不 import 整个模块，免得拉进语音模型等重依赖；测的是仓库里真正在用的那份代码）。"""
import ast
from pathlib import Path

R = Path(__file__).resolve().parents[3]


def load(rel, names, g=None):
    src = (R / rel).read_text('utf-8')
    tree = ast.parse(src)
    keep = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names:
            keep.append(n)
        elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets):
            keep.append(n)
    found = {getattr(n, 'name', None) or n.targets[0].id for n in keep}
    miss = set(names) - found
    if miss:
        raise SystemExit(f'{rel} 里找不到 {sorted(miss)}（函数改名或搬家了？双向验证要跟着改）')
    ns = dict(g or {})
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(R / rel), 'exec'), ns)
    return ns
