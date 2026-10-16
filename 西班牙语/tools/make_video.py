"""生成西班牙语逐句精读视频（沿用四级设计方案 C「杂志编号注释」，用户给的参考图就是四级视频的一帧）。

    python 西班牙语/tools/make_video.py es01 [--voice 音色名] [--scale 2] [--style C|1|2|3|4|5|6]
    python 西班牙语/tools/make_video.py es01 --stills [--style 5]     # 只出截图：默认写到 西班牙语/截图/es01_5/，1920×1080

截图用的浏览器：默认用 Playwright 自带的 Chromium（老师电脑上 `python -m playwright install chromium` 装的那个）；
环境变量 ES_CHROMIUM 可以指定另一个 Chromium 程序。每次运行都会打印一行，说明用的是哪个浏览器。

背景样式（--style，默认 C）：C = 四级设计方案 C（下面描述的默认画面）；1–6 = 中考设计的 6 种背景（晴空校园、手账笔记本、教室黑板、
活页单词卡、紫黄撞色、柔彩插画），由各项目共用的样式库 tools/video/themes/ 提供（基础样式 css/、字体 fonts/、截图前的检查 themes.py），
西班牙语自己的调整在 西班牙语/tools/样式/（每种背景一份「西班牙语版调整」，追加在基础样式之后；索引 styles.json）。
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
- 词条数据来自 西班牙语/文章/<id>.json（w：h 词头、pos 词性、zh 释义、surface 句中要高亮的原样文字），词性按《现代西班牙语》习惯（m. f. adj. adv. tr. loc.）
- 多词词条（comida típica、cada vez que……）算短语（砖红色）；短语不显示 loc.，名词短语保留阴阳性（f. / m.）
- 片头：西语标题 + 中文标题 + 文档里的插图；页眉「SPANISH READING」
- 电磁音检查：在 2–16 kHz 全频段找窄带峰（新的语音模型声码器频点和 Kokoro 不同，不能只查四级那 9 个频点）
- 响度四项、限值同高考，但 3 秒短时波动只测朗读部分（片头片尾的规定静音不进 3 秒窗，见 loudness.py）；另查逗号、分号、冒号、破折号处停顿 0.28 秒且无声
输入：西班牙语/文章/<id>.json、西班牙语/audio/timings.json（make_audio.py 生成）。输出：西班牙语/最终视频/。
"""
import argparse
import atexit
import html
import json
import math
import os
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
TH = c4.load('themes', 'tools/video/themes/themes.py')            # 共用背景样式库 1–6（基础样式、字体、字形 / 出界 / 封面检查）

W, H = C4V.W, C4V.H
MIN_FS, MIN_VS = C4V.MIN_FS, C4V.MIN_VS
LETTERS = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")
STYLE_DIR = HERE / '样式'
STYLES = {s['key']: s for s in json.loads((STYLE_DIR / 'styles.json').read_text('utf-8'))['styles']}
assert all(STYLES[k]['name'] == v['name'] for k, v in TH.THEMES.items()), '西班牙语 styles.json 与共用样式库 themes.json 的名称不一致'
STYLE = 'C'                     # 当前背景样式（main() 按 --style 设置）

CSS_ES = """
x-nb{white-space:nowrap}
/* 词条、词性与释义的间距放在左边元素的右侧（不放在释义左侧）：单行时位置完全不变（词条→词性 8px、→释义 10px），
   释义折到下一行时不再缩进（踩坑 33“折行释义多缩进”；C 的示例视频第 8 句曾出现） */
.v b{margin-right:10px}.v i{margin-left:-2px;margin-right:10px}.v span{margin-left:0}
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
""" + TH.VOCAB_GAPS + '\n'   # 词条间距放在左边元素的右侧：释义折到第二行时行首不会多出一截缩进（踩坑 33；共用样式库的版式骨架）

