"""专八 B 站投稿文案：标题（推荐 + 2 个备选）、简介、标签、粉丝动态。数字全部从 专八/data/vocab.json 现算，并检查 B 站字数限制。

    python3 专八/封面/make_post.py      → 专八/封面/B站上传文案.md

用户要求（2026-10-24）：让想学专八、专八词汇的学生尽可能搜得到。所以标题最前面放最常搜的词（专八 / 专八阅读 / 专八真题 / 专八词汇），
后面带上 英语专业八级、TEM-8、英专、逐句精读/翻译、年份、篇数；读起来要通顺、有点击欲，不堆关键词。字数限制同 中考/tools/封面/make_post.py。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TITLE_MAX, DESC_MAX, TAG_MAX, TAG_LEN, DYN_MAX = 80, 2000, 10, 20, 233

P = json.loads((REPO / '专八/data/vocab.json').read_text('utf-8'))['passages']
N = len(P)
SENTS = sum(len(pa) for p in P for pa in p['paras'])
UNIQ = len({w['h'].strip().lower() for p in P for pa in p['paras'] for s in pa for w in s['w']})
WORDS = sum(p['words'] for p in P)
Y0, Y1 = min(p['year'] for p in P), max(p['year'] for p in P)
U = f'{UNIQ // 1000 * 1000}+'          # 只往下取整，与封面一致
assert all(p.get('done') for p in P) and 2020 not in {p['year'] for p in P}

TITLE = f'专八阅读｜专八真题{N}篇逐句精读，用文章记住专八{U}重点词汇｜英语专业八级TEM-8 {Y0}—{Y1}｜英专必看'
ALTS = [f'【专八真题】{Y0}—{Y1}英语专业八级阅读{N}篇全收录｜逐句翻译+生词注释，读文章记住专八单词｜TEM8 英专',
        f'专八词汇别死背！{N}篇专八阅读真题帮你记住{U}重点单词｜英语专业八级TEM-8逐句精读 {Y0}—{Y1}']
TAGS = ['专八', '英语专业八级', '专八阅读', '专八真题', '专八词汇', '专八单词', 'TEM8', '英专', '英语精读', '逐句翻译']

PS = sorted(P, key=lambda p: -p['year'])        # 目录按年份从新到旧（同一年 Passage One—Three 顺序不变）
CAT = '\n'.join(f"P{i} {p['year']} {p['passage']} {p['title']}" for i, p in enumerate(PS, 1))
DESC = f"""【这是什么】{Y0}—{Y1} 年英语专业八级（专八 / TEM-8）阅读真题 {N} 篇全收录（每年 Passage One—Three，2020 年停考），一句一屏逐句精读，用真题文章记忆专八重点词汇：{N} 篇共 {WORDS} 词、{SENTS} 句，标注 {UNIQ} 个单词和短语。
【视频里有什么】逐句朗读 + 逐句中文翻译 + 生词短语编号注释（词性 + 中文释义），4K 大字版，手机上也看得清。
【适合谁】备考专八的英专生、想积累专八词汇 / 专八单词的同学、练英语精读和阅读理解的同学。
【怎么用】先听一遍原文，再暂停逐句看翻译和生词；每天 1—2 篇，读完 {N} 篇就把专八阅读里的重点词汇过了一遍。
【目录】
{CAT}"""
DYN = f'专八阅读真题{N}篇逐句精读来啦！{Y0}—{Y1}年英语专业八级阅读全收录，逐句朗读+逐句翻译+生词注释，用文章记住专八{U}重点词汇，英专备考收藏起来慢慢刷～'

# ───────────── v2 简介（2026-10-24 重做，与 v2 封面呼应）─────────────
# 3 个角度起草（痛点 / 2026 更新 / 方法）→ 3 位英专生盲评（乙 22、丙 21.5、甲 19 分）→ 合成定稿；评审挑出的夸大说法全部不用。
# 正文模板里的数字全部从 vocab.json 现算；目录由程序生成（按年份从新到旧）。输出 B站简介_v2_{N}篇.txt，不覆盖旧精修版。
N_NEW = sum(p['year'] == Y1 for p in P)
V2_HEAD = """单词书背了就忘？在专八阅读真题文章里记住专八重点单词：一句一屏，朗读 + 翻译 + 生词注释。
🆕 {Y1} 年 {N_NEW} 篇已更新｜{Y1}—{Y0} 共 {N} 篇、{SENTS} 句全收录。
同一个词，放回它在考试里出现的那句话，更容易记住。

