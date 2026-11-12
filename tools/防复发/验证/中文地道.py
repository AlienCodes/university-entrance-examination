"""双向验证：中文必须地道（铁律 24 补充；用户 2026-11-04：“忍泪……根本就不符合中国人的说话习惯……一般大家肯定会说他强忍住眼泪”）。
  ① 有问题的版本：改之前的续写新课标Ⅰ卷全课中文（数据/中文地道_旧稿.json，提交 d29bb517 里被报的 17 条）→ 每条都要报，其中必须有“忍泪”；
  ② 好的版本：现在的这一课全课中文、高考语法填空讲稿、合成副本 → 0 处；地道说法（强忍着眼泪、显得更真诚、互相帮助……）不许误报；
     再埋雷（挥别、驻足、颔首、未曾、彼时、进行了分析、被……所……、一个小句堆 4 个“的”），每颗都要报；
  ③ 入口：续写检查.check_dir（⑪）、稿检查 --口语 都调 中文地道（拿掉就报）。
    python3 tools/防复发/验证/中文地道.py"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import 中文地道 as Z  # noqa: E402

ok = True


def say(name, good):
    global ok
    ok &= good
    print(('  ✓ ' if good else '  ✗ ') + name)


old = json.loads((Path(__file__).parent / '数据/中文地道_旧稿.json').read_text('utf-8'))['items']
miss = [w for w, t in old if not Z.problems([(w, t)])]
say(f'旧稿 {len(old)} 条全部报出（漏 {len(miss)}）', not miss and len(old) >= 17)
say('旧稿里的“忍泪”报出', any('忍泪' in x for x in Z.problems([tuple(i) for i in old])))

lesson = ROOT / '高考续写/讲解/2026_新课标Ⅰ卷'
e = Z.problems(Z.lesson_items(lesson))
say(f'现在的续写全课 0 处（{len(e)}）', not e)
for f in ('高考语法填空/稿/2026_新课标Ⅰ卷.json', '高考语法填空/tts/稿_续写_2026_新课标Ⅰ卷.json'):
    e = Z.problems(Z.doc_items(json.loads((ROOT / f).read_text('utf-8')), f))
    say(f'{f} 0 处（{len(e)}）', not e)

good = ['艾米丽强忍着眼泪。', '瑞秋的回答轻描淡写，反而显得更真诚。', '邻居们互相帮助。', '她挥手告别，停下脚步。', '温暖从头到尾没变。',
        '他点了点头。', '那时候她还没到。', '她开始慌了。', '谢谢你们救了我的假期。', '一个动作、一种心情，一句写完。', '她眼里含着泪水。']
fp = [g for g in good if Z.problems([('好', g)])]
say(f'地道说法不误报（误报 {fp}）', not fp)
mines = ['她向他们挥别。', '她在车站驻足。', '瑞秋微微颔首。', '她未曾想到。', '彼时雪还在下。', '我们对这句话进行了分析。',
         '她被这份善意所打动。', '她含泪道谢。', '车驶离了车站。', '这是我们的老师的朋友的车的钥匙。',
         # 审阅员埋雷（2026-11-04）补成程序的四类
         '艾米丽给予了他们一盒饼干。', '一个句子拥有两个动作。', '在等车的过程中一直陪伴着她。', '她陷入了恐慌的状态之中。', '瑞秋问她是否处于良好的状态。']
leak = [m for m in mines if not Z.problems([('雷', m)])]
say(f'埋雷 {len(mines)} 颗全部报出（漏 {leak}）', not leak)

# 入口：拿掉调用就要被发现
src = (ROOT / '高考续写/tools/续写检查.py').read_text('utf-8')
say('续写检查.check_dir 调 中文地道', re.search(r"def check_dir[\s\S]*?ZD\.problems\(ZD\.lesson_items\(d\)\)[\s\S]*?return E", src) is not None)
src2 = (ROOT / '高考语法填空/tools/稿检查.py').read_text('utf-8')
say('稿检查 --口语 调 中文地道', 'ZD.problems(ZD.doc_items(doc))' in src2)
r = subprocess.run([sys.executable, str(ROOT / '高考续写/tools/续写检查.py'), str(lesson)], capture_output=True, text=True)
say('续写检查 真实运行 0 处', r.returncode == 0)
print('中文地道 双向验证', '通过' if ok else '失败')
sys.exit(0 if ok else 1)
