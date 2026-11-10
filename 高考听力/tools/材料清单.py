#!/usr/bin/env python3
"""高考听力材料清单：按（年份, 卷名）把音频、空白卷、解析卷、原文、otter 转写归到一套，量每份文字里有什么。
用法：python3 -I 材料清单.py <解压目录 x> <文字目录 txt>  → 打印 JSON 清单"""
import json, re, sys
from pathlib import Path

X, T = Path(sys.argv[1]), Path(sys.argv[2])
NORM = [('新课表', '新课标'), ('课标I卷', '课标Ⅰ卷'), ('全国一卷', '新课标Ⅰ卷'), ('全国二卷', '新课标Ⅱ卷'),
        ('全国1卷', '新课标Ⅰ卷'), ('全国高考一卷', '新课标Ⅰ卷'), ('全国高考二卷', '新课标Ⅱ卷'), ('全国2卷', '新课标Ⅱ卷'), ('新高考Ⅰ卷真题', '新课标Ⅰ卷'), ('新高考Ⅱ卷真题', '新课标Ⅱ卷'),
        ('浙江首考', '浙江（1月）'), ('浙江省1月', '浙江（1月）'), ('浙江一月', '浙江（1月）'), ('浙江 ', '浙江'), ('一月', '（1月）')]


def key(name):
    n = name
    for a, b in NORM:
        n = n.replace(a, b)
    y = re.search(r'(20\d\d)', n).group(1)
    if '浙江' in n:
        m = re.search(r'(\d+)月', n)
        return y, f'浙江卷（{m.group(1)}月）'
    for p, k in [('上海）（春考', '上海卷（春考）'), ('上海）（秋考', '上海卷（秋考）'), ('天津）（第一次', '天津卷（第一次）'),
                 ('天津）（第二次', '天津卷（第二次）'), ('北京', '北京卷'), ('江苏', '江苏卷'), ('全国甲卷', '全国甲卷'),
                 ('全国乙卷', '全国乙卷'), ('新课标Ⅲ卷', '新课标Ⅲ卷'), ('山东第1次', '新高考Ⅰ卷（山东第1次）'),
                 ('山东第2次', '新高考Ⅰ卷（山东第2次）'), ('山东', '新高考Ⅰ卷（山东）'), ('海南', '新高考Ⅱ卷（海南）'),
                 ('新课标Ⅰ卷）（版本一', '新课标Ⅰ卷（版本一）'), ('新课标Ⅰ卷）（版本二', '新课标Ⅰ卷（版本二）'),
                 ('新高考Ⅰ卷', '新高考Ⅰ卷'), ('新高考Ⅱ卷', '新高考Ⅱ卷'), ('新课标Ⅰ', '新课标Ⅰ卷'), ('新课标Ⅱ', '新课标Ⅱ卷')]:
        if p in n:
            return y, k
    return y, '?' + n


def kind(name):
    if name.endswith('.mp3'): return '音频'
    if 'otter' in name: return 'otter'
    if '听力原文' in name: return '原文'
    if '听力试题' in name: return '听力试题'
    if any(s in name for s in ('空白', '原卷')): return '空白卷'
    if any(s in name for s in ('解析', '答案')): return '解析'
    return '?'


def probe(txt):
    s = txt.read_text('utf-8', 'replace') if txt.exists() else ''
    qs = sorted({int(m) for m in re.findall(r'(?m)^\s*(\d{1,2})\s*[\.．、]', s) if 1 <= int(m) <= 20})
    return {'字数': len(s), '听力': bool(re.search(r'听力|第一节|Section A|听下面', s)),
            '题号1-20': len(qs), '原文': bool(re.search(r'(?m)^\s*(Text\s*\d|[MW]\s*[:：])', s)),
            '答案': len(re.findall(r'【答案】|答案[:：]|故选', s))}


sets = {}
for f in sorted(X.rglob('*')):
    if f.is_dir(): continue
    k = key(f.name); c = kind(f.name)
    e = sets.setdefault(' '.join(k), {})
    item = {'文件': str(f.relative_to(X)), '大小': f.stat().st_size}
    if c not in ('音频', 'otter'):
        item.update(probe(T / (f.stem + '.txt')))
    e.setdefault(c, []).append(item)
print(json.dumps(sets, ensure_ascii=False, indent=1))
