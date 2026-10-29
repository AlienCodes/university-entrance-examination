"""生成 四级作文/封面/B站详细简介.md：B 站简介（≤2000 字）+ 置顶评论（≤1000 字）。
数字全部从数据现算（踩坑 70）：篇数、考试次数、年份、每篇词数、句数、标注的单词 / 短语数、文体、每集时长。
    python3 四级作文/封面/详细简介.py"""
import json, re, collections
from pathlib import Path
HERE = Path(__file__).resolve().parent; P = HERE.parent
S = json.loads((P / '作文' / 'sents.json').read_text('utf-8'))
TM = json.loads((P / 'audio' / 'timings.json').read_text('utf-8'))
dur = {}
def walk(x):
    if isinstance(x, dict):
        if 'duration' in x and 'file' in x: dur[x['file'].split('/')[-1][:3]] = x['duration']
        else: [walk(v) for v in x.values()]
    elif isinstance(x, list): [walk(v) for v in x]
walk(TM)
GENRE = lambda g: '议论文' if g.startswith('议论文') else '建议信' if g.startswith('建议') else '记叙文' if g.startswith('记叙') else g
rows = []; W = set(); PH = set(); nsent = 0
for e in S:
    a = (P / 'ann' / f"{e['id']}.txt").read_text('utf-8')
    T = re.search(r'^T: (.*)$', a, re.M).group(1); g = GENRE(re.search(r'^G: (.*)$', a, re.M).group(1))
    items = [x.strip() for l in re.findall(r'^= (.*)$', a, re.M) for x in l.split(' | ')]
    W |= {re.sub(r'\{.*\}', '', x.split('=')[0]).lower() for x in items if not x.startswith('~')}
    PH |= {re.sub(r'\{.*\}', '', x.split('=')[0]).lower() for x in items if x.startswith('~')}
    nsent += len(re.findall(r'^\d+ ', a, re.M))
    rows.append(dict(id=e['id'], y=e['year'], m=e['month'], s=e['set'], T=T, g=g, w=e['words'], d=dur[e['id']]))
N = len(rows); EX = len({(r['y'], r['m']) for r in rows}); Y0 = min(r['y'] for r in rows); Y1 = max(r['y'] for r in rows)
NEW = max((r['y'], r['m']) for r in rows); nnew = sum((r['y'], r['m']) == NEW for r in rows)
w0, w1 = min(r['w'] for r in rows), max(r['w'] for r in rows); d0, d1 = min(r['d'] for r in rows), max(r['d'] for r in rows)
G = collections.Counter(r['g'] for r in rows)
fl = lambda n: n // 100 * 100   # “700 多个”
P_ = lambda k: [i + 1 for i, r in enumerate(rows) if k(r)]
TOPIC = [('🤖 科技与学习方式', [1, 9, 21, 30, 31, 32]), ('📚 学习与学术', [3, 5, 6, 8]),
         ('🏫 校园生活与活动', [2, 4, 12, 25, 26, 27, 28, 29]), ('🌏 文化与个人能力', [7, 11, 19, 24]),
         ('🏃 健康与运动', [22, 23]), ('🏙 大学与社会', [10, 13, 14, 15, 20]), ('✍️ 个人经历与描述', [16, 17, 18])]