# 背景样式 1–6 截图前的三步（C 不跑）：徽章间距、封面标题字号、字形检查。
GAP = 0.04       # 生词编号徽章与前一个字母笔画之间至少留 0.04 个字号的空隙（按字形实测右边距，踩坑 39：徽章贴字）
BADGE = """(gap) => { document.documentElement.style.setProperty('--fs', '64px'); const cv = document.createElement('canvas').getContext('2d');
  for (const s of document.querySelectorAll('.en sup')) { let n = s.previousSibling; while (n && n.nodeType === 1) n = n.lastChild || n.previousSibling;
    if (!n || !n.data) continue; const c = n.data.trim().slice(-1); if (!c) continue;
    const cs = getComputedStyle(n.parentElement), fs = parseFloat(cs.fontSize), ss = parseFloat(getComputedStyle(s).fontSize) / fs;
    cv.font = `${cs.fontStyle} ${cs.fontWeight} 100px ${cs.fontFamily}`; const m = cv.measureText(c), rsb = (m.width - m.actualBoundingBoxRight) / 100;
    const ls = (parseFloat(cs.letterSpacing) || 0) / fs;
    s.style.marginLeft = Math.max(0.04, (gap - rsb - ls) / ss).toFixed(3) + 'em'; } }"""
# 封面（样式 1–6 缩小西语标题；所有样式都核对封面各块）、横向出界、字形检查：共用样式库 tools/video/themes/themes.py
COVER, HBOX, GLYPH = TH.COVER, TH.HBOX, TH.GLYPH


def esc(s):
    return html.escape(s, quote=True)


def page(body):
    fonts = (ROOT / '四级' / 'tools' / 'fonts' / 'fonts.css').as_uri()
    extra = theme = ''
    if STYLE != 'C':            # 背景样式 1–6：样式字体 + 样式 CSS（追加在通用样式之后覆盖颜色、字体、装饰）
        extra = f'<link rel="stylesheet" href="{TH.FONTS_CSS.as_uri()}">'
        theme = f'<style>{TH.css(STYLE, STYLE_DIR / STYLES[STYLE]["file"])}</style>'      # 共用基础样式 + 西班牙语版调整
    return (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><link rel="stylesheet" href="{fonts}">{extra}'
            f'<style>{C4V.CSS}{CSS_ES}</style>{theme}{f"<style>{CSS_STYLED}</style>" if STYLE != "C" else ""}</head><body><div class="band"></div>{body}</body></html>')


def nb_tail(s):
    """中文最后两个字（连同句末标点）不拆开，避免最后一行只剩一个字（踩坑 33、41；所有样式，C 也一样：
    C 的示例视频曾出现「海滩和山 / 脉。」「多样 / 性。」，2026-10-15 改为与 1–6 相同）。"""
    k = len(s)
    while k and s[k - 1] in '。！？；：，、”’）》…—.!?;:,)':
        k -= 1
    if k < 3:
        return esc(s)
    return f'{esc(s[:k - 2])}<x-nb>{esc(s[k - 2:])}</x-nb>'


def gloss_html(s):
    """词汇释义（所有样式）：按逗号、分号、顿号切成小块，每块（≤ 8 字）整体不断行，只在标点后换行，
    避免「巨 / 大的」「可 / 能」这种在词中间断开（踩坑 33）；长块只绑定末两字（C 曾出现「做某 / 事」）。"""
    out = []
    for c in re.findall(r'[^，；、,;]+[，；、,;]?|[，；、,;]', s):
        out.append(f'<x-nb>{esc(c)}</x-nb>' if len(c) <= 8 else nb_tail(c))
    return ''.join(out)


def load(pid):
    """读文章，给每个词条算出在句中的位置；任何一条对不上都报错（不静默失效）。"""
    p = json.loads((ES / '文章' / f'{pid}.json').read_text('utf-8'))
    for k, s in enumerate((s for para in p['paras'] for s in para), 1):
        if not s['w']:
            raise SystemExit(f'第 {k} 句没有标生词：每一句至少要标一个（"w" 里至少一个词条）')
        taken = []
        for w in s['w']:
            n = s['es'].count(w['surface'])
            if n != 1:
                raise SystemExit(f'第 {k} 句：词条「{w["h"]}」的 surface（句中要高亮的原样文字）「{w["surface"]}」在这一句里出现 {n} 次'
                                 '（必须恰好 1 次，大小写、重音都要和原文一模一样；出现多次就多写几个字，让它只匹配一处）')
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


