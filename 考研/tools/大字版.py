"""考研大字版（晴空校园，与专八晴空校园版完全相同：片头带 985 教学楼、中英文全部加粗、生词晴空蓝、短语草绿带黄色底纹）。

    /opt/ttsenv/bin/python 考研/tools/大字版.py --stills [k01 …]     # ① 截图 + 全部程序检查（不写篇目 = 已定稿的篇目）
    /opt/ttsenv/bin/python 考研/tools/大字版.py --approve [k01 …]    # ② 审阅员看过截图后登记（协调人运行）
    /opt/ttsenv/bin/python 考研/tools/大字版.py --video [k01 …]      # ③ 生成 4K 视频 + 全部成品核查（只做已登记的篇目；可续跑）

本文件只是入口：做法与六级、专八完全相同，用同一个程序 六级/tools/大字版.py（项目切到考研）。
截图 考研/大字版/截图/<篇目>/、登记 考研/tools/画面核查/截图审阅通过.json、成品 考研/最终视频_校园/、核查 考研/大字版/成品核查/。
"""
import os
import runpy
from pathlib import Path

os.environ['DZB_PROJECT'] = '考研'
runpy.run_path(str(Path(__file__).resolve().parents[2] / '六级' / 'tools' / '大字版.py'), run_name='__main__')
