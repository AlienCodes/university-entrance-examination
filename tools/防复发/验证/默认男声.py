"""双向验证：配音默认四六级男声（铁律 8）。voices.json 的 cet4_male 必须是 am_fenrir 0.6 + am_onyx 0.4、语速 0.95；
所有用 Kokoro 配音的项目（高考除外，当年女声已定稿）make_audio.py 的默认 VOICE 必须是 cet4_male。
埋雷：把默认改成 female、把语速改成 1.0，必须报出。新项目的 make_audio.py 自动纳入（扫 */tools/make_audio.py）。
    python3 tools/防复发/验证/默认男声.py"""
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
SKIP = {'tools'}                           # 高考（tools/）当年用女声，已定稿不动


def check_voice(v):
    want = {'style': {'am_fenrir': 0.6, 'am_onyx': 0.4}, 'speed': 0.95}
    return [f'cet4_male 的 {k} 是 {v.get(k)}，应为 {w}' for k, w in want.items() if v.get(k) != w]


def check_src(name, src):
    m = re.search(r"^VOICE\s*=\s*(.+)$", src, re.M)
    if not m:
        return [f'{name}：没有 VOICE 默认值']
    return [] if re.search(r"""['"]cet4_male['"]\s*\)?\s*(#.*)?$""", m.group(1)) else [f'{name}：默认配音不是 cet4_male（{m.group(1)[:60]}）']


bad = []
voice = json.loads((R / 'tools/tts/voices.json').read_text('utf-8'))['cet4_male']
bad += check_voice(voice)
files = [f for f in sorted(R.glob('*/tools/make_audio.py')) if f.parts[-3] not in SKIP]
for f in files:
    bad += check_src(f.parts[-3], f.read_text('utf-8'))
# 埋雷
if not check_voice(dict(voice, speed=1.0)):
    bad.append('埋雷失效：语速 1.0 没报出')
src0 = files[0].read_text('utf-8')
if not check_src('雷', re.sub(r"^VOICE\s*=.*$", "VOICE = 'female'", src0, flags=re.M)):
    bad.append('埋雷失效：默认 female 没报出')
print(f'  检查了 {len(files)} 个项目：' + '、'.join(f.parts[-3] for f in files))
print('默认男声双向验证：' + ('全部通过' if not bad else f'{len(bad)} 处失败\n  ' + '\n  '.join(bad)))
sys.exit(1 if bad else 0)
