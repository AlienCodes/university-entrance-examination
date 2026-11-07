"""翻译复核定稿后重写双语字幕（.srt/.vtt）：音频只取决于封版的英文，可以先于翻译复核生成；字幕里的中文必须用复核定稿的翻译。
    /opt/ttsenv/bin/python 中考/tools/resub.py z01 z02 …      # 不列编号就处理全部已有音频的篇目
时间轴取自 中考/audio/timings.json（每句的起止时间），中文取自 中考/ann/zNN.txt；写完逐句核对字幕英文与朗读文本一致。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'tts'))
import gaokao_tts as G  # noqa: E402

C4 = ROOT / '中考'
G.ANN = C4 / 'ann'
VOICE = 'female'
tm = json.loads((C4 / 'audio' / 'timings.json').read_text('utf-8'))[VOICE]
ids = sys.argv[1:] or sorted(tm)
for pid in ids:
    t = tm[pid]
    zh = G.load_zh(pid)
    items = t['sentences']
    missing = [it['k'] for it in items if it['k'] not in zh]
    if missing:
        sys.exit(f'{pid}：第 {missing} 句没有中文翻译')
    base = C4 / 'audio' / t['file'][:-4]
    G.write_subs(base, items, zh)
    lines = Path(str(base) + '.srt').read_text('utf-8').split('\n\n')
    assert len([b for b in lines if b.strip()]) == len(items), pid
    print(pid, len(items), '句字幕已按定稿翻译重写')
