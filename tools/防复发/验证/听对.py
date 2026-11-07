"""双向验证 踩坑 124（逐句听对，tools/tts/听对.py）：
① 修正前的 202312-2 成品音轨（提交 e4d4e35，第 6—10 句被放到“试音结束，现在开始”上）必须报出第 6—10 句里的长句；
② 现在的 202312-2 音轨 0 句；
③ 把现在的时间轴整体挪 40 秒（每句都错位）必须几乎全报；
④ 原音音轨.py 的 raw6 必须调用 听对（拿掉就报）。

    /opt/ttsenv/bin/python tools/防复发/验证/听对.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools' / 'tts'))
import 听对 as H  # noqa: E402

OLD = 'e4d4e35'
A = '六级/听力/精读/audio/'
errs = []
texts = H.cet6_texts('202312-2')

with tempfile.TemporaryDirectory() as d:
    mp3 = Path(d) / 'old.mp3'
    mp3.write_bytes(subprocess.run(['git', '-C', str(ROOT), 'show', f'{OLD}:{A}原音/202312-2.mp3'], capture_output=True, check=True).stdout)
    tm = json.loads(subprocess.run(['git', '-C', str(ROOT), 'show', f'{OLD}:{A}timings.json'], capture_output=True, check=True).stdout)['cet4_male']['202312-2']
    a16 = H.load16(mp3)
    # 旧文字与现在相同（只改了时刻），用现在的原文
    old = H.problems(a16, [(x['start'], x['end']) for x in tm['sentences'][:12]], texts[:12])
    ks = [k for k, *_ in old]
    if not {7, 8, 9, 10} <= set(ks) or set(ks) - {6, 7, 8, 9, 10}:
        errs.append(f'① 旧音轨应报第 7—10 句（第 6 句也可），实际 {ks}')

new = H.cet6_check('202312-2')
if new:
    errs.append(f'② 现在的音轨应为 0，实际 {new}')

tm = json.loads((ROOT / A / 'timings.json').read_text('utf-8'))['cet4_male']['202312-2']
a16 = H.load16(ROOT / A / tm['file'])
sh = H.problems(a16, [(x['start'] + 40, x['end'] + 40) for x in tm['sentences'][20:40]], texts[20:40])
n = sum(len([w for w in H.norm(s) if not any(c.isdigit() for c in w)]) >= H.MIN_WORDS for s in texts[20:40])
if len(sh) < 0.8 * n:
    errs.append(f'③ 时间轴挪 40 秒应几乎全报（{n} 句），实际 {len(sh)} 句')

src = (ROOT / '专八/听力/原文/tools/原音音轨.py').read_text('utf-8')
if '听对' not in src.split('def raw6', 1)[1].split('\ndef ', 1)[0]:
    errs.append('④ 原音音轨.py 的 raw6 没有调用 听对')

print('\n'.join(errs) or f'听对 双向验证通过：旧音轨报 {ks}，现在 0 句，错位 {len(sh)}/{n} 句报出，raw6 已接上')
sys.exit(1 if errs else 0)
