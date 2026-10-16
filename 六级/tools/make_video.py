"""生成六级逐句精读视频——大字版、教室黑板（用户 2026-10-16：六级 60 篇全部改成专八样片选定的教室黑板画面）。

    /opt/ttsenv/bin/python 六级/tools/make_video.py s01            # 一篇（先 大字版.py --stills → 审阅 → --approve，否则拒绝生成）
    /opt/ttsenv/bin/python 六级/tools/大字版.py --video            # 全部（可续跑，做好的跳过；适合 setsid nohup 脱离会话跑）

本文件只是入口：引擎与专八共用同一个程序 专八/tools/make_video.py（等于 专八/tools/make_video.py --project 六级），不另复制一份，
专八的排版修正、检查、编码（整片一次压缩、成品体积 ≤ 95 MB）六级自动跟着用。六级只有这些不同（make_video.PROJECTS['六级']）：
数据 六级/data/vocab.json、音频 六级/audio/timings.json（cet4_male，沿用，不重新生成）、定稿登记 六级/ann/复核通过.json、
分屏 六级/tools/分屏.json、人名 六级/tools/人名.json、截图审阅登记 六级/tools/画面核查/截图审阅通过.json、
片头 CET-6 · READING · SECTION C / 大学英语六级、页眉 CET-6 READING、默认画面 3 教室黑板、
文件名与旧版相同：年份月份 第几套 Passage One/Two 题目.mp4（六级/最终视频/）。
其他六级工具 `import make_video` 得到的就是这个引擎（已切到六级），如 verify_all.py、layoutcheck.py --project 六级。

旧版（2026-10-12 起生成已发布的 60 个视频：米白底「杂志编号注释」、EB Garamond、64/30px 起）原样保存在 make_video_旧版.py，
它读 分屏.json 的旧格式，回退时：cp 六级/tools/make_video_旧版.py 六级/tools/make_video.py && cp 六级/tools/分屏_旧版.json 六级/tools/分屏.json
"""
import importlib.util
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2] / '专八' / 'tools' / 'make_video.py'
_spec = importlib.util.spec_from_file_location('make_video_六级', ENGINE)      # 单独一份模块实例：与同一进程里的专八互不影响
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
_m.set_project('六级')                       # 数据、分屏、人名、登记都切到六级，画面切到 3 教室黑板

if __name__ == '__main__':
    sys.exit(_m.main())
sys.modules[__name__] = _m                   # import make_video 得到的就是切到六级的引擎
