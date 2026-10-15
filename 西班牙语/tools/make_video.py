"""生成西班牙语逐句精读视频（沿用四级设计方案 C「杂志编号注释」，用户给的参考图就是四级视频的一帧）。

    /opt/ttsenv/bin/python 西班牙语/tools/make_video.py es01 [--voice 音色名] [--scale 2] [--style C|1|2|3|4|5|6]

背景样式（--style，默认 C）：C = 四级设计方案 C（下面描述的默认画面）；1–6 = 中考设计的 6 种背景（晴空校园、手账笔记本、教室黑板、
活页单词卡、紫黄撞色、柔彩插画），CSS 在 西班牙语/tools/样式/（索引 styles.json），字体在 西班牙语/tools/fonts/。
样式只换颜色、字体、装饰和片头，不改版面尺寸、时间轴、编码和核查；选了 1–6 时成品文件名末尾加「（背景 N 名称）」。
预览图和每种样式的命令见 西班牙语/背景样式/README.md。样式 1–6 另有（C 的画面一个像素都不变）：
- 封面：西语标题用样式自己的西文字体占整行（最多两行，放不下自动缩小，不小于 56px），下面左边中文标题 + 图例、右边插图
- 词汇栏起始字号 40px（放不下自动缩小）；释义按逗号切块、块内不断行，中文最后两个字不拆开（不留孤字）
- 生词编号徽章与前一个字母按字形实测留出空隙（不贴字）
- 截图前逐屏程序检查：字形（每个字都由样式字体画出，西语 á é í ó ú ü ñ ¿ ¡ 不落到系统字体）、横向出界、页眉拥挤、
  封面各块出界 / 重叠 / 插图未加载；任何一处不合格就报错、不生成。

画面、时间轴、编码、成品核查都沿用 四级/tools/make_video.py（不改四级程序，在这里覆盖西班牙语需要不同的部分）：
- 米白底、左侧墨绿竖带；西语原文 EB Garamond，生词右上角带编号，单词墨绿、短语砖红；中文思源宋体；右侧词汇栏按编号一一对应
- 片头静音 1.5 秒；句间 0.8 秒（读完后画面停留 0.5 秒再切换，0.3 秒后开读）；结尾静音 ≥ 2 秒
- 3840×2160，恒定 30 帧逐屏编码后无损拼接；生成后立即运行高考同一套 verify_videos.check 核查，任何一项不通过就删除成品
西班牙语不同的地方：
- 词条数据来自 西班牙语/文章/<id>.json（w：h 词头、pos 词性、zh 释义、surface 句中原形），词性按《现代西班牙语》习惯（m. f. adj. adv. tr. loc.）
- 多词词条（comida típica、cada vez que……）算短语（砖红色）；短语不显示 loc.，名词短语保留阴阳性（f. / m.）
- 片头：西语标题 + 中文标题 + 文档里的插图；页眉「SPANISH READING」
- 电磁音检查：在 2–16 kHz 全频段找窄带峰（新的语音模型声码器频点和 Kokoro 不同，不能只查四级那 9 个频点）
输入：西班牙语/文章/<id>.json、西班牙语/audio/timings.json（make_audio.py 生成）。输出：西班牙语/最终视频/。
"""
import argparse
import atexit
import html
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ES = HERE.parent
ROOT = ES.parent
sys.path.insert(0, str(HERE))
import c4  # noqa: E402
C4V = c4.load('cet4_make_video', '四级/tools/make_video.py')      # 四级的设计 C（CSS、字体、自动缩放字号）

W, H = C4V.W, C4V.H
MIN_FS, MIN_VS = C4V.MIN_FS, C4V.MIN_VS
LETTERS = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")
STYLE_DIR = HERE / '样式'
STYLES = {s['key']: s for s in json.loads((STYLE_DIR / 'styles.json').read_text('utf-8'))['styles']}
STYLE = 'C'                     # 当前背景样式（main() 按 --style 设置）

