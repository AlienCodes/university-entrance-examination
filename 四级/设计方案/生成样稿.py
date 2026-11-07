import json, html, sys
from pathlib import Path
FD=Path('/tmp/claude-0/-home-user/8ecea899-aaa9-5a52-878f-ec29bb403c87/scratchpad/fonts')
OUT=Path('/tmp/claude-0/-home-user/8ecea899-aaa9-5a52-878f-ec29bb403c87/scratchpad/design')
D=json.load(open('/home/user/university-entrance-examination/四级/data/vocab.json'))['passages']
p=next(x for x in D if x['id']=='c55'); S=[x for para in p['paras'] for x in para]
k=14; s=S[k-1]; n=len(S)
esc=lambda t: html.escape(t, quote=True)
def css(pkg, files): return ''.join(f'<link rel="stylesheet" href="{(FD/pkg/"package"/f).as_uri()}">' for f in files)
FONTS=(css('fontsource-lora-5.3.0',['400.css','500.css','600.css','400-italic.css'])+css('fontsource-inter-5.3.0',['400.css','500.css','600.css','700.css'])
      +css('fontsource-eb-garamond-5.3.0',['400.css','500.css','600.css','400-italic.css'])+css('fontsource-noto-serif-sc-5.3.0',['400.css','500.css','600.css','700.css'])
      +css('lxgw-wenkai-webfont-1.7.0',['lxgwwenkai-regular.css','lxgwwenkai-bold.css']))
def marked(s, fmt):
    ws=sorted(s['w'],key=lambda w:w['sp'][0][0]); idx={id(w):i+1 for i,w in enumerate(ws)}
    spans=sorted((a,b,w) for w in s['w'] for a,b in w['sp']); out,pos='',0
    for a,b,w in spans:
        if a<pos: continue
        out+=esc(s['en'][pos:a])+fmt(esc(s['en'][a:b]),w,idx[id(w)]); pos=b
    return out+esc(s['en'][pos:]), ws, idx
def pos_split(m):
    import re
    mm=re.match(r'^((?:n|v|adj|adv|prep|conj|pron|num|det|abbr|pref)\.)\s*(.*)$',m)
    return (mm.group(1),mm.group(2)) if mm else ('',m)
def page(style, body): return f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>*{{box-sizing:border-box;margin:0;padding:0}}html,body{{width:1920px;height:1080px;overflow:hidden}}{style}</style></head><body>{body}</body></html>'
head=f"2026年6月 第1套 · Passage One"
# ---------- A 墨蓝夜读
A_css="""body{background:radial-gradient(1200px 700px at 20% 10%,#1b2f4d 0%,#0d1829 60%,#0a1220 100%);color:#e9eef6;font-family:'Noto Serif SC',serif}
.top{position:absolute;left:110px;right:110px;top:56px;display:flex;justify-content:space-between;font-family:'Inter';font-size:24px;letter-spacing:.12em;color:#7f93b3;text-transform:uppercase}
.top b{color:#f0c36b;font-weight:600}
.stage{position:absolute;left:110px;right:110px;top:150px;bottom:110px;display:flex;flex-direction:column;justify-content:center}
.en{font-family:'Lora';font-size:58px;line-height:1.6;color:#f3f6fb}
.w{color:#f0c36b;border-bottom:2px dotted rgba(240,195,107,.7)}.ph{color:#7fd6c9;border-bottom:2px solid rgba(127,214,201,.6)}
.zh{font-size:44px;line-height:1.6;color:#a9b8cf;margin-top:30px;font-weight:400}
.voc{margin-top:46px;padding-top:30px;border-top:1px solid rgba(160,180,210,.25);display:grid;grid-template-columns:1fr 1fr;gap:16px 70px}
.v{display:flex;align-items:baseline;gap:16px;font-size:34px;border:0!important}.v b{font-family:'Lora';font-style:italic;font-weight:500;color:#f0c36b;font-size:38px}.v.vp b{color:#7fd6c9}
.v i{font-style:normal;font-family:'Inter';font-size:22px;color:#7f93b3;letter-spacing:.06em}.v span{color:#e3e9f2}
.bot{position:absolute;left:110px;right:110px;bottom:56px;display:flex;align-items:center;gap:26px;font-family:'Inter';color:#7f93b3;font-size:22px}
.bar{flex:1;height:3px;background:rgba(160,180,210,.2)}.bar i{display:block;height:100%;background:#f0c36b}
.ttl{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;padding:0 170px}
.ttl .tag{font-family:'Inter';letter-spacing:.3em;color:#f0c36b;font-size:28px;font-weight:600}.ttl h1{font-size:92px;font-weight:700;margin:34px 0 26px;color:#fff}
.ttl .sub{font-family:'Lora';font-style:italic;font-size:40px;color:#a9b8cf}.ttl .ln{width:120px;height:3px;background:#f0c36b;margin:48px 0 30px}.ttl .meta{font-size:30px;color:#7f93b3}"""
def A():
    en,ws,_=marked(s,lambda t,w,i: f'<span class="{"ph" if w["t"]=="phr" else "w"}">{t}</span>')
    voc=''.join(f'<div class="v {"vp" if w["t"]=="phr" else ""}"><b>{esc(w["h"])}</b><i>{pos_split(w["m"])[0]}</i><span>{esc(pos_split(w["m"])[1])}</span></div>' for w in ws)
    sl=page(A_css,f'<div class="top"><span><b>CET-4</b> · {head}</span><span>{esc(p["title"])}</span></div><div class="stage"><div class="en">{en}</div><div class="zh">{esc(s["zh"])}</div><div class="voc">{voc}</div></div><div class="bot"><div class="bar"><i style="width:{k/n*100}%"></i></div><span>{k:02d} / {n}</span></div>')
    tt=page(A_css,f'<div class="ttl"><div class="tag">CET-4 · READING · SECTION C</div><h1>{esc(p["title"])}</h1><div class="sub">2026年6月 第1套 · Passage One</div><div class="ln"></div><div class="meta">{esc(p["genre"])}　·　{p["words"]} 词　·　逐句精读</div></div>')
    return sl,tt
