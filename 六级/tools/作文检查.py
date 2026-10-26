"""六级作文范文程序检查：tools/作文规则.py 的全部规则 + 计入字数在 word_range（150—180，用户 2026-10-26：不超过下限的 120%；题目写明不含首句的，扣掉首句）。
python3 六级/tools/作文检查.py   有一处就退出码 1"""
import sys, pathlib
R = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / 'tools'))
import 作文规则 as r
D = str(R / '六级/作文')
n = r.run([D], {D: ('word_range', None)})
print('六级作文程序检查：问题', n, '处'); sys.exit(1 if n else 0)