CSS_ES = """
.ttl{right:110px}
.ttl .tag{font-size:26px}
.ttl .row{display:flex;align-items:center;gap:70px}
.ttl .txt{flex:1;min-width:0}
.ttl h1{font-family:'EB Garamond',serif;font-weight:600;font-size:104px;line-height:1.12;margin:34px 0 24px;text-wrap:balance}
.ttl .sub{font-size:52px;color:#3c4642}
.ttl figure{width:640px;flex:none;background:#fff;padding:14px;border-radius:6px;box-shadow:0 2px 0 #e6e1d4,0 18px 40px rgba(31,92,74,.10)}
.ttl figure img{display:block;width:100%;border-radius:3px}
.legend .lw{background:#1f5c4a}.legend .lp{background:#a14a2a}
.t-es{font-family:'EB Garamond'}
"""
# 只用于背景样式 1–6（C 的画面一个像素都不变），放在样式 CSS 之后：西语封面的版式骨架。中考样式的封面是一行中文标题，
# 西语封面是「西语标题 + 中文标题 + 插图」：西语标题占整行（最多两行，COVER 自动缩小字号），下面左边中文标题和图例、右边插图。
# 字体、字号、颜色、插图边框由每个样式 CSS 末尾的「西班牙语版调整」决定。
CSS_STYLED = """
x-nb{white-space:nowrap}
.ttl .row{display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-rows:auto auto auto;align-items:center}
.ttl .txt{display:contents}
.ttl h1{grid-column:1/-1;grid-row:1;white-space:normal;text-wrap:balance;height:auto;width:auto;max-width:100%;display:block;align-self:start}
.ttl .sub{grid-column:1;grid-row:2;align-self:end;min-width:0}
.ttl .legend{grid-column:1;grid-row:3;align-self:start;justify-self:start;position:static;transform:none;inset:auto}
.ttl figure{grid-column:2;grid-row:2/4;align-self:center}
.v b{margin-right:10px}.v i{margin-left:0!important;margin-right:10px}.v span{margin-left:0!important}
"""   # 词条间距放在左边元素的右侧：释义折到第二行时行首不会多出一截缩进（踩坑 33）

# 背景样式 1–6 截图前的三步（C 不跑）：徽章间距、封面标题字号、字形检查。
GAP = 0.04       # 生词编号徽章与前一个字母笔画之间至少留 0.04 个字号的空隙（按字形实测右边距，踩坑 39：徽章贴字）
BADGE = """(gap) => { document.documentElement.style.setProperty('--fs', '64px'); const cv = document.createElement('canvas').getContext('2d');
  for (const s of document.querySelectorAll('.en sup')) { let n = s.previousSibling; while (n && n.nodeType === 1) n = n.lastChild || n.previousSibling;
    if (!n || !n.data) continue; const c = n.data.trim().slice(-1); if (!c) continue;
    const cs = getComputedStyle(n.parentElement), fs = parseFloat(cs.fontSize), ss = parseFloat(getComputedStyle(s).fontSize) / fs;
    cv.font = `${cs.fontStyle} ${cs.fontWeight} 100px ${cs.fontFamily}`; const m = cv.measureText(c), rsb = (m.width - m.actualBoundingBoxRight) / 100;
    const ls = (parseFloat(cs.letterSpacing) || 0) / fs;
    s.style.marginLeft = Math.max(0.04, (gap - rsb - ls) / ss).toFixed(3) + 'em'; } }"""
