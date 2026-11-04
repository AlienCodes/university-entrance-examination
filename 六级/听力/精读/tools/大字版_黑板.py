"""六级听力原文精读「六级教室黑板」：与 专八/听力/原文/tools/大字版_水墨.py 同一条流水线（六级/tools/大字版.py），项目 六级听力（六级/听力/精读，make_video.PROJECTS）。

    /opt/ttsenv/bin/python 六级/听力/精读/tools/大字版_黑板.py --preflight|--stills|--approve|--video [202512-1 …]
"""
import os
import runpy
from pathlib import Path

os.environ['DZB_PROJECT'] = '六级听力'
os.environ.pop('DZB_VARIANT', None)
runpy.run_path(str(Path(__file__).resolve().parents[4] / '六级' / 'tools' / '大字版.py'), run_name='__main__')
