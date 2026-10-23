"""考研英语写作讲义 小店商品图（1:1，2000×2000，共 9 张）。

    /opt/ttsenv/bin/python 考研作文/讲义/商品图/素材.py      # 先画素材（真实内页元素、封面、内页）
    /opt/ttsenv/bin/python 考研作文/讲义/商品图/商品图.py

输出 考研作文/讲义/商品图/成品/01_….jpg 等（上传用 JPG）。
用户要求（2026-10-23）：讲义要在小店里卖，1:1 图片，非常详细地展示讲义的亮点，让考研的人看到就想下单。
原则：图上展示的全部是讲义里的真实内容（用讲义自己的排版程序渲染出来的元素和内页，不做假图）；
图上的每个数字都从讲义数据现算（篇数、句式、例句、替换说法、默写题、页数），数据一改就停下核对；
不写讲义本身没有的承诺（不写电子版 / 纸质版、价格、提分保证）。
渲染后程序自查：文字不出画、文字互不重叠、图片全部加载、字体全部加载。
"""
import glob
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]
REPO = C.parent
S = HERE / 'work' / '素材'
WORK = HERE / 'work'
OUT = HERE / '成品'
F_BLACK = REPO / '四级/封面/fonts/NotoSansSC_900Black.ttf'
F_BOLD = REPO / '四级/封面/fonts/NotoSansSC_700Bold.ttf'
F_INTER = REPO / '专八/tools/fonts/inter/files/inter-latin-800-normal.woff2'

# ---------------------------------------------------------------- 数字（从讲义数据现算）
D = [json.loads(open(f, encoding='utf-8').read()) for f in sorted(glob.glob(str(C / '讲义/data/w*.json')))]
P = {p['id']: p for p in json.loads((C / 'data/vocab.json').read_text('utf-8'))['passages']}
G = json.loads((C / '讲义/data/总论.json').read_text('utf-8'))
N = len(D)
PAT = sum(len(d['句式']) for d in D)
EX = sum(len(x['例句']) for d in D for x in d['句式'])
ALT = sum(len(x['替换']) for d in D for x in d['句式'])
VOC = sum(len(d['词汇']) for d in D)
DIC = sum(len(d['默写']) for d in D)
BAD = sum(len(b['行']) for s in G['小节'] for b in s['内容'] if b['类'] == '对照')


def pages(f):
    return int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', str(f)], capture_output=True, text=True).stdout).group(1))


PG = {k: pages(C / '讲义' / f) for k, f in (('讲义', '考研英语写作满分范文精讲.pdf'), ('默写卡', '考研作文默写卡.pdf'), ('答案', '考研作文默写卡（答案）.pdf'))}
assert (N, PAT, EX, ALT, VOC, DIC, BAD) == (24, 143, 286, 291, 187, 139, 10), (N, PAT, EX, ALT, VOC, DIC, BAD)
assert all(len(x['例句']) == 2 for d in D for x in d['句式'])          # “每个句式两个仿写例句”
assert PG == {'讲义': 194, '默写卡': 56, '答案': 31}, PG                # 数据或排版一改就停下，先核对图上的说法
TOTAL = sum(PG.values())

INK, INK2, MUTE, BLUE, BERRY, GREEN = '#1f2537', '#3d4458', '#6b7287', '#2456a6', '#c0185a', '#2e7d4f'
HY, HP, PAPER, COVER, KY = '#ffe46b', '#ffc4d8', '#faf8f3', '#7db4e8', '#ff4a12'


def img(name):
    return (S / name).as_uri()