DEV_CHROMIUM = Path('/opt/pw-browsers/chromium')   # 开发容器里的 Chromium：只在 Playwright 自带的打不开时才用


def launch_browser(pw):
    """打开截图用的 Chromium，并打印一行说明用的是哪个：
    ① 环境变量 ES_CHROMIUM 指定的程序（存在才用）；② 否则用 Playwright 自带的 Chromium（老师电脑上 playwright install chromium 装的就是它）；
    ③ 只有②打不开、并且有开发容器里的 /opt/pw-browsers/chromium 时，才改用它。"""
    env = os.environ.get('ES_CHROMIUM', '').strip()
    note = ''
    if env:
        if Path(env).exists():
            br = pw.chromium.launch(executable_path=env)
            print(f'  浏览器：环境变量 ES_CHROMIUM 指定的 {env}（Chromium {br.version}）')
            return br
        note = f'（环境变量 ES_CHROMIUM 指定的 {env} 不存在，没有用它）'
    try:
        br = pw.chromium.launch()
        print(f'  浏览器：Playwright 自带的 Chromium {br.version}{note}')
        return br
    except Exception as e:      # noqa: BLE001  自带的打不开：只有开发容器里有备用的才改用，否则照常报错
        if not DEV_CHROMIUM.exists():
            raise
        why = (str(e).strip().splitlines() or [type(e).__name__])[0]
        br = pw.chromium.launch(executable_path=str(DEV_CHROMIUM))
        print(f'  浏览器：Playwright 自带的 Chromium 打不开（{why}），改用 {DEV_CHROMIUM}（Chromium {br.version}）{note}')
        return br


def render_slides(slides, outdir, scale):
    """逐屏截图；句子屏自动缩放字号，放不下或字太小就报错（不硬挤）。返回每屏的 (英文字号, 词汇字号)。"""
    from playwright.sync_api import sync_playwright
    vs0 = STYLES[STYLE].get('vs_start', 30)          # 词汇栏起始字号（放不下自动缩小）；C 与四级相同 30px
    assert C4V.FIT.count('vs=30;') == 1
    fit = C4V.FIT.replace('vs=30;', f'vs={vs0};')
    sizes = []
    with sync_playwright() as pw:
        br = launch_browser(pw)
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


# ---------------------------------------------------------------- 西语自己的几项（对视频音轨独立测量）
def spanish_checks(mp4, tm, res):
    """在高考 / 四级同一套核查结果 res 上：
    ① 响度一致：同样四项、同样限值，3 秒短时波动只测朗读部分（片头片尾的规定静音另有两项检查），见 loudness.py；
    ② 逗号、分号、冒号、破折号处的停顿：每处正好 clause_pause（0.28 秒）且确实无声（和句间停顿同一标准：两头各让 0.08 秒，峰值 < −50 dB）；
    ③ 电磁音：梳状线自校准 + 全频段兜底，见 buzz.py。返回新的结果列表。"""
    import buzz
    import loudness
    from verify_videos import audio_of, peak_db
    x, sr = audio_of(mp4)
    times = tm['sentences']
    rep, errs = loudness.measure(x, sr, times, tm.get('voice_cfg', {}).get('lufs', -16.0))
    res = [(loudness.NAME, not errs, loudness.detail(rep, errs)) if n == loudness.NAME else (n, c, d) for n, c, d in res]
    cp = tm.get('voice_cfg', {}).get('clause_pause')
    gaps, bad, loud = [], [], []
    for k, t in enumerate(times, 1):
        ps = t.get('parts')
        if not ps or (t.get('segments') and len(ps) != len(t['segments'])):
            bad.append(k)
            continue
        for (a0, a1), (b0, b1) in zip(ps, ps[1:]):
            gaps.append(b0 - a1)
            if cp is None or abs(b0 - a1 - cp) > 0.01:
                bad.append(k)
            if peak_db(x[int((a1 + 0.08) * sr):int((b0 - 0.08) * sr)]) > -50:
                loud.append(k)
    res.append(('逗号、分号、冒号、破折号处停顿 0.28 秒且无声', cp == 0.28 and not bad and not loud,
                (f'{len(gaps)} 处，{min(gaps):.3f}–{max(gaps):.3f} 秒，全部无声' if gaps else '这篇没有句中停顿')
                + (f'；时长不对或没有分段记录：第 {sorted(set(bad))} 句' if bad else '')
                + (f'；有声音：第 {sorted(set(loud))} 句' if loud else '') + ('' if cp == 0.28 else f'；音色设置的停顿是 {cp} 秒')))
    rp = buzz.report(x, sr, times)
    res.append(('无电磁音（视频音轨独立测量）', not rp['errs'], buzz.detail(rp)))
    return res


