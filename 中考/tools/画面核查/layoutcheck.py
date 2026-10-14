"""排版机械检查（不花 token，生成视频之前跑）：用生成视频的同一程序排出每一屏，逐字量出位置，检查第 1 批画面核查（排版审阅员）报出的各类排版毛病：

  行首缩进   中文译文、词汇栏释义的每一行，第一个字必须顶格（行首的左括号、左引号要去掉左半空白）
  标点挤压   相邻两个全角标点（如“：“”“）；”“”。”）之间不能空出半个字以上
  孤字       中文译文最后一行只剩一个字
  释义断词   词汇栏释义只能在标点处、或在词条与释义之间换行，不能把“可/能”“泳/衣”拆开
  连字符     带连字符的英文词（southward-moving、wind-driven）不能在连字符处断行
  直引号     英文和词条里不能有直撇号、直引号（踩坑 18）
  留白       词汇栏内容必须在卡片内边距以内；句子区不能溢出；字号不低于下限
  标题       片头标题必须在卡片内一行放下

    /opt/ttsenv/bin/python 中考/tools/画面核查/layoutcheck.py z01 z02 …     （不写篇目 = 全部）
    /opt/ttsenv/bin/python 中考/tools/画面核查/layoutcheck.py --module <旧版 make_video.py> z01 …   （用旧版程序排版，检验本检查能查出旧版的毛病）
有问题退出码非 0。
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]

CHECK = r"""([minFs, minVs]) => {
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
    const L = lines(chars(k)), x0 = leftOf(k);
    L.forEach((ln, i) => {
      const f = ln[0];
      if (isGloss && i === 0) return;                        // 词汇栏第一行从词条开始
      const want = ZO.includes(f.c) && name !== '英文' ? x0 - em(f.el) / 2 : x0;     // 英文的弯引号是西文字形，不按全角半字计
      if (Math.abs(f.l - want) > 2) out.push(`行首缩进：${name}第 ${i + 1} 行「${txt(ln).slice(0, 12)}」偏 ${Math.round(f.l - want)} 像素`);
      if (i > 0) { const a = L[i - 1][L[i - 1].length - 1];
        const g = f.el.closest('span[lang]');
        if (isGloss && a.el.closest('span[lang]') && g && !PUN.includes(a.c) && !ZO.includes(f.c))      // 交给 Python 判断是否落在分词边界
          { let k = 0; const w = document.createTreeWalker(g, NodeFilter.SHOW_TEXT); let n;      // 在含空格的原文里的位置
            while ((n = w.nextNode()) && n !== f.n) k += n.data.length;
            out.push(['GLOSS', name, g.textContent, k + f.i]); }
        if (a.c === '-' && /[A-Za-z]/.test(f.c)) out.push(`连字符：${name}「${txt(L[i - 1]).slice(-12)}／${txt(ln).slice(0, 8)}」`); }
      for (let j = 1; j < ln.length; j++) { const a = ln[j - 1], b = ln[j];
        if (ZC.includes(a.c) && (ZC + ZO).includes(b.c) && b.l - a.l > em(a.el) * 0.75)
          out.push(`标点挤压：${name}「${a.c}${b.c}」间距 ${(((b.l - a.l) / em(a.el))).toFixed(2)} 字`); }
    });
    if (name === '译文' && L.length > 1) { const last = L[L.length - 1].filter(x => cjk(x.c));
      if (last.length <= 1) out.push(`孤字：${name}最后一行只有「${txt(L[L.length - 1])}」`); }
  };
  const ttl = document.querySelector('.ttl h1');
  if (ttl) { if (ttl.scrollWidth > ttl.clientWidth + 1) out.push(`标题：一行放不下（${ttl.scrollWidth} > ${ttl.clientWidth}）`); return out; }
  const en = document.querySelector('.en'), zh = document.querySelector('.zh');
  block(en, '英文', false); block(zh, '译文', false);
  document.querySelectorAll('.v > div').forEach((d, i) => block(d, `词条 ${i + 1} `, true));
  for (const el of [en, ...document.querySelectorAll('.v b')]) if (/['"]/.test(el.textContent)) out.push(`直引号：「${el.textContent.slice(0, 30)}」`);
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
    seg = [(a, b) for a, b in zip(cuts, cuts[1:]) if a < k < b]
    if not seg:
        print('  [调试] 断点不在任何块内部：', g, k, flush=True)
        return False
    a, b = seg[0]
    if b - a <= 10:
        return False
    pos, i = set(), a
    for w in jieba.cut(g[a:b]):
        i += len(w)
        pos.add(i)
    return k in pos


def problems(pg, min_fs, min_vs):
    """当前页面（已排版）的排版问题列表；make_video.py 每屏截图前调用，有问题就不生成视频。"""
    res = []
    for x in pg.evaluate(CHECK, [min_fs, min_vs]):
        if isinstance(x, list):          # 释义在标点以外的地方断行：只有超过 10 个字的块、且断在分词边界上才合格（与 make_video.words 一致）
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


def main():
    sys.path.insert(0, str(R / '中考' / 'tools'))
    argv = sys.argv[1:]
    if '--module' in argv:
        j = argv.index('--module')
        spec = importlib.util.spec_from_file_location('make_video', argv[j + 1])
        M = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(M)
        argv = argv[:j] + argv[j + 2:]
    else:
        import make_video as M
    from playwright.sync_api import sync_playwright
    P = {p['id']: p for p in json.loads((R / '中考' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
    bad = {}
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': M.W, 'height': M.H})
        f = Path(td) / 'x.html'
        for pid in (argv or sorted(P)):
            probs = []
            for label, h, fit in screens(M, P[pid]):
                f.write_text(h, 'utf-8')
                pg.goto(f.as_uri())
                pg.evaluate('document.fonts.ready')
                if fit:
                    pg.evaluate(M.FIT)
                probs += [f'{label}：{x}' for x in problems(pg, M.MIN_FS, M.MIN_VS)]
            bad[pid] = probs
            print(pid, 'OK' if not probs else f'{len(probs)} 处：\n  ' + '\n  '.join(probs), flush=True)
        br.close()
    n = sum(len(v) for v in bad.values())
    print('全部通过' if not n else f'共 {n} 处，涉及 {[k for k, v in bad.items() if v]}')
    sys.exit(1 if n else 0)


if __name__ == '__main__':
    main()
