"""六级作文：从 六级/真题/<年>/<年月>/*.txt 截出 Part I Writing 的题目（Directions 全文），输出草稿供逐字核对。
用法：python3 六级/tools/作文题截取.py > 草稿.txt
截不到的（txt 标题格式不同）报“截取失败”，要对照 PDF。"""
import re, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1] / '真题'
START = re.compile(r'Part\s*I\s+Writing.*?\n', re.S)
END = re.compile(r'\n\s*Part\s*(?:II|I\s*I|n|11|Il)\b[^\n]*Listening', re.S)
def key(p):
    m = re.search(r'(\d{4})年(\d+)月.*第(\d)套', p.name)
    return (int(m[1]), int(m[2]), int(m[3]))
def norm(t):
    paras = [re.sub(r'\s+', ' ', b).strip() for b in re.split(r'\n\s*\n', t)]
    return '\n\n'.join(p for p in paras if p)
for f in sorted(ROOT.glob('*/*/*.txt'), key=key, reverse=True):
    y, m, n = key(f)
    t = f.read_text(errors='replace')
    s = START.search(t); e = END.search(t, s.end()) if s else None
    print(f'=== {y}-{m:02d} 第{n}套')
    if not (s and e): print('截取失败'); continue
    print(norm(t[s.end():e.start()]))
