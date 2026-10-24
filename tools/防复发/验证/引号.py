"""双向验证：引号不停顿（铁律 11；踩坑 28）。6 个项目的 make_audio.py 各有一份 strip_quotes 和“残留引号”检查：
① 每份都把引号去干净、词内撇号保留；② 去引号函数坏了（原样返回）时残留检查必须报出；
③ 每个有 synth_sentence 的 make_audio 都在合成前调用 strip_quotes、合成段里查残留；④ 6 份代码完全一致（一份改了别的没跟上就报）。
    python3 tools/防复发/验证/引号.py"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _抽取 import R, load  # noqa: E402

PROJ = ['四级', '六级', '专八', '中考', '考研', '考研作文']
CASES = ['They call it the “right to grow” movement.', "He said, 'Don't go.'", '‘Yes,’ she said, “it’s the world’s best.”',
         'The "smart" phone isn’t cheap.']
bad, srcs = [], {}
for p in PROJ:
    rel = f'{p}/tools/make_audio.py'
    src = (R / rel).read_text('utf-8')
    strip = load(rel, ['strip_quotes'], {'re': re})['strip_quotes']
    m = re.search(r"if re\.search\(r'(.+?)', x\):\s*# 检查：送进模型的文字里不得残留引号", src)
    if not m:
        bad.append(f'{p}：找不到合成段的残留引号检查')
        continue
    resid = re.compile(m.group(1))
    body = src[src.index('def synth_sentence'):]
    body = body[:body.index('\ndef ', 10)]
    if 'strip_quotes(read)' not in body:
        bad.append(f'{p}：synth_sentence 合成前没调用 strip_quotes')
    for c in CASES:
        out = strip(c)
        if resid.search(out):
            bad.append(f'{p}：去引号后仍残留：{out}')
        for w in ("Don't", 'it’s', 'world’s', 'isn’t'):
            if w in c and w not in out:
                bad.append(f'{p}：词内撇号被去掉了：{w} → {out}')
    if not all(resid.search(c) for c in CASES if "'D" not in c):   # 埋雷：去引号函数坏了，残留检查必须报出
        # （直单引号 'Don't go.' 残留检查认不出：原文在 sent.py / fix_typography 已统一成弯引号，登记为缺口）
        bad.append(f'{p}：残留检查放过了带引号的句子')
    srcs[p] = re.search(r'def strip_quotes\(t\):\n(?:    .*\n)+', src).group(0) + m.group(1)
if len(set(srcs.values())) > 1:
    bad.append('6 份 strip_quotes / 残留检查不一致：' + '、'.join(f'{p}' for p in srcs if srcs[p] != srcs['四级']) + ' 与四级不同')
print(f'  检查了 {len(srcs)} 个项目 × {len(CASES)} 句')
print('引号双向验证：' + ('全部通过' if not bad else f'{len(bad)} 处失败\n  ' + '\n  '.join(bad)))
sys.exit(1 if bad else 0)
