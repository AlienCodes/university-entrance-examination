"""生成中考阅读逐句精读视频（由六级 make_video.py 复制，版式、规则完全相同，只改标题文字和路径；一句可分多屏）。
四级原说明：生成四级逐句精读视频（设计方案 C「杂志编号注释」，用户 2026-10-07 选定）。

    /opt/ttsenv/bin/python 中考/tools/make_video.py s01 [--scale 2]

画面：米白底、左侧墨绿竖带；英文 EB Garamond，生词右上角带编号，单词墨绿、短语砖红；
中文思源宋体；右侧词汇栏按编号一一对应。字体文件在 四级/tools/fonts/。
时间轴、编码和成品核查与高考 tools/video/make_video.py 完全相同（片头静音 1.5 秒、句间 0.8 秒、
读完后画面停留 0.5 秒再切换、结尾静音 ≥ 2 秒、恒定 30 帧逐屏编码后无损拼接），
生成后立即运行高考同一套 verify_videos.check 核查，任何一项不通过就删除成品。
字号：英文不小于 48px、词汇栏不小于 22px（1080p 基准，4K 下翻倍），保证手机上看得清；
一句话生词太多、一屏放不下时，按 分屏.json 在合适的分句处拆成两屏（用户要求：不硬挤），
换屏时刻用语音识别的词时间戳找到第二屏第一个词，再落在它前面的能量最低点（词与词之间的空隙）。
输入：中考/data/vocab.json（复核定稿）、中考/audio/timings.json（cet4_male）。输出：中考/最终视频/。
"""
import argparse
import html
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent
ROOT = C4.parent
sys.path.insert(1, str(ROOT / '四级' / 'tools'))      # debuzz.py（电磁音检查）与四级共用
VOICE = 'cet4_male'               # 中考用四六级男声（用户 2026-10-14；CLAUDE.md 铁律 8）
W, H = 1920, 1080
MIN_FS, MIN_VS = 48, 22          # 可读性下限：放不下就必须分屏
SPLIT = {k: v for k, v in json.loads((HERE / '分屏.json').read_text('utf-8')).items() if not k.startswith('_')}

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden;background:#fbf9f4;color:#1c2421;font-family:'Noto Serif SC',serif}
.band{position:absolute;left:0;top:0;bottom:0;width:22px;background:#1f5c4a}
.top{position:absolute;left:110px;right:90px;top:52px;display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid #1c2421;padding-bottom:16px}
.top b{font-family:'Inter';font-weight:800;font-size:24px;letter-spacing:.14em}
.top span{color:#6b746f;font-size:24px}
.main{position:absolute;left:110px;top:140px;bottom:96px;width:1070px;display:flex;align-items:center}
#box{width:100%}
.en{font-family:'EB Garamond',serif;font-size:var(--fs);line-height:1.5}
.w{font-weight:600;color:#1f5c4a}.ph{font-weight:600;color:#a14a2a}
sup{font-family:'Inter';font-size:calc(var(--fs)*.36);font-weight:700;color:#fff;background:#1f5c4a;border-radius:1em;padding:.05em .45em;margin-left:.12em;vertical-align:.95em;line-height:1}
.ph sup{background:#a14a2a}
.zh{font-size:calc(var(--fs)*.68);line-height:1.65;color:#3c4642;margin-top:calc(var(--fs)*.5);padding-left:24px;border-left:4px solid #d7d2c3}
.side{position:absolute;right:90px;top:140px;bottom:96px;width:600px;background:#eef2ec;border-radius:6px;padding:30px 36px;display:flex;flex-direction:column;justify-content:center}
#list{display:flex;flex-direction:column;gap:calc(var(--vs)*.42)}
.side h3{font-family:'Inter';font-size:20px;letter-spacing:.2em;color:#1f5c4a;margin-bottom:14px}
.v{display:grid;grid-template-columns:calc(var(--vs)*1.3) 1fr;column-gap:12px;font-size:var(--vs);line-height:1.32}
.v em{font-style:normal;font-family:'Inter';font-weight:700;font-size:calc(var(--vs)*.7);color:#fff;background:#1f5c4a;border-radius:50%;width:calc(var(--vs)*1.2);height:calc(var(--vs)*1.2);display:flex;align-items:center;justify-content:center;margin-top:.1em}
.v.ph em{background:#a14a2a}
.v b{font-family:'EB Garamond';font-weight:600;font-size:calc(var(--vs)*1.3)}
.v.ph b{color:#a14a2a}
.v i{font-style:italic;font-family:'EB Garamond';color:#6b746f;margin-right:10px}
.v b{margin-right:10px}
.v span{color:#3c4642}
.zh,.v .g{text-spacing-trim:space-all}
x-i{position:relative;margin:0 .03em}x-i::before,x-i::after{content:'';position:absolute;left:50%;width:.2em;margin-left:-.1em;height:.08em;background:currentColor;border-radius:.03em}
x-i::before{top:.295em}x-i::after{top:.945em}
.en .w x-i::before,.en .ph x-i::before,.en .w x-i::after,.en .ph x-i::after,.v b x-i::before,.v b x-i::after{width:.25em;margin-left:-.125em;height:.135em}
.en .w x-i::before,.en .ph x-i::before,.v b x-i::before{top:.29em}.en .w x-i::after,.en .ph x-i::after,.v b x-i::after{top:.89em}
sup.sd{margin-right:.2em}
.pr{margin-right:-.5em}.pl{margin-left:-.5em}
.cont{color:#9aa39e;font-weight:400}
.bot{position:absolute;left:110px;right:90px;bottom:40px;display:flex;justify-content:space-between;align-items:center;font-family:'Inter';font-size:22px;color:#6b746f;letter-spacing:.1em}
.bar{flex:1;height:3px;background:#dcd8cc;margin:0 30px}.bar i{display:block;height:100%;background:#1f5c4a}
.ttl{position:absolute;left:150px;right:150px;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center}
.ttl .tag{font-family:'Inter';font-weight:800;letter-spacing:.3em;font-size:28px;color:#1f5c4a}
.ttl h1{font-size:96px;font-weight:700;margin:30px 0 26px;line-height:1.25}
.ttl .sub{font-size:44px;color:#3c4642}
.ttl .sub i{font-family:'EB Garamond';font-style:italic}
.ttl .meta{margin-top:50px;padding-top:26px;border-top:2px solid #1c2421;font-size:30px;color:#6b746f;display:flex;justify-content:space-between}
.legend{position:absolute;right:120px;bottom:60px;display:flex;gap:30px;font-size:24px;color:#3c4642}
.legend em{display:inline-block;width:22px;height:22px;border-radius:50%;margin-right:8px;vertical-align:-3px}
.legend .lw{background:#1f5c4a}.legend .lp{background:#a14a2a}
"""
# 中考专用样式（用户 2026-10-10：四六级一直同一种样子，会审美疲劳，中考换新样子）：样式.css 追加在上面的通用样式之后覆盖它，
# 只改颜色、字体、装饰和封面，不改版面尺寸（字号由 FIT 自动适配，样式定稿前对全部句子屏重新适配，任何一屏字号都不得变小）。
THEME = HERE / '样式.css'
THEME_FONTS = HERE / 'fonts' / 'fonts.css'
POS = re.compile(r'^((?:n|v|adj|adv|prep|conj|pron|num|det|int|abbr|pref|suf)\.)\s*(.*)$')


def esc(s):
    return html.escape(s, quote=True)


def cap_i(h):
    """英文大写 I 加上下衬线（z06 画面核查：圆体 Nunito 的大写 I 与小写 l 一模一样，人名 Ieoh 读成 leoh；字体没有带衬线的替换字形，
    用 x-i 的 ::before/::after 画两道短横，位置按 Nunito 实测：常规体竖笔宽 0.085 字、顶 0.30 字、底 1.02 字，粗体竖笔宽 0.155 字、顶 0.295、底 1.015；
    短横比竖笔每边宽约 0.05 字、底横盖住竖笔圆头，I 左右各留 0.03 字，不碰相邻字母和徽章。
    用自定义元素 x-i 而不用 span：词汇栏的 .v span 样式（中文字体、灰色）会套到 span 上，第 1 批第三次画面核查发现词条里的 I 变成灰色细体、像“‡”）。
    h 是已转义的 HTML，标签里的字不动。"""
    return re.sub(r'(<[^>]*>)|I', lambda m: m.group(1) or '<x-i>I</x-i>', h)


def nobr(h):
    """带连字符的英文词整体不断行（画面核查发现词条 southward-/moving、高亮词 wind-/driven 被拆到两行）。h 是已转义的 HTML，标签里的字不动。"""
    return re.sub(r'(<[^>]*>)|(?<![\w’])([A-Za-z0-9’]+(?:-[A-Za-z0-9’]+)+)', lambda m: m.group(1) or f'<nobr>{m.group(2)}</nobr>', h)


def esc_en(s):
    """英文里试卷的中文注释（如 architecture (建筑).）整体不断行：中文字之间默认可以断行，画面核查发现“(建 / 筑).”被拆到两行。"""
    return nobr(re.sub(r'\([^()]*[\u4e00-\u9fff][^()]*\)[.,;:!?”’]*', lambda m: f'<span style="white-space:nowrap">{m.group(0)}</span>', esc(s)))


GLOSS_CHUNK = 9      # 词汇栏一行最多约 9.6 个字（字号最大 40px 时）：9 个字以内的释义块整体不断行（原定 10，z20 “下面就是……的方法；”溢出 16 像素）
ZCLOSE, ZOPEN = set('，。、：；！？）”’】」》'), set('（“‘【「《')   # 思源黑体实测：前一组字形在左半（右半空白），后一组在右半（左半空白）


def words(s, out):
    """超过 GLOSS_CHUNK 个字的释义块（如“（代替前面提到的复数名词）”）一行放不下，只允许在词与词之间断行：用 jieba 分词，每个多字词整体不断行
    （依赖：/opt/ttsenv/bin/pip install jieba）。"""
    import logging
    import jieba
    jieba.setLogLevel(logging.WARNING)
    res, i = [], 0
    for w in jieba.cut(s):
        piece = ''.join(out[i:i + len(w)])
        res.append(f'<nobr>{piece}</nobr>' if len(w) > 1 else piece)
        i += len(w)
    return ''.join(res)


def zh_html(s, gloss=False):
    """中文标点挤压（第 1 批画面核查：“说：  “我们”“看法）  ；”“母亲养育” 。”中间空出半个到一个字，段首“记忆…”比下一行缩进半个字；
    字体的 halt 对冒号、引号不生效，所以关掉浏览器自带的挤压（text-spacing-trim: space-all），由这里统一决定）：
    右半空白的标点后面紧跟标点 → 去掉它的右半空白（.pr）；左半空白的标点在开头或紧跟在左半空白的标点后 → 去掉左半空白（.pl）；
    其余左半空白的标点标 .po，排版后落在行首的由 FIT 去掉左半空白。
    断行（同一次画面核查：释义“可/能”“泳/衣”被拆开，译文最后一行只剩“念。”一个字）：
    gloss=True（词汇栏释义）按标点切块（右半空白的标点之后、左半空白的标点之前），GLOSS_CHUNK（9）个字以内的块整体不断行，更长的块只在词与词之间断行（words）；
    gloss=False（译文）最后两个字连同后面的标点绑在一起，最后一行至少两个字。"""
    out = []
    for i, c in enumerate(s):
        nxt, prv = s[i + 1:i + 2], s[i - 1:i]
        if c in ZCLOSE and nxt and (nxt in ZCLOSE or nxt in ZOPEN):
            out.append(f'<span class="pr">{esc(c)}</span>')
        elif c in ZOPEN and (not prv or prv in ZOPEN):
            out.append(f'<span class="pl">{esc(c)}</span>')
        elif c in ZOPEN:
            out.append(f'<span class="po">{esc(c)}</span>')
        else:
            out.append(esc(c))
    if gloss:
        cuts = [0] + [i for i in range(1, len(s)) if (s[i - 1] in ZCLOSE and s[i] not in ZCLOSE) or (s[i] in ZOPEN and s[i - 1] not in ZOPEN)] + [len(s)]
        return ''.join((f'<nobr>{"".join(out[a:b])}</nobr>' if b - a <= GLOSS_CHUNK else words(s[a:b], out[a:b])) for a, b in zip(cuts, cuts[1:]) if b > a)
    han = [i for i, c in enumerate(s) if '\u4e00' <= c <= '\u9fff']
    if len(han) >= 3:
        k = han[-2]
        return ''.join(out[:k]) + f'<nobr>{"".join(out[k:])}</nobr>'
    return ''.join(out)


def page(body):
    fonts = (ROOT / '四级' / 'tools' / 'fonts' / 'fonts.css').as_uri()      # 字体与四级共用
    extra = f'<link rel="stylesheet" href="{THEME_FONTS.as_uri()}">' if THEME_FONTS.exists() else ''
    theme = f'<style>{THEME.read_text("utf-8")}</style>' if THEME.exists() else ''
    return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{fonts}">{extra}<style>{CSS}</style>{theme}</head>'
            f'<body><div class="band"></div>{body}</body></html>')


def ordered(s):
    """词条按在句中第一次出现的位置编号。"""
    return sorted(s['w'], key=lambda w: w['sp'][0][0])


def sentence_html(s, lo=0, hi=None):
    """只排 en[lo:hi]（分屏时每屏一段）；编号按整句统一，第二屏接着第一屏编号。"""
    hi = len(s['en']) if hi is None else hi
    ws = ordered(s)
    num = {id(w): i + 1 for i, w in enumerate(ws)}
    spans = sorted((a, b, w, j) for w in s['w'] for j, (a, b) in enumerate(w['sp']) if lo <= a and b <= hi)
    last = {}
    for a, b, w, j in spans:
        last[id(w)] = j
    out, pos = '', lo
    for a, b, w, j in spans:
        if a < pos:
            continue
        cls = 'ph' if w['t'] == 'phr' else 'w'
        sup = f'<sup>{num[id(w)]}</sup>' if j == last[id(w)] else ''     # 分开的短语，编号标在本屏最后一段
        out += esc_en(s['en'][pos:a]) + f'<span class="{cls}">{nobr(esc(s["en"][a:b]))}{sup}</span>'
        pos = b
    out += esc_en(s['en'][pos:hi])
    # 连字符复合词跨在普通文字和高亮词之间（z21 “a 600-” + 高亮 kilometer），两段合起来不断行
    hl = r'<span class="(?:w|ph)">(?:(?!</span>).)*</span>'
    out = re.sub(rf'(?<![\w’])([A-Za-z0-9’]+-)({hl})', r'<nobr>\1\2</nobr>', out)
    out = re.sub(rf'({hl})(-[A-Za-z0-9’]+)', r'<nobr>\1\2</nobr>', out)
    out = re.sub(rf'(<span class="(?:w|ph)">(?:(?!</span>).)*-(?:<sup>\d+</sup>)?</span>)([A-Za-z0-9’]+)', r'<nobr>\1\2</nobr>', out)
    return cap_i(re.sub(r'<sup>(\d+</sup></span>(?:</nobr>)?[—–])', r'<sup class="sd">\1', out))      # 大写 I 最后统一加，免得上面按 </span> 配对的规则配错     # 编号徽章后紧跟破折号时留空（z06 “idea²—let”徽章贴着破折号）


def vocab_html(s, lo=0, hi=None):
    """释义标 lang="zh-CN"：释义以“……”开头时（……的关键），前面紧挨着英文词条，浏览器会按拉丁文排成底线六点，标了中文才是居中的省略号（画面核查发现，2026-10-10）。"""
    hi = len(s['en']) if hi is None else hi
    out = []
    for i, w in enumerate(ordered(s), 1):
        if not any(lo <= a and b <= hi for a, b in w['sp']):
            continue
        m = POS.match(w['m'])
        pos, mean = (m.group(1), m.group(2)) if m else ('', w['m'])
        # 词条的直撇号改弯撇号（与句子一致，踩坑 18）；<wbr>：词性、释义前一定能换行（z09 “Bluetooth-connected adj.”整体不断行，伸进了词汇栏右边留白）
        out.append(f'<div class="v {"ph" if w["t"] == "phr" else ""}"><em>{i}</em><div><b>{cap_i(nobr(esc(w["h"].replace(chr(39), "’"))))}</b>'
                   f'{f"<wbr><i>{pos}</i>" if pos else ""}<wbr><span class="g" lang="zh-CN">{zh_html(mean, gloss=True)}</span></div></div>')
    return ''.join(out)


def head(p):
    return f'{esc(p["paper"])} · {esc(p["passage"])}'


def title_slide(p):
    """--n = 标题字数：中考样式据此把标题排成一行（字号 64—100px），避免在词中间断行（如“使用语|言”“调查|者”）。"""
    return page(f'''<div class="ttl"><div class="tag">中考英语 · 阅读理解</div><h1 style="--n:{max(len(p.get("title") or ""), 1)}">{esc(p.get("title") or "")}</h1>
      <div class="sub">中考英语 {esc(p["paper"])} · <i>{esc(p["passage"])}</i></div>
      <div class="meta"><span>{esc(p.get("genre") or "")}</span><span>全文 {p["words"]} 词 · 逐句精读</span></div></div>
      <div class="legend"><span><em class="lw"></em>单词</span><span><em class="lp"></em>短语</span></div>''')


def split_parts(pid, k, s):
    """分屏：返回 [(lo, hi, 中文, 标签), …]；不分屏返回一屏。中考长句多，可拆成多屏：at 写一个分屏点或按顺序的多个分屏点，
    zh 是各屏中文（比分屏点多一段），必须是定稿译文的原样片段（逐个分句核对），合起来不多不少。"""
    c = SPLIT.get(pid, {}).get(str(k))
    if not c:
        return [(0, len(s['en']), s['zh'], '')]
    en, zh = s['en'], s['zh']
    ats = c['at'] if isinstance(c['at'], list) else [c['at']]
    if len(c['zh']) != len(ats) + 1:
        raise SystemExit(f'分屏.json：{pid} 第 {k} 句有 {len(ats)} 个分屏点，中文应分 {len(ats) + 1} 段')
    cuts = []
    for at in ats:
        if en.count(at) != 1:
            raise SystemExit(f'分屏.json：{pid} 第 {k} 句找不到或不唯一：{at}')
        cut = en.index(at)
        if not re.search(r'[ —]$', en[:cut]):
            raise SystemExit(f'分屏.json：{pid} 第 {k} 句的分屏点不在词边界：{at}')
        if any(a < cut < b for w in s['w'] for a, b in w['sp']):
            raise SystemExit(f'分屏.json：{pid} 第 {k} 句的分屏点切断了一个生词')
        cuts.append(cut)
    if cuts != sorted(cuts):
        raise SystemExit(f'分屏.json：{pid} 第 {k} 句的分屏点没有按顺序排列')
    if sorted(''.join(c['zh'])) != sorted(zh) or ''.join(c['zh']) != zh or any(x not in zh for z in c['zh'] for x in re.split(r'(?<=[，；：、])', z) if x):
        raise SystemExit(f'分屏.json：{pid} 第 {k} 句的中文不是定稿译文的原样片段')
    b = [0] + cuts + [len(en)]
    n = len(b) - 1
    return [(b[x], b[x + 1], c['zh'][x], f' · PART {x + 1}/{n}') for x in range(n)]


def sentence_slide(p, s, k, n, part=None):
    lo, hi, zh, tag = part or (0, len(s['en']), s['zh'], '')
    en = sentence_html(s, lo, hi).rstrip()
    if lo > 0:
        en = '<span class="cont">… </span>' + en
    if hi < len(s['en']):
        en += '<span class="cont"> …</span>'
    return page(f'''<div class="top"><b>中考英语 READING</b><span>{head(p)}　{esc(p.get("title") or "")}</span></div>
      <div class="main"><div id="box"><div class="en">{en}</div><div class="zh" lang="zh-CN">{zh_html(zh)}</div></div></div>
      <div class="side" id="side"><h3>VOCABULARY</h3><div id="list">{vocab_html(s, lo, hi)}</div></div>
      <div class="bot"><span>SENTENCE {k} / {n}{tag}</span><div class="bar"><i style="width:{k / n * 100:.2f}%"></i></div><span>逐句精读</span></div>''')


# 左侧句子区与右侧词汇栏分别缩放字号，直到都放得下；词汇栏的内容必须在卡片内边距以内（第 1 批画面核查：内容挤进底部留白，离边框只剩 7 像素）；
# 之后把落在行首的左半空白标点（zh_html 标的 .po）去掉左半空白，与上下行的字对齐，并在它前面固定换行
# （样片 z10 画面核查：去掉半字后括号变窄，整块被挤回上一行行末，成了行中的“花（时间）”过度挤压）；
# 词条一行放不下时（z03 “with the development of”被拆成“…development / of 随着……”），在最均衡的词间断开，释义另起一行（hw，每次量词汇栏前重排）
FIT = """() => { const r=document.documentElement.style, main=document.querySelector('.main'), box=document.getElementById('box'),
  side=document.getElementById('side'), list=document.getElementById('list');
  const hw = () => { for (const x of document.querySelectorAll('br.hw')) x.remove();
    for (const b of document.querySelectorAll('.v b')) { if (b.dataset.h === undefined) b.dataset.h = b.innerHTML; else b.innerHTML = b.dataset.h;
      if (b.getClientRects().length < 2) continue;
      const ps = b.dataset.h.split(/ (?![^<>]*>)/); let best = null;
      for (let k = 1; k < ps.length; k++) { b.innerHTML = ps.slice(0, k).join(' ') + '<br>' + ps.slice(k).join(' ');
        const rs = b.getClientRects(); if (rs.length !== 2) continue; const w = Math.max(rs[0].width, rs[1].width); if (!best || w < best[0]) best = [w, b.innerHTML]; }
      b.innerHTML = best ? best[1] : b.dataset.h; const br = document.createElement('br'); br.className = 'hw'; b.after(br); } };
  const sideFits = () => { hw(); const s=side.getBoundingClientRect(), c=getComputedStyle(side), l=list.getBoundingClientRect(), top=s.top+side.clientTop;
    return l.top >= top + parseFloat(c.paddingTop) - 0.5 && l.bottom <= top + side.clientHeight - parseFloat(c.paddingBottom) + 0.5; };
  let fs=64, vs=40; r.setProperty('--fs', fs+'px'); r.setProperty('--vs', vs+'px');
  while (box.scrollHeight > main.clientHeight && fs > 30) { fs -= 2; r.setProperty('--fs', fs+'px'); }
  while (!sideFits() && vs > 16) { vs -= 1; r.setProperty('--vs', vs+'px'); }
  for (const e of document.querySelectorAll('.po')) { const k=e.closest('.zh, .v > div'), b=k.getBoundingClientRect();
    if (Math.abs(e.getClientRects()[0].left - (b.left + k.clientLeft + parseFloat(getComputedStyle(k).paddingLeft))) < 1) { e.className = 'pl'; e.before(document.createElement('br')); } }
  return [fs, vs, box.scrollHeight <= main.clientHeight && sideFits()]; }"""


def switch_time(audio, it, en, cut):
    """分屏换屏时刻：语音识别得到第二屏第一个词的开口时间，再在它之前 0.45 秒内找能量最低的 60 毫秒（词间空隙）的中点。"""
    import glob
    import numpy as np
    import sherpa_onnx
    import soundfile as sf
    import soxr
    a, sr = sf.read(str(audio), dtype='float32')
    a16 = soxr.resample(a, sr, 16000).astype(np.float32)
    s0 = it['start']
    seg = a16[int(s0 * 16000): int(it['end'] * 16000)]
    d = Path(glob.glob(str(ROOT / 'tools' / 'tts' / 'models' / 'sherpa-onnx-nemo-parakeet*'))[0])
    asr = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(d / 'encoder.int8.onnx'), decoder=str(d / 'decoder.int8.onnx'), joiner=str(d / 'joiner.int8.onnx'),
        tokens=str(d / 'tokens.txt'), model_type='nemo_transducer', num_threads=4)
    st = asr.create_stream()
    st.accept_waveform(16000, seg)
    asr.decode_stream(st)
    words = []                                       # (词, 开口时间)
    for tok, t in zip(st.result.tokens, st.result.timestamps):
        if tok.startswith(' ') or not words:
            words.append([tok.strip(), t])
        else:
            words[-1][0] += tok
    first = re.sub(r'[^a-z]', '', en[cut:].split()[0].lower())
    expect = (it['end'] - s0) * cut / len(en)
    cand = [t for w, t in words if re.sub(r'[^a-z]', '', w.lower()) == first]
    if not cand:
        raise SystemExit(f'分屏：语音识别里找不到第二屏第一个词 “{first}”')
    wt = min(cand, key=lambda t: abs(t - expect))
    if abs(wt - expect) > 3:
        raise SystemExit(f'分屏：“{first}” 的识别位置 {wt:.2f}s 与估计位置 {expect:.2f}s 相差太远')
    e = np.convolve(seg.astype(np.float64) ** 2, np.ones(960) / 960, mode='same')      # 60 毫秒滑动能量
    lo, hi = int(max(0, wt - 0.45) * 16000), int(min(len(seg) / 16000, wt + 0.05) * 16000)
    return s0 + (lo + int(np.argmin(e[lo:hi]))) / 16000


def switch_check(mp4, times, sw):
    """换屏核查（四级版）：高考的同名检查假定一句一屏；有分屏时改用这一项。
    每句读完后 0.45 秒仍是本句最后一屏、0.55 秒已是下一句第一屏；分屏的句子在换屏时刻前 0.1 秒是第一屏、后 0.1 秒是第二屏，且两屏确实不同。"""
    import numpy as np
    from verify_videos import frame
    same = lambda a, b: np.abs(a - b).mean() <= 1
    bad = []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i, it in enumerate(times):
            first = frame(mp4, it['start'] + 0.2, td)
            last = first
            for x, ts in enumerate(sw.get(i, []), 2):          # 中考：一句可分多屏，逐个换屏核对
                nxt = frame(mp4, ts + 0.2, td)
                if not (same(frame(mp4, ts - 0.1, td), last) and same(frame(mp4, ts + 0.1, td), nxt) and not same(last, nxt)):
                    bad.append(f'第 {i + 1} 句第 {x} 屏')
                last = nxt
            if i + 1 < len(times):
                if not (same(frame(mp4, it['end'] + 0.45, td), last)
                        and same(frame(mp4, it['end'] + 0.55, td), frame(mp4, times[i + 1]['start'] + 0.2, td))):
                    bad.append(f'第 {i + 1} 句')
    return ('读完停留 0.5 秒再切屏，0.3 秒后开读（含分屏）', not bad,
            f'不符合：{bad}' if bad else f'{len(times) - 1} 处切换全部正确' + (f'，另有 {sum(len(v) for v in sw.values())} 处分屏换屏正确' if sw else ''))


def buzz_check(mp4, times):
    """铁律第 10 条：视频音轨不得有电磁音（独立解码测量声码器的 9 个固定频点）。"""
    import numpy as np
    import debuzz as D
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-vn', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    f0, r, e = D.check(np.frombuffer(raw, np.float32), 48000, times)
    return ('无电磁音', not e, f'最强 {f0} Hz {r:+.1f} dB（上限 {D.MAX_DB:+.1f}）')


def video_name(p):
    title = (p.get('title') or '').translate(str.maketrans('/\\:*?"<>|', '／＼：＊？＂＜＞｜'))
    return f"{p['paper']} {p['passage']} {title}.mp4"     # 用户指定：年份月份 第几套 第几篇 题目，前面不加“四级”


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pid')
    ap.add_argument('--scale', type=int, default=2, help='2 = 3840×2160（4K）')
    ap.add_argument('--out', default=str(C4 / '最终视频'))
    ap.add_argument('--audio-root', default=str(C4 / 'audio'), help='音频目录（含 timings.json），试听样片用')
    a = ap.parse_args()

    data = json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))
    p = next(x for x in data['passages'] if x['id'] == a.pid)
    if not p.get('reviewed'):                     # 踩坑 14：复核通过前不生成视频
        raise SystemExit(f'{a.pid} 的翻译与标注还没有通过复核（build_vocab.py --reseal {a.pid}），不生成视频')
    # 踩坑 36：先审截图，后生成视频——程序或数据改过、截图还没审阅通过，就不生成视频
    subprocess.run([sys.executable, str(HERE / '画面核查' / 'screens_fp.py'), 'check', a.pid], check=True)
    tm = json.loads((Path(a.audio_root) / 'timings.json').read_text('utf-8'))[VOICE][a.pid]
    sents = [s for para in p['paras'] for s in para]
    times = tm['sentences']
    assert len(sents) == len(times), '音频句数与文章句数不一致，请重新生成音频'
    empty = [i + 1 for i, s in enumerate(sents) if not s['w']]
    if empty:                                   # 铁律：每一句至少标出一个单词
        raise SystemExit(f'第 {empty} 句没有标注单词，不生成视频')
    audio = Path(a.audio_root) / tm['file']

    from playwright.sync_api import sync_playwright
    # 踩坑 29：临时目录（每个视频约 35 MB 的截图和分段）以前从不删除，积累到磁盘写满，浏览器截图崩溃（Page crashed）
    import atexit
    import shutil
    free = shutil.disk_usage(C4).free / 2**30
    if free < 3:
        raise SystemExit(f'磁盘剩余只有 {free:.1f} GB（至少需要 3 GB），先清理临时文件再生成视频')
    tmp = Path(tempfile.mkdtemp(prefix='zkvideo_'))
    atexit.register(shutil.rmtree, tmp, True)          # 无论成功、核查失败还是出错，退出时都删除
    slides, owner = [title_slide(p)], [None]      # owner：每屏属于第几句、第几屏
    for i, s in enumerate(sents):
        for j, part in enumerate(split_parts(p['id'], i + 1, s)):
            slides.append(sentence_slide(p, s, i + 1, len(sents), part))
            owner.append((i, j, part))
    sizes = []
    from 画面核查.layoutcheck import problems as layout_problems
    with sync_playwright() as pw:
        exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': W, 'height': H}, device_scale_factor=a.scale)
        for i, h in enumerate(slides):
            f = tmp / f'{i:03d}.html'
            f.write_text(h, 'utf-8')
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            pg.wait_for_timeout(150)
            if i:
                fs, vs, fits = pg.evaluate(FIT)
                k = owner[i][0] + 1
                if not fits or fs < MIN_FS or vs < MIN_VS:     # 放不下或字太小：必须分屏，不硬挤
                    raise SystemExit(f'第 {k} 句一屏放不下（英文 {fs}px、词汇 {vs}px，下限 {MIN_FS}/{MIN_VS}px）：'
                                     f'请在 中考/tools/分屏.json 里为 {p["id"]} 第 {k} 句选合适的分句处拆成两屏或多屏')
                sizes.append((fs, vs))
            bad = layout_problems(pg, MIN_FS, MIN_VS)          # 排版机械检查（第 1 批画面核查报出的各类排版毛病，踩坑 33）
            if bad:
                raise SystemExit(f'{p["id"]} 第 {i + 1} 屏排版不合格（中考/tools/画面核查/layoutcheck.py）：\n  ' + '\n  '.join(bad))
            pg.screenshot(path=str(tmp / f'{i:03d}.png'))
        br.close()

    starts = [x['start'] for x in times]
    ends = [x['end'] for x in times]
    TAIL = 2.0
    total = max(tm['duration'], ends[-1] + TAIL)
    HOLD, GAP = 0.5, 0.8
    bad = [i + 2 for i in range(len(times) - 1) if abs(starts[i + 1] - ends[i] - GAP) > 0.01]
    if bad:
        raise SystemExit(f'第 {bad} 句之前的停顿不是 {GAP} 秒，请用最新设置重新生成音频')
    cuts, sw = [0.0], {}
    for i, j, part in owner[1:]:
        if j == 0:
            cuts.append(starts[0] if i == 0 else ends[i - 1] + HOLD)
        else:                                       # 分屏的第二屏：在第二屏第一个词开口之前切换
            t = switch_time(audio, times[i], sents[i]['en'], part[0])
            if not starts[i] + 0.3 < t < ends[i] - 0.3:
                raise SystemExit(f'第 {i + 1} 句分屏时刻 {t:.2f}s 不在句子朗读范围内')
            print(f'  第 {i + 1} 句第 {j + 1} 屏，{t - starts[i]:.2f}s 处换屏（第二屏从 “{sents[i]["en"][part[0]:part[0] + 24]}…” 开始）')
            cuts.append(t)
            sw.setdefault(i, []).append(t)
    cuts.append(total)
    assert len(cuts) == len(slides) + 1
    FPS = 30
    frames = [round(c * FPS) for c in cuts[:-1]] + [math.ceil(cuts[-1] * FPS)]
    lst = []
    for i in range(len(slides)):
        n = frames[i + 1] - frames[i]
        segf = tmp / f'seg{i:03d}.mp4'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-framerate', str(FPS),
                        '-i', str(tmp / f'{i:03d}.png'), '-frames:v', str(n), '-vf', 'format=yuv420p',
                        '-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-tune', 'stillimage',
                        '-pix_fmt', 'yuv420p', '-g', str(FPS * 10), str(segf)], check=True)
        lst.append(f"file '{segf}'")
    (tmp / 'list.txt').write_text('\n'.join(lst))
    total = frames[-1] / FPS

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = video_name(p)
    silent = tmp / 'video.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(tmp / 'list.txt'),
                    '-c', 'copy', str(silent)], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(silent), '-i', str(audio),
                    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', f'apad=whole_dur={total:.3f}',
                    '-t', f'{total:.3f}', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
                    str(out / name)], check=True)
    durs = [float(x) for x in subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=duration', '-of', 'csv=p=0',
                                str(out / name)], capture_output=True, text=True).stdout.split()]
    dur = min(durs)
    if dur - ends[-1] < TAIL - 0.05:
        raise SystemExit(f'结尾静音只有 {dur - ends[-1]:.2f} 秒，不足 {TAIL} 秒')
    # 成品核查：复用高考 verify_videos.check（分辨率、流畅度、声画等长、朗读与画面逐句一致、静音、停顿、响度……）
    sys.path[:0] = [str(ROOT / 'tools' / 'video'), str(ROOT / 'tools' / 'tts')]
    from verify_videos import check
    res = [r for r in check(out / name, p, tm) if not r[0].startswith('文件名') and not (sw and r[0].startswith('读完停留'))]
    if sw:
        res.append(switch_check(out / name, times, sw))
    res.append(buzz_check(out / name, times))
    fails = [f'{n}：{d}' for n, c, d in res if not c]
    if not re.fullmatch(r'20\d\d年 \S+ (?:\S*阅读\S*|七选五) \S.*\.mp4', name) or name != video_name(p):
        fails.append(f'文件名：{name}')
    if fails:
        (out / name).unlink()
        raise SystemExit('核查未通过，已删除成品：\n  ' + '\n  '.join(fails))
    print(f'  英文字号 {min(x[0] for x in sizes)}–{max(x[0] for x in sizes)}px，词汇栏字号 {min(x[1] for x in sizes)}–{max(x[1] for x in sizes)}px')
    print(f'已生成并核查通过 {out / name}（时长 {dur:.2f} 秒，读完后静音 {dur - ends[-1]:.2f} 秒）')


if __name__ == '__main__':
    sys.exit(main())
