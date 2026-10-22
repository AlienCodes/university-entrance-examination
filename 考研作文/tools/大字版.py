"""考研作文视频（手账笔记本，用户 2026-10-22：范文与阅读视频一样逐句翻译、标生词，换成笔记主题；开头展示原题高清截图）。

    /opt/ttsenv/bin/python 考研作文/tools/大字版.py --stills [w02 …]     # ① 截图 + 全部程序检查（含原题屏：高清、比例、不出界）
    /opt/ttsenv/bin/python 考研作文/tools/大字版.py --approve [w02 …]    # ② 审阅员看过截图后登记（协调人运行）
    /opt/ttsenv/bin/python 考研作文/tools/大字版.py --video [w02 …]      # ③ 生成 4K 视频 + 全部成品核查

本文件只是入口：与六级、专八、考研阅读用同一个程序 六级/tools/大字版.py（项目切到考研作文），引擎 专八/tools/make_video.py（PROJECTS['考研作文']）。
截图 考研作文/大字版/截图/<篇目>/、登记 考研作文/tools/画面核查/截图审阅通过.json、成品 考研作文/最终视频/、核查 考研作文/大字版/成品核查/。
"""
import os
import runpy
from pathlib import Path

os.environ['DZB_PROJECT'] = '考研作文'
runpy.run_path(str(Path(__file__).resolve().parents[2] / '六级' / 'tools' / '大字版.py'), run_name='__main__')