# 封面：样式 1–6 的西语标题最多两行，放不下就逐步缩小字号（不小于 56px）；所有样式都核对封面各块不出界、不互相重叠、插图已加载
COVER = """(shrink) => { const q = s => document.querySelector(s), t = q('.ttl'), h = q('.ttl h1');
  const lh = () => { const c = getComputedStyle(h); return parseFloat(c.lineHeight) || parseFloat(c.fontSize) * 1.2; };
  const lines = () => Math.round(h.getBoundingClientRect().height / lh());
  const over = () => { const r = document.createRange(); r.selectNodeContents(h.querySelector('x-t') || h);      // 只量文字本身（荧光笔衬底可以略出边）
    const a = r.getBoundingClientRect(), b = h.getBoundingClientRect();
    return t.scrollHeight > t.clientHeight + 1 || a.right > b.right + 1 || a.left < b.left - 1; };
  let fs = parseFloat(getComputedStyle(h).fontSize);
  while (shrink && (lines() > 2 || over()) && fs > 56) { fs -= 2; h.style.fontSize = fs + 'px'; }
  const names = ['.tag', 'h1', '.sub', 'figure', '.meta', '.legend'], bad = [];
  const R = names.map(s => q(s) && q(s).getBoundingClientRect());
  R.forEach((r, i) => { if (r && (r.left < 0 || r.top < 0 || r.right > innerWidth || r.bottom > innerHeight)) bad.push(names[i] + ' 出界'); });
  for (let i = 0; i < R.length; i++) for (let j = i + 1; j < R.length; j++) { const a = R[i], b = R[j];
    if (a && b && a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) bad.push(names[i] + ' 与 ' + names[j] + ' 重叠'); }
  const img = q('.ttl figure img'); if (img && !(img.complete && img.naturalWidth)) bad.push('插图没有加载');
  if (over()) bad.push('标题或封面内容溢出');
  return [fs, lines(), bad]; }"""
# 横向不出界：整块不断行（x-nb）以后，词条、释义、原文、译文的每一段都必须在所在栏的内边距以内
HBOX = """() => { const bad = [];
  for (const [box, sel] of [['#side', '#list'], ['.main', '#box']]) { const b = document.querySelector(box), c = getComputedStyle(b), r = b.getBoundingClientRect();
    const L = r.left + b.clientLeft + parseFloat(c.paddingLeft) - 1, R = r.left + b.clientLeft + b.clientWidth - parseFloat(c.paddingRight) + 1;
    const w = document.createTreeWalker(document.querySelector(sel), NodeFilter.SHOW_TEXT), g = document.createRange();
    for (let n; (n = w.nextNode());) { g.selectNodeContents(n);      // 只量文字本身（荧光笔、徽章的衬底可以略出边）
      for (const q of g.getClientRects()) if (q.width && (q.left < L || q.right > R)) { bad.push(n.data.slice(0, 20)); break; } } }
  const a = document.querySelector('.top b').getBoundingClientRect(), t = document.querySelector('.top span').getBoundingClientRect();
  if (a.right > t.left - 20 || t.right > innerWidth) bad.push('页眉标题太长，和 SPANISH READING 挤在一起或出界');
  return bad; }"""
# 字形检查：画面上每个字都必须由该元素 font-family 里列出的网页字体之一画出（不许落到系统字体，如西语重音字母、¿ ¡ 或生僻汉字）。
# 方法：分别用两种字形明显不同的备用字体垫底画同一个字，像素完全相同 = 列出的字体自己有这个字。
GLYPH = """async () => { const GEN = new Set(['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui']);
  const LAT = ['EB Garamond', 'Inter', 'Noto Serif SC'], CJK = ['Noto Serif SC', 'Noto Sans SC', 'LXGW WenKai'];
  const cv = document.createElement('canvas'); cv.width = cv.height = 160; const g = cv.getContext('2d', {willReadFrequently: true});
  const draw = (font, ch) => { g.clearRect(0, 0, 160, 160); g.font = font; g.fillText(ch, 20, 120); return g.getImageData(0, 0, 160, 160).data; };
  const same = (a, b) => { for (let i = 3; i < a.length; i += 4) if (a[i] !== b[i]) return false; return true; };
  const bad = new Set(), seen = new Set(), w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) { const txt = n.data.replace(/\s/g, ''); if (!txt) continue;
    const cs = getComputedStyle(n.parentElement), fams = cs.fontFamily.split(',').map(f => f.trim().replace(/^["']|["']$/g, '')).filter(f => !GEN.has(f));
    const pre = `${cs.fontStyle} ${cs.fontWeight} 100px `;
    for (const ch of new Set(txt)) { const key = pre + fams.join('|') + ch; if (seen.has(key)) continue; seen.add(key);
      const cjk = /[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef\u3000-\u303f]/.test(ch); let ok = false;
      for (const f of fams) { const fb = (cjk ? CJK : LAT).filter(x => x !== f).slice(0, 2);
        await Promise.all([f, ...fb].map(x => document.fonts.load(`${pre}"${x}"`, ch)));
        if (same(draw(`${pre}"${f}", "${fb[0]}"`, ch), draw(`${pre}"${f}", "${fb[1]}"`, ch))) { ok = true; break; } }
      if (!ok) bad.add(`${ch}（${fams.join(', ')}）`); } }
  return [...bad]; }"""


