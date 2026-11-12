"""双向验证：讲解配音稿的口语检查（铁律 24；用户 2026-11-04：自然、不要过多语气词、该停就停、不要一口气说完）。
  ① 有问题的版本：重写之前的续写讲解稿（数据/讲解口语_旧稿.json）→ 必须报“一口气 / ‖ 之间太长 / 答案前没停”；
  ② 好的版本：现在的续写讲解稿 → 0 处；再在它上面埋 6 颗雷（语气词、全稿语气词、一口气长句、‖ 切开意群、太碎、答案前没停），每颗都要报出；
  ③ 入口：续写检查.check_dir 调 稿检查.talk_problems（拿掉就报）；阈值来自老师录音（BREATH 注释里有实测分位数）。
    python3 tools/防复发/验证/讲解口语.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '高考语法填空/tools'))
import 稿检查 as GK  # noqa: E402

old = json.loads((Path(__file__).parent / '数据/讲解口语_旧稿.json').read_text('utf-8'))
new = json.loads((ROOT / '高考续写/讲解/2026_新课标Ⅰ卷/稿.json').read_text('utf-8'))
bad = []
if not GK.talk_selftest(new, old):
    bad.append('①② 口语检查双向验证失败')
src = (ROOT / '高考续写/tools/续写检查.py').read_text('utf-8')
if 'E += GK.talk_problems(doc)' not in src:
    bad.append('③ 续写检查没有调 稿检查.talk_problems')
if GK.BREATH != {'CLAUSE_MAX': 24, 'UNIT_MAX': 70, 'SEG_MAX': 150, 'UNIT_MIN': 7}:
    bad.append(f'③ 阈值被改了（{GK.BREATH}），改阈值要重新按老师录音实测并更新本验证')
print('讲解口语双向验证', '通过' if not bad else '失败：' + '；'.join(bad))
sys.exit(1 if bad else 0)
