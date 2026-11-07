"""朋克英语 B 站头像：三个方向的预览（自绘 SVG → PNG）+ 圆形裁切 96/48 像素对比图。
python3 B站头像/头像.py   （需要 playwright）"""
import pathlib
OUT = pathlib.Path(__file__).parent
SKIN, SKIN_D, HAIR, INK = '#F6D2B4', '#E9B796', '#2B2522', '#2B2522'

def face(glasses):
    g = ''
    if glasses:
        g = f'''<g fill="none" stroke="{INK}" stroke-width="7">
        <rect x="186" y="200" width="56" height="44" rx="14"/><rect x="270" y="200" width="56" height="44" rx="14"/>
        <path d="M242 214 q14 -8 28 0"/></g>'''
    return f'''
    <rect x="226" y="290" width="60" height="70" fill="{SKIN_D}"/>
    <ellipse cx="172" cy="228" rx="16" ry="22" fill="{SKIN_D}"/><ellipse cx="340" cy="228" rx="16" ry="22" fill="{SKIN_D}"/>
    <path d="M178 200 Q178 120 256 118 Q334 120 334 200 L332 250 Q326 318 256 330 Q186 318 180 250 Z" fill="{SKIN}"/>
    <path d="M170 210 Q160 120 220 98 Q256 84 300 96 Q352 112 346 206 Q338 160 312 148 Q286 170 232 160 Q196 156 184 178 Z" fill="{HAIR}"/>
    <path d="M232 160 Q262 128 312 148 Q300 120 262 118 Z" fill="#3E3532"/>
    <path d="M196 192 q18 -10 38 -2" stroke="{HAIR}" stroke-width="7" fill="none" stroke-linecap="round"/>
    <path d="M278 190 q20 -8 38 2" stroke="{HAIR}" stroke-width="7" fill="none" stroke-linecap="round"/>
    <ellipse cx="214" cy="223" rx="8" ry="10" fill="{INK}"/><ellipse cx="298" cy="223" rx="8" ry="10" fill="{INK}"/>
    <circle cx="217" cy="219" r="2.6" fill="#fff"/><circle cx="301" cy="219" r="2.6" fill="#fff"/>
    {g}
    <path d="M256 236 q-6 22 -2 30 q6 3 10 0" stroke="{SKIN_D}" stroke-width="5" fill="none" stroke-linecap="round"/>
    <path d="M222 278 Q256 306 292 278 Q256 290 222 278 Z" fill="#fff" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/>
    <ellipse cx="200" cy="262" rx="14" ry="8" fill="#F4A9A0" opacity=".55"/><ellipse cx="312" cy="262" rx="14" ry="8" fill="#F4A9A0" opacity=".55"/>'''

