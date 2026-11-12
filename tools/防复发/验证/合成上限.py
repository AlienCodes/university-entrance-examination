"""双向验证：合成长度上限与单段超时（踩坑 95；2026-11-03 第 3 轮 run 41587537407：15 台合成机里 synth(3) 某一段生成停不下来，
卡约 60 分钟被超时杀掉，整台没有产物）。纯 Python + numpy，CI 能跑。
  ① 旧写法（51357c9 的 qwen_synth：不设 max_new_tokens、不换种子重来）→ 必须报；现在的 → 不报；
  ② 讲解音频.run_unit：第一次顶到上限 → 换种子第二次成功；一直顶到上限 → 报错（不无限重来）；单段超时 → 换种子；
  ③ 上限够用：仓库里第 2 版第 56 题样片每个小段的真实时长 ≤ 上限的 60%；全稿最大上限远小于默认 2048。
    python3 tools/防复发/验证/合成上限.py"""
import ast
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / '高考语法填空/tools'), str(ROOT / 'tools/tts')]
import 讲解音频 as J  # noqa: E402

bad = []
QS = '高考语法填空/tools/qwen_synth.py'


def problems(src):
    t = ast.parse(src)
    e = []
    calls = [n for n in ast.walk(t) if isinstance(n, ast.Call) and getattr(n.func, 'attr', '') in ('generate_voice_clone', 'generate_custom_voice')]
    for c in calls:
        if not any(k.arg == 'max_new_tokens' for k in c.keywords):
            e.append(f'第 {c.lineno} 行 {c.func.attr} 没设 max_new_tokens')
    if 'run_unit' not in src:
        e.append('没有经 讲解音频.run_unit（顶到上限 / 超时换种子重来）')
    return e


old = subprocess.run(['git', 'show', f'51357c9:{QS}'], cwd=ROOT, capture_output=True, text=True).stdout
e_old, e_new = problems(old), problems((ROOT / QS).read_text('utf-8'))
print(f'① 旧写法 {len(e_old)} 处（应 > 0）；现在 {len(e_new)} 处（应 0）{e_new}')
if not e_old or e_new:
    bad.append('①')

SR = 24000
cap = 100
calls = []


def g_once(seed):
    calls.append(seed)
    n = cap / J.TOK_PER_SEC if len(calls) == 1 else 2.0
    return np.zeros(int(n * SR), np.float32), SR


x, sr, k = J.run_unit(g_once, 5, cap)
ok_a = k == 2 and len(set(calls)) == 2
try:
    J.run_unit(lambda s: (np.zeros(int(cap / J.TOK_PER_SEC * SR), np.float32), SR), 5, cap)
    ok_b = False
except RuntimeError:
    ok_b = True
calls.clear()


def g_slow(seed):
    calls.append(seed)
    if len(calls) == 1:
        time.sleep(3)
    return np.zeros(SR, np.float32), SR


x, sr, k2 = J.run_unit(g_slow, 5, cap, timeout=1)
ok_c = k2 == 2
print(f'② 顶到上限换种子 {"对" if ok_a else "错"}；一直停不下来报错 {"对" if ok_b else "错"}；超时换种子 {"对" if ok_c else "错"}')
if not (ok_a and ok_b and ok_c):
    bad.append('②')

tm = json.loads((ROOT / '高考语法填空/audio/2026 新课标Ⅰ卷 语法填空 第56题样片（用户本人声音）.timings.json').read_text('utf-8'))
ratio = max((u['end'] - u['start']) * J.TOK_PER_SEC / J.token_cap(u['text']) for it in tm['items'] for u in it['units'])
segs = json.loads((ROOT / '高考语法填空/稿/2026_新课标Ⅰ卷.json').read_text('utf-8'))['segments']
mx = max(J.token_cap(u['text'], u['lang']) for u in J.expand(segs))
print(f'③ 样片小段真实时长 / 上限 最大 {ratio:.2f}（≤ 0.6）；全稿最大上限 {mx}（< 1000）')
if ratio > 0.6 or mx >= 1000:
    bad.append('③')
print('合成上限双向验证', '通过' if not bad else '失败：' + '、'.join(bad))
sys.exit(1 if bad else 0)
