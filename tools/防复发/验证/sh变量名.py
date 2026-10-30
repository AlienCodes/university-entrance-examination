"""双向验证 + 检查：shell 脚本里的非 ASCII 变量名（踩坑 90）。
bash 只认 [A-Za-z_][A-Za-z0-9_]* 的变量名：`稿=$1` 被当成命令（command not found），`$稿` 展开成 `$` 加汉字。
高考语法填空/tools/全片.sh 曾这样写，2026-10-30 14:31 一启动就失败，从来没跑起来过。
  ① 仓库里所有 *.sh（以及工作流 run 块不查：YAML 里少见且另有步骤数比对）：赋值 `名=`、`$名`、`${名`、`local/export/read 名` 出现非 ASCII 名 → 报；
  ② 旧写法（全片.sh 修正前的那两行）必须报出，修正后的写法不报。
    python3 tools/防复发/验证/sh变量名.py"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NA = r'[^\x00-\x7f\s=$\'"`;|&(){}<>\[\]/.,:：，。]'
PATS = [re.compile(r'(?:^|[\s;&|(])((?:[A-Za-z0-9_]*' + NA + r'[A-Za-z0-9_' + NA[1:-1] + r']*))=(?!=)'),
        re.compile(r'\$\{?((?:[A-Za-z0-9_]*' + NA + r'[A-Za-z0-9_' + NA[1:-1] + r']*))'),
        re.compile(r'\b(?:local|export|read|declare)\s+(?:-\w+\s+)*((?:[A-Za-z0-9_]*' + NA + r'[^\s=]*))')]


def problems(text, name='?'):
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith('#'):
            continue
        s = re.sub(r"'[^']*'", "''", s)          # 单引号里的是字面文字
        s = re.sub(r'\s#.*$', '', s)
        for p in PATS:
            for m in p.finditer(s):
                out.append(f'{name}:{n}：非 ASCII 变量名 “{m.group(1)}”（bash 不认，改成 ASCII）')
    return out


def main():
    bad = []
    old = '稿=$1; RUN=$2; NAME=$3\n$PY x.py --稿 "$稿" --run "$RUN"\n'
    new = 'SCRIPT=$1; RUN=$2; NAME=$3\n$PY x.py --稿 "$SCRIPT" --run "$RUN"\necho "用法：<稿.json>"  # 注释里 稿=1\n'
    po, pn = problems(old), problems(new)
    print(f'② 旧写法 {len(po)} 处（应 ≥ 2），新写法 {len(pn)} 处（应 0）')
    if len(po) < 2 or pn:
        bad.append(f'双向验证：旧 {po} 新 {pn}')
    files = subprocess.run(['git', 'ls-files', '*.sh'], cwd=ROOT, capture_output=True, text=True).stdout.split('\n')
    files = [f for f in files if f]
    rep = []
    for f in files:
        p = ROOT / f
        if p.exists():
            rep += problems(p.read_text('utf-8', 'replace'), f)
    print(f'① 仓库 {len(files)} 个 .sh：{len(rep)} 处')
    for x in rep:
        print('  ✗', x)
    bad += rep
    print('sh 变量名检查', '通过' if not bad else '失败')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