def css():
    return f"""
@font-face{{font-family:Black;src:url({F_BLACK.as_uri()})}}
@font-face{{font-family:Bold;src:url({F_BOLD.as_uri()})}}
@font-face{{font-family:Inter;font-weight:800;src:url({F_INTER.as_uri()})}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1000px;height:1000px;overflow:hidden}}
body{{position:relative;font-family:Bold,sans-serif;color:{INK};background:{PAPER}}}
.dots{{position:absolute;inset:0;background:radial-gradient(circle at 1.5px 1.5px,rgba(70,92,128,.16) 1.3px,transparent 1.8px) 12px 12px/26px 26px}}
.blue{{background:{COVER}}}.blue .dots{{background:radial-gradient(circle at 2px 2px,rgba(255,255,255,.30) 1.8px,transparent 2.3px) 14px 14px/30px 30px}}
.ab{{position:absolute;white-space:nowrap}}
.lat{{font-family:Inter,Black,sans-serif;font-weight:800}}
.hy{{box-shadow:inset 0 -.44em 0 {HY};border-radius:.06em;padding:0 .04em}}
.hp{{box-shadow:inset 0 -.44em 0 {HP};border-radius:.06em;padding:0 .04em}}
.h1{{font:900 58px/1.18 Black;color:{INK}}}
.sub{{font:700 27px/1.4 Bold;color:{INK2}}}
.top{{font:900 21px/1 Black;color:#fff;background:{BLUE};padding:9px 20px 10px;border-radius:999px;letter-spacing:.06em}}
.no{{font:800 22px/1 Inter;color:{BLUE};letter-spacing:.08em}}
.shot{{position:absolute;background:#fff;border-radius:14px;box-shadow:0 2px 0 rgba(31,37,55,.06),0 14px 34px rgba(31,37,55,.16);overflow:hidden}}
.shot img{{display:block;width:100%}}
.tag{{position:absolute;white-space:nowrap;font:900 22px/1 Black;color:#fff;padding:9px 16px 10px;border-radius:12px;box-shadow:0 5px 14px rgba(31,37,55,.22)}}
.tb{{background:{BLUE}}}.tr{{background:{BERRY}}}.tg{{background:{GREEN}}}.tk{{background:{KY}}}
.dot{{display:inline-block;width:34px;height:34px;border-radius:50%;background:{BERRY};color:#fff;font:800 20px/34px Inter;text-align:center}}
.page{{position:absolute;background:#fff;box-shadow:0 3px 0 rgba(31,37,55,.06),0 18px 40px rgba(31,37,55,.24);border-radius:4px}}
.page img{{display:block;width:100%;border-radius:4px}}
"""


def head(no, title, sub, y=46):
    return (f'<div class="ab" style="left:50px;top:{y}px"><span class="top">考研英语写作满分范文精讲</span></div>'
            f'<div class="ab no" style="right:50px;top:{y + 8}px">{no:02d} / 09</div>'
            f'<div class="ab h1" data-k="h1" style="left:48px;top:{y + 52}px">{title}</div>'
            + (f'<div class="ab sub" data-k="sub" style="left:50px;top:{y + 128}px">{sub}</div>' if sub else ''))


# ---------------------------------------------------------------- 01 主图
def p01():
    nums = [(f'{N}', '篇', '6 年真题全收录'), (f'{PAT}', '个', '高分句式'), (f'{EX}', '个', '仿写例句'), (f'{TOTAL}', '页', '讲义+默写卡+答案')]
    rows = ''.join(f'<div style="display:flex;align-items:baseline;margin-bottom:22px"><span class="lat" style="font-size:66px;color:{KY};letter-spacing:-.02em;min-width:150px;text-align:right">{a}</span>'
                   f'<span style="font:900 30px Black;margin:0 14px 0 6px">{b}</span><span style="font:700 28px Bold;color:{INK}">{c}</span></div>' for a, b, c in nums)
    return f"""<body class="blue"><div class="dots"></div>
<div class="ab" data-k="pill" style="left:50px;top:44px"><span class="top" style="font-size:25px;background:#173d7a"><span class="lat">2021—2026</span> · 英语一 + 英语二 · 大小作文</span></div>
<div class="ab" data-k="t1" style="left:44px;top:104px;font:900 112px/1.1 Black"><span style="color:{KY};text-shadow:0 .05em 0 {HY}">考研</span>英语写作</div>
<div class="ab" data-k="t2" style="left:48px;top:236px;font:900 98px/1.15 Black"><span class="hy">满分范文精讲</span></div>
<div class="ab" data-k="hook" style="left:50px;top:378px;font:900 36px/1 Black;color:#fff;background:{INK};padding:14px 24px 16px;border-radius:14px">一步一步教你写出满分作文</div>
<div class="ab" data-box style="left:20px;top:470px;width:470px;height:470px;background:#fffdf8;border-radius:30px;box-shadow:0 18px 40px rgba(20,50,90,.25)"></div>
<div class="ab" data-k="nums" style="left:24px;top:506px">{rows}</div>
<div class="page" style="left:655px;top:470px;width:300px;transform:rotate(9deg)"><img src="{img('封面_答案.png')}"></div>
<div class="page" style="left:600px;top:455px;width:300px;transform:rotate(3deg)"><img src="{img('封面_默写卡.png')}"></div>
<div class="page" style="left:520px;top:440px;width:310px;transform:rotate(-5deg)"><img src="{img('封面_讲义.png')}"></div>
<div class="tag tk" data-k="g1" style="left:540px;top:900px;transform:rotate(-3deg)">讲义 {PG['讲义']} 页</div>
<div class="tag tb" data-k="g2" style="left:700px;top:912px;transform:rotate(2deg)">默写卡 {PG['默写卡']} 页 + 答案</div>
</body>"""


