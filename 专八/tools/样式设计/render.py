"""Design harness for TEM-8 video themes.

    /opt/ttsenv/bin/python render.py <design.css> <outdir> [--quick]

<design.css> is appended AFTER the production CSS (so it overrides it). Output in <outdir>:
  cover.png, s_short.png, s_split.png, s_dense.png, s_zh.png   (1920x1080 = exactly what the 4K video shows, at half scale)
  phone_*.png    the same screens downscaled to 844x475 (a phone held sideways) - judge legibility on these
  sheet.png      2x2 overview (cover + 3 sentence screens)
  report.json / printed summary:
    fit   : every sentence screen of t01-t10 (with the approved screen splits) re-fitted with this CSS:
            must fit with English >= 48px and vocabulary >= 22px; also counts screens whose font size got
            SMALLER than with the current production design (should be 0 - legibility must not get worse)
    contrast : WCAG contrast ratio of each text style against its own background
  --quick skips the full fit sweep (use while iterating; the final run must be without --quick).
"""
import json, sys, tempfile
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
LEGEND = '.legend .lw{background:#1f5c4a}.legend .lp{background:#a14a2a}'


def page(body):
    return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}"><link rel="stylesheet" href="{EXTRA}">'
            f'<style>{M.CSS}{LEGEND}</style><style>{DESIGN}</style></head><body><div class="band"></div>{body}</body></html>')


M.page = page
_title = M.title_slide


def title_slide(p):
    h = _title(p)
    h = h.replace('<em style="background:#1f5c4a"></em>', '<em class="lw"></em>').replace('<em style="background:#a14a2a"></em>', '<em class="lp"></em>')
    assert 'class="lw"' in h and 'class="lp"' in h
    return h


P = {p['id']: p for p in json.loads((R / '专八' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
IDS = [f't{i:02d}' for i in range(1, 11)]


def sents(pid):
    return [s for pa in P[pid]['paras'] for s in pa]


def slide(pid, k, part=0):
    S = sents(pid)
    return M.sentence_slide(P[pid], S[k - 1], k, len(S), M.split_parts(pid, k, S[k - 1])[part])


SAMPLES = [('cover', lambda: title_slide(P['t04'])),
           ('s_short', lambda: slide('t04', 5)),
           ('s_split', lambda: slide('t04', 39, 0)),
           ('s_dense', lambda: slide('t09', 14, 0)),
           ('s_zh', lambda: slide('t06', 36, 1))]

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

    rep = {'samples': {}}
    for name, fn in SAMPLES:
        r = load(fn(), name != 'cover')
        pg.screenshot(path=str(out / f'{name}.png'))
        Image.open(out / f'{name}.png').resize((844, 475), Image.LANCZOS).save(out / f'phone_{name}.png')
        if name != 'cover':
            rep['samples'][name] = {'english_px': r[0], 'vocab_px': r[1], 'fits': r[2]}
        if name in ('s_short', 's_split'):
            rep.setdefault('contrast', {}).update(pg.evaluate(CONTRAST))
    ims = [Image.open(out / f'{n}.png').resize((960, 540), Image.LANCZOS) for n in ('cover', 's_short', 's_split', 's_dense')]
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
        rep['fit'] = {'screens': len(fit), 'failures': bad, 'smaller_than_current_design': smaller,
                      'min_english_px': min(v[0] for v in fit.values()), 'min_vocab_px': min(v[1] for v in fit.values()),
                      'mean_english_px': round(sum(v[0] for v in fit.values()) / len(fit), 1), 'mean_vocab_px': round(sum(v[1] for v in fit.values()) / len(fit), 1)}
    br.close()
(out / 'report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), 'utf-8')
print(json.dumps(rep, ensure_ascii=False, indent=1)[:3000])
if not QUICK:
    print('FIT OK' if not rep['fit']['failures'] and not rep['fit']['smaller_than_current_design'] else 'FIT PROBLEMS (see above)')
