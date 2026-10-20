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
  文字重叠   英文、译文、页眉、页脚、词汇栏标题、每个词条的文字框互不相交（专八 t03 第二轮审阅：埋雷“译文压住英文”只有人看出来）。两个项目都查
  括注拆开   释义里放得下一行的括注不能拆到两行（专八 t03 第二轮审阅：（同 / gunwale）、（风暴、/ 夜晚等））。只对专八开（breaks）
  括注断开   放不下一行的括注只能在中英交界、逗号顿号分号冒号之后、或长中文片段的词间断开（（down the length of 顺着…… / 一路））；
             括注里的英文片段放得下一行就不能拆开（（down the / length of 顺着……一路））。只对专八开
  短语断开   英文高亮短语放得下一行就不能拆到两行（rough / treatment、at the / expense of）。只对专八开
  译文断词   译文不能在一个词（jieba）的中间断行（蹦 / 跳、相 / 同、霎时 / 间）。只对专八开
             这四项在审阅前的专八程序（59b1562）上 t03 七种画面查出 26—47 处，修正后 0 处；埋雷测试：专八/tools/画面核查/埋雷_排版检查.py
  分屏字号   一句分成几屏时，各屏英文、译文、词汇栏、词条、释义的实测字号必须相同（sizes / size_diff；不看排版程序自己的返回值）
  六级黑板审阅（2026-10-17，6 批盲审的真问题；下面各项只对专八 / 六级开（breaks），在审阅前的引擎 专八/tools/make_video_审阅前.py 上能查出，修正后 0 处）：
  高亮丢失   英文的编号必须在高亮词里、高亮不能是空的（s39 嵌套的 <nobr> 被 HTML 解析器拆开，over-imitate 成了正文白色）
  所有格样式 所有格（不高亮）的颜色、粗细、字体与英文正文相同（样式 3 没有 --ink，corporations’ 的撇号是近黑色、几乎看不见）
  注释分离   英文里试卷的中文注释不能单独落到行首、与前一个词分开（s45 “toddlers / (学步儿童)”）
  英文短行   英文不是最后一行、却空出一半以上，而下一行的第一个词放得进来（s54 “We / don't have to look further than”，高亮短语整体换行）；
             短语断开的例外：整体换行会让上一行空出一半以上时可以在词间断开（与 make_video FIT 的 phr 同一条线）
  数字单位   加上 million / billion / trillion / thousand / hundred（s01 “$13 / billion”）
  行首禁则   译文、释义的一行不能以右半空白的标点（，。、；：！？）”’ 等）开头（s02 “（音乐、视频等） / ；流式传输”）
  中英断开   专八 / 六级只查英文、数字与后面的汉字分开（加 %：“100% / 可再生”）；汉字与后面的英文之间可以断行
  西文断开   译文里的一段英文（Stable Diffusion）不能在空格处拆到两行
  西文撇号   译文、释义里英文词中间的撇号必须是窄的西文撇号（思源黑体的“’”是全角：s57 “Hunt’ s在”）
  术语断开   译文里短的引号术语（不超过 6 个字、没有标点）、书名（不超过 10 个字）不能拆开（“能源 / 转型”、《思考，快与 / 慢》）
  分句单字   译文一个分句（，。、；：！？之间）的第一个或最后一个字不能单独落在另一行（“传达得 / 好，”）
  括注分离   释义里括注与紧挨着的词（中间没有标点）不能拆开——只要这个分句放得下一行（“前景；（成功的） / 希望”“使用 / （的机会）”）
  释义单字   释义在括号外断行时，分句开头或结尾的一个字不能单独落在另一行（“内化；使 / 成为……”“在 / 没有……的情况下”）
  译文断词、释义断词先加载 分词补充.txt（jieba 没有的词，如“占比”：s35 “占 / 比过高”）
  译文短行   译文不是最后一行、行末空着，而下一行开头第一个按断行规则可以断开的单位（zh_breaks：词、人名、术语、英文段、分句首尾、末两字、标点禁则）
             放得进这段空，却被推到了下一行——排版程序绑得比规则多（s05 “这种转移 / 自20世纪80年代以来从未停歇”空出 6.9 字、s13、s02 第 1 句）。
             收尾复查（2026-10-17）在全部 60 篇里又查出两处并已修正：s02 第 5 句（汉字与“‘”之间浏览器不断行，加 <wbr>）、s29 第 21 句（分句开头的右引号被绑进下一个字）
  英文短行（收紧）上一行的长度按徽章的框量、空格按实测宽（s49 第 21 句误报）；短语前面紧贴的左引号、左括号与短语一起算（s33 第 11 句 “survival of the fittest”）
  释义单字的例外：断在“一个字 | 长括注”交界、这个字连同括注一行放不下而括注本身放得下（s39 第 4 句：单字并进长括注排成一块，放不下一行时括注被拆开，“括注拆开”查出；引擎改为字与括注分两层 x-n，放不下时括注整体换行）
  双向验证：六级/tools/画面核查/审阅修正双向验证.py（审阅前的引擎上每类必须报出、现在 0；审阅后补的修正撤掉必须报出）
  徽章撇号   编号不能把高亮词和后面的所有格撇号隔开（专八旧版画面核查：drivers⑫’）。只对专八开（--project 专八、专八 make_video.py）：
             中考程序还没有这项修正，打开后中考已发布的 z04、z09、z10、z28 共 5 屏会报出（2026-10-16 实测），中考下次重做时移植 x-ps 再打开

    /opt/ttsenv/bin/python 中考/tools/画面核查/layoutcheck.py z01 z02 …     （不写篇目 = 全部）
    /opt/ttsenv/bin/python 中考/tools/画面核查/layoutcheck.py --project 专八 [--style 1] t03 …     （专八；默认 中考；--style 选画面 C、1–6，默认 C）
    /opt/ttsenv/bin/python 中考/tools/画面核查/layoutcheck.py --project 六级 [--style 3] s01 …     （六级：与专八同一个引擎，凡是“只对专八开”的检查六级同样开；默认画面 3 教室黑板）
    /opt/ttsenv/bin/python 中考/tools/画面核查/layoutcheck.py --module <旧版 make_video.py> z01 …   （用旧版程序排版，检验本检查能查出旧版的毛病）