# ---------------------------------------------------------------- 02 痛点 → 解决
def p02():
    pain = [('拿到题目没思路', '不知道每段该写什么、写多少'), ('背了一堆模板', '一写就和别人撞车，分数上不去'), ('句子写不地道', '满篇中式英语，自己还看不出来')]
    fix = [('审题 + 写作思路', '每段写什么，提纲列得清清楚楚'), ('一步一步写', '每一句话是怎么想出来的，全部讲透'), (f'{PAT} 个高分句式 + 中式英语黑名单', '公式、讲解、仿写例句，写出地道句子')]
    p = ''.join(f'<div style="display:flex;align-items:center;background:#fff;border-radius:18px;padding:14px 24px;margin-bottom:12px;box-shadow:0 8px 24px rgba(31,37,55,.10)">'
                f'<span style="flex:none;width:46px;height:46px;border-radius:50%;background:#ffe3ea;color:{BERRY};font:900 30px/46px Black;text-align:center;margin-right:20px">✕</span>'
                f'<div><div style="font:900 34px/1.25 Black">{a}</div><div style="font:700 24px/1.4 Bold;color:{MUTE}">{b}</div></div></div>' for a, b in pain)
    f = ''.join(f'<div style="display:flex;align-items:center;margin-bottom:22px">'
                f'<span style="flex:none;width:46px;height:46px;border-radius:50%;background:{GREEN};color:#fff;font:900 30px/46px Black;text-align:center;margin-right:20px">✓</span>'
                f'<div><div style="font:900 32px/1.25 Black"><span class="hy">{a}</span></div><div style="font:700 24px/1.4 Bold;color:{INK2}">{b}</div></div></div>' for a, b in fix)
    return f"""<body><div class="dots"></div>{head(2, '考研作文，你是不是也这样？', '')}
<div class="ab" data-k="pain" style="left:50px;top:200px;width:900px">{p}</div>
<div class="ab" data-k="arrow" style="left:50px;top:556px;width:900px;text-align:center;font:900 34px/1 Black;color:#fff;background:{BLUE};padding:20px 0 22px;border-radius:18px">这本讲义，一篇一篇帮你解决 ↓</div>
<div class="ab" data-k="fix" style="left:60px;top:664px">{f}</div>
</body>"""


# ---------------------------------------------------------------- 03 每篇 7 步
def p03():
    steps = [('原题', '真题原题高清截图'), ('审题', '要写什么、哪里容易失分'), ('写作思路', '先列提纲，每段一个任务'), ('满分范文', '荧光笔标出高分句式 + 参考译文'),
             ('一步一步写', '每一句话是怎么写出来的'), ('高分句式', '公式 + 讲解 + 两个仿写例句'), ('亮点词汇', '把普通说法换成高分说法')]
    li = ''.join(f'<div style="display:flex;align-items:center;margin-bottom:17px"><span class="lat" style="flex:none;width:52px;height:52px;border-radius:14px;background:{BLUE};color:#fff;font-size:28px;line-height:52px;text-align:center;margin-right:16px">{i}</span>'
                 f'<div><div style="font:900 30px/1.2 Black">{a}</div><div style="font:700 21px/1.35 Bold;color:{MUTE}">{b}</div></div></div>' for i, (a, b) in enumerate(steps, 1))
    return f"""<body><div class="dots"></div>{head(3, '每一篇都讲透：<span class="hy">7 步</span>写出满分', f'以 2026 英语一大作文为例，这一篇就讲了 {len(list(S.glob("内页_*.png")))} 页')}
<div class="ab" data-k="steps" style="left:50px;top:258px">{li}</div>
<div class="page" style="left:640px;top:250px;width:320px;transform:rotate(6deg)"><img src="{img('内页_06.png')}"></div>
<div class="page" style="left:560px;top:290px;width:320px;transform:rotate(0deg)"><img src="{img('内页_02.png')}"></div>
<div class="page" style="left:470px;top:350px;width:330px;transform:rotate(-6deg)"><img src="{img('内页_01.png')}"></div>
<div class="tag tr" data-k="t1" style="left:500px;top:880px;transform:rotate(-4deg)">真实内页 · 不是样板</div>
</body>"""


