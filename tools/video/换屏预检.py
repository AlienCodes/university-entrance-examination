"""换屏预检（音频重做后、触发 GitHub 生成前必须跑，2026-10-29 四级作文 cet4w-4 教训）：
大字版的分屏句，换屏时刻由语音识别在音频里找第二屏第一个词的开口（专八/tools/make_video.switch_time），必须落在句中停顿里。
只换音频（哪怕时间轴不变、只改了电平）也可能让识别结果变（c13 第 10 句 “well, and opening” 被听成 “well. An opening”，
找到前面另一个 and，换屏时刻 3.49s 不在停顿里），GitHub 上截图阶段才报错、32 台机器白跑。这里在本机对全部篇目一次查完（只做识别，不截图）。

    env -u LANG -u LC_ALL -u LANGUAGE /opt/ttsenv/bin/python tools/video/换屏预检.py 四级作文 [c01 …]

项目：用 六级/tools/大字版.py 的项目（四级作文、六级作文、考研作文、六级、考研、专八）。任何一处问题退出码 1。"""
import json
import os
import runpy
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
proj, ids = sys.argv[1], sys.argv[2:]
os.environ['DZB_PROJECT'] = proj
os.chdir(R)
g = runpy.run_path(str(R / '六级' / 'tools' / '大字版.py'), run_name='dzb')
P = [p for p in json.loads((g['C6'] / 'data' / 'vocab.json').read_text('utf-8'))['passages'] if p.get('done') and (not ids or p['id'] in ids)]
bad = {}
for p in P:
    out, b = g['split_pauses'](p)
    print(f"{p['id']}：{len(out)} 处换屏，{'0 处问题' if not b else '；'.join(b)}", flush=True)
    if b:
        bad[p['id']] = b
print(f'换屏预检：{len(P)} 篇，问题 {sum(map(len, bad.values()))} 处' + (f'（{" ".join(bad)}）' if bad else ''))
sys.exit(1 if bad else 0)