📚 收录范围
英语专业八级（专八 / TEM-8）阅读真题，{Y1}—{Y0} 每年 Passage One—Three 全部收录（2020 年停考），共 {N} 篇。
P1—P{N_NEW} 就是 {Y1} 年最新的 {N_NEW} 篇。明年要考、想先熟悉专八真题的英专同学，现在就能用上。

📊 一共有多少内容
{N} 篇共 {WORDS} 词、{SENTS} 句，标注了 {UNIQ} 个不重复的单词和短语。每个标注的词都在它出现的那一句里就地注释，专八词汇在真题句子里一句一句读到。

🎬 画面怎么看
· 一句一屏：英文男声逐句朗读，同屏显示这一句的中文翻译
· 生词带编号注释：词性 + 中文释义，单词蓝色、短语绿色
· 4K 大字版，手机上也看得清

✍️ 建议这样用
一天 1 篇，一个月读完 {N} 篇。第一遍跟着朗读，把每一句读懂；第二遍看到编号的专八单词先停一下，自己想意思，再看注释。

⚠️ 先说清楚
这是真题文章的逐句精读，视频里没有题目、选项、答案和解析，也不讲做题技巧。可以先用自己的真题册做题，做完再来逐句精读。适合想把专八阅读文章真正读懂、顺带积累专八词汇的英专同学。

📖 分P目录（点分P直接跳到对应篇目）"""
V2_TAIL = """觉得有用就先收藏，备考时随时回来翻；也可以转给一起考专八的同学。
哪句翻译或注释你觉得不准确，欢迎在评论区指出，我会一条条看、认真改。哪一篇读得最吃力？也在评论区告诉我 👇"""
# 评审指出的夸大 / 与画面不符的说法：一律不许出现
V2_BANNED = ['不用单独去背', '都标出来', '都放回', '复盘', '遮住翻译', '只听朗读', '系统积累', '比单词表', '一篇读不完', '所有重点', '包过', '必过', '命中']
V2_KEYS = ['专八', '专八阅读', '专八真题', '专八词汇', '专八单词', '英语专业八级', 'TEM-8', '英专']


def v2_desc():
    return V2_HEAD.format(N=N, SENTS=SENTS, UNIQ=UNIQ, WORDS=WORDS, Y0=Y0, Y1=Y1, N_NEW=N_NEW) + '\n' + CAT + '\n\n' + V2_TAIL


def v2_check(t):
    import re
    errs = []
    if len(t) > DESC_MAX:
        errs.append(f'简介 {len(t)} 字，超过 {DESC_MAX}')
    ok = {str(x) for x in (N, SENTS, UNIQ, WORDS, Y0, Y1, 2020, N_NEW, 1, 4)} | {str(i) for i in range(1, N + 1)}
    body = t.replace(CAT, '')
    errs += [f'数字 {x} 不是从数据算出来的' for x in re.findall(r'\d+', body) if x not in ok]
    errs += [f'夸大说法：{b}' for b in V2_BANNED if b in t]
    errs += [f'缺搜索词：{k}' for k in V2_KEYS if k not in t]
    if '没有题目、选项、答案和解析' not in t:
        errs.append('缺“视频里没有题目、选项、答案和解析”的说明（不许让人以为有讲解）')
    top = '\n'.join(t.splitlines()[:2])               # 手机上折叠时露出的前两行
    errs += [f'前两行缺：{k}' for k in ('专八', '单词书背了就忘', str(Y1), f'{N} 篇') if k not in top]
    if CAT not in t:
        errs.append('目录不是程序生成的那份')
    return errs


if '--简介v2' in sys.argv or '--简介v2自检' in sys.argv:
    T2 = v2_desc()
    if '--简介v2自检' in sys.argv:               # 双向验证：正常 0 处；放进错数字、夸大说法、删掉说明，都必须报出
        bad = []
        if v2_check(T2):
            bad.append(f'正常简介报错：{v2_check(T2)}')
        for name, t in [('错数字', T2.replace(str(SENTS), str(SENTS + 4), 1)), ('夸大', T2 + '专八词汇不用单独去背'),
                        ('删说明', T2.replace('没有题目、选项、答案和解析', '有题目')), ('超长', T2 + '啊' * 2000),
                        ('前两行没钩子', T2.replace('单词书背了就忘？', '', 1))]:
            if not v2_check(t):
                bad.append(f'埋雷“{name}”没报出')
        print('\n'.join(bad) or '简介 v2 自检通过：正常 0 处，5 种埋雷全部报出')
        sys.exit(1 if bad else 0)
    e = v2_check(T2)
    if e:
        print('简介 v2 检查不通过：\n  ' + '\n  '.join(e))
        sys.exit(1)
    (HERE / f'B站简介_v2_{N}篇.txt').write_text(T2, 'utf-8')
    print(f'B站简介_v2_{N}篇.txt {len(T2)} 字，检查通过')
    sys.exit(0)


errs = [f'{n} {len(t)} 字，超过 {TITLE_MAX}' for n, t in [('标题', TITLE)] + [(f'备选{i}', a) for i, a in enumerate(ALTS, 1)] if len(t) > TITLE_MAX]
if len(DESC) > DESC_MAX:
    errs.append(f'简介 {len(DESC)} 字，超过 {DESC_MAX}')
if len(DYN) > DYN_MAX:
    errs.append(f'粉丝动态 {len(DYN)} 字，超过 {DYN_MAX}')
if len(TAGS) > TAG_MAX or len(set(TAGS)) != len(TAGS) or any(len(t) > TAG_LEN for t in TAGS):
    errs.append('标签超出限制或重复')
for kw in ['专八', '专八阅读', '专八真题', '英语专业八级', '英专']:          # 搜索词必须都在推荐标题里
    if kw not in TITLE:
        errs.append(f'推荐标题缺搜索词：{kw}')
if errs:
    sys.exit('文案检查不通过：\n  ' + '\n  '.join(errs))

alts = '\n'.join(f'- 备选 {i}（{len(a)} 字）：{a}' for i, a in enumerate(ALTS, 1))
(HERE / ('B站上传文案.md' if N == 27 else f'B站上传文案_{N}篇.md')).write_text(f"""# 专八阅读真题 {N} 篇 · B 站上传文案

