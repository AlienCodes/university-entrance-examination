"""排版检查自身的埋雷测试（踩坑 21、37：每条检查都要证明能查出来）：t03 第二轮审阅后新加的检查，每种画面各埋一次，必须全部查出。

    /opt/ttsenv/bin/python 专八/tools/画面核查/埋雷_排版检查.py [t03] [--styles C,1,2,3,4,5,6]

用生成视频的同一排版（make_video.layout）排出真实的屏，排好后在页面上故意做坏一处，再跑 layoutcheck（make_video.screen_checks 用的同一套），
看报没报出对应的那一项：
  文字重叠   译文上移压住英文最后一行（行高的 25%）；某个词条上移压住上一个词条（行高的 25%）
  分屏字号   分屏句子的第 2 屏把词汇栏字号改小 3px（实测字号比对 LC.sizes / size_diff）
  括注拆开   放得下一行的括注（同 gunwale）被强行拆成两行
  括注断开   括注在中文片段中间断开（顺着…… / 一路）
  短语断开   放得下一行的高亮短语被拆到两行
  译文断词   译文在一个词的中间断行
另外每种画面都核对：没埋雷的同一屏这些项为 0（埋雷前先查一遍）。有任何一项没查出或误报，退出码非 0。
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import make_video as M  # noqa: E402
LC = M.LC

KEYS = ('文字重叠', '分屏字号', '括注拆开', '括注断开', '短语断开', '译文断词')

PLANT = {
    'overlap_zh': """() => { const zh = document.querySelector('.zh'), en = document.querySelector('.en');
      const r = el => { const g = document.createRange(); g.selectNodeContents(el); return [...g.getClientRects()].filter(x => x.width); };
      const eb = Math.max(...r(en).map(x => x.bottom)), z = r(zh), zt = Math.min(...z.map(x => x.top)), lh = z[0].bottom - z[0].top;
      zh.style.marginTop = (parseFloat(getComputedStyle(zh).marginTop) - (zt - eb) - 0.25 * lh) + 'px'; return true; }""",
    'overlap_vocab': """() => { const vs = [...document.querySelectorAll('#list > .v')]; if (vs.length < 2) return false;
      const a = vs[0].getBoundingClientRect(), b = vs[1].getBoundingClientRect(), lh = parseFloat(getComputedStyle(vs[1]).lineHeight);
      vs[1].style.marginTop = (-(b.top - a.bottom) - 0.25 * lh) + 'px'; return true; }""",
    'split_size': """() => { const r = document.documentElement.style, vs = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--vs'));
      r.setProperty('--vs', (vs - 3) + 'px'); return true; }""",
    # 括注：改成行内、在指定的字前面强行换行
    'note': """(at) => { for (const x of document.querySelectorAll('x-n')) { const t = x.textContent, k = t.indexOf(at); if (k < 0) continue;
        x.style.display = 'inline'; const w = document.createTreeWalker(x, NodeFilter.SHOW_TEXT); let n, p = 0;
        while ((n = w.nextNode())) { if (p + n.data.length > k) { const s = n.splitText(k - p); s.parentNode.insertBefore(document.createElement('br'), s); return true; } p += n.data.length; } }
      return false; }""",
    'phrase': """() => { for (const e of document.querySelectorAll('.en .ph')) { const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT); let n;
        while ((n = w.nextNode())) { const k = n.data.indexOf(' '); if (k > 0 && k < n.data.length - 1) { e.style.whiteSpace = 'normal';
          const s = n.splitText(k + 1); s.parentNode.insertBefore(document.createElement('br'), s); return e.textContent; } } }
      return false; }""",
    'zhword': """() => { for (const b of document.querySelectorAll('.zh nobr')) { const t = b.textContent;
        if (t.length >= 2 && /^[一-鿿]{2}/.test(t)) { const n = b.firstChild; if (!n || n.nodeType !== 3) continue;
          const s = n.splitText(1); b.insertBefore(document.createElement('br'), s); return t; } }
      return false; }""",
}


def main():
    argv = sys.argv[1:]
    looks = list(M.LOOKS)
    if '--styles' in argv:
        j = argv.index('--styles')
        looks, argv = argv[j + 1].split(','), argv[:j] + argv[j + 2:]
    pid = argv[0] if argv else 't03'
    p = next(x for x in json.loads((M.C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages'] if x['id'] == pid)
    from playwright.sync_api import sync_playwright
    fails, n = [], 0
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': M.W, 'height': M.H}, device_scale_factor=2)
        f = Path(td) / 'x.html'

        def probs():
            return [x for x in LC.problems(pg, M.MIN_FS, M.MIN_VS, poss=True, names=M.NAMES, fonts=False, gaps=True, breaks=True) if x.startswith(KEYS)]

        def reload(r):
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            pg.wait_for_timeout(150)
            pg.evaluate(M.FIT, list(r[:2]))

        for look in looks:
            M.set_style(look)
            done, first = set(), None
            for i, label, fit, r in M.layout(pg, p, f):
                if not fit:
                    continue
                todo = []
                if pg.evaluate("() => [...document.querySelectorAll('x-n')].some(x => x.textContent.includes('同 gunwale'))"):
                    todo.append(('note', '括注拆开', 'gunwale'))
                if pg.evaluate("() => [...document.querySelectorAll('x-n')].some(x => x.textContent.includes('顺着……一路'))"):
                    todo.append(('note', '括注断开', '一路'))
                if label.endswith('第 1 屏'):
                    first = LC.sizes(pg)
                if label.endswith('第 2 屏') and 'split_size' not in done:
                    todo.append(('split_size', '分屏字号', None))
                for t in ('overlap_zh', 'overlap_vocab', 'phrase', 'zhword'):
                    if t not in done:
                        todo.append((t, '文字重叠' if t.startswith('overlap') else '短语断开' if t == 'phrase' else '译文断词', None))
                if not todo:
                    continue
                clean = probs() + (LC.size_diff(first, LC.sizes(pg)) if label.endswith('第 2 屏') else [])
                if clean:
                    fails.append(f'{look} {label} 没埋雷就报：{clean}')
                for t, want, arg in todo:
                    if t in done or (t == 'note' and want in done):
                        continue
                    reload(r)
                    planted = pg.evaluate(PLANT[t], arg) if arg else pg.evaluate(PLANT[t])
                    if not planted:
                        continue
                    got = LC.size_diff(first, LC.sizes(pg)) if t == 'split_size' else probs()
                    n += 1
                    ok = any(x.startswith(want) for x in got)
                    print(f'  {look} {label} 埋 {t}{"（" + arg + "）" if arg else ""} → {"查出" if ok else "漏查"}：{[x for x in got if x.startswith(want)][:1] or got[:2]}', flush=True)
                    if not ok:
                        fails.append(f'{look} {label} {t} 漏查')
                    done.add(want if t == 'note' else t)
            missing = {'overlap_zh', 'overlap_vocab', 'phrase', 'zhword', 'split_size', '括注拆开', '括注断开'} - done
            if missing:
                fails.append(f'{look} 没埋上：{sorted(missing)}')
        br.close()
    print(f'埋雷 {n} 处，' + ('全部查出、没埋雷的屏 0 误报' if not fails else '不合格：\n  ' + '\n  '.join(fails)))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