def esc(s):
    return html.escape(s, quote=True)


def page(body):
    fonts = (ROOT / '四级' / 'tools' / 'fonts' / 'fonts.css').as_uri()
    extra = theme = ''
    if STYLE != 'C':            # 背景样式 1–6：样式字体 + 样式 CSS（追加在通用样式之后覆盖颜色、字体、装饰）
        extra = f'<link rel="stylesheet" href="{(HERE / "fonts" / "fonts.css").as_uri()}">'
        theme = f'<style>{(STYLE_DIR / STYLES[STYLE]["file"]).read_text("utf-8")}</style>'
    return (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><link rel="stylesheet" href="{fonts}">{extra}'
            f'<style>{C4V.CSS}{CSS_ES}</style>{theme}{f"<style>{CSS_STYLED}</style>" if STYLE != "C" else ""}</head><body><div class="band"></div>{body}</body></html>')


def nb_tail(s):
    """样式 1–6：中文最后两个字（连同句末标点）不拆开，避免最后一行只剩一个字（踩坑 33、41）。C 原样输出。"""
    k = len(s)
    while k and s[k - 1] in '。！？；：，、”’）》…—.!?;:,)':
        k -= 1
    if STYLE == 'C' or k < 3:
        return esc(s)
    return f'{esc(s[:k - 2])}<x-nb>{esc(s[k - 2:])}</x-nb>'


def gloss_html(s):
    """样式 1–6 的词汇释义：按逗号、分号、顿号切成小块，每块（≤ 8 字）整体不断行，只在标点后换行，
    避免「巨 / 大的」「可 / 能」这种在词中间断开（踩坑 33）；长块只绑定末两字。C 原样输出。"""
    if STYLE == 'C':
        return esc(s)
    out = []
    for c in re.findall(r'[^，；、,;]+[，；、,;]?|[，；、,;]', s):
        out.append(f'<x-nb>{esc(c)}</x-nb>' if len(c) <= 8 else nb_tail(c))
    return ''.join(out)


def load(pid):
    """读文章，给每个词条算出在句中的位置；任何一条对不上都报错（不静默失效）。"""
    p = json.loads((ES / '文章' / f'{pid}.json').read_text('utf-8'))
    for k, s in enumerate((s for para in p['paras'] for s in para), 1):
        if not s['w']:
            raise SystemExit(f'第 {k} 句没有标注单词（铁律 1）')
        taken = []
        for w in s['w']:
            n = s['es'].count(w['surface'])
            if n != 1:
                raise SystemExit(f'第 {k} 句：词条「{w["h"]}」的原形「{w["surface"]}」在句中出现 {n} 次（必须恰好 1 次）')
            a = s['es'].index(w['surface'])
            b = a + len(w['surface'])
            if any(a < y and x < b for x, y in taken):
                raise SystemExit(f'第 {k} 句：词条「{w["h"]}」与别的词条重叠')
            taken.append((a, b))
            w['sp'] = [(a, b)]
            w['t'] = 'phr' if ' ' in w['h'].strip() else 'word'
        s['w'].sort(key=lambda w: w['sp'][0][0])          # 编号 = 在句中出现的先后顺序
    return p


