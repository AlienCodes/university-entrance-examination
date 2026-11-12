"""专八大字版「书卷水墨」（用户 2026-10-23：用原来的古风主题，沿用新的字体模式——英文全部加粗；先做一篇样片看效果）。

    /opt/ttsenv/bin/python 专八/tools/大字版_水墨.py --stills [t01 …]     # ① 截图 + 全部程序检查
    /opt/ttsenv/bin/python 专八/tools/大字版_水墨.py --approve [t01 …]    # ② 看过截图后登记
    /opt/ttsenv/bin/python 专八/tools/大字版_水墨.py --video [t01 …]      # ③ 生成 4K 视频 + 全部成品核查

与 专八/tools/大字版.py（晴空校园）是同一条流水线（六级/tools/大字版.py），只是选了变体 水墨（make_video.PROJECTS['专八']['variants']['水墨']）：
画面 C 书卷水墨 + 样式/C_水墨大字.css（英文 700、生词短语 800、译文加粗）；截图 专八/大字版水墨/截图/、成品 专八/最终视频_水墨/、
分屏方案 专八/tools/分屏_水墨.json（起点是晴空校园版的 分屏.json，按水墨的字号重新跑分屏建议）。晴空校园版的截图、登记、成品都不动。
"""
import os
import runpy
from pathlib import Path

os.environ['DZB_PROJECT'] = '专八'
os.environ['DZB_VARIANT'] = '水墨'
runpy.run_path(str(Path(__file__).resolve().parents[2] / '六级' / 'tools' / '大字版.py'), run_name='__main__')