assert sorted(sum((v for _, v in TOPIC), [])) == list(range(1, N + 1)), '话题分类必须恰好覆盖全部篇目'
pl = lambda L: ' '.join(f'P{i}' for i in L)
gline = '、'.join(f'{k} {v} 篇' for k, v in G.most_common())
dirl = '\n'.join(f"P{i+1} {r['y']}.{r['m']} 第{r['s']}套｜{r['T']}（{r['g']}）" for i, r in enumerate(rows))
desc = f"""【{Y0}—{Y1} 大学英语四级写作真题｜{N} 篇满分范文逐句精读】{NEW[0]}年{NEW[1]}月最新 {nnew} 套已更新，一集 1 分多钟，彻底搞定四级写作！

😫 你是不是也这样？
· 拿到题目不知道怎么开头，憋半天写不满 120 词
· 背了一堆模板，一到考场还是卡壳，句子写得像中文
· 真题做了不少，好词好句一个也没记住

✅ 这套视频能帮你什么
· 真题全覆盖：{Y0}年6月—{NEW[0]}年{NEW[1]}月，{EX} 次考试、{N} 套真题，每套一篇满分范文
· 字数刚刚好：每篇 {w0}—{w1} 词（题目要求 120—180 词），照着练不怕写不满
· 文体全覆盖：{gline}
· 词句积累：{N} 篇共 {nsent} 句，标注 {fl(len(W))} 多个高频单词、{fl(len(PH))} 多个地道短语，考场直接能用

📺 每一集都有
① 片头：年份、试卷、第几套、题目，一眼看清
② 原题屏：原卷题目 + 完整中文翻译，字数要求、写作要点逐条看懂
③ 逐句朗读：一句一屏，标准男声，句与句之间停 0.8 秒，跟读不着急
④ 逐句翻译：每句英文下面都有中文，看得懂才记得住
⑤ 好词好句：绿色是单词、红色是短语，带圆圈编号；右边词汇栏写明词性和意思
⑥ 4K 高清，全片音量统一、没有杂音，手机上也看得清、听得清

📖 推荐用法（每篇 3 遍）
第 1 遍 审题：停在原题屏，自己想 1 分钟——开头怎么写、分几点、怎么结尾，再看范文
第 2 遍 跟读：一句一句跟着读，把绿色单词、红色短语抄进笔记本
第 3 遍 默写：关掉声音，只看中文说出 / 写出英文，默得出来，考场上就写得出来
进阶：同类题连着看（如 P13—P15 都是“大学设施该不该向公众开放”），对比开头、过渡、结尾的写法

📅 {N} 天打卡：每天 1 集，评论区打卡“第 N 天”；按话题分类的目录见置顶评论

🗂 全部 {N} 集目录（括号里是文体）
{dirl}

⭐ 点赞 + 收藏，考前一周拿出来再刷一遍；关注我，同系列还有四级阅读真题逐句精读。"""
pin = f"""📌 按话题分类（同类题连着看，开头、过渡、结尾的写法最好对比）
""" + '\n'.join(f'{k}：{pl(v)}' for k, v in TOPIC) + f"""

📌 按文体
建议信：{pl(P_(lambda r: r['g'] == '建议信'))}
报告：{pl(P_(lambda r: r['g'] == '报告'))}
记叙文 / 命题作文：{pl(P_(lambda r: r['g'] in ('记叙文', '命题作文')))}
其余 {G['议论文']} 篇都是议论文

📌 考前冲刺怎么用
考前 1 周：每个话题挑 1 篇，把开头句、过渡句、结尾句默写一遍
考前 1 天：只看收藏的好词好句，不再看新的
考场上：先花 2 分钟列提纲（开头表态 → 2—3 个理由或建议 → 结尾总结），再动笔

每集 {round(d0)}—{round(d1)} 秒，一共 {round(sum(r['d'] for r in rows) / 60)} 分钟左右；有问题评论区留言，看到都会回 💬"""
for name, t, lim in (('简介', desc, 2000), ('置顶评论', pin, 1000)):
    assert len(t) <= lim, f'{name} {len(t)} 字，超过上限 {lim}'
    for bad in ('押题', '保过', '100%', '微信', 'QQ', '网盘', '加群'):
        assert bad not in t, f'{name} 含禁用词 {bad}'
(HERE / 'B站详细简介.md').write_text(f"""# 四级写作 B站详细简介（由 详细简介.py 生成，数字现算）

## 简介（{len(desc)} 字，上限 2000）——复制到投稿页“简介”

```
{desc}
```

## 置顶评论（{len(pin)} 字，上限 1000）——发布后发一条评论并置顶

```
{pin}
```
""", 'utf-8')
print(len(desc), len(pin), N, EX, w0, w1, nsent, len(W), len(PH), dict(G), round(d0, 1), round(d1, 1))
