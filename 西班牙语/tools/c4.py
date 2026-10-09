"""按文件路径载入四级 / 高考的程序模块（西班牙语的文件和四级同名，不能靠 sys.path 顺序区分）。"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for d in ('tools/tts', 'tools/video', '四级/tools'):
    if str(ROOT / d) not in sys.path:
        sys.path.append(str(ROOT / d))


def load(name, rel):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
