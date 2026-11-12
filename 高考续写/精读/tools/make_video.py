"""生成高考读后续写原文精读视频——大字版、晴空校园（与考研、专八晴空校园版同一个引擎）。

    /opt/ttsenv/bin/python 高考续写/精读/tools/大字版.py --stills / --approve / --video     # 截图 → 审阅登记 → 视频（见 六级/tools/大字版.py）

本文件只是入口：引擎是 专八/tools/make_video.py（等于 --project 高考续写），不另复制一份。项目差异都在 make_video.PROJECTS['高考续写']：
数据 高考续写/精读/data/vocab.json、音频 高考续写/精读/audio/female/（女声）、分屏 / 人名 / 截图审阅登记在 高考续写/精读/tools/、
文件名“2026 新课标Ⅰ卷 读后续写 题目.mp4”（name_re）、成品 高考续写/精读/最终视频_校园/。
其他工具 `import make_video` 得到的就是这个引擎（已切到高考续写），如 verify_all.py。
"""
import importlib.util
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[3] / '专八' / 'tools' / 'make_video.py'
_spec = importlib.util.spec_from_file_location('make_video_高考续写', ENGINE)      # 单独一份模块实例：与同一进程里的专八互不影响
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
_m.set_project('高考续写')                       # 数据、分屏、人名、登记都切到高考续写精读，画面 1 晴空校园

if __name__ == '__main__':
    sys.exit(_m.main())
sys.modules[__name__] = _m                   # import make_video 得到的就是切到高考续写的引擎
