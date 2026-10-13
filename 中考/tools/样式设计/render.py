"""Design harness for the 中考 (junior-high entrance exam) reading videos.

    /opt/ttsenv/bin/python render.py <design.css> <outdir> [--quick]

<design.css> is appended AFTER the shared production CSS (专八/tools/make_video.py CSS; the TEM-8 样式.css is NOT included).
Sample screens use a real 2026 中考 passage (北京 阅读 C, Antarctic sea ice) with hand-written translation/vocabulary,
plus one very dense TEM-8 screen as a stress test. Outputs in <outdir>:
  cover.png, s1.png, s2.png, s3.png (中考 sample), s_dense.png (stress test)   — 1920x1080 (= the 4K video at half scale)
  phone_*.png   the same downscaled to 844x475 (a phone held sideways) — judge legibility on these
  sheet.png     2x2 overview (cover, s1, s2, s_dense)
  report.json   contrast (WCAG ratio of each text style vs its own background) and, without --quick, the full fit sweep:
                all 482 real sentence screens of TEM-8 t01-t10 re-fitted with this CSS — every one must fit (English >= 48px,
                vocabulary >= 22px) and none may get SMALLER than with the plain production CSS ("FIT OK").
"""
import json, re, sys, tempfile
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
R = Path('/home/user/university-entrance-examination')
sys.path.insert(0, str(R / '专八' / 'tools'))
import make_video as M  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

css_file, out = Path(sys.argv[1]), Path(sys.argv[2])
QUICK = '--quick' in sys.argv
out.mkdir(parents=True, exist_ok=True)
DESIGN = css_file.read_text('utf-8') if css_file.name != 'BASE' else ''
EXTRA = (HERE / 'fonts_extra.css').as_uri()
FONTS = (R / '四级' / 'tools' / 'fonts' / 'fonts.css').as_uri()


def page(body):
    return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}"><link rel="stylesheet" href="{EXTRA}">'
            f'<style>{M.CSS}</style><style>{DESIGN}</style></head><body><div class="band"></div>{body}</body></html>')


M.page = page


def zk(h):
    """TEM-8 wording -> 中考 wording (the 中考 pipeline will have its own titles)."""
    return (h.replace('TEM-8 · READING · SECTION A', '中考英语 · 阅读理解').replace('TEM-8 READING', '中考英语 READING')
             .replace('英语专业八级 ', '中考英语 '))


def ent(en, h, t, m, *subs):
    """vocabulary entry; subs = substrings (each must occur exactly once, or 'text@n' for the n-th occurrence)."""
    sp = []
    for x in subs:
        x, _, n = x.partition('@')
        idx = [i.start() for i in re.finditer(re.escape(x), en)]
        i = idx[int(n) - 1] if n else idx[0]
        assert n or len(idx) == 1, (x, len(idx))
        sp.append([i, i + len(x)])
    return {'h': h, 't': t, 'm': m, 'sp': sp}


S1 = 'While the size of Arctic sea ice has dropped by about 40 percent over 40 years, until recently, the size of the sea ice around Antarctica was slowly increasing.'
S2 = 'Then, after 2015, Antarctic ice extent (范围) fell from a record high to several record lows, losing an area as large as Greenland.'
S3 = 'Some research has suggested that higher air temperatures may be the cause.'
SENTS = [
    {'en': S1, 'zh': '虽然北极海冰的面积在40年里减少了约40%，但直到最近，南极洲周围海冰的面积一直在缓慢增加。', 'w': [
        ent(S1, 'size', 'core', 'n. 大小；面积', 'size@1'), ent(S1, 'Arctic', 'core', 'adj. 北极的', 'Arctic'),
        ent(S1, 'sea ice', 'phr', '海冰', 'sea ice@1'), ent(S1, 'drop by', 'phr', '下降了（多少）', 'dropped by'),
        ent(S1, 'percent', 'core', 'n. 百分之……', 'percent'), ent(S1, 'until recently', 'phr', '直到最近', 'until recently'),
        ent(S1, 'Antarctica', 'core', 'n. 南极洲', 'Antarctica'), ent(S1, 'increase', 'core', 'v. 增加；增长', 'increasing')]},
    {'en': S2, 'zh': '然后，2015年之后，南极海冰的范围从创纪录的高点跌至数个历史低点，失去的面积有格陵兰岛那么大。', 'w': [
        ent(S2, 'Antarctic', 'core', 'adj. 南极的', 'Antarctic'), ent(S2, 'extent', 'core', 'n. 范围；程度', 'extent'),
        ent(S2, 'fall from…to', 'phr', '从……下降到', 'fell from', 'to several'[:2]),
        ent(S2, 'record high', 'phr', '历史最高（纪录）', 'record high'), ent(S2, 'record low', 'phr', '历史最低（纪录）', 'record lows'),
        ent(S2, 'area', 'core', 'n. 面积；地区', 'area'), ent(S2, 'as large as', 'phr', '和……一样大', 'as large as'),
        ent(S2, 'Greenland', 'core', 'n. 格陵兰岛', 'Greenland')]},
    {'en': S3, 'zh': '一些研究认为，气温升高可能是原因。', 'w': [
        ent(S3, 'research', 'core', 'n. 研究', 'research'), ent(S3, 'suggest', 'core', 'v. 表明；认为', 'suggested'),
        ent(S3, 'air temperature', 'phr', '气温', 'air temperatures'), ent(S3, 'cause', 'core', 'n. 原因', 'cause')]},
]
ZK = {'id': 'zk', 'paper': '2026年 北京市', 'passage': '阅读 C', 'title': '南极海冰为何骤减', 'genre': '说明文 · 气候与环境', 'words': 382,
      'paras': [SENTS]}