# ---------------------------------------------------------------- 04 满分范文
def p04():
    return f"""<body><div class="dots"></div>{head(4, '满分范文：<span class="hy">荧光笔</span> + 圆圈编号', '范文里的每个高分句式都标出来，后面逐个讲；每段附参考译文')}
<div class="shot" style="left:50px;top:250px;width:900px"><img src="{img('范文.png')}"></div>
<div class="tag tr" data-k="t1" style="left:640px;top:226px;transform:rotate(3deg)">① 编号 = 后面讲的高分句式</div>
<div class="tag tb" data-k="t2" style="left:36px;top:228px;transform:rotate(-2deg)">每句标序号，一句一句对照</div>
</body>"""


# ---------------------------------------------------------------- 05 一步一步写
def p05():
    return f"""<body><div class="dots"></div>{head(5, '一步一步写：<span class="hy">每句话怎么来的</span>', '先列提纲，再一句一句讲：这句要做什么、怎么写、范文原句 + 中文')}
<div class="tag tb" data-k="t1" style="left:80px;top:236px">写作思路：每段一个任务</div>
<div class="shot" style="left:80px;top:284px;width:840px"><img src="{img('思路.png')}"></div>
<div class="tag tr" data-k="t2" style="left:80px;top:494px">一步一步写：共 {sum(len(d['步骤']) for d in D)} 步，覆盖每一句</div>
<div class="shot" style="left:80px;top:542px;width:840px"><img src="{img('步骤.png')}"></div>
</body>"""


# ---------------------------------------------------------------- 06 高分句式
def p06():
    pos = json.loads((S / '句式6位置.json').read_text('utf-8'))
    w, x0, y0 = 800, 130, 282
    im = Image.open(S / '句式6.png')
    h = w * im.height / im.width
    lab = [('mean', '这个句式表达什么'), ('f', '公式：照着套'), ('o', '范文原句 + 中文'), ('why', '讲解：为什么高分'), ('ex', '两个仿写例句 + 中文'), ('alt', '也可以这样说')]
    marks = ''.join(f'<div class="ab" style="left:{x0 - 50}px;top:{y0 + (pos[k][0] + pos[k][1]) / 2 * h - 17:.0f}px"><span class="dot">{i}</span></div>' for i, (k, _) in enumerate(lab, 1))
    legend = ''.join(f'<span style="margin-right:22px;white-space:nowrap"><span class="dot" style="width:28px;height:28px;font-size:17px;line-height:28px;vertical-align:2px;margin-right:6px">{i}</span>{t}</span>' for i, (_, t) in enumerate(lab, 1))
    return f"""<body><div class="dots"></div>{head(6, f'<span class="lat" style="color:{KY}">{PAT}</span> 个<span class="hy">高分句式</span>，个个讲透', f'每个句式都有：公式、范文原句、讲解、{EX // PAT} 个仿写例句、替换说法，全附中文')}
<div class="shot" style="left:{x0}px;top:{y0}px;width:{w}px"><img src="{img('句式6.png')}"></div>
{marks}
<div class="ab" data-k="legend" style="left:50px;top:{y0 + h + 22:.0f}px;width:900px;white-space:normal;font:700 22px/1.9 Bold;color:{INK}">{legend}</div>
<div class="tag tk" data-k="t1" style="left:690px;top:238px;transform:rotate(3deg)">共 {EX} 个仿写例句</div>
</body>"""


