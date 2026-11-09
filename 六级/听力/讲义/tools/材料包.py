"""给写解析的子代理生成精简材料包（总协调 2026-11-09：压每套 token）：一页要点 + 一题范例 + 这几套的材料，
子代理只读这一个文件、只写解析 JSON，检查由 解析检查.py 跑。六级 / 四级共用（项目配置 讲义/项目.json）。
python3 材料包.py 输出文件 套 [套 …]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import 材料 as M  # noqa: E402
import 解析检查 as JC  # noqa: E402

RULES = """# 写法要点（程序会查，报几处改几处）
每套写一个文件 {out}/<套>.json，格式：{{"套": "<套>", "题": {{"1": {{…}}, …}}}}，每题一行（紧凑 JSON），全部题都要写。每题字段：
- 答案：= 材料里的答案（已核，不许改）。
- 依据：1—3 条 {{"sid": 句号, "句": "该句的逐字片段（≥3 词，大小写、标点、弯撇号 ’ 照抄）"}}，sid 必须属于本篇原文。
- 讲：30—220 字，先依据后结论：先说在哪儿听到（新闻 / 短文里说、对话里谁说的），再说这句话什么意思，再说和哪个选项对应；要有“因为 / 所以 / 也就是说 / 可见 / 对应”这类说法；写明“答案选 X”（只出现正确字母）。
- 替换：1—4 条 {{"选项": "正确选项的逐字片段", "原文": "依据句的逐字片段", "类型": 同义改写 / 词性句式转换 / 正反转换 / 概括归纳 / 原词复现}}；两边只差大小写或完全相同才用“原词复现”。尽量找真正的换说法。
- 错项：另外三个字母各一条 {{"类": 没提到 / 张冠李戴 / 偷换 / 说反了 / 过度推断, "说": "8—70 字，点到原文哪里或缺了什么"}}。
- 选项译：A—D 四条通顺中文。标了“（缺念题句）”的题另加 "题译": "题干中文"。
- 长对话没有标说话人，按上下文判断；题干只问 the man / the woman 时，讲里说的必须是这一方。新闻、短文不写“男士 / 女士”。
- 中文地道口语（不要“进行了分析”“被……所……”、不堆“的”），全角标点，不用直引号。自己写，不抄任何出版社 / 网站解析。

# 范例（一题）
"9": {example}
"""


def main(outfile, sets):
    ex_sid = next(s for s in M.SETS if (JC.J / f'{s}.json').exists() and s not in sets)
    ex = json.loads((JC.J / f'{ex_sid}.json').read_text('utf-8'))['题']['9']
    parts = [RULES.format(out=JC.J, example=json.dumps(ex, ensure_ascii=False))]
    for s in sets:
        parts.append('\n' + M.material(s))
    Path(outfile).write_text('\n'.join(parts), 'utf-8')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
