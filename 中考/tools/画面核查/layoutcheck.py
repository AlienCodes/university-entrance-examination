"""排版机械检查（不花 token，生成视频之前跑）：用生成视频的同一程序排出每一屏，逐字量出位置，检查第 1 批画面核查（排版审阅员）报出的各类排版毛病：

  行首缩进   中文译文、词汇栏释义的每一行，第一个字必须顶格（行首的左括号、左引号要去掉左半空白）
  标点挤压   相邻两个全角标点（如“：“”“）；”“”。”）之间不能空出半个字以上
  孤字       中文译文最后一行只剩一个字；词汇栏释义折行后的一行只有一个字（z35 截图审阅：“用心 / （做）”“节日；（文化） / 节”）
  数字单位   英文的数字与后面的单位不能拆到两行（z25 截图审阅：“only about 6 / kg”）
  释义断词   词汇栏释义只能在标点处、或在词条与释义之间换行，不能把“可/能”“泳/衣”拆开
  连字符     带连字符的英文词（southward-moving、wind-driven）不能在连字符处断行
  直引号     英文和词条里不能有直撇号、直引号（踩坑 18）
  留白       词汇栏内容必须在卡片内边距以内；句子区不能溢出；字号不低于下限
  标题       片头标题必须在卡片内一行放下
  人名断开   中文人名的间隔号“·”前后不能断行（专八旧版画面核查：理查德·帕克 在 · 处断行）；专八另查登记的整名（专八/tools/人名.json）
             不能拆到两行（t03 审阅：“理查 / 德·帕克”断在名字中间，只查间隔号两边漏掉了）
  词条间距   词汇栏同一行上词条、词性、释义的文字之间至少隔词汇栏字号的 0.15 倍（专八共用背景 2 的“backn.”）。只对专八开
  省略号     词条里不能出现三个点“...”，要显示成“…”（专八 t03 审阅：pull...through）。只对专八开
  字体回退   画面上每一段文字都只能用网页字体（设计字体）画，不许落到系统字体（t03 审阅：英文里的中文注释“(防水布)”落到了系统黑体
             WenQuanYi Zen Hei）：用 Chrome 开发者协议 CSS.getPlatformFontsForNode 问浏览器每个元素实际用了哪些字体，非网页字体就报。只对专八开
  续接号     分屏的续接号“…”不能落到英文行首（专八旧版画面核查）
  徽章撇号   编号不能把高亮词和后面的所有格撇号隔开（专八旧版画面核查：drivers⑫’）。只对专八开（--project 专八、专八 make_video.py）：
             中考程序还没有这项修正，打开后中考已发布的 z04、z09、z10、z28 共 5 屏会报出（2026-10-16 实测），中考下次重做时移植 x-ps 再打开

    /opt/ttsenv/bin/python 中考/tools/画面核查/layoutcheck.py z01 z02 …     （不写篇目 = 全部）
    /opt/ttsenv/bin/python 中考/tools/画面核查/layoutcheck.py --project 专八 [--style 1] t03 …     （专八；默认 中考；--style 选画面 C、1–6，默认 C）
    /opt/ttsenv/bin/python 中考/tools/画面核查/layoutcheck.py --module <旧版 make_video.py> z01 …   （用旧版程序排版，检验本检查能查出旧版的毛病）
有问题退出码非 0。
半宽字形：专八译文字体霞鹜文楷的弯引号“”‘’是半宽（0.44/0.33 字），没有半字空白可去；行首缩进、过度挤压只对全角字形（宽 > 0.75 字）按半字计。
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]

CHECK = r"""([minFs, minVs, poss, names, gaps]) => { names = names || [];
  const ZC='，。、：；！？）”’】」》', ZO='（“‘【「《', PUN=ZC+ZO+'…—·', out=[];
  const cjk = c => /[一-鿿]/.test(c);
  const chars = el => { const res=[], w=document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n;
    while ((n=w.nextNode())) for (let i=0;i<n.data.length;i++) { if (/\s/.test(n.data[i])) continue;
      const rg=document.createRange(); rg.setStart(n,i); rg.setEnd(n,i+1); const rs=rg.getClientRects(); if (!rs.length) continue;
      const r=rs[rs.length-1]; res.push({c:n.data[i], l:r.left, r:r.right, t:r.top, el:n.parentElement, n, i}); }
    return res; };
  const lines = cs => { const L=[]; for (const x of cs) { const p=L.length && L[L.length-1][L[L.length-1].length-1];
      if (!p || x.l < p.l - 2) L.push([x]); else L[L.length-1].push(x); } return L; };
  const leftOf = k => k.getBoundingClientRect().left + k.clientLeft + parseFloat(getComputedStyle(k).paddingLeft);
  const em = el => parseFloat(getComputedStyle(el).fontSize);
  const txt = L => L.map(x => x.c).join('');
  const block = (k, name, isGloss) => {
    const L = lines(chars(k)), x0 = leftOf(k), sd = document.getElementById('side'), sr = sd.getBoundingClientRect();
    const x1 = isGloss ? sr.left + sd.clientLeft + sd.clientWidth - parseFloat(getComputedStyle(sd).paddingRight)    // 词条撑宽格子时格子本身也变宽，按词汇栏卡片的内边界量
                       : x0 + k.clientWidth - parseFloat(getComputedStyle(k).paddingLeft) - parseFloat(getComputedStyle(k).paddingRight);
    for (const x of L.flat()) { const xr = x.el.classList.contains('pr') ? x.r - em(x.el) / 2 : x.r;      // 挤压过的标点（.pr，右半空白被去掉）只占左半个字
      if (xr > x1 + 1) { out.push(`横向溢出：${name}「${x.c}」超出右边界 ${Math.round(xr - x1)} 像素`); break; } }   // z09 词条伸进右边留白
    if (name === '英文' && poss) L.flat().forEach((x, j, A) => { const s = x.el.closest('sup'), y = A[j + 1];      // 专八旧版 drivers⑫’：所有格（’s，或 -s 词后的 ’ 且本句没有左单引号）不能被编号隔开
      if (!s || !y || y.el.closest('sup') || y.c !== '’') return;
      const after = y.n.data.slice(y.i), word = s.parentElement.textContent.slice(0, -s.textContent.length);
      if (/^’s(?![A-Za-z])/.test(after) || (/^’(?![A-Za-z])/.test(after) && /s$/.test(word) && !k.textContent.includes('‘')))
        out.push(`徽章撇号：${name}「${word.slice(-12)}」的编号 ${s.textContent} 把词和后面的所有格撇号隔开`); });
    if (name === '英文') L.flat().forEach((x, j, A) => { const s = x.el.closest('sup'), y = A[j + 1];             // z06 编号徽章贴着破折号
      if (s && y && !y.el.closest('sup') && '—–'.includes(y.c) && Math.abs(y.t - x.t) < 40 && y.l - s.getBoundingClientRect().right < 4)
        out.push(`徽章贴破折号：${name}徽章 ${s.textContent} 与「${y.c}」只隔 ${(y.l - s.getBoundingClientRect().right).toFixed(1)} 像素`); });
    // 大写 I 只查圆体 Nunito、Baloo 2（思源黑体的 I 比 l 矮，分得清）
    // 加了衬线的大写 I：颜色、字体、粗细必须与所在的词一致（第三次画面核查：词条里的 I 被 .v span 样式套成灰色细体），短横不能碰相邻字母和徽章（“AI”粘连）
    L.forEach(ln => ln.forEach((x, j) => { const e = x.el.closest('x-i'); if (!e) return;
      const a = getComputedStyle(e), b = getComputedStyle(e.parentElement), bar = parseFloat(getComputedStyle(e, '::after').width), r = e.getBoundingClientRect(), c = (r.left + r.right) / 2;
      if (a.color !== b.color || a.fontFamily !== b.fontFamily || a.fontWeight !== b.fontWeight || a.fontSize !== b.fontSize)
        out.push(`衬线I：${name}「${txt(ln).slice(Math.max(0, j - 4), j + 5)}」的 I 与所在的词样式不同（${a.color} ${a.fontWeight} / ${b.color} ${b.fontWeight}）`);
      const p = ln[j - 1], n = ln[j + 1], nr = n && (n.el.closest('sup') || n.el).getBoundingClientRect();
      if ((p && c - bar / 2 < p.r + 1) || (n && c + bar / 2 > (n.el.closest('sup') ? nr.left : n.l) - 1))
        out.push(`衬线I：${name}「${txt(ln).slice(Math.max(0, j - 4), j + 5)}」的 I 短横碰到相邻的字`); }));
    for (const x of L.flat()) if (x.c === 'I' && !x.el.closest('x-i') && /^(Nunito|"?Baloo 2)/.test(getComputedStyle(x.el).fontFamily)) { out.push(`大写I：${name}的大写 I 没有衬线（与小写 l 分不清）`); break; }   // Baloo 2（专八共用背景 3、4）的 I 只比 l 矮 5%
    L.forEach((ln, i) => {
      const f = ln[0];
      const want = ZO.includes(f.c) && name !== '英文' && f.r - f.l > em(f.el) * 0.75 ? x0 - em(f.el) / 2 : x0;     // 英文的弯引号是西文字形、霞鹜文楷的弯引号是半宽，不按全角半字计
      if (name === '英文' && '—–'.includes(f.c)) out.push(`行首破折号：英文第 ${i + 1} 行「${txt(ln).slice(0, 12)}」以破折号开头`);   // z19 “comes in¹ / —giving”
      if (name === '英文' && i > 0 && f.c === '…') out.push(`续接号：英文第 ${i + 1} 行以续接号「…」开头`);
      if (name !== '英文' && i > 0 && (f.c === '·' || L[i - 1][L[i - 1].length - 1].c === '·'))
        out.push(`人名断开：${name}「${txt(L[i - 1]).slice(-6)}／${txt(ln).slice(0, 6)}」在间隔号处断行`);
      if (name !== '英文' && i > 0) { const s = txt(L[i - 1]) + txt(ln), cut = txt(L[i - 1]).length;      // 登记的整名跨两行（理查 / 德·帕克）
        for (const nm of names) for (let j = s.indexOf(nm); j >= 0; j = s.indexOf(nm, j + 1))
          if (j < cut && j + nm.length > cut) out.push(`人名断开：${name}「${nm}」被拆到两行（${s.slice(j, cut)}／${s.slice(cut, j + nm.length)}）`); }
      if (name === '译文' && i > 0) { const a = L[i - 1][L[i - 1].length - 1], an = /[A-Za-z0-9]/, h = cjk;            // z14 “所说的Z / 世代。”
        if ((an.test(a.c) && h(f.c)) || (h(a.c) && an.test(f.c))) out.push(`中英断开：译文「${txt(L[i - 1]).slice(-6)}／${txt(ln).slice(0, 6)}」英文与紧挨的汉字分在两行`); }
      if (!(isGloss && i === 0) && Math.abs(f.l - want) > 2) out.push(`行首缩进：${name}第 ${i + 1} 行「${txt(ln).slice(0, 12)}」偏 ${Math.round(f.l - want)} 像素`);
      if (i > 0) { const a = L[i - 1][L[i - 1].length - 1];
        const g = f.el.closest('span[lang]');
        if (isGloss && a.el.closest('span[lang]') && g && !PUN.includes(a.c) && !ZO.includes(f.c))      // 交给 Python 判断是否落在分词边界
          { let k = 0; const w = document.createTreeWalker(g, NodeFilter.SHOW_TEXT); let n;      // 在含空格的原文里的位置
            while ((n = w.nextNode()) && n !== f.n) k += n.data.length;
            out.push(['GLOSS', name, g.textContent, k + f.i]); }
        if (a.c === '-' && /[A-Za-z]/.test(f.c)) out.push(`连字符：${name}「${txt(L[i - 1]).slice(-12)}／${txt(ln).slice(0, 8)}」`); }
      for (let j = 1; j < ln.length; j++) { const a = ln[j - 1], b = ln[j];
        if (ZC.includes(a.c) && (ZC + ZO).includes(b.c) && b.l - a.l > em(a.el) * 0.75)
          out.push(`标点挤压：${name}「${a.c}${b.c}」间距 ${(((b.l - a.l) / em(a.el))).toFixed(2)} 字`);
        // 过度挤压（样片 z10 画面核查：行中的“花（时间）”左括号被去掉了半字空白）：只有相邻两个标点、或行首的左标点才可以挤
        if (name !== '英文' && ZO.includes(b.c) && !(ZC + ZO).includes(a.c) && b.l < a.r - 2 && !(isGloss && !a.el.closest('span[lang]')))   // 释义开头紧跟词条、词性的左括号，按设计去半字
          out.push(`过度挤压：${name}「${a.c}${b.c}」左括号或左引号在行中被去掉了半字空白`);
        if (name !== '英文' && ZC.includes(a.c) && a.r - a.l > em(a.el) * 0.75 && !(ZC + ZO).includes(b.c) && cjk(b.c) && b.l - a.l < em(a.el) * 0.95)
          out.push(`过度挤压：${name}「${a.c}${b.c}」标点后面被去掉了半字空白`); }
    });
    if (name === '译文' && L.length > 1) { const last = L[L.length - 1].filter(x => cjk(x.c));
      if (last.length <= 1) out.push(`孤字：${name}最后一行只有「${txt(L[L.length - 1])}」`); }
    if (isGloss) for (let j = 1; j < L.length; j++) { const g = x => x.el.closest('.g');
      if (L[j].every(g) && L[j - 1].some(g) && L[j].filter(x => cjk(x.c) || /[A-Za-z0-9]/.test(x.c)).length <= 1)
        out.push(`孤字：${name}释义折行后一行只有「${txt(L[j])}」`); }
    if (name === '英文') for (let j = 1; j < L.length; j++)
      if (/\d$/.test(txt(L[j - 1].filter(x => !x.el.closest('sup')))) && /^(kg|g|mg|km|m|cm|mm|ml|mph|°C|°F|percent|kilo(gram|metre|meter)s?|(centi|milli)?(metre|meter)s?|grams?|tonnes?|tons?|miles?|feet|foot|inch(es)?|degrees?|hours?|minutes?|seconds?|days?|weeks?|months?|years?)(?![A-Za-z])/.test(txt(L[j])))
        out.push(`数字单位：英文「${txt(L[j - 1]).slice(-8)} / ${txt(L[j]).slice(0, 8)}」数字与单位被拆到两行`);
  };
  const ttl = document.querySelector('.ttl h1');
  if (ttl) { const g = document.createRange(); g.selectNodeContents(ttl); const a = g.getBoundingClientRect(), b = ttl.getBoundingClientRect(),
      card = document.querySelector('.ttl'), c = card.getBoundingClientRect(), cs = getComputedStyle(card), rows = new Set([...g.getClientRects()].filter(r => r.width).map(r => Math.round(r.top)));
    const L = c.left + card.clientLeft + parseFloat(cs.paddingLeft), R = c.left + card.clientLeft + card.clientWidth - parseFloat(cs.paddingRight);
    // 量标题文字本身（专八共用背景 3 的粉笔下划线是 h1 的绝对定位伪元素，向右多出 0.25 字，撑大了 scrollWidth，文字其实放得下）
    if (a.right > b.right + 1 || a.left < b.left - 1 || a.left < L - 1 || a.right > R + 1 || rows.size > 1)
      out.push(`标题：一行放不下（文字 ${Math.round(a.left)}–${Math.round(a.right)}，标题框 ${Math.round(b.left)}–${Math.round(b.right)}，卡片 ${Math.round(L)}–${Math.round(R)}，${rows.size} 行）`);
    return out; }
  const en = document.querySelector('.en'), zh = document.querySelector('.zh');
  block(en, '英文', false); block(zh, '译文', false);
  document.querySelectorAll('.v > div').forEach((d, i) => { block(d, `词条 ${i + 1} `, true);
    const b = d.querySelector('b'), rs = b.getClientRects(), g = d.querySelector('span[lang]'), last = rs[rs.length - 1];   // z03 词条折行后释义紧接在词条尾巴后面
    if (rs.length > 1) for (const e of [d.querySelector('i'), g].filter(Boolean)) { const r = e.getClientRects()[0];
      if (r && r.top < last.top + 2) { out.push(`词条折行：词条 ${i + 1} 「${b.textContent}」折行后，${e === g ? '释义' : '词性'}没有另起一行`); break; } } });
  for (const el of [en, ...document.querySelectorAll('.v b')]) if (/['"]/.test(el.textContent)) out.push(`直引号：「${el.textContent.slice(0, 30)}」`);
  // 词条间距（专八共用背景 2：样式里的 .v b{margin:0 -.08em} 把词条与词性之间的间距吃掉，成了“backn.”）：同一行上词条、词性、释义的文字之间至少隔词汇栏字号的 0.15 倍
  if (gaps) for (const el of document.querySelectorAll('.v b')) if (el.textContent.includes('...'))      // 专八 t03 审阅：分开的短语词条 pull...through 用了三个点
    out.push(`省略号：词条「${el.textContent.slice(0, 30)}」用了三个点，应显示为“…”`);
  if (gaps) { const vs0 = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--vs'));
    const end = (el, last) => { const cs = chars(el).filter(x => x.c.trim()); return cs.length ? cs[last ? cs.length - 1 : 0] : null; };
    const box = x => { const g = document.createRange(); g.setStart(x.n, x.i); g.setEnd(x.n, x.i + 1); const rs = g.getClientRects(); return rs[rs.length - 1]; };
    document.querySelectorAll('.v > div').forEach((d, i) => { const els = [d.querySelector('b'), d.querySelector('i'), d.querySelector('span[lang]')].filter(Boolean);
      for (let j = 1; j < els.length; j++) { const p = end(els[j - 1], true), q = end(els[j], false); if (!p || !q) continue;
        const a = box(p), b = box(q), same = Math.abs((a.top + a.bottom) / 2 - (b.top + b.bottom) / 2) < 0.4 * Math.max(a.height, b.height);
        const gap = b.left + (ZO.includes(q.c) ? em(q.el) / 2 : 0) - a.right;      // 释义开头的左括号按设计去掉了左半字空白（墨迹在右半），从墨迹量
        if (same && gap < vs0 * 0.15)
          out.push(`词条间距：词条 ${i + 1}「${els[j - 1].textContent.slice(-10)}」与「${els[j].textContent.slice(0, 6)}」只隔 ${gap.toFixed(1)} 像素`); } }); }
  // 徽章贴字（z16 cricket¹、breakfast² 等：f、t、r 的笔画伸出字身碰到徽章）：前一个字母的笔画右边缘到徽章至少 1.2 像素（审阅员认可 1.2 像素以上的间距）
  // 按词尾整个词量（专八 EB Garamond 的 ff 是连字，连字里第二个 f 的位置浏览器按平分估算，单按最后一个字母量会多算 1.7 像素，off、staff 误报只隔 0.1 像素）：
  // 墨迹右边缘 = 这个词的排版右边缘 − 字间距 − 这个词（含连字、字偶距）的右侧空白；没有连字时与只量最后一个字母完全相同
  const cv = document.createElement('canvas').getContext('2d');
  for (const s of en.querySelectorAll('sup')) { let n = s.previousSibling; while (n && n.nodeType === 1) n = n.lastChild || n.previousSibling;
    if (!n || !n.data || !n.data.trim()) continue; const i = n.data.trimEnd().length - 1; let i0 = i; while (i0 > 0 && /[A-Za-z]/.test(n.data[i0 - 1]) && /[A-Za-z]/.test(n.data[i])) i0--;
    const rg = document.createRange(); rg.setStart(n, i0); rg.setEnd(n, i + 1);
    const rr = rg.getClientRects(); if (!rr.length) continue; const cs = getComputedStyle(n.parentElement), px = parseFloat(cs.fontSize);
    cv.font = `${cs.fontWeight} 100px ${cs.fontFamily}`; const mw = cv.measureText(n.data.slice(i0, i + 1)), ls = parseFloat(cs.letterSpacing) || 0;
    const ink = rr[rr.length - 1].right - ls - (mw.width - mw.actualBoundingBoxRight) / 100 * px;
    const gap = s.getBoundingClientRect().left - ink;
    if (gap < 1.2) out.push(`徽章贴字：英文「${n.data.slice(Math.max(0, i - 8), i + 1)}」与徽章 ${s.textContent} 只隔 ${gap.toFixed(1)} 像素`); }
  const main = document.querySelector('.main'), box = document.getElementById('box'), side = document.getElementById('side'), list = document.getElementById('list');
  if (box.scrollHeight > main.clientHeight) out.push('留白：句子区溢出');
  const s = side.getBoundingClientRect(), c = getComputedStyle(side), l = list.getBoundingClientRect(), top = s.top + side.clientTop;
  if (l.top < top + parseFloat(c.paddingTop) - 0.5 || l.bottom > top + side.clientHeight - parseFloat(c.paddingBottom) + 0.5)
    out.push(`留白：词汇栏内容挤进内边距（上 ${Math.round(l.top - top)}，下 ${Math.round(top + side.clientHeight - l.bottom)} 像素）`);
  const fs = parseFloat(getComputedStyle(en).fontSize), vs = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--vs'));
  if (fs < minFs || vs < minVs) out.push(`字号过小：英文 ${fs}px、词汇栏 ${vs}px`);
  return out;
}"""


def ok_break(g, k):
    if g[k - 1:k].isspace() or g[k:k + 1].isspace():          # 释义里的英文（as A as it is）在空格处换行，正常
        return True
    import logging
    import jieba
    jieba.setLogLevel(logging.WARNING)
    zc, zo = '，。、：；！？）”’】」》', '（“‘【「《'
    cuts = [0] + [i for i in range(1, len(g)) if (g[i - 1] in zc and g[i] not in zc) or (g[i] in zo and g[i - 1] not in zo)] + [len(g)]
    ch = [[a, b] for a, b in zip(cuts, cuts[1:]) if b > a]
    solo = lambda j: sum(c.isalnum() for c in g[ch[j][0]:ch[j][1]]) <= 1
    while True:                                            # 与 make_video.gloss_chunks 相同：单字块并到前一块；并完超过 9 个字且后面还有块时并到后一块；第一块单字并到后一块（不超过 9 个字时）
        j = next((j for j in range(len(ch)) if solo(j) and (j or len(ch) > 1 and ch[1][1] - ch[0][0] <= 9)), None)
        if j is None:
            break
        if j == 0 or ch[j][1] - ch[j - 1][0] > 9 and j + 1 < len(ch) and ch[j + 1][1] - ch[j][0] <= 9:
            ch[j:j + 2] = [[ch[j][0], ch[j + 1][1]]]
        else:
            ch[j - 1:j + 1] = [[ch[j - 1][0], ch[j][1]]]
    seg = [(a, b) for a, b in ch if a < k < b]
    if not seg:
        print('  [调试] 断点不在任何块内部：', g, k, flush=True)
        return False
    a, b = seg[0]
    if b - a <= 9:                                         # 与 make_video.GLOSS_CHUNK 相同
        return False
    pos, i = set(), a
    for w in jieba.cut(g[a:b]):
        i += len(w)
        pos.add(i)
    return k in pos


def font_fallback(pg):
    """字体回退：问浏览器（Chrome 开发者协议 CSS.getPlatformFontsForNode）页面上每个直接含文字的元素、每个带文字的伪元素实际用了哪些字体，
    只要有一个不是网页字体（isCustomFont 为假，即系统字体），就报出字体名和那段文字。"""
    cdp = pg.context.new_cdp_session(pg)
    try:
        cdp.send('DOM.enable')
        cdp.send('CSS.enable')
        doc = cdp.send('DOM.getDocument', {'depth': -1, 'pierce': True})
        bad, todo = {}, [doc['root']]
        while todo:
            n = todo.pop()
            kids = n.get('children', [])
            txt = ''.join(c.get('nodeValue', '') for c in kids if c['nodeType'] == 3).strip()
            for x in ([n] if n['nodeType'] == 1 and txt else []) + n.get('pseudoElements', []):
                try:
                    fs = cdp.send('CSS.getPlatformFontsForNode', {'nodeId': x['nodeId']})['fonts']
                except Exception:      # noqa: BLE001  没有排版框的节点（如 ::marker）
                    continue
                for ft in fs:
                    if not ft.get('isCustomFont'):
                        bad.setdefault(ft['familyName'], txt[:16] if x is n else f'::{x.get("pseudoType")}')
            todo += kids
    finally:
        cdp.detach()
    return [f'字体回退：「{t}」用了系统字体 {fam}（只能用网页字体）' for fam, t in bad.items()]


def problems(pg, min_fs, min_vs, poss=False, names=(), fonts=False, gaps=False):
    """当前页面（已排版）的排版问题列表；make_video.py 每屏截图前调用，有问题就不生成视频。
    poss：是否查“徽章撇号”；names：登记的中文整名（查是否被拆到两行）；fonts：是否查字体回退；gaps：是否查词条间距（这几项专八开，中考不变）。"""
    res = font_fallback(pg) if fonts else []
    for x in pg.evaluate(CHECK, [min_fs, min_vs, poss, list(names), gaps]):
        if isinstance(x, list):          # 释义在标点以外的地方断行：只有超过 9 个字的块、且断在分词边界上才合格（与 make_video.words 一致）
            _, name, g, k = x
            if not ok_break(g, k):
                res.append(f'释义断词：{name}「{g[max(0, k - 6):k]}／{g[k:k + 6]}」')
        else:
            res.append(x)
    return res


def screens(M, p):
    sents = [s for pa in p['paras'] for s in pa]
    out = [('片头', M.title_slide(p), False)]
    for k, s in enumerate(sents, 1):
        parts = M.split_parts(p['id'], k, s)
        for n, part in enumerate(parts, 1):
            out.append((f'第 {k} 句' + (f' 第 {n} 屏' if len(parts) > 1 else ''), M.sentence_slide(p, s, k, len(sents), part), True))
    return out


def laid_out(M, pg, p, f):
    """逐屏排版（与生成视频完全相同），每排好一屏 yield (标签, 是否句子屏, 字号)：程序有 layout（专八：分屏的句子各屏统一字号）就用它，
    否则逐屏 FIT（中考，不变）。字号 = (英文, 词汇栏) 或 None（片头）。"""
    if hasattr(M, 'layout'):
        for _, label, fit, r in M.layout(pg, p, f):
            yield label, fit, r and tuple(r[:2])
        return
    for label, h, fit in screens(M, p):
        f.write_text(h, 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        r = pg.evaluate(M.FIT) if fit else None
        yield label, fit, r and tuple(r[:2])


def project(argv):
    """--project 中考|专八（默认 中考）：layoutcheck、screens_fp、canary_layout、prep 由两个项目共用。返回 (项目名, 项目 tools 目录, 其余参数)。"""
    name = '中考'
    if '--project' in argv:
        j = argv.index('--project')
        name, argv = argv[j + 1], argv[:j] + argv[j + 2:]
    if name not in ('中考', '专八'):
        raise SystemExit(f'--project 只能是 中考 或 专八：{name}')
    return name, R / name / 'tools', argv


def main():
    proj, T, argv = project(sys.argv[1:])
    sys.path.insert(0, str(T))
    if '--module' in argv:
        j = argv.index('--module')
        spec = importlib.util.spec_from_file_location('make_video', argv[j + 1])
        M = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(M)
        argv = argv[:j] + argv[j + 2:]
    else:
        import make_video as M
    if '--style' in argv:                 # 专八：画面 C、1–6
        j = argv.index('--style')
        M.set_style(argv[j + 1])
        argv = argv[:j] + argv[j + 2:]
    elif hasattr(M, 'set_style'):
        M.set_style('C')
    NAMES = json.loads((T / '人名.json').read_text('utf-8'))['names'] if (T / '人名.json').exists() else []      # 专八登记的中文整名（中考没有）
    from playwright.sync_api import sync_playwright
    P = {p['id']: p for p in json.loads((R / proj / 'data' / 'vocab.json').read_text('utf-8'))['passages'] if p.get('done', True)}
    bad = {}
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': M.W, 'height': M.H}, device_scale_factor=2)      # 与 make_video.py 生成 4K 视频时相同：倍率不同，字宽有细微差别，换行可能不同
        f = Path(td) / 'x.html'
        for pid in (argv or sorted(P)):
            probs, size = [], {}
            for label, fit, r in laid_out(M, pg, P[pid], f):
                if ' 第 ' in label[2:]:          # 分屏的句子（“第 k 句 第 n 屏”）：各屏字号必须相同（专八 t03 审阅：s20 两屏词汇栏 40/35px）
                    size.setdefault(label.split(' 第 ')[0], []).append(r)
                probs += [f'{label}：{x}' for x in problems(pg, M.MIN_FS, M.MIN_VS, poss=proj == '专八', names=NAMES, fonts=proj == '专八', gaps=proj == '专八')]
            if proj == '专八':
                probs += [f'{k}：分屏字号不一致（各屏英文/词汇栏 {v}）' for k, v in size.items() if len(set(v)) > 1]
            bad[pid] = probs
            print(pid, 'OK' if not probs else f'{len(probs)} 处：\n  ' + '\n  '.join(probs), flush=True)
        br.close()
    n = sum(len(v) for v in bad.values())
    print('全部通过' if not n else f'共 {n} 处，涉及 {[k for k, v in bad.items() if v]}')
    sys.exit(1 if n else 0)


if __name__ == '__main__':
    main()
