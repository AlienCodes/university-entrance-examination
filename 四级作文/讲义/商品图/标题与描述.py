"""四级写作讲义 B 站小店：商品标题.md、商品描述.md（数字全部取自 商品图.py，同源现算、同样断言）。

    python3 四级作文/讲义/商品图/标题与描述.py

检查：短标题 ≤ 30 字；全文不出现 商品图.BANNED 里的词（绝对化用语、纸质版、价格、销量）。
"""
import ast
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESC_MAX = 1000                       # 小店简介上限（用户 2026-10-26）：按粘贴进去的全部字符算，换行不算
REFUND_KEYS = ('虚拟商品', '不支持退')  # 简介必须写明：虚拟商品、一经售出不支持退款（用户 2026-10-26）
# 禁用词与商品图同一份（直接读 商品图.py 里 BANNED 那一行，不加载渲染程序）
BANNED = ast.literal_eval(re.search(r"^BANNED = (\[.*\])", (HERE / '商品图.py').read_text('utf-8'), re.M)[1])


def desc_len(desc):
    return len(desc.replace('\n', ''))


def desc_problems(desc):
    """简介：≤ 1000 字；必须有虚拟商品不退款说明；不许有禁用词。"""
    out = []
    if desc_len(desc) > DESC_MAX:
        out.append(f'简介 {desc_len(desc)} 字 > {DESC_MAX}')
    out += [f'简介缺少「{k}」（虚拟商品不退款说明）' for k in REFUND_KEYS if k not in desc]
    out += [f'简介出现禁用词「{w}」' for w in BANNED if w in desc]
    return out


def selftest():
    """双向验证：1001 字报、1000 字不报；去掉退款说明报；放进禁用词报。"""
    base = '本商品为 PDF 电子讲义（虚拟商品），一经售出暂不支持退换，还请您谅解。'
    fill = lambda n: base + '四' * (n - desc_len(base))
    cases = [(fill(1000), False), (fill(1001), True), (fill(999).replace('\n', '') + '\n', False),
             (fill(1000).replace('虚拟商品', '电子资料'), True), (fill(1000).replace('不支持退换', '可以联系'), True),
             (fill(998) + '保过', True)]
    wrong = [i for i, (t, want) in enumerate(cases) if bool(desc_problems(t)) != want]
    print('简介检查双向验证：', len(cases), '例', '全部正确' if not wrong else f'不符 {wrong}')
    return 1 if wrong else 0


def load():
    spec = importlib.util.spec_from_file_location('spt', HERE / '商品图.py')
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    return M


if __name__ == '__main__' and sys.argv[1:] == ['--自检']:
    sys.exit(selftest())
M = load()
N, PAT, EX, VOC, DIC, STEP, REQ, UP, PG, TOTAL, Y0, Y1, SEC = M.N, M.PAT, M.EX, M.VOC, M.DIC, M.STEP, M.REQ, M.UP, M.PG, M.TOTAL, M.Y0, M.Y1, M.SEC
NE = len(M.EXAMS)
NEW = M.NEWEST.replace('.', '年') + '月'
W0, W1 = min(M.WC), max(M.WC)
LIM = {tuple(map(int, re.findall(r'\d+', e['limit']))) for e in M.ES}       # 题目字数要求，从题目数据现算
assert len(LIM) == 1 and len(next(iter(LIM))) == 2, LIM
L0, L1 = next(iter(LIM))

SHORT = f'四级作文真题满分范文{N}篇 {Y0}-{Y1} 讲义+默写卡'
LONG = f'四级英语写作满分范文精讲 {Y0}-{Y1}大学英语四级作文真题全{N}篇 {NEW}已更新 原题中文译文 升格示范 高分句式 讲义+默写卡+答案 PDF'

