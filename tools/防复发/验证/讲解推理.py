"""双向验证：讲解推理必须说完整（用户 2026-11-04 第 19 条：“直接说是过去的事，要用过去式……应该这样说：因为这件事情发生在过去，
所以我们这个句子的时态要用过去式……如果要表示‘有’的话，我们就需要使用 there be 句型……你刚讲的有点过于省略了”）。
  ① 有问题的版本：改之前的续写逐块翻译配音（数据/讲解推理_旧稿.json，提交 f9b0a04）→ 必须报，且老师点到的两处
     （s1b1“讲的是过去的事，用过去式”、s1b2“有，用 there be”）都在里面；
  ② 好的版本：现在的续写全课 → 0 处；完整的因果说法不许误报；再埋雷（省略写法），每颗都要报；
  ③ 入口：续写检查.check_dir（⑫）、稿检查 --口语 都调 讲解推理（拿掉就报）。
    python3 tools/防复发/验证/讲解推理.py"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import 讲解推理 as T  # noqa: E402

ok = True


def say(name, good):
    global ok
    ok &= good
    print(('  ✓ ' if good else '  ✗ ') + name)


def seg(text, i='x', ph='chunk'):
    return {'segments': [{'id': i, 'lang': 'Chinese', 'ph': ph, 'text': text}]}


old = json.loads((Path(__file__).parent / '数据/讲解推理_旧稿.json').read_text('utf-8'))
e = T.problems(old)
say(f'旧稿报出 {len(e)} 处（应 ≥ 40）', len(e) >= 40)
say('老师点到的 s1b1“讲的是过去的事，用过去式”报出', any('s1b1' in x and '用过去式' in x for x in e))
say('老师点到的 s1b2“有，用 there be”报出', any('s1b2' in x and '有，用 there be' in x for x in e))

lesson = ROOT / '高考续写/讲解/2026_新课标Ⅰ卷'
e = T.problems(json.loads((lesson / '稿.json').read_text('utf-8')))
say(f'现在的续写全课 0 处（{len(e)}）', not e)

good = ['因为这件事发生在过去，所以这个句子的时态，要用一般过去时。',
        '如果我们要表示某个地方有什么东西，就要用 there be 句型，所以这里用 there be。',
        '既然主语相同，后面的 they 就可以省掉。',
        '静静地，这里要用形容词 quiet。为什么？因为 lie 在这里像 be 一样。',
        '英文是：There was a station nearby。', '可是，表示转折，英语里就是 but。']
fp = [g for g in good if T.problems(seg(g))]
say(f'完整的因果说法不误报（误报 {fp}）', not fp)
mines = ['讲的是过去的事，用过去式。', '有，用 there be。', '接着，就是 then，放在动词前面。', '车是被停放的，用被动。',
         '静静地，用形容词 quiet。', '主语相同，就省掉后一个。', '在多伦多，in Toronto，放在后面。']
leak = [m for m in mines if not T.problems(seg(m))]
say(f'埋雷 {len(mines)} 颗全部报出（漏 {leak}）', not leak)
say('得分点段的评语不查', not T.problems(seg('得分点二：That evening，时间状语放在句首。', ph='pt')))

src = (ROOT / '高考续写/tools/续写检查.py').read_text('utf-8')
say('续写检查.check_dir 调 讲解推理', re.search(r"def check_dir[\s\S]*?TL\.problems\(doc\)[\s\S]*?return E", src) is not None)
src2 = (ROOT / '高考语法填空/tools/稿检查.py').read_text('utf-8')
say('稿检查 --口语 调 讲解推理', 'TL.problems(doc)' in src2)
r = subprocess.run([sys.executable, str(ROOT / '高考续写/tools/续写检查.py'), str(lesson)], capture_output=True, text=True)
say('续写检查 真实运行 0 处', r.returncode == 0)
print('讲解推理 双向验证', '通过' if ok else '失败')
sys.exit(0 if ok else 1)
