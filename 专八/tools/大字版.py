"""专八大字版（晴空校园，用户 2026-10-17：用校园主题做完所有的专八视频——片头带 985 教学楼、英文全部加粗、生词晴空蓝、短语 B 站粉、短语下面没有黄色底纹）。

    /opt/ttsenv/bin/python 专八/tools/大字版.py --stills [t01 …]     # ① 截图 + 全部程序检查（不写篇目 = 已定稿的 t01—t10）
    /opt/ttsenv/bin/python 专八/tools/大字版.py --approve [t01 …]    # ② 审阅员看过截图后登记（协调人运行）
    /opt/ttsenv/bin/python 专八/tools/大字版.py --video [t01 …]      # ③ 生成 4K 视频 + 全部成品核查（只做已登记的篇目；可续跑）

本文件只是入口：做法与六级完全相同，用同一个程序 六级/tools/大字版.py（项目切到专八），不另复制一份。专八只有这些不同（make_video.PROJECTS['专八']）：
截图 专八/大字版/截图/<篇目>/、登记 专八/tools/画面核查/截图审阅通过.json（专八/样片/ 和 样片审阅通过.json 是“同一篇、多种画面”的样片，分开）、
成品 专八/最终视频_校园/（旧版 10 个仍在 专八/最终视频/，不动）、核查 专八/大字版/成品核查/、默认画面 1 晴空校园。
"""
import os
import runpy
from pathlib import Path

os.environ['DZB_PROJECT'] = '专八'
runpy.run_path(str(Path(__file__).resolve().parents[2] / '六级' / 'tools' / '大字版.py'), run_name='__main__')