# ---------- B 手账荧光笔
B_css="""body{background:#f5f2ea;background-image:radial-gradient(#d9d3c4 1.4px,transparent 1.4px);background-size:34px 34px;color:#232220;font-family:'LXGW WenKai',serif}
.top{position:absolute;left:100px;right:100px;top:50px;display:flex;justify-content:space-between;align-items:center;font-size:28px;color:#6d675c}
.top b{font-family:'Inter';font-weight:700;background:#232220;color:#f5f2ea;padding:6px 16px;border-radius:8px;margin-right:14px;font-size:24px;letter-spacing:.05em}
.card{position:absolute;left:100px;right:100px;top:130px;bottom:110px;background:#fffdf8;border-radius:28px;box-shadow:0 10px 40px rgba(60,50,30,.10);padding:60px 76px;display:flex;flex-direction:column;justify-content:center}
.en{font-family:'Inter';font-weight:500;font-size:54px;line-height:1.62;letter-spacing:-.005em}
.w{background:linear-gradient(transparent 52%,#ffe36e 52%,#ffe36e 92%,transparent 92%);padding:0 2px}
.ph{background:linear-gradient(transparent 52%,#a9e5c8 52%,#a9e5c8 92%,transparent 92%);padding:0 2px}
.zh{font-size:46px;line-height:1.55;color:#4a4740;margin-top:28px}
.voc{display:flex;flex-wrap:wrap;gap:16px 18px;margin-top:40px}
.v{font-size:32px;background:#f6f3eb;border:2px solid #ece6d8;border-radius:16px;padding:8px 20px;display:flex;align-items:baseline;gap:12px}
.v b{font-family:'Inter';font-weight:700;font-size:32px}.v.w2 b{box-shadow:inset 0 -12px 0 #ffe36e}.v.ph b{box-shadow:inset 0 -12px 0 #a9e5c8}
.v i{font-style:normal;font-family:'Inter';font-size:22px;color:#8c8475}
.bot{position:absolute;left:100px;right:100px;bottom:44px;display:flex;gap:10px;align-items:center;font-family:'Inter';color:#8c8475;font-size:22px}
.dots{flex:1;display:flex;gap:6px}.dots i{flex:1;height:8px;border-radius:4px;background:#e2dccd}.dots i.on{background:#232220}
.ttl{position:absolute;left:140px;right:140px;top:150px;bottom:150px;background:#fffdf8;border-radius:36px;box-shadow:0 10px 40px rgba(60,50,30,.10);padding:90px 110px;display:flex;flex-direction:column;justify-content:center}
.ttl .tag{font-family:'Inter';font-weight:700;font-size:30px;letter-spacing:.08em}.ttl .tag span{background:#ffe36e;padding:4px 14px;border-radius:8px}
.ttl h1{font-size:96px;margin:38px 0 22px}.ttl .sub{font-size:40px;color:#6d675c}.ttl .meta{margin-top:40px;font-size:32px;color:#8c8475}"""
def B():
    en,ws,_=marked(s,lambda t,w,i: f'<span class="{"ph" if w["t"]=="phr" else "w"}">{t}</span>')
    voc=''.join(f'<div class="v {"ph" if w["t"]=="phr" else "w2"}"><b>{esc(w["h"])}</b><i>{pos_split(w["m"])[0]}</i><span>{esc(pos_split(w["m"])[1])}</span></div>' for w in ws)
    dots=''.join(f'<i class="{"on" if i<k else ""}"></i>' for i in range(n))
    sl=page(B_css,f'<div class="top"><span><b>CET-4</b>{head}</span><span>{esc(p["title"])}</span></div><div class="card"><div class="en">{en}</div><div class="zh">{esc(s["zh"])}</div><div class="voc">{voc}</div></div><div class="bot"><div class="dots">{dots}</div><span>&nbsp;{k}/{n}</span></div>')
    tt=page(B_css,f'<div class="ttl"><div class="tag"><span>CET-4</span> 仔细阅读</div><h1>{esc(p["title"])}</h1><div class="sub">2026年6月 第1套 · Passage One</div><div class="meta">{esc(p["genre"])}　·　{p["words"]} 词　·　逐句精读</div></div>')
    return sl,tt
