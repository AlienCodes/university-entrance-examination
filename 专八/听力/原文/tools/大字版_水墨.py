"""专八听力原文精读「书卷水墨」：与 专八/tools/大字版_水墨.py 同一条流水线（六级/tools/大字版.py），项目 专八听力（专八/听力/原文，make_video.PROJECTS）。

    /opt/ttsenv/bin/python 专八/听力/原文/tools/大字版_水墨.py --preflight|--stills|--approve|--video [L1 L2 L3]
"""
import os
import runpy
from pathlib import Path

os.environ['DZB_PROJECT'] = '专八听力'
os.environ['DZB_VARIANT'] = '水墨'
runpy.run_path(str(Path(__file__).resolve().parents[4] / '六级' / 'tools' / '大字版.py'), run_name='__main__')