def sentence_html(s):
    out, pos = '', 0
    for i, w in enumerate(s['w'], 1):
        a, b = w['sp'][0]
        cls = 'ph' if w['t'] == 'phr' else 'w'
        out += esc(s['es'][pos:a]) + f'<span class="{cls}">{esc(s["es"][a:b])}<sup>{i}</sup></span>'
        pos = b
    return out + esc(s['es'][pos:])


def vocab_html(s):
    out = []
    for i, w in enumerate(s['w'], 1):
        pos = '' if w['pos'] == 'loc.' else w['pos']          # 短语不写 loc.（颜色已经表示短语），名词短语保留阴阳性
        out.append(f'<div class="v {"ph" if w["t"] == "phr" else ""}"><em>{i}</em><div><b lang="es">{esc(w["h"])}</b>'
                   f'{f"<i class=pos>{esc(pos)}</i>" if pos else ""}<span>{gloss_html(w["zh"])}</span></div></div>')
    return ''.join(out)


def head(p):
    return f'每日一练 · <i lang="es" class="t-es">{esc(p["title_es"])}</i>　{esc(p["title_zh"])}'


def words(p):
    return sum(len(LETTERS.findall(s['es'])) for para in p['paras'] for s in para)


def title_slide(p):
    img = (ES / '图片' / f'{p["id"]}_插图.jpg')
    fig = f'<figure><img src="{img.as_uri()}"></figure>' if img.exists() else ''
    n = sum(len(x) for x in p['paras'])
    legend = '<div class="legend"><span><em class="lw"></em>单词</span><span><em class="lp"></em>短语</span></div>'
    inner, outer = (legend, '') if STYLE != 'C' else ('', legend)      # 样式 1–6：图例放在中文标题下面（随内容排，不会和插图重叠）
    return page(f'''<div class="ttl"><div class="tag">SPANISH · READING · 西班牙语阅读</div>
      <div class="row"><div class="txt"><h1 lang="es"><x-t>{esc(p["title_es"])}</x-t></h1><div class="sub">{esc(p["title_zh"])}</div>{inner}</div>{fig}</div>
      <div class="meta"><span>{esc(p.get("series") or "")}</span><span>全文 {words(p)} 词 · {n} 句 · 逐句精读</span></div></div>
      {outer}''')


def sentence_slide(p, s, k, n):
    return page(f'''<div class="top"><b>SPANISH READING</b><span>{head(p)}</span></div>
      <div class="main"><div id="box"><div class="en" lang="es">{sentence_html(s).rstrip()}</div><div class="zh">{nb_tail(s["zh"])}</div></div></div>
      <div class="side" id="side"><h3>VOCABULARY</h3><div id="list">{vocab_html(s)}</div></div>
      <div class="bot"><span>SENTENCE {k} / {n}</span><div class="bar"><i style="width:{k / n * 100:.2f}%"></i></div><span>逐句精读</span></div>''')


