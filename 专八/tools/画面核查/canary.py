"""画面核查埋雷：按 埋雷位置.json，用与成品相同的渲染程序把指定屏做成带缺陷的屏，其余屏直接复制成品截图，组成一套“假视频截图”。
/opt/ttsenv/bin/python 专八/tools/画面核查/canary.py <frames dir> 埋雷位置.json
每处篡改都断言恰好改动一次（踩坑：埋雷锚点不唯一）。"""
import json, re, shutil, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
R = HERE.parents[2]
S = Path(sys.argv[1])
sys.path.insert(0, str(R / '专八' / 'tools'))
import make_video as M
from playwright.sync_api import sync_playwright
P = {p['id']: p for p in json.loads((R / '专八' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}


def region(h, start):
    a = h.index(start)
    b = h.index('</div>', a) if start != '<div id="list">' else len(h)
    return a, b


def sub1(h, start, old, new):
    a, b = region(h, start)
    z = h[a:b]
    assert z.count(old) == 1, (start, old, z.count(old))
    return h[:a] + z.replace(old, new) + h[b:]


def tamper(h, op, args, parts, part):
    if op == 'zh':
        return sub1(h, '<div class="zh">', *args)
    if op == 'zh_part':                     # 这一屏显示同一句另一屏的中文
        return sub1(h, '<div class="zh">', M.esc(parts[part][2]), M.esc(parts[args[0]][2]))
    if op == 'zh_trunc':                    # 中文截掉最后一个分句
        a, b = region(h, '<div class="zh">')
        z = h[a:b]
        j = z.rindex('，')
        return h[:a] + z[:j] + '。' + h[b:]
    if op == 'en':
        return sub1(h, '<div class="en">', *args)
    if op == 'gloss':
        return sub1(h, '<div id="list">', *args)
    if op == 'swapnum':
        x, y = args
        h = sub1(h, '<div id="list">', f'<em>{x}</em>', '<em>@@</em>')
        h = sub1(h, '<div id="list">', f'<em>{y}</em>', f'<em>{x}</em>')
        return sub1(h, '<div id="list">', '<em>@@</em>', f'<em>{y}</em>')
    if op == 'dropsup':
        return sub1(h, '<div class="en">', f'<sup>{args[0]}</sup>', '')
    if op == 'color':                       # 短语高亮改用单词的绿色
        return sub1(h, '<div class="en">', f'<span class="ph">{args[0]}', f'<span class="w">{args[0]}')
    if op in ('footer', 'title'):
        assert h.count(args[0]) == 1, (op, args[0], h.count(args[0]))
        return h.replace(*args)
    raise ValueError(op)


plan = json.loads(Path(sys.argv[2]).read_text('utf-8'))
with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
    br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': M.W, 'height': M.H})
    for cid, spec in plan.items():
        if cid.startswith('_'):
            continue
        src = spec['from']
        p = P[src]
        sents = [s for pa in p['paras'] for s in pa]
        screens = [(0, 0, None)]
        for k, s in enumerate(sents, 1):
            parts = M.split_parts(src, k, s)
            screens += [(k, i, parts) for i in range(len(parts))]
        real = sorted((S / src).glob('screen*.png'))
        assert len(real) == len(screens), (src, len(real), len(screens))
        defects = {(d['sent'], d.get('part', 1) - 1): d for d in spec['defects']}
        assert len(defects) == len(spec['defects'])
        out = S / cid
        if out.exists():
            shutil.rmtree(out)
        out.mkdir()
        n, used = 0, set()
        for (k, i, parts), shot in zip(screens, real):
            d = defects.get((k, i))
            if d and d['op'] == 'drop':
                used.add((k, i))
                continue
            n += 1
            dst = out / f'screen{n:02d}.png'
            if not d:
                shutil.copy(shot, dst)
                continue
            used.add((k, i))
            h = M.title_slide(p) if k == 0 else M.sentence_slide(p, sents[k - 1], k, len(sents), parts[i])
            h2 = tamper(h, d['op'], d.get('args', []), parts, i)
            assert h2 != h, (cid, k, i)
            f = Path(td) / 'x.html'
            f.write_text(h2, 'utf-8')
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            if k:
                pg.evaluate(M.FIT)
            pg.screenshot(path=str(dst))
        assert used == set(defects), (cid, set(defects) - used)
        ref = (S / 'ref' / f'{src}.txt').read_text('utf-8')
        (S / 'ref' / f'{cid}.txt').write_text(ref.replace(f'# {src} ', f'# {cid} ', 1), 'utf-8')
        print(cid, 'from', src, 'screens', n, 'defects', len(defects))
    br.close()