# ---------------------------------------------------------------- 07 写作总攻略
def p07():
    chips = ['阅卷老师看什么', '书信与通知格式', '图画 / 图表三段式', '图表数据表达', '字数与时间', '中式英语黑名单']
    c = ''.join(f'<span style="display:inline-block;margin:0 10px 12px 0;padding:8px 16px 9px;border-radius:999px;background:#fff;border:3px solid {BLUE};font:900 22px/1 Black;color:{BLUE}">{t}</span>' for t in chips)
    return f"""<body><div class="dots"></div>{head(7, '开篇写作总攻略：<span class="hy">先学会怎么拿分</span>', '评分标准、书信格式、三段式结构、常用模板句，考前一章过一遍')}
<div class="ab" data-k="chips" style="left:50px;top:236px;width:900px;white-space:normal">{c}</div>
<div class="tag tr" data-k="t1" style="left:50px;top:370px">中式英语黑名单：{BAD} 条，都是范文复核时真实改掉的说法</div>
<div class="shot" style="left:50px;top:420px;width:900px;height:540px"><img src="{img('黑名单.png')}"></div>
</body>"""


# ---------------------------------------------------------------- 08 默写卡
def p08():
    return f"""<body><div class="dots"></div>{head(8, '配套默写卡：<span class="hy">默句子</span>，不只是默单词', f'{DIC} 道句式填空 + {DIC} 句看中文默整句 + 答案，右侧提醒这句练什么句式')}
<div class="tag tb" data-k="t1" style="left:100px;top:232px">A 句式填空：补全关键表达</div>
<div class="shot" style="left:100px;top:278px;width:800px"><img src="{img('卡A.png')}"></div>
<div class="tag tb" data-k="t2" style="left:100px;top:510px">B 看中文，默写整句</div>
<div class="shot" style="left:100px;top:556px;width:800px"><img src="{img('卡B.png')}"></div>
<div class="tag tr" data-k="t3" style="left:100px;top:754px">答案：粉色就是填空的部分</div>
<div class="shot" style="left:100px;top:800px;width:800px"><img src="{img('答案卡.png')}"></div>
<div class="tag tk" data-k="t4" style="left:660px;top:240px;transform:rotate(3deg)">为什么值得背 ↓</div>
</body>"""


# ---------------------------------------------------------------- 09 全收录目录
def p09():
    ids = sorted(P)
    kind = lambda g, big: ('图画+图表' if '图画' in g and '图表' in g else '图画' if '图画' in g else '表格' if '表格' in g else '图表') if big else \
        ('通知' if '通知' in g else '邀请信' if '邀请' in g else '建议信' if '建议' in g else '回信' if '回信' in g else '书信')
    cols = [('英语一', 'Part A', '英一 小作文'), ('英语一', 'Part B', '英一 大作文'), ('英语二', 'Part A', '英二 小作文'), ('英语二', 'Part B', '英二 大作文')]
    th = '<div style="display:grid;grid-template-columns:92px repeat(4,1fr);gap:6px;margin-bottom:6px">' + '<div></div>' + ''.join(
        f'<div style="background:{BLUE};color:#fff;font:900 22px/1 Black;text-align:center;padding:12px 0;border-radius:10px">{c[2]}</div>' for c in cols) + '</div>'
    rows = ''
    for y in range(2026, 2020, -1):
        cell = ''
        for e, part, _ in cols:
            p = next(P[i] for i in ids if P[i]['year'] == y and e in P[i]['paper'] and P[i]['passage'] == part)
            t = re.sub(r'^回信：', '', p['title'])
            cell += (f'<div style="background:#fff;border-radius:10px;padding:9px 11px;box-shadow:0 3px 10px rgba(31,37,55,.08);white-space:normal">'
                     f'<div style="font:700 15px/1 Bold;color:{BERRY};margin-bottom:5px">{kind(p["genre"], part == "Part B")}</div>'
                     f'<div style="font:900 19px/1.28 Black;color:{INK}">{t}</div></div>')
        rows += (f'<div style="display:grid;grid-template-columns:92px repeat(4,1fr);gap:6px;margin-bottom:6px">'
                 f'<div class="lat" style="display:flex;align-items:center;justify-content:center;font-size:27px;color:{KY}">{y}</div>{cell}</div>')
    return f"""<body><div class="dots"></div>{head(9, f'6 年真题 <span class="lat" style="color:{KY}">{N}</span> 篇，<span class="hy">一篇不落</span>', '英一、英二，大小作文全收录；书末附全部句式总表')}
<div class="ab" data-k="grid" style="left:40px;top:236px;width:920px;white-space:normal">{th}{rows}</div>
</body>"""