P = {p['id']: p for p in json.loads((R / '专八' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
IDS = [f't{i:02d}' for i in range(1, 11)]


def sents(pid):
    return [s for pa in P[pid]['paras'] for s in pa]


def slide(pid, k, part=0):
    S = sents(pid)
    return M.sentence_slide(P[pid], S[k - 1], k, len(S), M.split_parts(pid, k, S[k - 1])[part])


SAMPLES = [('cover', lambda: zk(M.title_slide(ZK))),
           ('s1', lambda: zk(M.sentence_slide(ZK, SENTS[0], 1, 21))),
           ('s2', lambda: zk(M.sentence_slide(ZK, SENTS[1], 2, 21))),
           ('s3', lambda: zk(M.sentence_slide(ZK, SENTS[2], 3, 21))),
           ('s_dense', lambda: zk(slide('t09', 14, 0)))]

CONTRAST = """() => {
  const lum = c => { const m = c.match(/[\\d.]+/g).map(Number); const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); };
    return [.2126 * f(m[0]) + .7152 * f(m[1]) + .0722 * f(m[2]), m.length > 3 ? m[3] : 1]; };
  const bg = el => { for (let e = el; e; e = e.parentElement) { const s = getComputedStyle(e);
      if (s.backgroundImage && s.backgroundImage !== 'none') return [s.backgroundColor, 'IMAGE'];
      const a = s.backgroundColor.match(/[\\d.]+/g).map(Number); if (a.length < 4 || a[3] > .5) return [s.backgroundColor, '']; }
    return ['rgb(255,255,255)', '']; };
  const out = {};
  const pick = { 'English body (.en)': '.en', 'single-word highlight (.w)': '.en .w', 'phrase highlight (.ph)': '.en .ph',
    'number in circle (sup)': 'sup', 'phrase circle (.ph sup)': '.ph sup', 'Chinese (.zh)': '.zh', 'vocab headword (.v b)': '.v b',
    'phrase headword (.v.ph b)': '.v.ph b', 'vocab meaning (.v span)': '.v span', 'vocab POS (.v i)': '.v i', 'panel number (.v em)': '.v em',
    'header left (.top b)': '.top b', 'header right (.top span)': '.top span', 'footer (.bot)': '.bot', 'VOCABULARY label': '.side h3' };
  for (const [name, sel] of Object.entries(pick)) { const el = document.querySelector(sel); if (!el) continue;
    const [b, img] = bg(el); const [l1] = lum(getComputedStyle(el).color); const [l2] = lum(b);
    out[name] = Math.round(((Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05)) * 10) / 10 + (img ? ' (background is an image/gradient: ratio vs its base colour only - check by eye)' : ''); }
  return out; }"""

with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': M.W, 'height': M.H})
    f = Path(td) / 'x.html'

    def load(h, fit=True):
        f.write_text(h, 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        return pg.evaluate(M.FIT) if fit else None

    rep = {'samples': {}, 'contrast': {}}
    for name, fn in SAMPLES:
        r = load(fn(), name != 'cover')
        pg.screenshot(path=str(out / f'{name}.png'))
        Image.open(out / f'{name}.png').resize((844, 475), Image.LANCZOS).save(out / f'phone_{name}.png')
        if name != 'cover':
            rep['samples'][name] = {'english_px': r[0], 'vocab_px': r[1], 'fits': r[2]}
        if name in ('s1', 's2'):
            rep['contrast'].update(pg.evaluate(CONTRAST))
    ims = [Image.open(out / f'{n}.png').resize((960, 540), Image.LANCZOS) for n in ('cover', 's1', 's2', 's_dense')]
    sheet = Image.new('RGB', (1940, 1100), '#808080')
    for i, im in enumerate(ims):
        sheet.paste(im, (10 + (i % 2) * 970, 10 + (i // 2) * 550))
    sheet.save(out / 'sheet.png')

    if not QUICK:
        base_f = HERE / 'base_fit.json'
        base = json.loads(base_f.read_text()) if base_f.exists() else None
        fit, bad, smaller = {}, [], []
        for pid in IDS:
            for k, s in enumerate(sents(pid), 1):
                for i in range(len(M.split_parts(pid, k, s))):
                    fs, vs, ok = load(slide(pid, k, i))
                    key = f'{pid}:{k}:{i + 1}'
                    fit[key] = [fs, vs]
                    if not (ok and fs >= M.MIN_FS and vs >= M.MIN_VS):
                        bad.append(f'{key} english {fs}px vocab {vs}px fits={ok}')
                    if base and (fs < base[key][0] or vs < base[key][1]):
                        smaller.append(f'{key} english {base[key][0]}->{fs}px vocab {base[key][1]}->{vs}px')
        if css_file.name == 'BASE':
            base_f.write_text(json.dumps(fit))
        rep['fit'] = {'screens': len(fit), 'failures': bad, 'smaller_than_plain_css': smaller,
                      'min_english_px': min(v[0] for v in fit.values()), 'min_vocab_px': min(v[1] for v in fit.values()),
                      'mean_english_px': round(sum(v[0] for v in fit.values()) / len(fit), 1), 'mean_vocab_px': round(sum(v[1] for v in fit.values()) / len(fit), 1)}
    br.close()
(out / 'report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), 'utf-8')
print(json.dumps(rep, ensure_ascii=False, indent=1)[:3000])
if not QUICK:
    print('FIT OK' if not rep['fit']['failures'] and not rep['fit']['smaller_than_plain_css'] else 'FIT PROBLEMS (see above)')