def render_slides(slides, outdir, scale):
    """逐屏截图；句子屏自动缩放字号，放不下或字太小就报错（不硬挤）。返回每屏的 (英文字号, 词汇字号)。"""
    from playwright.sync_api import sync_playwright
    vs0 = STYLES[STYLE].get('vs_start', 30)          # 词汇栏起始字号（放不下自动缩小）；C 与四级相同 30px
    assert C4V.FIT.count('vs=30;') == 1
    fit = C4V.FIT.replace('vs=30;', f'vs={vs0};')
    sizes = []
    with sync_playwright() as pw:
        exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': W, 'height': H}, device_scale_factor=scale)
        for i, h in enumerate(slides):
            f = outdir / f'{i:03d}.html'
            f.write_text(h, 'utf-8')
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            pg.wait_for_timeout(150)
            missing = pg.evaluate("""() => [...document.fonts].filter(f => f.status === 'error').map(f => f.family)""")
            if missing:
                raise SystemExit(f'第 {i} 屏字体加载失败：{missing}')
            if STYLE != 'C':
                bad = pg.evaluate(GLYPH)
                if bad:
                    raise SystemExit(f'第 {i} 屏有字落到了系统字体（样式 {STYLE} 的字体缺字）：{bad}')
            if not i:
                cfs, lines, bad = pg.evaluate(COVER, STYLE != 'C')
                if bad:
                    raise SystemExit(f'封面排版有问题（标题 {cfs:.0f}px、{lines} 行）：{bad}')
                print(f'  封面标题 {cfs:.0f}px，{lines} 行')
            else:
                if STYLE != 'C':
                    pg.evaluate(BADGE, GAP)
                fs, vs, fits = pg.evaluate(fit)
                if STYLE != 'C' and (bad := pg.evaluate(HBOX)):
                    raise SystemExit(f'第 {i} 句有内容横向出界（样式 {STYLE}）：{bad}')
                if not fits or fs < MIN_FS or vs < MIN_VS:
                    raise SystemExit(f'第 {i} 句一屏放不下（原文 {fs}px、词汇 {vs}px，下限 {MIN_FS}/{MIN_VS}px）')
                sizes.append((fs, vs))
            pg.screenshot(path=str(outdir / f'{i:03d}.png'))
        br.close()
    return sizes


# ---------------------------------------------------------------- 电磁音（梳状线自校准 + 全频段兜底，见 buzz.py）
def buzz_check(mp4, times):
    import numpy as np
    import buzz
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-vn', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    f0, r, c, e = buzz.check(np.frombuffer(raw, np.float32), 48000, times)
    return ('无电磁音（视频音轨独立测量）', not e,
            f'梳状线 {c:+.2f} dB（上限 {buzz.COMB_MAX_DB:+.1f}）；全频段最强 {f0:.0f} Hz {r:+.1f} dB（上限 {buzz.FULL_MAX_DB:+.1f}）')


