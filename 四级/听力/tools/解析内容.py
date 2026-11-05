"""每份解析里有没有官方听力原文、听力 25 题的讲解（含答案）。只量，不判对错。
原文覆盖率：这份试卷所用录音的转写（parakeet 识别，没有时用 otter）的词 4 元组，有多少出现在解析文字里
  （转写里有考试说明和念题，所以满覆盖约 0.6—0.8；≥ 0.4 判“有”）。
讲解：第 1—25 题的英文题干（录音里念的题目，如 “What did Joe's parents decide to do?”）在解析里出现了几道。
用法：python3 解析内容.py 文字目录（每套 <年月-套>/all.txt） → 四级/听力/原始材料/解析内容.json"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; H = ROOT / '四级/听力'
def words(t): return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", t.lower().replace('’', "'"))
def grams(ws): return set(zip(ws, ws[1:], ws[2:], ws[3:]))
dz = json.loads((H / '对照.json').read_text('utf-8'))
def rec_words(rid):
    f = H / '识别' / rid / '识别.json'
    if f.exists(): return [w[0] for w in json.loads(f.read_text())], 'parakeet'
    return words((H / 'otter' / f'{rid}.txt').read_text('utf-8')), 'otter'
out = {}
for d in sorted(Path(sys.argv[1]).iterdir()):
    f = d / 'all.txt'; p = d.name
    if not f.exists() or p not in dz.get('choice', {}): continue
    jw = words(f.read_text('utf-8', 'ignore')); jg = grams(jw)
    rw, src = rec_words(dz['choice'][p]); rw = words(' '.join(rw)); rg = grams(rw)
    cov = len(rg & jg) / max(1, len(rg))
    # 念题：录音里 “question <n>” 后面到问号的那一句；看解析里有没有这句（前 6 个词）
    txt = ' '.join(rw); stems = 0
    for m in re.finditer(r'question (?:number )?(?:\w+(?: \w+)?)\s+(what|why|how|who|where|when|which|according)((?: [a-z0-9\']+){3,6})', txt):
        g = tuple((m.group(1) + m.group(2)).split()[:5])
        if any(g == tuple(jw[i:i + len(g)]) for i in range(len(jw) - len(g))): stems += 1
    out[p] = {'录音': dz['choice'][p], '转写来源': src, '原文覆盖率': round(cov, 2), '听力原文': '有' if cov >= 0.4 else ('部分' if cov >= 0.15 else '没有'),
              '题干出现': min(stems, 25), '文字来源': 'OCR' if (d / 'ocr').exists() else '文字层'}
(H / '原始材料/解析内容.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), 'utf-8')
for k, v in out.items(): print(k, v)