# ---------- C 杂志编号注释
C_css="""body{background:#fbf9f4;color:#1c2421;font-family:'Noto Serif SC',serif}
.band{position:absolute;left:0;top:0;bottom:0;width:22px;background:#1f5c4a}
.top{position:absolute;left:110px;right:90px;top:52px;display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid #1c2421;padding-bottom:16px;font-family:'Inter';font-size:24px;letter-spacing:.14em;text-transform:uppercase;color:#1c2421}
.top b{font-weight:800}.top span{color:#6b746f;letter-spacing:.04em;text-transform:none;font-family:'Noto Serif SC'}
.main{position:absolute;left:110px;top:150px;bottom:100px;width:1060px;display:flex;flex-direction:column;justify-content:center}
.en{font-family:'EB Garamond';font-size:62px;line-height:1.5}
.w{font-weight:600;color:#1f5c4a}.ph{font-weight:600;color:#a14a2a}
sup{font-family:'Inter';font-size:22px;font-weight:700;color:#fff;background:#1f5c4a;border-radius:12px;padding:1px 8px;margin-left:3px;vertical-align:28px}
.ph sup{background:#a14a2a}
.zh{font-size:42px;line-height:1.65;color:#3c4642;margin-top:32px;padding-left:24px;border-left:4px solid #d7d2c3}
.side{position:absolute;right:90px;top:150px;bottom:100px;width:600px;background:#eef2ec;border-radius:6px;padding:36px 40px;display:flex;flex-direction:column;justify-content:center;gap:14px}
.side h3{font-family:'Inter';font-size:22px;letter-spacing:.2em;color:#1f5c4a;margin-bottom:6px}
.v{display:grid;grid-template-columns:44px 1fr;gap:4px 14px;font-size:28px;line-height:1.35}
.v em{font-style:normal;font-family:'Inter';font-weight:700;font-size:22px;color:#fff;background:#1f5c4a;border-radius:50%;width:38px;height:38px;display:flex;align-items:center;justify-content:center;margin-top:4px}
.v.ph em{background:#a14a2a}.v b{font-family:'EB Garamond';font-weight:600;font-size:38px}.v i{font-style:italic;font-family:'EB Garamond';color:#6b746f;font-size:28px;margin-left:8px}.v div span{color:#3c4642;margin-left:12px}
.bot{position:absolute;left:110px;right:90px;bottom:42px;display:flex;justify-content:space-between;font-family:'Inter';font-size:22px;color:#6b746f;letter-spacing:.1em}
.ttl{position:absolute;left:150px;right:150px;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center}
.ttl .tag{font-family:'Inter';font-weight:800;letter-spacing:.3em;font-size:28px;color:#1f5c4a}.ttl h1{font-size:100px;font-weight:700;margin:30px 0;line-height:1.25}
.ttl .sub{font-family:'EB Garamond';font-style:italic;font-size:46px;color:#3c4642}.ttl .meta{margin-top:50px;padding-top:26px;border-top:2px solid #1c2421;font-size:30px;color:#6b746f;display:flex;justify-content:space-between}"""
def C():
    en,ws,idx=marked(s,lambda t,w,i: f'<span class="{"ph" if w["t"]=="phr" else "w"}">{t}<sup>{i}</sup></span>')
    voc=''.join(f'<div class="v {"ph" if w["t"]=="phr" else ""}"><em>{idx[id(w)]}</em><div><b>{esc(w["h"])}</b><i>{pos_split(w["m"])[0]}</i><span>{esc(pos_split(w["m"])[1])}</span></div></div>' for w in ws)
    sl=page(C_css,f'<div class="band"></div><div class="top"><b>CET-4 Reading</b><span>{head}　{esc(p["title"])}</span></div><div class="main"><div class="en">{en}</div><div class="zh">{esc(s["zh"])}</div></div><div class="side"><h3>VOCABULARY</h3>{voc}</div><div class="bot"><span>SENTENCE {k} / {n}</span><span>逐句精读</span></div>')
    tt=page(C_css,f'<div class="band"></div><div class="ttl"><div class="tag">CET-4 · READING</div><h1>{esc(p["title"])}</h1><div class="sub">June 2026 · Set 1 · Passage One</div><div class="meta"><span>{esc(p["genre"])}</span><span>{p["words"]} 词 · 逐句精读</span></div></div>')
    return sl,tt
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    br=pw.chromium.launch(executable_path='/opt/pw-browsers/chromium'); pg=br.new_page(viewport={'width':1920,'height':1080})
    for name,fn in (('A',A),('B',B),('C',C)):
        for tag,h in zip(('句子页','片头'),fn()):
            f=OUT/f'{name}_{tag}.html'; f.write_text(h,'utf-8'); pg.goto(f.as_uri()); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(800)
            pg.screenshot(path=str(OUT/f'{name}_{tag}.png')); print(name,tag)
    br.close()
