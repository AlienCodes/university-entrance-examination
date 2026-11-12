"""视频画面背景样式库（6 种）——各项目共用（2026-10-16 起：西班牙语、专八；中考设计库原样移来，见 README.md）。

    import themes as TH
    TH.THEMES['1']['name']                     # '晴空校园'
    TH.css('1', 项目调整文件)                  # 基础样式 + 换行 + 本项目调整（项目调整追加在后面覆盖）
    TH.FONTS_CSS.as_uri()                      # 1–6 用到的网页字体
    TH.files('1')                              # 决定画面的全部文件（写进“截图审阅通过”的指纹）
    pg.evaluate(TH.GLYPH) / pg.evaluate(TH.HBOX) / pg.evaluate(TH.COVER, 是否缩小标题)   # 截图前的程序检查（不合格返回问题列表）

基础样式只管颜色、字体、装饰与封面，不改版面尺寸；版面、时间轴、编码和成品核查由各项目自己的 make_video.py 负责。
只用 Python 标准库（西班牙语工具包在老师的电脑上运行）。
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS_CSS = HERE / 'fonts' / 'fonts.css'
THEMES = {t['key']: t for t in json.loads((HERE / 'themes.json').read_text('utf-8'))['themes']}


def css(key, tail=None):
    """样式 key（'1'–'6'）的完整 CSS：共用基础样式；tail（项目调整文件）给了就接在后面，中间隔一个换行。"""
    base = (HERE / 'css' / THEMES[key]['file']).read_text('utf-8')
    return base if tail is None else base + '\n' + Path(tail).read_text('utf-8')


def files(key=None):
    """决定画面的共用文件（本程序、索引、基础样式、全部字体文件）：给指纹用，字体换了、样式改了，指纹就变。"""
    out = [Path(__file__).resolve(), HERE / 'themes.json']
    if key is not None:
        out.append(HERE / 'css' / THEMES[key]['file'])
    out += sorted(p for p in (HERE / 'fonts').rglob('*') if p.is_file())
    return out


# 版式骨架（各项目共用）：词条、词性与释义的间距放在左边元素的右侧（词条→词性、词性→释义各 10px），释义折到下一行时不再缩进（踩坑 33）；
# 基础样式 2 的 .v b{margin:0 -.08em}、4/6 的 .v i/.v span{margin-left} 是按旧版程序（词条与词性之间有空格）设计的，在新程序里会粘连或多缩进
def vocab_gaps(gloss='.v span'):
    """gloss = 释义元素的选择器：西班牙语的释义是 .v 里唯一的 span；专八的释义里还套着标点挤压用的 span（.pl 去左半字），要写 '.v div>span'，
    否则 margin-left:0!important 把行首左括号的去半字也取消了（t03 截图检查：释义行首“（航海用语）”多缩进半个字）。"""
    return f".v b{{margin-right:10px}}.v i{{margin-left:0!important;margin-right:10px}}{gloss}{{margin-left:0!important}}"


VOCAB_GAPS = vocab_gaps()

# 封面：缩小标题（shrink=True：最多两行，放不下逐步缩小字号，不小于 56px）；所有样式都核对封面各块不出界、不互相重叠、插图已加载
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
# 横向不出界：整块不断行以后，词条、释义、原文、译文的每一段都必须在所在栏的内边距以内；页眉左边的标签与右边的标题不挤在一起、不出界
HBOX = """() => { const bad = [];
  for (const [box, sel] of [['#side', '#list'], ['.main', '#box']]) { const b = document.querySelector(box), c = getComputedStyle(b), r = b.getBoundingClientRect();
    const L = r.left + b.clientLeft + parseFloat(c.paddingLeft) - 1, R = r.left + b.clientLeft + b.clientWidth - parseFloat(c.paddingRight) + 1;
    const w = document.createTreeWalker(document.querySelector(sel), NodeFilter.SHOW_TEXT), g = document.createRange();
    for (let n; (n = w.nextNode());) { g.selectNodeContents(n);      // 只量文字本身（荧光笔、徽章的衬底可以略出边）
      for (const q of g.getClientRects()) if (q.width && (q.left < L || q.right > R)) { bad.push(n.data.slice(0, 20)); break; } } }
  const a = document.querySelector('.top b').getBoundingClientRect(), t = document.querySelector('.top span').getBoundingClientRect();
  if (a.right > t.left - 20 || t.right > innerWidth) bad.push('页眉标题太长，和左边的标签挤在一起或出界');
  return bad; }"""
# 字形检查：画面上每个字都必须由该元素 font-family 里列出的网页字体之一画出（不许落到系统字体，如西语重音字母、¿ ¡ 或生僻汉字）。
# 方法：分别用两种字形明显不同的备用字体垫底画同一个字，像素完全相同 = 列出的字体自己有这个字。
GLYPH = r"""async () => { const GEN = new Set(['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui']);
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