由 `专八/封面/make_post.py` 从 `专八/data/vocab.json` 生成，数字与视频、封面一致；字数已按 B 站限制检查（标题 ≤ {TITLE_MAX} 字、简介 ≤ {DESC_MAX} 字、标签 ≤ {TAG_MAX} 个且每个 ≤ {TAG_LEN} 字、粉丝动态 ≤ {DYN_MAX} 字）。

## 标题

推荐（{len(TITLE)} 字）：{TITLE}

{alts}

## 标签（{len(TAGS)} 个，按搜索量排）

{'　'.join(TAGS)}

## 简介（{len(DESC)} 字）

{DESC}

## 粉丝动态（{len(DYN)} 字）

{DYN}

## 封面

`专八/封面/系列封面/专八阅读真题{N}篇_封面_16比9.jpg`、`专八阅读真题{N}篇_封面_4比3.jpg`
""", 'utf-8')
FINE = f"""专八词汇别再死背单词书了！{Y0}—{Y1} 专八阅读真题 {N} 篇全收录，一句一屏逐句精读，在真题文章里记住 {UNIQ} 个专八重点单词和短语。

📌 视频里有什么
✅ 真题原文：英语专业八级（TEM-8）{Y0}—{Y1} 每年 Passage One—Three（2020 年停考），共 {N} 篇、{WORDS} 词、{SENTS} 句
✅ 一句一屏：逐句朗读 + 逐句中文翻译，边听边看
✅ 生词全标注：{UNIQ} 个单词和短语编号注释（词性 + 中文释义），单词蓝色、短语绿色，一眼分清
✅ 4K 大字版：手机上也看得清清楚楚

📖 推荐用法（每天 1 篇，{N} 天刷完）
① 先不看翻译，听一遍原文，记下没听懂、不认识的地方
② 再逐句暂停，看翻译和生词注释，跟着读一遍
③ 第二天先回看前一天的生词，在文章里复习，比背词表记得牢

🎯 适合谁
备考专八的英专生；想系统积累专八词汇、专八单词的同学；想练英语精读、阅读理解和翻译的同学

📂 目录（按年份从新到旧，点分P直接看）
{CAT}

💬 评论区告诉我：你今年考专八吗？最想先看哪一年？
觉得有用就点赞、收藏起来慢慢刷，转给一起备考的同学，专八一起加油！"""
assert len(FINE) <= DESC_MAX, f'精修版简介 {len(FINE)} 字，超过 {DESC_MAX}'
FP = HERE / f'B站简介精修版_{N}篇.txt'
if N == 27:          # 27 篇版是人工精修定稿：程序生成的必须与它逐字相同（证明模板与定稿一致），不覆盖
    assert FP.read_text('utf-8') == FINE, '精修版模板与 27 篇定稿不一致'
else:
    FP.write_text(FINE, 'utf-8')
print(FP.name, len(FINE), '字')
print(TITLE, len(TITLE))
for a in ALTS:
    print(a, len(a))
print(len(DESC), len(DYN))