def svg(bg, body, deco='', glasses=False):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="1024" height="1024">
    <defs><clipPath id="k"><circle cx="256" cy="256" r="246"/></clipPath></defs>
    <rect width="512" height="512" fill="#fff"/>{bg}
    <g clip-path="url(#k)"><g transform="translate(256 262) scale(1.12) translate(-256 -236)">{body}{face(glasses)}</g></g>{deco}</svg>'''

# A 书卷学者：藏青 V 领毛衣 + 浅蓝衬衫领 + 圆框眼镜，暖奶油底
A = svg('<circle cx="256" cy="256" r="246" fill="#FFF3DC"/>',
 f'''<path d="M96 512 Q100 384 196 352 L256 340 L316 352 Q412 384 416 512 Z" fill="#23365E"/>
 <path d="M206 350 L256 430 L306 350 L286 344 L256 392 L226 344 Z" fill="#CFE3F6" stroke="#9DBBD9" stroke-width="3"/>
 <path d="M226 344 L256 392 L286 344 L256 360 Z" fill="#B23A48"/>
 <path d="M196 352 L256 470 L316 352" fill="none" stroke="#1A2847" stroke-width="10" stroke-linejoin="round"/>
 <path d="M318 404 h34" stroke="#F2B544" stroke-width="8" stroke-linecap="round"/>''', deco='<circle cx="256" cy="256" r="243" fill="none" stroke="#F2B544" stroke-width="10"/>', glasses=True)

# B 活力潮讲：芥末黄飞行员夹克 + 白 T + 挂脖耳机（听力），B 站粉底
B = svg('<circle cx="256" cy="256" r="246" fill="#FFE3EC"/><path d="M60 360 L120 300 M410 120 L460 80 M420 380 l40 10" stroke="#FB7299" stroke-width="10" stroke-linecap="round"/>',
 f'''<path d="M90 512 Q94 380 200 350 L256 344 L312 350 Q418 380 422 512 Z" fill="#E9A92B"/>
 <path d="M206 350 Q256 400 306 350 L256 340 Z" fill="#fff"/><path d="M216 352 Q256 392 296 352" fill="#fff" stroke="#E6E6E6" stroke-width="2"/>
 <path d="M200 350 Q256 386 312 350" fill="none" stroke="#3B3B3B" stroke-width="16" stroke-linecap="round"/>
 <path d="M246 400 L238 512 M266 400 L274 512" stroke="#C88A16" stroke-width="5"/>
 <path d="M178 360 Q160 300 190 300 M334 360 Q352 300 322 300" fill="none" stroke="{INK}" stroke-width="12" stroke-linecap="round"/>
 <path d="M170 372 Q256 420 342 372" fill="none" stroke="{INK}" stroke-width="12" stroke-linecap="round"/>
 <rect x="150" y="350" width="36" height="46" rx="14" fill="{INK}"/><rect x="326" y="350" width="36" height="46" rx="14" fill="{INK}"/>
 <rect x="156" y="358" width="24" height="30" rx="9" fill="#FB7299"/><rect x="332" y="358" width="24" height="30" rx="9" fill="#FB7299"/>''')

# C 摇滚教授（朋克元素点到为止）：深灰立领夹克 + 白衬衫黑窄领带，荧光黄闪电徽章，黑白黄高对比
C = svg('<circle cx="256" cy="256" r="246" fill="#FFE94D"/><path d="M0 0" />',
 f'''<path d="M92 512 Q96 382 198 350 L256 340 L314 350 Q416 382 420 512 Z" fill="#2F3238"/>
 <path d="M212 346 L256 380 L300 346 L300 512 L212 512 Z" fill="#fff"/>
 <path d="M248 372 L264 372 L270 500 L256 512 L242 500 Z" fill="{INK}"/><path d="M246 362 L266 362 L262 378 L250 378 Z" fill="{INK}"/>
 <path d="M198 350 L212 346 L240 400 L212 512 L198 512 Z" fill="#3D4148"/><path d="M314 350 L300 346 L272 400 L300 512 L314 512 Z" fill="#3D4148"/>
 <circle cx="342" cy="408" r="22" fill="#FFE94D" stroke="{INK}" stroke-width="5"/>
 <path d="M345 393 L333 412 L343 412 L337 425 L352 403 L342 403 Z" fill="{INK}"/>''',
 deco=f'<path d="M184 170 Q200 120 250 112" stroke="#FFE94D" stroke-width="0" />')

NAMES = {'A_书卷学者': A, 'B_活力潮讲': B, 'C_摇滚教授': C}

def render():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=next(iter(sorted(pathlib.Path('/opt/pw-browsers').glob('chromium-*/chrome-linux*/chrome'))), None)); pg = b.new_page(viewport={'width': 1024, 'height': 1024})
        for n, s in NAMES.items():
            (OUT / f'{n}.svg').write_text(s)
            pg.set_content(f'<body style="margin:0">{s}</body>'); pg.screenshot(path=str(OUT / f'{n}.png'))
        # 对比图：每行一个方向，原图 256 + 圆形裁切 96 + 48（按实际像素缩小，再原样摆放）
        import base64
        uri = {n: 'data:image/png;base64,' + base64.b64encode((OUT / f'{n}.png').read_bytes()).decode() for n in NAMES}
        rows = ''.join(f'''<div class=r><b>{n}</b><img src="{uri[n]}" width=256 class=c>
          <img src="{uri[n]}" width=96 class=c><img src="{uri[n]}" width=48 class=c>
          <div class=dk><img src="{uri[n]}" width=96 class=c><img src="{uri[n]}" width=48 class=c></div></div>''' for n in NAMES)
        pg.set_viewport_size({'width': 900, 'height': 860})
        pg.set_content(f'''<style>body{{margin:0;font:20px "WenQuanYi Zen Hei";background:#f4f5f7}}.r{{display:flex;align-items:center;gap:28px;padding:10px 20px}}
        b{{width:120px}}.c{{border-radius:50%}}.dk{{display:flex;gap:20px;align-items:center;background:#18191c;padding:16px;border-radius:12px}}</style>{rows}''')
        pg.screenshot(path=str(OUT / '辨识度对比_96_48.png'), full_page=True)
        b.close()

if __name__ == '__main__':
    render()
