"""列出合集里每份试卷（年月-套）对应的答案解析 PDF：页数、文字层字数、文字层里有没有听力原文标记。
写 四级/听力/原始材料/解析清单.json。用法：python3 解析清单.py 合集解压目录"""
import json, re, subprocess, sys, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
CN = {'一': 1, '二': 2, '三': 3}
out = {}
for f in sorted(Path(sys.argv[1]).rglob('*.pdf')):
    if not re.search(r'解析|详解', f.name) or '一键' in f.name: continue
    m = re.search(r'(20\d\d)\s*[年.]\s*(\d{1,2})', f.name)
    k = re.search(r'第\s*(\d)\s*套|[卷第]([一二三])', f.name)
    n = k.group(1) or CN[k.group(2)] if k else 1
    key = f'{m.group(1)}{int(m.group(2)):02d}-{n}'
    t = subprocess.run(['pdftotext', str(f), '-'], capture_output=True, text=True).stdout
    pages = int(re.search(r'Pages:\s*(\d+)', subprocess.run(['pdfinfo', str(f)], capture_output=True, text=True).stdout).group(1))
    out[key] = {'原名': str(f.relative_to(Path(sys.argv[1]))).split('/', 1)[-1], 'pages': pages, 'text_chars': len(t.strip()),
                'script_marks': len(re.findall(r'(?i)news report (one|1)|conversation (one|1)|passage (one|1)|recording (one|1)', t)),
                'sha256': hashlib.sha256(f.read_bytes()).hexdigest()}
(ROOT / '四级/听力/原始材料/解析清单.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), 'utf-8')
print(len(out))
