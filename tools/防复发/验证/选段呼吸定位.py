"""双向验证（踩坑 102）：选段整篇检查报“呼吸声 [(起, 止, 峰值)]”时，blame 必须找到那个时间点所在的小段换候选。
2026-11-03 续写整片：报错格式是 [(133.02, 133.22, -33.1)]，blame 只认“（12.34s）”，找不到时间点，退回去换“意群最差的段”，
呼吸所在的段一轮也没换，16 轮白跑后失败。
  ① 旧写法（只认（…s））：从真实报错里取出 0 个时间点；
  ② 现在的 选段.blame：真实报错 → 133.02 所在的小段；意群报错“（12.34s）”照旧能定位。
    /opt/ttsenv/bin/python tools/防复发/验证/选段呼吸定位.py"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / '高考语法填空/tools')]
import 选段 as X  # noqa: E402

MSG = '呼吸声 1 处（停顿里的非浊音孤岛，峰值 > -60.0 dBFS）：[(133.02, 133.22, -33.1)]，未输出'
items = [{'id': 'a1', 'start': 120.0, 'end': 128.0}, {'id': 's2z~3', 'start': 128.5, 'end': 133.4},
         {'id': 's2z~4', 'start': 134.0, 'end': 140.0}]
bad = []
old = [float(x) for x in re.findall(r'（(\d+\.\d+)s', MSG)]
print(f'① 旧写法取出时间点 {old}（应 []）')
if old:
    bad.append('①')
got = X.blame(None, items, MSG)
got2 = X.blame(None, items, '意群 a 比相邻小 1.5 LU（125.00s）')
print(f'② blame 呼吸 → {got}（应含 s2z~3）；意群（125.00s）→ {got2}（应含 a1）')
if 's2z~3' not in got or 'a1' in got or 'a1' not in got2:
    bad.append('②')
print('选段呼吸定位：' + ('失败 ' + ' '.join(bad) if bad else '通过'))
sys.exit(1 if bad else 0)
