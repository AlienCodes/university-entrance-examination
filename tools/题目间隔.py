"""视频标准规格（铁律 19，用户 2026-10-25）：同一屏上有多道题（选项一览、答案表等），每题之间必须有空隙，并用一条浅灰细线分开。

所有画题目的引擎都这样用：
  · 每一道题（连同它的选项 / 答案）包在 class="qg" 的元素里；
  · 截图时在页面上跑 QGAP_JS（page.evaluate(QGAP_JS, MIN_GAP)），返回的问题列表非空就停。
检查内容（只看上下相邻的两题，左右两栏各算各的）：
  · 两题文字之间的空隙 ≥ MIN_GAP（按 1920×1080 的 CSS 像素量）；
  · 中间有一条实线：粗 ≤ 2.5 像素、灰色（R、G、B 相差 ≤ 6）、浅（平均亮度 150—235，不是黑线，也不能浅到看不出）；
  · 页面上有两个以上纯编号标签（“1.”“(3)”）不在任何 .qg 里 → 报“题目没有分组”，防止新引擎忘了标。
双向验证：python3 tools/题目间隔.py --自检（正常 0 处；去掉空隙、去掉线、黑粗线、没分组都必须报出）。
"""
import sys
from pathlib import Path

MIN_GAP = 20

QGAP_JS = r"""(minGap) => {
 const bad = [];
 const box = e => {      // 只量文字本身（文本节点），不量元素框——flex / grid 里的子元素框会撑满整行，量出来空隙几乎为 0
   const rs = [], w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
   for (let n = w.nextNode(); n; n = w.nextNode()) { if (!n.textContent.trim()) continue;
     const r = document.createRange(); r.selectNodeContents(n); rs.push(...[...r.getClientRects()].filter(x => x.width > 0 && x.height > 0)); }
   if (!rs.length) return null;
   return {top: Math.min(...rs.map(x => x.top)), bottom: Math.max(...rs.map(x => x.bottom))}; };
 const G = [...document.querySelectorAll('.qg')].map(g => [g, box(g), g.getBoundingClientRect()]);
 for (const [g, t, b] of G) {
   if (!t) continue;
   let nx = null;
   for (const h of G) {
     const [e, u, c] = h;
     if (e === g || !u) continue;
     if (c.left < b.right - 1 && c.right > b.left + 1 && c.top >= b.bottom - 1 && (!nx || c.top < nx[2].top)) nx = h;
   }
   if (!nx) continue;
   const name = g.textContent.trim().slice(0, 24);
   const gap = nx[1].top - t.bottom;
   if (gap < minGap) bad.push('题间空隙 ' + gap.toFixed(0) + 'px < ' + minGap + '：' + name);
   let s = getComputedStyle(g), w = parseFloat(s.borderBottomWidth), col = s.borderBottomColor, st = s.borderBottomStyle;
   if (!(w > 0 && st !== 'none')) { s = getComputedStyle(nx[0]); w = parseFloat(s.borderTopWidth); col = s.borderTopColor; st = s.borderTopStyle; }
   if (!(w > 0 && st !== 'none')) { bad.push('题间没有分隔线：' + name); continue; }
   const [r, gg, bb] = col.match(/[\d.]+/g).map(Number), lum = (r + gg + bb) / 3;
   if (st !== 'solid') bad.push('分隔线不是实线（' + st + '）：' + name);
   if (w > 2.5) bad.push('分隔线太粗 ' + w + 'px：' + name);
   if (Math.max(r, gg, bb) - Math.min(r, gg, bb) > 6) bad.push('分隔线不是灰色（' + col + '）：' + name);
   if (lum < 150) bad.push('分隔线太深（' + col + '），要浅灰：' + name);
   if (lum > 235) bad.push('分隔线太浅看不出（' + col + '）：' + name);
 }
 const labels = [...document.querySelectorAll('body *')].filter(e => e.children.length === 0 && /^\(?\d{1,2}[.)]$/.test(e.textContent.trim()) && !e.closest('.qg'));
 if (labels.length >= 2) bad.push('题目没有分组（' + labels.length + ' 个编号不在 .qg 里，如 ' + labels[0].textContent.trim() + '）');
 return bad;
}"""


def selftest():
    from playwright.sync_api import sync_playwright
    css = ("body{margin:40px;font:40px serif;width:1840px}.r{display:grid;grid-template-columns:70px 1fr 1fr;line-height:54px}"
           ".qg{padding:13px 0 14px;border-bottom:1.5px solid #c8c8c8}.qg:last-child{border-bottom:none}")
    rows = ''.join(f'<div class="qg"><div class="r"><span>{i}.</span><span>A. one</span><span>B. two</span></div>'
                   f'<div class="r"><span></span><span>C. three</span><span>D. four</span></div></div>' for i in range(1, 6))
    cases = [('正常（空隙 + 浅灰细线）', css, rows, False),
             ('去掉空隙', css.replace('padding:13px 0 14px', 'padding:0'), rows, True),
             ('去掉分隔线', css.replace('border-bottom:1.5px solid #c8c8c8', 'border-bottom:none'), rows, True),
             ('黑色粗线', css.replace('1.5px solid #c8c8c8', '4px solid #000'), rows, True),
             ('没分组（旧的选项一览）', css, rows.replace('<div class="qg">', '<div>'), True)]
    ok = True
    with sync_playwright() as pw:
        exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': 1920, 'height': 1080})
        for name, c, body, want in cases:
            pg.set_content(f'<style>{c}</style>{body}')
            got = pg.evaluate(QGAP_JS, MIN_GAP)
            print(('✅' if bool(got) == want else '❌'), name, '→', got[:2] or '0 处')
            ok &= bool(got) == want
        br.close()
    sys.exit(0 if ok else 1)


if __name__ == '__main__' and '--自检' in sys.argv:
    selftest()
