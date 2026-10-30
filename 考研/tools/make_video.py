"""生成考研逐句精读视频——大字版、晴空校园（用户 2026-10-20：考研与专八晴空校园版完全相同的主题、字体、颜色）。

    /opt/ttsenv/bin/python 考研/tools/大字版.py --stills / --approve / --video     # 截图 → 审阅登记 → 视频（见 六级/tools/大字版.py）

本文件只是入口：引擎与专八、六级共用同一个程序 专八/tools/make_video.py（等于 专八/tools/make_video.py --project 考研），不另复制一份。
考研只有这些不同（make_video.PROJECTS['考研']）：数据 考研/data/vocab.json、音频 考研/audio/、定稿登记 考研/ann/复核通过.json、
分屏 考研/tools/分屏.json、人名 考研/tools/人名.json、截图审阅登记 考研/tools/画面核查/截图审阅通过.json、
片头 KAOYAN · READING · PART A、页眉 KAOYAN READING、文件名“2026年考研英语一 Text 1 题目.mp4”、成品 考研/最终视频_校园/。
其他考研工具 `import make_video` 得到的就是这个引擎（已切到考研），如 verify_all.py、layoutcheck.py --project 考研。
"""
import importlib.util
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2] / '专八' / 'tools' / 'make_video.py'
_spec = importlib.util.spec_from_file_location('make_video_考研', ENGINE)      # 单独一份模块实例：与同一进程里的专八互不影响
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
_m.set_project('考研')                       # 数据、分屏、人名、登记都切到考研，画面 1 晴空校园

if __name__ == '__main__':
    sys.exit(_m.main())
sys.modules[__name__] = _m                   # import make_video 得到的就是切到考研的引擎