有问题退出码非 0。
半宽字形：专八译文字体霞鹜文楷的弯引号“”‘’是半宽（0.44/0.33 字），没有半字空白可去；行首缩进、过度挤压只对全角字形（宽 > 0.75 字）按半字计。
"""
import importlib.util
import re
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]

CHECK = r"""([minFs, minVs, poss, names, gaps, breaks]) => { names = names || [];
  const ZC='，。、：；！？）”’】」》', ZO='（“‘【「《', PUN=ZC+ZO+'…—·', out=[];
  const cjk = c => /[一-鿿]/.test(c);
  const chars = el => { const res=[], w=document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n, sp = false;
    while ((n=w.nextNode())) for (let i=0;i<n.data.length;i++) { if (/\s/.test(n.data[i])) { if (/[ \t\n]/.test(n.data[i])) sp = true; continue; }
      const rg=document.createRange(); rg.setStart(n,i); rg.setEnd(n,i+1); const rs=rg.getClientRects(); if (!rs.length) continue;
      const r=rs[rs.length-1]; res.push({c:n.data[i], l:r.left, r:r.right, t:r.top, b:r.bottom, el:n.parentElement, n, i, sp}); sp = false; }
    return res; };      // sp：这个字前面有可以断行的空格（不算不换行空格）——“英文短行”按它找下一行的第一个词
  // 换行：下一个字在前一个字左边，或明显低于前一个字（字身高度的 0.6 以上：一行只有一个字时，下一行的第一个字并不在它左边，专八埋雷测试发现）
  const lines = cs => { const L=[]; for (const x of cs) { const p=L.length && L[L.length-1][L[L.length-1].length-1];
      if (!p || x.l < p.l - 2 || x.t > p.t + 0.6 * (p.b - p.t)) L.push([x]); else L[L.length-1].push(x); } return L; };
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
    if (name === '英文' && breaks) {      // 六级黑板审阅（专八 / 六级引擎）
      // 高亮丢失：s39 “over-imitate” 嵌套的 <nobr> 被 HTML 解析器拆开，高亮 span 空了、编号跑到 span 外面，生词成了正文白色
      for (const sp of k.querySelectorAll('sup')) { const h = sp.parentElement;
        if (!h.matches('.w, .ph')) out.push(`高亮丢失：英文编号 ${sp.textContent} 不在高亮词里（前面是「${(sp.previousSibling && sp.previousSibling.textContent || '').slice(-12)}」）`); }
      for (const h of k.querySelectorAll('.w, .ph')) { const t = [...h.childNodes].filter(c => !(c.nodeType === 1 && c.matches('sup, x-ps'))).map(c => c.textContent).join('');
        if (!/[A-Za-z0-9]/.test(t)) out.push(`高亮丢失：英文有一个空的高亮（${h.className}${h.querySelector('sup') ? ' 编号 ' + h.querySelector('sup').textContent : ''}）`); }
      // 所有格样式：所有格不高亮，颜色、粗细、字体与英文正文相同（s05 corporations’ 等在黑板上是近黑色，几乎看不见）
      const ec = getComputedStyle(k);
      for (const p of k.querySelectorAll('x-ps')) { const c = getComputedStyle(p);
        if (c.color !== ec.color || c.fontWeight !== ec.fontWeight || c.fontFamily !== ec.fontFamily)
          out.push(`所有格样式：「${p.parentElement.textContent.slice(0, 16)}」的所有格是 ${c.color} ${c.fontWeight}，英文正文是 ${ec.color} ${ec.fontWeight}`); }
      // 注释分离：试卷的中文注释“(学步儿童)”不能与它注释的前一个词分在两行（s45）
      L.forEach((ln, i) => { if (i && ln[0].c === '(' && ln[1] && cjk(ln[1].c)) out.push(`注释分离：英文第 ${i + 1} 行以中文注释「${txt(ln).slice(0, 8)}」开头，与前一个词分开`); });
      // 英文短行：不是最后一行、却空出一半以上，而下一行的第一个词放得进来（s54 “We / don't have to look further than”：高亮短语整体换行留下的空）
      const W = k.clientWidth, spw = (() => { const c = document.createElement('canvas').getContext('2d'), s = getComputedStyle(k); c.font = `${s.fontWeight} ${s.fontSize} ${s.fontFamily}`; return c.measureText(' ').width; })();
      L.forEach((ln, i) => { if (i === L.length - 1) return; const nx = L[i + 1]; let j = 1; while (j < nx.length && !nx[j].sp) j++;
        const rt = x => { const s = x.el.closest('sup'); return s ? s.getBoundingClientRect().right : x.r; };      // 编号按徽章的框量（含内边距）
        // 上一行的长度也按徽章的框量、空格按实测宽（s49 第 21 句“Doing a poor job¹”：按编号数字量少了 10 像素，communicating² 其实放不下，误报）
        const fill = rt(ln[ln.length - 1]) - x0, word = Math.max(...nx.slice(0, j).map(rt)) - nx[0].l;
        if (fill < 0.5 * W && fill + spw + word <= W - 2) out.push(`英文短行：英文第 ${i + 1} 行「${txt(ln).slice(0, 16)}」只占 ${Math.round(fill / W * 100)}%，下一行的「${txt(nx.slice(0, j))}」放得进来`); }); }
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
    if (breaks && name !== '英文') { const A = L.flat();      // 西文撇号：中文里英文词中间的撇号（Hunt’s）必须是窄的西文撇号（思源黑体的“’”是全角，s57 “Hunt’ s在”）
      A.forEach((x, j) => { if ('’\''.includes(x.c) && j && j + 1 < A.length && /[A-Za-z]/.test(A[j - 1].c) && /[A-Za-z]/.test(A[j + 1].c) && x.r - x.l > em(x.el) * 0.5)
        out.push(`西文撇号：${name}「${A.slice(Math.max(0, j - 5), j + 3).map(y => y.c).join('')}」的撇号是全角（宽 ${((x.r - x.l) / em(x.el)).toFixed(2)} 字）`); }); }
    for (const x of L.flat()) if (x.c === 'I' && !x.el.closest('x-i') && /^(Nunito|"?Baloo 2|"?Inter)/.test(getComputedStyle(x.el).fontFamily)) { out.push(`大写I：${name}的大写 I 没有衬线（与小写 l 分不清）`); break; }   // Baloo 2（专八共用背景 3、4）的 I 只比 l 矮 5%
    { const A = L.flat();      // 专八校园版第 2 批截图盲审（t04 “W hoa”、t06 “W hy”、t07 “W hen”）：Nunito 的 W+h 字距偏大，W 必须收紧（make_video.wh 的 x-w）
      for (let j = 0; j + 1 < A.length; j++) { const x = A[j]; if (x.c !== 'W' || A[j + 1].c !== 'h') continue; const cs = getComputedStyle(x.el);
        const ls = parseFloat(cs.letterSpacing); if (/^"?Nunito/.test(cs.fontFamily) && (isNaN(ls) ? 0 : ls) > -0.05 * em(x.el)) {
          out.push(`W与h间隙：${name}「${A.slice(j, j + 5).map(y => y.c).join('')}」的 W 与 h 之间空隙偏大（Nunito 的 W+h 字距没有收紧）`); break; } } }
    for (const x of L.flat()) if (x.c === '—' && !x.el.closest('x-dash') && /^"?ZH (Bold|Regular)/.test(getComputedStyle(x.el).fontFamily)) {   // 专八 t03 审阅：思源黑体的“—”是西文窄破折号，粗体汉字旁又细又偏下
      out.push(`中文破折号：${name}的「——」没有画成全角居中横线（x-dash）`); break; }
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
      if (name === '译文' && i > 0) { const a = L[i - 1][L[i - 1].length - 1], an = /[A-Za-z0-9%％]/, h = cjk;            // z14 “所说的Z / 世代。”
        // 专八 / 六级（breaks）：只查英文、数字与后面的汉字分开（Z / 世代、100% / 可再生）；汉字与后面的英文、数字之间可以断行（“自 / 20世纪”，六级黑板审阅：两边都绑会连成一长串、上一行空出一大段）
        if ((an.test(a.c) && h(f.c)) || (!breaks && h(a.c) && an.test(f.c))) out.push(`中英断开：译文「${txt(L[i - 1]).slice(-6)}／${txt(ln).slice(0, 6)}」英文与紧挨的汉字分在两行`);
        if (breaks && /[A-Za-z0-9]/.test(a.c) && /[A-Za-z0-9]/.test(f.c)) out.push(`西文断开：译文里的英文「${txt(L[i - 1]).slice(-8)}／${txt(ln).slice(0, 8)}」被拆到两行`); }   // Stable / Diffusion
      if (breaks && name !== '英文' && i > 0 && '，。、：；！？）”’】」》'.includes(f.c))      // 行首禁则（s02 “（音乐、视频等） / ；流式传输”）
        out.push(`行首禁则：${name}第 ${i + 1} 行以「${f.c}」开头`);
      if (!(isGloss && i === 0) && Math.abs(f.l - want) > 2) out.push(`行首缩进：${name}第 ${i + 1} 行「${txt(ln).slice(0, 12)}」偏 ${Math.round(f.l - want)} 像素`);
      if (i > 0) { const a = L[i - 1][L[i - 1].length - 1];
        const g = f.el.closest('span[lang]');
        if (isGloss && a.el.closest('span[lang]') && g && !PUN.includes(a.c) && !ZO.includes(f.c))      // 交给 Python 判断是否落在分词边界
          { let k = 0; const w = document.createTreeWalker(g, NodeFilter.SHOW_TEXT); let n;      // 在含空格的原文里的位置
            while ((n = w.nextNode()) && n !== f.n) k += n.data.length;
            out.push(['GLOSS', name, g.textContent, k + f.i]); }
        // 例外：这个连字符词本身比整行还宽（六级 s10 词条 you-and-me-against-the-world），只能在连字符处断开——按词的总宽实测，不看排版程序怎么标
        const nb = a.el.closest('nobr'), box = nb && nb.parentElement.closest('.v > div, .en, .zh, h1');
        const wide = nb && box && [...nb.getClientRects()].reduce((s, r) => s + r.width, 0) > box.clientWidth + 0.5;
        if (a.c === '-' && /[A-Za-z]/.test(f.c) && !wide) out.push(`连字符：${name}「${txt(L[i - 1]).slice(-12)}／${txt(ln).slice(0, 8)}」`); }
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
    // 专八 t03 第二轮审阅（breaks）：释义括注能放一行却被拆开（（同 / gunwale）），括注里的断点交给 Python 判断；译文在词中间断行交给 Python 按 jieba 判断
    const offs = el => { const m = new Map(); let p = 0; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n;
      while ((n = w.nextNode())) { m.set(n, p); p += n.data.length; } return m; };
    if (breaks && isGloss) { const g = k.querySelector('span[lang]'), om = g && offs(g);
      if (g) { const gt = g.textContent, li = new Map(), at = new Map();
        L.forEach((ln, i) => ln.forEach(x => { if (om.has(x.n)) { li.set(om.get(x.n) + x.i, i); at.set(om.get(x.n) + x.i, x); } }));
        const st = [], ns = []; for (let i = 0; i < gt.length; i++) { if ('（('.includes(gt[i])) st.push(i); else if ('）)'.includes(gt[i]) && st.length) { const a = st.pop(); if (!st.length) ns.push([a, i + 1]); } }
        const gs = getComputedStyle(g), cv2 = document.createElement('canvas').getContext('2d'); cv2.font = `${gs.fontWeight} ${gs.fontSize} ${gs.fontFamily}`;
        const spw = cv2.measureText(' ').width;
        for (const [a, b] of ns) { const qs = []; for (let q = a; q < b; q++) if (li.has(q)) qs.push(q);
          if (new Set(qs.map(q => li.get(q))).size < 2) continue;
          let W = 0; for (const q of qs) { const x = at.get(q); W += x.r - x.l;
            if (x.el.classList.contains('pl') || x.el.classList.contains('pr')) { const c = getComputedStyle(x.el); W += parseFloat(c.marginLeft) + parseFloat(c.marginRight); } }
          for (let q = a; q < b; q++) if (/\s/.test(gt[q])) W += spw;
          if (W <= x1 - x0 - 2) out.push(`括注拆开：${name}释义「${gt.slice(a, b)}」放得下一行（宽 ${Math.round(W)}，行宽 ${Math.round(x1 - x0)} 像素）却被拆到两行`);
          // 断在英文片段（括注里两个汉字或中文标点之间的一段）中间：这一段放得下一行就不许断（（down the / length of 顺着……一路））
          const stop = c => cjk(c) || '，；：、。'.includes(c);
          for (let j = 1; j < qs.length; j++) if (li.get(qs[j]) !== li.get(qs[j - 1])) { const q = qs[j]; let lo = q, hi = q, fits = false;
            if (!stop(gt[qs[j - 1]]) && !stop(gt[q])) { while (lo > a && !stop(gt[lo - 1])) lo--; while (hi < b && !stop(gt[hi])) hi++;
              let w = 0; for (let z = lo; z < hi; z++) { const x = at.get(z); if (x) w += x.r - x.l; else if (/\s/.test(gt[z])) w += spw; }
              fits = w <= x1 - x0 - 2; }
            out.push(['NOTE', name, gt, a, b, q, fits ? gt.slice(lo, hi).trim() : '']); } } } }
    if (breaks && name === '译文') { const om = offs(k);
      for (let j = 1; j < L.length; j++) { const a = L[j - 1][L[j - 1].length - 1], f = L[j][0];
        if (cjk(a.c) && cjk(f.c) && om.has(f.n)) out.push(['ZHBRK', name, k.textContent, om.get(f.n) + f.i]);
        if (om.has(f.n)) out.push(['ZHEDGE', name, k.textContent, om.get(f.n) + f.i]); }     // 分句首尾单字、书名 / 术语断开（Python 判断）
      // 译文短行（六级黑板审阅：s05 “这种转移 / 自20世纪80年代以来从未停歇”、s13 “只是说， / 如果20世纪……”上一行空出一大段）：
      // 每一行（不算最后一行）行末到右边界的空，与下一行开头的各字位置交给 Python：按断行规则（词、人名、术语、英文段、分句首尾、末两字、标点禁则）
      // 下一行开头第一个可以断开的单位放得进上一行的空，却被整个推到下一行，就是排版程序绑得太多
      for (let j = 1; j < L.length; j++) { const a = L[j - 1][L[j - 1].length - 1], f = L[j][0]; if (!om.has(f.n)) continue;
        const gap = x1 - (a.r + (a.el.classList.contains('pr') ? parseFloat(getComputedStyle(a.el).marginRight) : 0));
        const pos = L[j].filter(x => om.has(x.n)).map(x => [om.get(x.n) + x.i, x.l, x.el.classList.contains('pr') ? parseFloat(getComputedStyle(x.el).marginRight) : 0]), last = L[j][L[j].length - 1];
        out.push(['ZHGAP', name, j, k.textContent, om.get(f.n) + f.i, gap, pos, last.r, f.el.classList.contains('pl') ? em(f.el) / 2 : 0, em(k)]); } }
    if (breaks && isGloss) { const g = k.querySelector('span[lang]'), om = g && offs(g);      // 括注分离、释义开头 / 结尾单字（Python 判断，宽度用实测）
      if (g) { const wd = new Array(g.textContent.length).fill(0);
        const gt0 = g.textContent;
        for (const ln of L) for (const x of ln) if (om.has(x.n)) { let w = x.r - x.l, q = om.get(x.n) + x.i;
          if (x.el.classList.contains('pl') || x.el.classList.contains('pr')) { const c = getComputedStyle(x.el); w += parseFloat(c.marginLeft) + parseFloat(c.marginRight); }
          // 行首的左括号被 FIT 去掉了左半空白（.po → .pl）；放在一行里时它在行中、是全宽：按全宽算（设计上就去半字的：紧跟在左标点后面或在释义开头，不加）
          if (x === ln[0] && x.el.classList.contains('pl') && q > 0 && !ZO.includes(gt0[q - 1])) w += em(x.el) / 2;
          wd[q] = w; }
        const sw = (() => { const c2 = document.createElement('canvas').getContext('2d'), gs = getComputedStyle(g); c2.font = `${gs.fontWeight} ${gs.fontSize} ${gs.fontFamily}`; return c2.measureText(' ').width; })();
        g.textContent.split('').forEach((c, q) => { if (/\s/.test(c)) wd[q] = sw; });
        for (let j = 1; j < L.length; j++) { const f = L[j][0], a = L[j - 1][L[j - 1].length - 1];
          if (om.has(f.n)) out.push(['GBRK', name, g.textContent, om.get(f.n) + f.i, om.has(a.n), wd, x1 - x0]); } } }
    if (name === '英文') for (let j = 1; j < L.length; j++)          // 专八校园版第 2 批盲审：t06 “Mr.” 落在行末、人名在下一行
      { const z = L[j - 1].filter(x => !x.el.closest('sup')).at(-1);      // 行文字 txt 不带空格（from Mr. → fromMr.），按最后一个字所在的原文判断
        if (z && /\b(Mr|Mrs|Ms|Dr|Prof|St)\.$/.test(z.n.data.slice(0, z.i + 1))) out.push(`称谓断开：英文第 ${j} 行以「${txt(L[j - 1]).slice(-12)}」结尾，称谓与人名被拆到两行`); }
    if (name === '英文') for (let j = 1; j < L.length; j++)
      if (/\d$/.test(txt(L[j - 1].filter(x => !x.el.closest('sup')))) && (/^(kg|g|mg|km|m|cm|mm|ml|mph|°C|°F|percent|kilo(gram|metre|meter)s?|(centi|milli)?(metre|meter)s?|grams?|tonnes?|tons?|miles?|feet|foot|inch(es)?|degrees?|hours?|minutes?|seconds?|days?|weeks?|months?|years?)(?![A-Za-z])/.test(txt(L[j]))
          || (breaks && /^((m|b|tr)illions?|thousands?|hundreds?)(?![A-Za-z])/.test(txt(L[j])))))     // 数目单位只对专八 / 六级（六级黑板审阅：“$13 / billion”）
        out.push(`数字单位：英文「${txt(L[j - 1]).slice(-8)} / ${txt(L[j]).slice(0, 8)}」数字与单位被拆到两行`);
  };
  const ttl = document.querySelector('.ttl h1');
  if (ttl) { const g = document.createRange(); g.selectNodeContents(ttl); const a = g.getBoundingClientRect(), b = ttl.getBoundingClientRect(),
      card = document.querySelector('.ttl'), c = card.getBoundingClientRect(), cs = getComputedStyle(card), rows = new Set([...g.getClientRects()].filter(r => r.width).map(r => Math.round(r.top)));
    const L = c.left + card.clientLeft + parseFloat(cs.paddingLeft), R = c.left + card.clientLeft + card.clientWidth - parseFloat(cs.paddingRight);
    // 量标题文字本身（专八共用背景 3 的粉笔下划线是 h1 的绝对定位伪元素，向右多出 0.25 字，撑大了 scrollWidth，文字其实放得下）
    // 只许在引擎加的 br.tb（第一个冒号后面）分成两行（专八 make_video.TITLE_JS；六级 s06 的长标题），别的地方换行、伸出卡片都不行
    if (a.right > b.right + 1 || a.left < b.left - 1 || a.left < L - 1 || a.right > R + 1 || rows.size > (ttl.querySelector('br.tb') ? 2 : 1))
      out.push(`标题：一行放不下（文字 ${Math.round(a.left)}–${Math.round(a.right)}，标题框 ${Math.round(b.left)}–${Math.round(b.right)}，卡片 ${Math.round(L)}–${Math.round(R)}，${rows.size} 行）`);
    return out; }
  const en = document.querySelector('.en'), zh = document.querySelector('.zh');
  block(en, '英文', false); block(zh, '译文', false);
  document.querySelectorAll('.v > div').forEach((d, i) => { block(d, `词条 ${i + 1} `, true);
    const b = d.querySelector('b'), rs = b.getClientRects(), g = d.querySelector('span[lang]'), last = rs[rs.length - 1];   // z03 词条折行后释义紧接在词条尾巴后面
    if (rs.length > 1) for (const e of [d.querySelector('i'), g].filter(Boolean)) { const r = e.getClientRects()[0];
      if (r && r.top < last.top + 2) { out.push(`词条折行：词条 ${i + 1} 「${b.textContent}」折行后，${e === g ? '释义' : '词性'}没有另起一行`); break; } } });
  for (const el of [en, ...document.querySelectorAll('.v b')]) if (/['"]/.test(el.textContent)) out.push(`直引号：「${el.textContent.slice(0, 30)}」`);
  // 文字重叠（专八 t03 第二轮审阅：埋雷“译文压在英文上 32 像素”人看出来了、程序没有这项）：英文、译文、页眉、页脚、词汇栏标题、每个词条各自按行合成文字框，
  // 不同块的文字框不许相交（横向超过 1 像素且纵向超过 2 像素）。字框是字体的字身高度，行距不算，正常排版相邻两块之间总有空隙
  { const boxes = el => { const B = []; for (const x of chars(el)) { const g = document.createRange(); g.setStart(x.n, x.i); g.setEnd(x.n, x.i + 1);
        const rs = g.getClientRects(), r = rs[rs.length - 1], p = B[B.length - 1], h = r.bottom - r.top;
        if (p && r.left >= p.r - 2 && Math.abs((r.top + r.bottom) / 2 - (p.t + p.b) / 2) < 0.5 * h) { p.r = Math.max(p.r, r.right); p.t = Math.min(p.t, r.top); p.b = Math.max(p.b, r.bottom); p.s += x.c; }
        else B.push({l: r.left, r: r.right, t: r.top, b: r.bottom, s: x.c}); } return B; };
    const blocks = [['英文', en], ['译文', zh], ['页眉', document.querySelector('.top')], ['页脚', document.querySelector('.bot')], ['词汇栏标题', document.querySelector('.side h3')],
      ...[...document.querySelectorAll('#list > .v')].map((e, i) => [`词条 ${i + 1}`, e])].filter(x => x[1]).map(([nm, el]) => [nm, boxes(el)]);
    let hit = 0;
    for (let a = 0; a < blocks.length && !hit; a++) for (let c = a + 1; c < blocks.length && !hit; c++) for (const x of blocks[a][1]) { if (hit) break;
      for (const y of blocks[c][1]) if (x.l < y.r - 1 && y.l < x.r - 1 && x.t < y.b - 2 && y.t < x.b - 2) {
        out.push(`文字重叠：${blocks[a][0]}「${x.s.slice(0, 8)}」与${blocks[c][0]}「${y.s.slice(0, 8)}」相交 ${Math.round(Math.min(x.b, y.b) - Math.max(x.t, y.t))} 像素`); hit = 1; break; } } }
  // 短语断开（专八 t03 第二轮审阅：rough / treatment、at the / expense of 等）：高亮短语放得下一行就不许拆到两行（宽度 = 各段宽度之和 + 断开处的空格）
  if (breaks) { const ecs = getComputedStyle(en), cv3 = document.createElement('canvas').getContext('2d');
    for (const e of en.querySelectorAll('.ph')) { const rs = [...e.getClientRects()].filter(r => r.width > 0), n = new Set(rs.map(r => Math.round(r.top))).size;
      if (n < 2) continue; const es = getComputedStyle(e); cv3.font = `${es.fontWeight} ${es.fontSize} ${es.fontFamily}`;
      const W = rs.reduce((s, r) => s + r.width, 0) + (n - 1) * cv3.measureText(' ').width;
      // 例外：短语后面一直到英文结尾都是不能断开的（只有标点、不换行空格和分屏续接号“ …”），合起来一行放不下（六级 s26 第 19 句）——按实测总宽判断
      const g = document.createRange(); g.setStartAfter(e); g.setEnd(en, en.childNodes.length);
      let tw = 0; if (!g.toString().includes(' ')) { const wk = document.createTreeWalker(en, NodeFilter.SHOW_TEXT), tr = document.createRange();
        for (let t; (t = wk.nextNode());) if (!e.contains(t) && (e.compareDocumentPosition(t) & Node.DOCUMENT_POSITION_FOLLOWING)) {
          tr.selectNodeContents(t); for (const q of tr.getClientRects()) tw += q.width; } }
      if (W <= en.clientWidth + 0.5 && W + tw > en.clientWidth + 0.5 && e === [...en.querySelectorAll('.ph')].pop() && en.lastElementChild && en.lastElementChild.classList.contains('cont')) continue;
      // 例外（六级黑板审阅）：短语整体换到下一行会让上一行空出一半以上（s54 “We / don't have to look further than”），可以在词间断开——
      // 按断开后短语前面那段文字的实测右边界判断（与 make_video FIT 的 phr 同一条线：不到行宽的一半）
      // 紧贴在短语前面、中间没有空格的字（左引号“：s33 第 11 句 “survival of the fittest”）算短语的一部分：按它们前面最后一个非空白字量
      { const w2 = document.createTreeWalker(en, NodeFilter.SHOW_TEXT), cs2 = []; let n2;
        while ((n2 = w2.nextNode()) && !e.contains(n2) && (e.compareDocumentPosition(n2) & Node.DOCUMENT_POSITION_PRECEDING))
          for (let i = 0; i < n2.data.length; i++) cs2.push([n2, i]);
        const sp2 = j => /[ \t\n]/.test(cs2[j][0].data[cs2[j][1]]),      // 不换行空格不算（与 make_video FIT 相同：Mr. 连着人名短语）
             _b2 = 0, box2 = c => { const g2 = document.createRange(); g2.setStart(c[0], c[1]); g2.setEnd(c[0], c[1] + 1); const q2 = g2.getClientRects(); return q2[q2.length - 1]; };
        let j2 = cs2.length; while (j2 > 0 && !sp2(j2 - 1)) j2--;
        const head = j2 < cs2.length ? cs2[j2] : null; while (j2 > 0 && sp2(j2 - 1)) j2--;
        if (j2 > 0) { const last = box2(cs2[j2 - 1]), first = head ? box2(head) : rs[0];
          if (last && first && last.bottom > first.top + 1 && last.right - (en.getBoundingClientRect().left + en.clientLeft) < 0.5 * en.clientWidth) continue; } }
      if (W <= en.clientWidth + 0.5) out.push(`短语断开：英文高亮短语「${e.textContent}」放得下一行（宽 ${Math.round(W)}，行宽 ${en.clientWidth} 像素）却被拆到两行`); } }
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


def jb(z8=False):
    """jieba；z8（专八 / 六级）先加载本目录的 分词补充.txt（与专八 make_video.jb 相同；中考不加载，结果不变）。"""
    import logging
    import jieba
    jieba.setLogLevel(logging.WARNING)
    if z8 and not getattr(jieba, '_zb_dict', False):
        for w in (HERE / '分词补充.txt').read_text('utf-8').splitlines():
            if w.strip() and not w.startswith('#'):
                jieba.add_word(w.strip())
        jieba._zb_dict = True
    return jieba


def wordch(c):
    return '\u4e00' <= c <= '\u9fff' or c.isalnum() or c == '…'


def ok_break(g, k, z8=False, names=()):
    """z8（专八 / 六级）：分词先加载 分词补充.txt。names：登记的中文整名——名字两头可以断（专八校园版 t04 第 8 句“卢埃拉·凯洛格和／温思罗普·凯洛格”，
    jieba 切成“格和温”跨过名字边界），名字中间不能断（jieba 在“凯洛／格”之间也有边界）。"""
    if g[k - 1:k].isspace() or g[k:k + 1].isspace():          # 释义里的英文（as A as it is）在空格处换行，正常
        return True
    jieba = jb(z8)
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
    han = lambda c: '一' <= c <= '鿿'
    pos = {x for x in pos if not (g[x - 1:x] == '…' and g[x:x + 1] in ('的', '地', '得', '之')) and not (g[x - 2:x - 1] == '…' and g[x - 1:x] in ('的', '地', '得', '之') and han(g[x:x + 1]))}       # 省略号后面、省略号后的单字后面不断开（专八校园版第 2 批盲审：“没有走到…… / 的地步”；与 make_video.words 相同）
    import re
    for nm in names:
        for m in re.finditer(re.escape(nm), g):
            pos |= {m.start(), m.end()}
            pos -= set(range(m.start() + 1, m.end()))
    return k in pos


def jieba_bounds(t, z8=False):
    """t 按 jieba 分词后的词边界位置（与 专八 make_video.jieba_words 一样对整段文字分词；z8 先加载 分词补充.txt）。"""
    out, i = {0}, 0
    for w in jb(z8).cut(t):
        i += len(w)
        out.add(i)
    return out


def note_ok(t, i):
    """括注 t（含两头括号）在 t[i] 之前断行是否合格（与 专八 make_video.note_breaks 分开写的独立判断）：
    空格处、中英文交界（两边最近的字母 / 汉字一边是字母一边是汉字）、逗号顿号分号冒号之后可以断；左括号之后、右括号和句读标点之前不能断；
    其余只在“比 9 个字还长的中文片段”（两头是空格、中英交界或逗号等）的分词边界上可以断（中文片段不超过 9 个字时整体不断行）。"""
    han = lambda c: '\u4e00' <= c <= '\u9fff'
    lat = lambda c: c.isascii() and c.isalnum()
    if t[i - 1] in '（(“‘' or t[i] in '）)，。、；：！？”’…':
        return False
    if t[i - 1].isspace() or t[i].isspace() or t[i - 1] in '，；：、':
        return True
    a = next((c for c in reversed(t[:i]) if han(c) or lat(c)), '')
    b = next((c for c in t[i:] if han(c) or lat(c)), '')
    if a and b and han(a) != han(b):
        return True
    lo, hi = i, i                                   # 断点所在的中文片段
    while lo > 0 and not t[lo - 1].isspace() and not lat(t[lo - 1]) and t[lo - 1] not in '，；：、':
        lo -= 1
    while hi < len(t) and not t[hi].isspace() and not lat(t[hi]) and not (hi > lo and t[hi - 1] in '，；：、'):
        hi += 1
    seg = t[lo:hi]
    return sum(han(c) for c in seg) > 9 and (i - lo) in jieba_bounds(seg)


SIZES = """() => { const f = s => { const e = document.querySelector(s); return e ? parseFloat(getComputedStyle(e).fontSize) : null; };
  return {英文: f('.en'), 译文: f('.zh'), 词汇栏: parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--vs')) || null, 词条: f('.v b'), 释义: f('.v span[lang]')}; }"""


def sizes(pg):
    """当前屏实际的字号（浏览器算出的像素值，不看排版程序自己的返回值）：英文、译文、词汇栏 --vs、词条、释义。"""
    return pg.evaluate(SIZES)


def size_diff(a, b):
    """分屏字号：同一句的两屏实测字号 a（第 1 屏）、b 不同就报（只比两屏都有的项）。"""
    return [f'分屏字号：{k} 第 1 屏 {a[k]}px，这一屏 {b[k]}px（同一句各屏必须一样大）' for k in a
            if a[k] is not None and b.get(k) is not None and abs(a[k] - b[k]) > 0.01]


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


LATIN_RUN = r"[A-Za-z0-9][A-Za-z0-9’'.&%％-]*(?: [A-Za-z0-9][A-Za-z0-9’'.&%％-]*)*"
CLAUSE = r'[^，。、；：！？]+'
TERM = r'“[^“”，。；：！？、]{1,12}”（[^（）]{1,6}）|“[^“”，。；：！？、]{1,6}”|《[^《》]{1,8}》|（[^（），。；：]{1,6}）'      # 与 make_video.ZH_TERM 相同（专八校园版第 2 批盲审：短括注、引号术语 + 括注）


def zh_edge(t, k):
    """译文在 t[k] 之前断行（六级黑板审阅）：分句（，。、；：！？之间的一段）开头或结尾只有一个字落在断点的一边（“传达得 / 好，”），
    或者把短的引号术语、书名拆开（“能源 / 转型”、《思考，快与 / 慢》）。返回问题文字或 None。"""
    import re
    for m in re.finditer(TERM, t):
        if m.start() < k < m.end():
            return f'术语断开：译文「{t[m.start():k]}／{t[k:m.end()]}」短的引号术语或书名被拆到两行'
    for m in re.finditer(CLAUSE, t):
        a, b = m.span()
        if not a < k < b:
            continue
        units, i = [], a                    # 字单位：一个汉字或一段英文 / 数字（标点不算）
        while i < b:
            r = re.compile(LATIN_RUN).match(t, i, b)
            j = r.end() if r and r.end() > i else i + 1
            if r and r.end() > i or '\u4e00' <= t[i] <= '\u9fff':
                units.append((i, j))
            i = j
        left, right = [u for u in units if u[1] <= k], [u for u in units if u[0] >= k]
        if len(left) == 1 and left[0][1] - left[0][0] == 1 or len(right) == 1 and right[0][1] - right[0][0] == 1:
            return f'分句单字：译文「{t[a:k]}／{t[k:b]}」分句的第一个或最后一个字单独落在另一行'
    return None


def zh_breaks(t, names=()):
    """译文 t 按断行规则可以断开的位置（在 t[k] 之前断行，k = 1 … len(t) − 1）。与专八 make_video.zh_html 的绑定分开写（独立判断），规则即本程序的各项检查：
    标点禁则（右半空白的标点、省略号不在行首，左半空白的标点不在行末，“——”“……”不拆开）、译文断词（jieba 词，先加载 分词补充.txt）、
    人名（间隔号前后、登记的整名）、西文（一段英文 / 数字连同后面紧挨的汉字、连续的西文字符）、术语、分句首尾单字、最后一行至少两个字。"""
    import re
    han = lambda c: '一' <= c <= '鿿'
    n, bad = len(t), set()
    wb = jieba_bounds(t, True) | {x for nm in names for m in re.finditer(re.escape(nm), t) for x in m.span()}     # 登记人名的两头可以断（与 make_video.jieba_words 相同）
    for k in range(1, n):
        a, b = t[k - 1], t[k]
        if b in '，。、：；！？）”’】」》…' or a in '（“‘【「《' or (a == b and a in '—…') or '·' in (a, b) or (han(a) and han(b) and k not in wb) or num_split(t, k):
            bad.add(k)
    spans = [(m.start(), m.end() + (m.end() < n and han(t[m.end()]))) for m in re.finditer(LATIN_RUN, t)]
    spans += [m.span() for m in re.finditer(r'[!-~]+', t)]                     # 连续的西文字符（10,000、Hunt’s 之外的标点）浏览器不断开
    spans += [m.span() for nm in names for m in re.finditer(re.escape(nm), t)]
    spans += [m.span() for m in re.finditer(TERM, t)]
    for a, b in spans:
        bad.update(range(a + 1, b))
    hz = [i for i, c in enumerate(t) if han(c)]
    if len(hz) >= 2:
        bad.update(range(hz[-2] + 1, n))
    return {k for k in range(1, n) if k not in bad and not zh_edge(t, k)}


def num_split(t, k):
    """在 t[k] 之前断行，把单独成词的数词（“一”“两”“几”……）与后面的词拆开（专八校园版第 2 批盲审：t06 “后部放着一 / 板条箱活鸡”）。"""
    toks = jieba_bounds(t, True)
    return k in toks and k - 1 in toks and t[k - 1] in '一二两三四五六七八九十百千万几半' and '一' <= t[k:k + 1] <= '鿿'


def zh_short(name, j, t, k, gap, pos, right, pl, em, names=()):
    """译文短行（六级黑板审阅：s05 第 5 句“这种转移 / 自20世纪80年代以来从未停歇。”上一行空出 7 个字、s13 第 18 句、s02 第 1 句）：
    第 j 行（下一行从 t[k] 开始）行末空出 gap 像素；按 zh_breaks 的规则，下一行开头第一个可以断开的单位（到下一行里第一个可断位置为止）
    放得进这段空（留 0.25 字余量），却被推到了下一行——排版程序绑在一起的比规则要求的多（如把英文段前面的汉字也绑上，连成一长串）。
    pos：下一行每个字 [位置, 左边界]；right：下一行最后一个字的右边界；pl：下一行第一个字是去掉了左半空白的左标点（放回行中要加回半字）。"""
    ok = zh_breaks(t, names)
    left = {x[0]: x[1] for x in pos}
    q = sorted(left)
    p = next((x for x in q if x > k and any(k < y <= x for y in ok)), None)
    w = (left[p] if p is not None else right) - left[k] + pl
    # 专八校园版 t09 第 8 句「说道：“」：单位末尾的右标点在行中与下一个标点挤压（“：”右边距 −0.5 字），放到上一行行末时浏览器按全宽算
    # （实测：行宽再多 2 像素“说道：”才上得去）——按全宽量，不把放不下的误报成短行
    mr = {x[0]: x[2] for x in pos if len(x) > 2}
    if p is not None and mr.get(p - 1, 0) < 0:
        w -= mr[p - 1]
    if w <= gap - 0.25 * em:
        return (f'译文短行：译文第 {j} 行后面空出 {gap / em:.1f} 字，下一行开头的「{t[k:p] if p is not None else t[k:q[-1] + 1]}」'
                f'（{w / em:.1f} 字）按断行规则放得进来，却被推到了下一行')
    return None


def note_span(g, k):
    """g[k] 是左括号或 g[k-1] 是右括号时，这个括注（最外层）的 (起, 止)。"""
    st, spans = [], []
    for i, c in enumerate(g):
        if c in '（(':
            st.append(i)
        elif c in '）)' and st:
            a = st.pop()
            if not st:
                spans.append((a, i + 1))
    return next(((a, b) for a, b in spans if a == k or b == k), None)


def segments(g):
    """释义的分句：最外层（不在括号里）的 ，。、；：！？ 之后切开，标点连同紧跟的右半空白标点归前一个分句（与专八 make_video.gloss_segments 分开写）。"""
    out, a, depth, i = [], 0, 0, 0
    while i < len(g):
        c = g[i]
        if c in '（(':
            depth += 1
        elif c in '）)':
            depth = max(0, depth - 1)
        elif not depth and c in '，。、；：！？':
            j = i + 1
            while j < len(g) and g[j] in '，。、：；！？）”’】」》':
                j += 1
            out.append((a, j))
            a = i = j
            continue
        i += 1
    if a < len(g):
        out.append((a, len(g)))
    return out


def depth_at(g, k):
    d = 0
    for c in g[:k]:
        d = d + 1 if c in '（(' else max(0, d - 1) if c in '）)' else d
    return d


def gloss_break(name, g, k, prev_in, wd, linew):
    """释义在 g[k] 之前断行（六级黑板审阅）：
    括注分离——在括注与紧挨着的词（中间没有标点）之间断开（“前景；（成功的） / 希望”“使用 / （的机会）”“受 / （法律、规定等）保护”），
    而这个分句（最外层标点之间，连同句末标点）整个放得下一行（宽度按每个字实测相加）；
    释义单字——在括号外断开时，分句开头或结尾只有一个字落在断点的一边（“内化；使 / 成为……”“在 / 没有……的情况下”“……并 / 不像……”）。"""
    import re
    out = []
    if not prev_in or k <= 0 or k >= len(g):
        return out
    seg = next(((a, b) for a, b in segments(g) if a < k < b), None)
    if seg and ((g[k] == '（' and wordch(g[k - 1])) or (g[k - 1] == '）' and wordch(g[k]))):
        w = sum(wd[seg[0]:seg[1]])
        if w <= linew - 2:
            out.append(f'括注分离：{name}释义「{g[seg[0]:k]}／{g[k:seg[1]]}」括注与紧挨着的词被拆到两行（这个分句宽 {round(w)}，行宽 {round(linew)} 像素，放得下一行）')
    if seg and not depth_at(g, k):
        a, b = seg
        while b > a and g[b - 1] in '，。、；：！？）”’】」》' and depth_at(g, b - 1) == 0:      # 去掉句末标点（括注的右括号不算）
            b -= 1
        lc, rc = sum(c.isalnum() for c in g[a:k]), sum(c.isalnum() for c in g[k:b])
        # 例外：断在“一个字 | 括注”交界，而这个字连同括注一行放不下、括注本身放得下（s39 第 4 句“that of ……的 / （代替前面提到的名词）”）——
        # 只能二选一：字留在上一行、括注整体换行（括注不拆开，括注拆开检查要求的）。字连同括注放得下一行的（“受 / （法律、规定等）保护”）照样报
        ns = note_span(g, k)
        unit = ns and ((a, ns[1]) if ns[0] == k and lc == 1 else (ns[0], b) if ns[1] == k and rc == 1 else None)
        if unit and sum(wd[unit[0]:unit[1]]) > linew - 2 and sum(wd[ns[0]:ns[1]]) <= linew - 2:
            return out
        if (lc == 1 and re.search(r'[\u4e00-\u9fff]', g[a:k])) or (rc == 1 and re.search(r'[\u4e00-\u9fff]', g[k:b])):
            out.append(f'释义单字：{name}释义「{g[a:k]}／{g[k:b]}」分句开头或结尾的一个字单独落在另一行')
    return out


def jieba_words_z8(t):
    out, i = [], 0
    for w in jb(True).cut(t):
        out.append((i, i + len(w)))
        i += len(w)
    return out


def problems(pg, min_fs, min_vs, poss=False, names=(), fonts=False, gaps=False, breaks=False):
    """当前页面（已排版）的排版问题列表；make_video.py 每屏截图前调用，有问题就不生成视频。
    poss：是否查“徽章撇号”；names：登记的中文整名（查是否被拆到两行）；fonts：是否查字体回退；gaps：是否查词条间距；
    breaks：是否查括注拆开 / 括注断开、短语断开、译文断词（这几项专八开，中考不变）。文字重叠两个项目都查。"""
    res = font_fallback(pg) if fonts else []
    for x in pg.evaluate(CHECK, [min_fs, min_vs, poss, list(names), gaps, breaks]):
        if isinstance(x, list) and x[0] == 'NOTE':      # 括注里的断点：只许在中英交界、逗号等处（note_ok）；英文片段放得下一行就不许断开（JS 实测）
            _, name, g, a, b, k, run = x
            if run:
                res.append(f'括注断开：{name}释义「{g[a:k]}／{g[k:b]}」英文片段「{run}」放得下一行却被拆开')
            elif not note_ok(g[a:b], k - a):
                res.append(f'括注断开：{name}释义「{g[a:k]}／{g[k:b]}」')
        elif isinstance(x, list) and x[0] == 'ZHEDGE':  # 分句首尾单字、短术语 / 书名拆开（专八 / 六级）
            why = zh_edge(x[2], x[3])
            if why:
                res.append(why)
        elif isinstance(x, list) and x[0] == 'ZHGAP':   # 译文短行（专八 / 六级）
            why = zh_short(*x[1:], names=names)
            if why:
                res.append(why)
        elif isinstance(x, list) and x[0] == 'GBRK':    # 括注分离、释义单字（专八 / 六级）
            res += gloss_break(*x[1:])
        elif isinstance(x, list) and x[0] == 'ZHBRK':   # 译文在一个词的中间断行
            _, name, t, k = x
            if k not in jieba_bounds(t, breaks) | {x for nm in names for m in re.finditer(re.escape(nm), t) for x in m.span()}:     # 登记人名两头可以断
                res.append(f'译文断词：{name}「{t[max(0, k - 6):k]}／{t[k:k + 6]}」把一个词拆到两行')
            elif num_split(t, k):
                res.append(f'数词断开：{name}「{t[max(0, k - 6):k]}／{t[k:k + 6]}」单独成词的数词与后面的词被拆到两行')
        elif isinstance(x, list):        # 释义在标点以外的地方断行：只有超过 9 个字的块、且断在分词边界上才合格（与 make_video.words 一致）
            _, name, g, k = x
            if not ok_break(g, k, breaks, names):
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
    """--project 中考|专八|六级（默认 中考）：layoutcheck、screens_fp、canary_layout、prep 由几个项目共用（六级与专八用同一个引擎）。返回 (项目名, 项目 tools 目录, 其余参数)。"""
    name = '中考'
    if '--project' in argv:
        j = argv.index('--project')
        name, argv = argv[j + 1], argv[:j] + argv[j + 2:]
    if name not in ('中考', '专八', '六级', '考研'):
        raise SystemExit(f'--project 只能是 中考、专八、六级 或 考研：{name}')
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
        if proj != '中考' and hasattr(M, 'set_project'):      # 专八 / 六级的旧版引擎（如 专八/tools/make_video_审阅前.py）：切到要查的项目
            M.set_project(proj, look=False)
    else:
        import make_video as M
    if '--style' in argv:                 # 专八：画面 C、1–6
        j = argv.index('--style')
        M.set_style(argv[j + 1])
        argv = argv[:j] + argv[j + 2:]
    elif hasattr(M, 'set_style'):
        M.set_style(M.PJ['look'] if getattr(M, 'PJ', None) else 'C')      # 项目的默认画面（专八 C、六级 3）
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
                if ' 第 ' in label[2:]:          # 分屏的句子（“第 k 句 第 n 屏”）：各屏实测字号必须相同（专八 t03 审阅：s20 两屏词汇栏 40/35px）
                    got, first = sizes(pg), size.setdefault(label.split(' 第 ')[0], [])
                    if first and proj in ('专八', '六级', '考研'):
                        probs += [f'{label}：{x}' for x in size_diff(first[0], got)]
                    first.append(got)
                z8 = proj in ('专八', '六级', '考研')          # 六级、考研与专八同一个引擎：专八的检查全部打开
                probs += [f'{label}：{x}' for x in problems(pg, M.MIN_FS, M.MIN_VS, poss=z8, names=NAMES, fonts=z8, gaps=z8, breaks=z8)]
            bad[pid] = probs
            print(pid, 'OK' if not probs else f'{len(probs)} 处：\n  ' + '\n  '.join(probs), flush=True)
        br.close()
    n = sum(len(v) for v in bad.values())
    print('全部通过' if not n else f'共 {n} 处，涉及 {[k for k, v in bad.items() if v]}')
    sys.exit(1 if n else 0)


if __name__ == '__main__':
    main()