CHECK_JS = """
() => {
  const W = innerWidth, H = innerHeight, out = [];
  const r = [...document.querySelectorAll('[data-k]')].map(e => { const b = e.getBoundingClientRect(); return {k: e.dataset.k, x0: b.left, y0: b.top, x1: b.right, y1: b.bottom}; });
  for (const a of r) if (a.x0 < 8 || a.y0 < 8 || a.x1 > W - 8 || a.y1 > H - 8) out.push(`${a.k} 出画 ${JSON.stringify(a)}`);
  for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) {
    const a = r[i], b = r[j], ox = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), oy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
    if (ox > 0 && oy > 0) out.push(`${a.k} 与 ${b.k} 重叠 ${ox.toFixed(0)}×${oy.toFixed(0)}`);
  }
  for (const im of document.images) if (!im.complete || !im.naturalWidth) out.push('图片没加载: ' + im.src.slice(-30));
  for (const e of document.querySelectorAll('.shot,.page')) { const b = e.getBoundingClientRect();
    if (b.left < 0 || b.top < 0 || b.right > W || b.bottom > H - 6) out.push('截图出画: ' + e.querySelector('img').src.split('/').pop() + ' ' + JSON.stringify([b.left, b.top, b.right, b.bottom].map(Math.round))); }
  const box = document.querySelector('[data-box]'), nums = document.querySelector('[data-k=nums]');
  if (box && nums) { const a = box.getBoundingClientRect();
    for (const e of nums.querySelectorAll('span')) { const b = e.getBoundingClientRect(); if (b.right > a.right - 10) out.push('数字说明伸出白框: ' + e.textContent); } }
  const fonts = [...document.fonts].filter(f => f.status !== 'loaded').map(f => f.family);
  if (fonts.length) out.push('字体未加载: ' + fonts.join(','));
  return out;
}"""

PAGES = [('01_主图', p01), ('02_痛点与解决', p02), ('03_每篇7步', p03), ('04_满分范文', p04), ('05_一步一步写', p05),
         ('06_高分句式', p06), ('07_写作总攻略', p07), ('08_默写卡', p08), ('09_24篇全收录', p09)]

if __name__ == '__main__':
    from playwright.sync_api import sync_playwright
    OUT.mkdir(exist_ok=True)
    only = sys.argv[1:]
    bad = []
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for name, fn in PAGES:
            if only and not any(name.startswith(o) for o in only):
                continue
            body = fn()
            if not body.startswith('<body'):
                body = '<body>' + body + '</body>'
            html = WORK / f'{name}.html'
            html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{css()}</style></head>{body}</html>', 'utf-8')
            pg = br.new_page(viewport={'width': 1000, 'height': 1000}, device_scale_factor=2)
            pg.goto(html.as_uri())
            pg.evaluate('document.fonts.ready.then(() => [...document.fonts].forEach(f => f.load()))')
            pg.evaluate('document.fonts.ready')
            pg.wait_for_timeout(400)
            bad += [f'{name}: {x}' for x in pg.evaluate(CHECK_JS)]
            png = WORK / f'{name}.png'
            pg.screenshot(path=str(png))
            pg.close()
            im = Image.open(png).convert('RGB')
            assert im.size == (2000, 2000), im.size
            im.save(OUT / f'{name}.jpg', quality=92, optimize=True, progressive=True)
            print(f'{name}.jpg {(OUT / f"{name}.jpg").stat().st_size / 1e6:.2f} MB')
        br.close()
    if bad:
        print('自查不通过：\n  ' + '\n  '.join(bad))
        sys.exit(1)
    print('自查通过：文字不出画、互不重叠、图片和字体全部加载')
