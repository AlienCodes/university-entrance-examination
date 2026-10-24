"""考研作文视频引擎入口：等于 专八/tools/make_video.py --project 考研作文（同一个程序，不另复制）。其他考研作文工具 `import make_video` 得到的就是切到考研作文的引擎。"""
import importlib.util
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2] / '专八' / 'tools' / 'make_video.py'
_spec = importlib.util.spec_from_file_location('make_video_考研作文', ENGINE)
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
_m.set_project('考研作文')

if __name__ == '__main__':
    sys.exit(_m.main())
sys.modules[__name__] = _m
