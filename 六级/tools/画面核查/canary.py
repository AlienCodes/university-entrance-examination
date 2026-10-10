"""Build canary screen sets q1 (from s44) and q2 (from s28) with deliberate visual/content defects.
Every tamper is asserted to actually change the HTML before anything is written."""
import json, re, shutil, sys, tempfile
from pathlib import Path
R = Path('/home/user/university-entrance-examination')
S = Path('/tmp/claude-0/-home-user/8ecea899-aaa9-5a52-878f-ec29bb403c87/scratchpad/cet6/frames')
sys.path.insert(0, str(R / '六级' / 'tools'))
import make_video as M
from playwright.sync_api import sync_playwright
P = {p['id']: p for p in json.loads((R / '六级' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}

def once(h, old, new, why):
    assert h.count(old) >= 1, (why, old)
    return h.replace(old, new, 1)

def drop_vocab_item(h, idx):          # remove the idx-th (1-based) vocab item
    items = list(re.finditer(r'<div class="v [^"]*"><em>\d+</em>.*?</span></div></div>', h))
    assert len(items) >= idx, 'vocab items'
    m = items[idx - 1]
    return h[:m.start()] + h[m.end():]

def drop_plain_word(h, word):         # remove an unhighlighted word from the English line
    en_start = h.index('<div class="en">'); en_end = h.index('</div>', en_start)
    en = h[en_start:en_end]
    new = re.sub(rf'(?<=[ >]){word} ', '', en, count=1)
    assert new != en, ('plain word', word)
    return h[:en_start] + new + h[en_end:]

def screens_for(pid):
    p = P[pid]
    sents = [s for pa in p['paras'] for s in pa]
    out = [('title', None, None, M.title_slide(p))]
    for k, s in enumerate(sents, 1):
        for part in M.split_parts(pid, k, s):
            out.append(('sent', k, part, M.sentence_slide(p, s, k, len(sents), part)))
    return p, sents, out

plans = {
 'q1': ('s44', {
    3: lambda h: drop_vocab_item(h, 2),                                   # vocab list missing item 2
    6: lambda h: once(h, '，', '，\ufffd\ufffd', 'tofu'),                  # unrenderable glyphs in Chinese
    9: lambda h: once(h, 'SENTENCE 9 / ', 'SENTENCE 8 / ', 'counter'),     # wrong sentence counter
    16: lambda h: once(h, '<span class="ph">', '<span class="w">', 'colour'),  # phrase drawn in word colour
    19: lambda h: drop_plain_word(h, 'us'),                            # English word missing on screen
  }, {12: 'overflow'}, {21}),                                              # 12: Chinese overflows; 21: screen dropped
 'q2': ('s28', {
    'title': lambda h: once(h, '<i>Passage One</i>', '<i>Passage Two</i>', 'title passage'),  # wrong passage on title card
    7: lambda h: once(h, '<em>3</em>', '<em>4</em>', 'num'),               # list numbering skips 3 / duplicates 4
    13: lambda h: once(h, '安全', '安仝', 'zh typo'),                        # Chinese typo
    16: 'nextzh',                                                         # Chinese of the next sentence shown
  }, {}, set()),
}
with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': M.W, 'height': M.H})
    for cid, (src, tamper, js, drop) in plans.items():
        p, sents, scr = screens_for(src)
        real = sorted((S / src).glob('screen*.png'))
        assert len(real) == len(scr), (src, len(real), len(scr))
        out = S / cid
        if out.exists(): shutil.rmtree(out)
        out.mkdir()
        n = 0
        q2_split_done = False
        for (kind, k, part, h), png in zip(scr, real):
            key = 'title' if kind == 'title' else k
            if kind == 'sent' and k in drop:
                continue
            t = tamper.get(key)
            # q2 extra: on the split sentence's second screen, delete words from the English
            if cid == 'q2' and kind == 'sent' and part and part[0] > 0 and not q2_split_done:
                t = lambda h: once(h, ' <span class="w">within<sup>14</sup></span> their <span class="w">team<sup>15</sup></span>', '', 'split words'); q2_split_done = True
            n += 1
            dst = out / f'screen{n:02d}.png'
            if t is None and k not in js:
                shutil.copy(png, dst); continue
            if t == 'nextzh':
                h = h.replace(M.esc(sents[k - 1]['zh']), M.esc(sents[k]['zh']), 1)
                assert M.esc(sents[k]['zh']) in h
            elif t is not None:
                h2 = t(h); assert h2 != h, (cid, key); h = h2
            f = Path(td) / 'x.html'; f.write_text(h, 'utf-8')
            pg.goto(f.as_uri()); pg.evaluate('document.fonts.ready')
            if kind == 'sent': pg.evaluate(M.FIT)
            if js.get(k) == 'overflow':
                pg.evaluate("document.querySelector('.zh').style.fontSize='118px'")
            pg.screenshot(path=str(dst))
        assert q2_split_done or cid != 'q2'
        print(cid, 'from', src, 'screens', n)
    br.close()