DESC = f"""【四级英语写作 · 真题满分范文精讲】
{Y0}—{Y1} 年大学英语四级写作真题全收录：{NE} 次考试、{N} 篇满分范文，{NEW}已更新。
不只给范文，更一篇一篇教你：题目怎么审、每条要求落到哪一句、每句话怎么写出来、普通句怎么改成满分句。

📦 3 份 PDF 电子讲义，共 {TOTAL} 页（A4 排版，可打印）
①《四级英语写作满分范文精讲》{PG['讲义']} 页
②《四级作文默写卡》{PG['默写卡']} 页
③《四级作文默写卡（答案）》{PG['答案']} 页

📖 每篇 {SEC} 个板块讲透
原题 + 题目译文 → 审题 → 题目要求逐条落实 → 写作思路 → 满分范文 → 一步一步写 → 为什么是满分档 → 升格示范 → 高分句式 → 亮点词汇
· 原题配中文译文：英文题目看不懂也不怕，每篇逐句翻译
· 满分范文：每篇 {W0}—{W1} 词（题目要求 {L0}—{L1} 词），荧光笔标出高分句式，附参考译文
· 题目要求逐条落实：共 {REQ} 条，每条要求对应范文哪一句
· 一步一步写：共 {STEP} 步，每一句是怎么想出来的都讲清楚
· 升格示范：共 {UP} 组，普通句一步一步改成满分句
· 高分句式：共 {PAT} 个，公式 + 讲解 + 2 个仿写例句，书末附总表
· 亮点词汇：共 {VOC} 个，把普通说法换成高分说法
· 开篇写作总攻略：评分标准、常考题型、30 分钟写作流程、字数控制、中式英语黑名单

✍️ 默写卡：默句子，不只是默单词
{DIC} 道句式填空 + {DIC} 句看中文默整句，答案单独一册，默完马上自己批改。

🧭 用起来方便
三份 PDF 都有可点击目录和侧边栏书签，点一下标题就跳到那一篇；每篇都有“已读”勾选框，打勾保存，读到哪里一目了然。

🎯 适合：准备四级、拿到作文题没思路、写不满字数、背了模板分数上不去、句子写不地道的同学。
配套视频：B 站「四级真题范文」{N} 集逐句精读，可以对照着看。

💝 温馨提示
本商品为 PDF 电子讲义（虚拟商品），下单后即可获取全部内容，因此一经售出暂不支持退换，还请您谅解。使用中如有任何问题，欢迎随时私信，我们会尽力帮您解决。资料仅供个人学习使用，请勿转发或转售，感谢您的支持！"""

TITLE_MD = f"""# 四级写作讲义 商品标题（由 标题与描述.py 生成，数字现算）

## 短版（{len(SHORT)} 字）

{SHORT}

## 长版（{len(LONG)} 字，给允许长标题的平台）

{LONG}

不写纸质版、价格、销量、提分保证；不用“最、第一、保过、必过”等绝对化用语（程序检查）。
"""

DESC_MD = f"""# 四级写作讲义 商品描述（由 标题与描述.py 生成，数字现算）

数字全部与商品图同源（商品图.py 从讲义数据现算并断言）：{N} 篇、{NE} 次考试、{PAT} 句式、{EX} 例句、{VOC} 词汇、{STEP} 步、{REQ} 条要求、{UP} 组升格、{DIC} 默写、{PG['讲义']} + {PG['默写卡']} + {PG['答案']} = {TOTAL} 页。

## 简介（{desc_len(DESC)} 字，上限 {DESC_MAX}，换行不计）

```
{DESC}
```

## 卖点（一句话版，放商品副标题）

{Y0}—{Y1} 四级写作真题 {N} 篇满分范文，原题配中文译文，每篇 {SEC} 个板块讲透：审题、逐条落实、一步一步写、{UP} 组升格示范、{PAT} 个高分句式；附默写卡 + 答案，PDF 共 {TOTAL} 页。

## B 站评论区挂链接（一条评论）

```
📌 视频配套讲义（PDF）：{N} 篇范文每篇都有原题中文译文，讲清楚怎么审题、每条要求落到哪句、每句话怎么写出来；{UP} 组升格示范把普通句一步步改成满分句；{PAT} 个高分句式带公式和仿写例句；另附默写卡 + 答案。需要的同学可以看看👇
```
"""

if __name__ == '__main__':
    bad = desc_problems(DESC)
    if len(SHORT) > 30:
        bad.append(f'短标题 {len(SHORT)} 字 > 30')
    for name, t in (('标题', TITLE_MD.split('不写纸质版')[0]), ('描述', DESC_MD)):
        bad += [f'{name}出现禁用词「{w}」' for w in BANNED if w in t]
    if bad:
        print('\n'.join(bad))
        sys.exit(1)
    (HERE / '商品标题.md').write_text(TITLE_MD, 'utf-8')
    (HERE / '商品描述.md').write_text(DESC_MD, 'utf-8')
    (HERE / 'work').mkdir(exist_ok=True)
    (HERE / 'work' / '简介.txt').write_text(DESC + '\n', 'utf-8')            # 打包.py 用：只有可直接粘贴的简介正文
    (HERE / 'work' / '标题.txt').write_text(f'短版（{len(SHORT)} 字）\n{SHORT}\n\n长版（{len(LONG)} 字）\n{LONG}\n', 'utf-8')
    print(f'短标题 {len(SHORT)} 字：{SHORT}\n长标题 {len(LONG)} 字\n简介 {desc_len(DESC)} 字（上限 {DESC_MAX}）；退款说明、禁用词检查通过')