def video_name(p):
    tag = '' if STYLE == 'C' else f'（背景 {STYLE} {STYLES[STYLE]["name"]}）'
    return f'西班牙语 每日一练 {p["title_es"]} {p["title_zh"]}{tag}.mp4'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pid')
    ap.add_argument('--voice', help='timings.json 里的音色名（默认用 timings.json 的 "_final"）')
    ap.add_argument('--scale', type=int, help='画面倍数：2 = 3840×2160（4K，视频默认）；--stills 默认 1（1920×1080）')
    ap.add_argument('--out', help='输出文件夹（视频默认 西班牙语/最终视频/；--stills 默认 西班牙语/截图/<篇目>_<背景>/）')
    ap.add_argument('--audio-root', default=str(ES / 'audio'))
    ap.add_argument('--name', help='输出文件名（默认「西班牙语 每日一练 标题.mp4」）')
    ap.add_argument('--stills', action='store_true', help='只截图，不编码视频（默认写到 西班牙语/截图/<篇目>_<背景>/）')
    ap.add_argument('--draft', action='store_true', help='草稿：核查不通过也保留成品（只打印问题）')
    ap.add_argument('--style', default='C', choices=list(STYLES),
                    help='背景样式：' + '，'.join(f'{k} {v["name"]}' for k, v in STYLES.items()) + '（默认 C；预览见 西班牙语/背景样式/）')
    a = ap.parse_args()
    global STYLE
    STYLE = a.style
    scale = a.scale if a.scale is not None else (1 if a.stills else 2)
    final = ES / '最终视频'
    out = Path(a.out) if a.out else (ES / '截图' / f'{a.pid}_{a.style}' if a.stills else final)   # 截图文件夹与 batch.py 相同
    if a.stills and (out.resolve() == final.resolve() or final.resolve() in out.resolve().parents):
        raise SystemExit('截图不能放进 最终视频/（那里只放成品视频）。不写 --out 就会放到 西班牙语/截图/，或用 --out 指定别的文件夹')

    p = load(a.pid)
    sents = [s for para in p['paras'] for s in para]
    free = shutil.disk_usage(ES).free / 2**30
    need = 0.5 if a.stills else 3                   # 踩坑 29（只截图时只写十几张 PNG）
    if free < need:
        raise SystemExit(f'磁盘剩余只有 {free:.1f} GB（至少需要 {need} GB），先清理临时文件再生成视频')
    tmp = Path(tempfile.mkdtemp(prefix='esvideo_'))
    atexit.register(shutil.rmtree, tmp, True)
    slides = [title_slide(p)] + [sentence_slide(p, s, k, len(sents)) for k, s in enumerate(sents, 1)]
    sizes = render_slides(slides, tmp, scale)
    print(f'  原文字号 {min(x[0] for x in sizes)}–{max(x[0] for x in sizes)}px，词汇栏字号 {min(x[1] for x in sizes)}–{max(x[1] for x in sizes)}px')
    if a.stills:
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
    res = [(n.replace('画面英文', '画面西语原文'), c, d) for n, c, d in check(out / name, pv, tmv) if not n.startswith('文件名')]
    res = spanish_checks(out / name, tm, res)
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
