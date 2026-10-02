"""生成 B 站视频封面：16:9（1920×1080）和 4:3（1440×1080）各一张，内容相同。

    /opt/ttsenv/bin/python tools/cover/make_cover.py      # 输出到 封面/
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / '封面'
SIZES = {'16x9': ('w169', 1920), '4x3': ('w43', 1440)}


def main():
    OUT.mkdir(exist_ok=True)
    html = (HERE / 'cover.html').resolve()
    with sync_playwright() as pw:
        exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        for name, (cls, w) in SIZES.items():
            pg = br.new_page(viewport={'width': w, 'height': 1080})
            pg.goto(html.as_uri())
            pg.evaluate(f"document.body.className = '{cls}'")
            pg.evaluate('document.fonts.ready')
            pg.wait_for_timeout(300)
            # 检查：所有文字都在画面内，不被裁切
            out = pg.evaluate("""() => [...document.querySelectorAll('.tag,.h1,.h2,.badge,.card,.feat,.yrs')]
                .map(e => e.getBoundingClientRect()).filter(r => r.left < -1 || r.top < -1 || r.right > innerWidth + 1 || r.bottom > innerHeight + 1).length""")
            if out:
                raise SystemExit(f'{name}：有 {out} 处内容超出画面')
            pg.screenshot(path=str(OUT / f'封面_{name}.png'))
            print('已生成', OUT / f'封面_{name}.png')
        br.close()


if __name__ == '__main__':
    main()