def video_name(p):
    tag = '' if STYLE == 'C' else f'（背景 {STYLE} {STYLES[STYLE]["name"]}）'
    return f'西班牙语 每日一练 {p["title_es"]} {p["title_zh"]}{tag}.mp4'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pid')
    ap.add_argument('--voice', help='timings.json 里的音色名（默认用 timings.json 的 "_final"）')
    ap.add_argument('--scale', type=int, default=2, help='2 = 3840×2160（4K）')
    ap.add_argument('--out', default=str(ES / '最终视频'))
    ap.add_argument('--audio-root', default=str(ES / 'audio'))
    ap.add_argument('--name', help='输出文件名（默认「西班牙语 每日一练 标题.mp4」）')
    ap.add_argument('--stills', action='store_true', help='只截图（写到 --out），不编码视频')
    ap.add_argument('--draft', action='store_true', help='草稿：核查不通过也保留成品（只打印问题）')
    ap.add_argument('--style', default='C', choices=list(STYLES),
                    help='背景样式：' + '，'.join(f'{k} {v["name"]}' for k, v in STYLES.items()) + '（默认 C；预览见 西班牙语/背景样式/）')
    a = ap.parse_args()
    global STYLE
    STYLE = a.style

    p = load(a.pid)
    sents = [s for para in p['paras'] for s in para]
    free = shutil.disk_usage(ES).free / 2**30
    need = 0.5 if a.stills else 3                   # 踩坑 29（只截图时只写十几张 PNG）
    if free < need:
        raise SystemExit(f'磁盘剩余只有 {free:.1f} GB（至少需要 {need} GB），先清理临时文件再生成视频')
    tmp = Path(tempfile.mkdtemp(prefix='esvideo_'))
    atexit.register(shutil.rmtree, tmp, True)
    slides = [title_slide(p)] + [sentence_slide(p, s, k, len(sents)) for k, s in enumerate(sents, 1)]
    sizes = render_slides(slides, tmp, a.scale)
    print(f'  原文字号 {min(x[0] for x in sizes)}–{max(x[0] for x in sizes)}px，词汇栏字号 {min(x[1] for x in sizes)}–{max(x[1] for x in sizes)}px')
    if a.stills:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        for f in sorted(tmp.glob('*.png')):
            shutil.copy(f, out / f.name)
        print('截图已保存到', out)
        return

    T = json.loads((Path(a.audio_root) / 'timings.json').read_text('utf-8'))
    voice = a.voice or T['_final']
    tm = T[voice][a.pid]
    times = tm['sentences']
    if len(times) != len(sents):
        raise SystemExit('音频句数与文章句数不一致，请重新生成音频')
    stale = [k for k, (s, t) in enumerate(zip(sents, times), 1) if s['es'] != t['text']]
    if stale:
        raise SystemExit(f'第 {stale} 句的朗读文本和画面原文不一致，请重新生成音频')
    audio = Path(a.audio_root) / tm['file']
    starts, ends = [x['start'] for x in times], [x['end'] for x in times]
    TAIL, HOLD, GAP, FPS = 2.0, 0.5, 0.8, 30
    bad = [i + 2 for i in range(len(times) - 1) if abs(starts[i + 1] - ends[i] - GAP) > 0.01]
    if bad:
        raise SystemExit(f'第 {bad} 句之前的停顿不是 {GAP} 秒，请用最新设置重新生成音频')
    total = max(tm['duration'], ends[-1] + TAIL)
    cuts = [0.0, starts[0]] + [ends[i - 1] + HOLD for i in range(1, len(sents))] + [total]
    frames = [round(c * FPS) for c in cuts[:-1]] + [math.ceil(cuts[-1] * FPS)]
    lst = []
    for i in range(len(slides)):
        segf = tmp / f'seg{i:03d}.mp4'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-framerate', str(FPS),
                        '-i', str(tmp / f'{i:03d}.png'), '-frames:v', str(frames[i + 1] - frames[i]), '-vf', 'format=yuv420p',
                        '-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-tune', 'stillimage',
                        '-pix_fmt', 'yuv420p', '-g', str(FPS * 10), str(segf)], check=True)
        lst.append(f"file '{segf}'")
    (tmp / 'list.txt').write_text('\n'.join(lst))
    total = frames[-1] / FPS
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = a.name or video_name(p)
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
    # 成品核查：高考 / 四级同一套 verify_videos.check（分辨率、流畅度、声画等长、朗读与画面逐句一致、静音、停顿、响度、切屏……）
    from verify_videos import check
    pv = {'year': '', 'paper': '', 'part': '', 'title': '',
          'paras': [[{'en': s['es'], 'w': s['w']} for s in para] for para in p['paras']]}
    tmv = {**tm, 'sentences': [{**t, 'text': t['text']} for t in times]}
    res = [r for r in check(out / name, pv, tmv) if not r[0].startswith('文件名')]
    res.append(buzz_check(out / name, times))
    fails = [f'{n}：{d}' for n, c, d in res if not c]
    for n, c, d in res:
        print(f"  {'✅' if c else '❌'} {n}：{d}")
    if fails and a.draft:
        print('  草稿：以下核查未通过，成品保留：\n  ' + '\n  '.join(fails))
    elif fails:
        (out / name).unlink()
        raise SystemExit('核查未通过，已删除成品：\n  ' + '\n  '.join(fails))
    (out / (Path(name).stem + '_核查.json')).write_text(json.dumps(
        {'video': name, 'voice': voice, 'duration': round(dur, 3), 'checks': [{'item': n, 'ok': c, 'detail': d} for n, c, d in res]},
        ensure_ascii=False, indent=1), 'utf-8')
    print(f'已生成{"（草稿，有未通过的核查项）" if fails else "并核查通过"} {out / name}（时长 {dur:.2f} 秒，读完后静音 {dur - ends[-1]:.2f} 秒）')


if __name__ == '__main__':
    sys.exit(main())
