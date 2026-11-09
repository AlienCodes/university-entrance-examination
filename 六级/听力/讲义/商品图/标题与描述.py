"""六级 / 四级听力讲义套装 小店标题与简介（数字取自 商品图.py，同源现算）。
    python3 六级/听力/讲义/商品图/标题与描述.py       → 商品标题.md、商品描述.md、work/标题.txt、work/简介.txt
简介检查（≤ 1000 字、写明虚拟商品不退、禁用词）的规则直接取 六级作文/讲义/商品图/标题与描述.py 的 desc_len / desc_problems（只写一处）。"""
import ast
import os
import re
import sys
from pathlib import Path

HERE = Path(os.path.abspath(__file__)).parent   # 不解析软链接：四级 商品图 的程序是指向这里的软链接
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import 商品图 as G  # noqa: E402

_src = (REPO / '六级作文/讲义/商品图/标题与描述.py').read_text('utf-8')
_ns = {'DESC_MAX': 1000, 'REFUND_KEYS': ('虚拟商品', '不支持退'), 'BANNED': G.BANNED}
for n in ast.parse(_src).body:
    if isinstance(n, ast.Assign) and any(getattr(t, 'id', '') in ('DESC_MAX', 'REFUND_KEYS') for t in n.targets):
        exec(ast.get_source_segment(_src, n), _ns)
    if isinstance(n, ast.FunctionDef) and n.name in ('desc_len', 'desc_problems'):
        exec(ast.get_source_segment(_src, n), _ns)
desc_len, desc_problems = _ns['desc_len'], _ns['desc_problems']

NEW = f"{G.M.V[G.SETS[0]]['year']} 年"
LV, P = G.LV, G.P
SHORT = f'{LV}听力真题{G.NS}套精讲 {G.Y1}-{G.Y0} 讲义+听写本'
LONG = (f"{LV}听力真题{G.NS}套精讲 {G.Y1}-{G.Y0}{P['全称']}听力 {NEW}已更新"
        f' 原文逐句对照 答案依据 同义替换 错项排除 '
        f'高频词手册 听写本 {G.NS}天计划 PDF')
PG = G.PG
DESC = f"""【{LV}听力真题 {G.NS} 套精讲 · 全套讲义】
{G.Y1}—{G.Y0} 年 {G.EXAMS} 次考试、{G.NS} 套真题、{G.NQ} 道题全部收录，{NEW}真题已更新，新的在前。

一、真题 {G.NS} 套精讲（{PG['main']} 页）
· 原文逐句英汉对照：{P['篇型列举']}全部原文，每句配中文；答案出处在原文里黄色标出、标上题号；
· 每道题四个板块：答案依据（逐字引出原文那一句）→ 思路（先依据、后结论，基础弱也跟得上）→ 同义替换（选项和原文换了什么说法）→ 错项排除（每个错误选项属于哪种陷阱：没提到、张冠李戴、偷换、说反了、过度推断）；
· 四个选项都有中文翻译，每套有答案速查和本套高频词。

二、同义替换手册（{PG['syn']} 页）：{G.NSYN} 组“正确选项 ⇄ 原文”的换说法，按五种类型分组，每组标出处。听懂换说法，就听懂了{LV}听力的出题规律。

三、高频词手册（{PG['vocab']} 页）：{G.NS} 套原文逐词统计，{G.NV} 个词条按考到的套数排序（必背 {G.TIER[0]}、常考 {G.TIER[1]}、高频 {G.TIER[2]}），每词标出处。

四、听写本 + 答案（{PG['dict']} + {PG['dans']} 页）：{G.NS} 套原文，每句挖出一个关键词，共 {G.NB} 个空，边听边写。

五、{G.NS} 天刷题计划（{PG['plan']} 页）：每天一套，五项任务打勾，页码直接对到精讲。

六、{LV}历年真题原卷。

所有 PDF 的目录都能点击跳转，带书签；每一章左边有“已读”方框，打勾保存就记住进度。配套视频（视频版真题考试、逐句精读）在 B 站（哔哩哔哩）搜索「朋克英语」免费观看，与讲义原文、译文一致。

PDF 电子讲义，共 {G.TOTAL} 页，手机、平板、电脑都能看，也可以自己打印。
温馨提示：本商品为 PDF 电子讲义（虚拟商品），一经售出暂不支持退换，还请您谅解。"""


def main():
    bad = desc_problems(DESC)
    bad += [f'短标题 {len(SHORT)} 字 > 30' for _ in [0] if len(SHORT) > 30]
    bad += [f'标题出现禁用词「{w}」' for w in G.BANNED if w in SHORT + LONG] + G.year_problems(SHORT + LONG + DESC)
    if bad:
        sys.exit('不写文件：\n  ' + '\n  '.join(bad))
    w = HERE / 'work'
    w.mkdir(exist_ok=True)
    (w / '标题.txt').write_text(f'短版（{len(SHORT)} 字）：\n{SHORT}\n\n长版（{len(LONG)} 字）：\n{LONG}\n', 'utf-8')
    (w / '简介.txt').write_text(DESC + '\n', 'utf-8')
    (HERE / '商品标题.md').write_text(f'# {LV}听力讲义套装 商品标题（标题与描述.py 生成，数字现算）\n\n## 短版（{len(SHORT)} 字）\n\n{SHORT}\n\n## 长版（{len(LONG)} 字）\n\n{LONG}\n', 'utf-8')
    (HERE / '商品描述.md').write_text(f'# {LV}听力讲义套装 商品描述（{desc_len(DESC)} 字，上限 1000；标题与描述.py 生成）\n\n{DESC}\n', 'utf-8')
    print(f'标题 {len(SHORT)} / {len(LONG)} 字，简介 {desc_len(DESC)} 字，检查通过')


if __name__ == '__main__':
    main()
