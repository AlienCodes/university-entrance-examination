"""Canary set q3 (from s12): subtler defects. Each tamper asserted to change the page."""
import json, re, shutil, sys, tempfile
from pathlib import Path
R = Path('/home/user/university-entrance-examination')
S = Path('/tmp/claude-0/-home-user/8ecea899-aaa9-5a52-878f-ec29bb403c87/scratchpad/cet6/frames')
sys.path.insert(0, str(R / '六级' / 'tools'))
import make_video as M
from playwright.sync_api import sync_playwright
P = {p['id']: p for p in json.loads((R / '六级' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}

def zh_part(h):
    a = h.index('<div class="zh">'); b = h.index('</div>', a); return a, b
def en_part(h):
    a = h.index('<div class="en">'); b = h.index('</div>', a); return a, b

def t_zh_lookalike(h):                          # 日常 → 曰常
    a, b = zh_part(h); z = h[a:b]; assert '日常' in z; return h[:a] + z.replace('日常', '曰常', 1) + h[b:]
def t_gloss_typo(h):                            # 威胁 → 威协 in a panel meaning
    i = h.index('<div id="list">'); L = h[i:]; assert '威胁' in L; return h[:i] + L.replace('威胁', '威协', 1)
def t_swap_numbers(h):                          # panel numbers 2 and 3 swapped (shown 1,3,2,4…)
    i = h.index('<div id="list">'); L = h[i:]
    assert '<em>2</em>' in L and '<em>3</em>' in L
    L = L.replace('<em>2</em>', '<em>@@</em>', 1).replace('<em>3</em>', '<em>2</em>', 1).replace('<em>@@</em>', '<em>3</em>', 1)
    return h[:i] + L
def t_drop_plural(h):                           # an unhighlighted plural loses its -s
    a, b = en_part(h); e = h[a:b]
    plain = re.sub(r'<span class="[^"]*">.*?</span>', lambda m: '\0' * len(m.group()), e)
    m = next(m for m in re.finditer(r'(?<= )([a-z]{4,})s(?=[ ,.])', plain) if not m.group(1).endswith('s'))
    return h[:a] + e[:m.end(1)] + e[m.end(1) + 1:] + h[b:]
def t_drop_sup(h):                              # one numbered circle missing
    a, b = en_part(h); e = h[a:b]; sups = list(re.finditer(r'<sup>\d+</sup>', e)); assert len(sups) >= 3
    m = sups[1]; return h[:a] + e[:m.start()] + e[m.end():] + h[b:]
def t_truncate_zh(h):                           # Chinese translation loses its last clause
    a, b = zh_part(h); z = h[a:b]; j = z.rindex('，'); return h[:a] + z[:j] + '。' + h[b:]

plan = {3: t_zh_lookalike, 8: t_gloss_typo, 10: t_swap_numbers, 15: t_drop_plural, 21: t_drop_sup, 27: t_truncate_zh}
src, cid = 's12', 'q3'
p = P[src]; sents = [s for pa in p['paras'] for s in pa]
real = sorted((S / src).glob('screen*.png')); assert len(real) == 1 + len(sents)
out = S / cid
if out.exists(): shutil.rmtree(out)
out.mkdir()
with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': M.W, 'height': M.H})
    shutil.copy(real[0], out / 'screen01.png')
    for k, s in enumerate(sents, 1):
        dst = out / f'screen{k + 1:02d}.png'
        if k not in plan:
            shutil.copy(real[k], dst); continue
        h = M.sentence_slide(p, s, k, len(sents)); h2 = plan[k](h); assert h2 != h, k
        f = Path(td) / 'x.html'; f.write_text(h2, 'utf-8')
        pg.goto(f.as_uri()); pg.evaluate('document.fonts.ready'); pg.evaluate(M.FIT)
        pg.screenshot(path=str(dst))
    br.close()
ref = (S / 'ref' / f'{src}.txt').read_text('utf-8')
(S / 'ref' / f'{cid}.txt').write_text(ref.replace(f'# {src} ', f'# {cid} ', 1), 'utf-8')
print(cid, 'screens', len(list(out.glob('*.png'))))
