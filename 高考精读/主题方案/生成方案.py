"""柔彩插画：左下角绿色树苗的 3 个替代装饰（独立 CSS 覆盖，不改共用样式文件）。

    python3 生成方案.py      # 写出 装饰_A/B/C.css（各自只含一条 .band 覆盖规则，接在 6_柔彩插画.css 之后加载）
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
THEME = HERE.parents[1] / 'tools' / 'video' / 'themes' / 'css' / '6_柔彩插画.css'

SVG = {
 'A_热气球': """<svg xmlns='http://www.w3.org/2000/svg' width='100' height='330' viewBox='0 0 100 330'>
<path d='M14 318 Q14 304 28 306 Q32 294 46 300 Q58 296 60 310 Q72 310 70 320 Z' fill='#ebe4fd'/>
<ellipse cx='50' cy='196' rx='31' ry='37' fill='#d8ccfa'/>
<path d='M50 159 C34 172 34 220 46 233 L54 233 C66 220 66 172 50 159Z' fill='#ffd0b0'/>
<path d='M50 159 C45 172 45 220 49 233 L51 233 C55 220 55 172 50 159Z' fill='#ffc85c'/>
<path d='M27 218 L42 254 M73 218 L58 254' stroke='#b9a8ef' stroke-width='2' stroke-linecap='round'/>
<rect x='40' y='252' width='20' height='15' rx='3' fill='#ffb48a'/>
<path d='M80 128 Q80 137 89 137 Q80 137 80 146 Q80 137 71 137 Q80 137 80 128Z' fill='#ffc85c'/>
<circle cx='16' cy='150' r='4' fill='#b9a8ef'/><circle cx='84' cy='262' r='3.5' fill='#ffb48a'/>
</svg>""",
 'B_叠书铅笔': """<svg xmlns='http://www.w3.org/2000/svg' width='100' height='330' viewBox='0 0 100 330'>
<rect x='8' y='302' width='80' height='22' rx='5' fill='#b9a8ef'/><rect x='14' y='308' width='68' height='4' rx='2' fill='#ebe4fd'/>
<rect x='16' y='280' width='68' height='22' rx='5' fill='#ffb48a'/><rect x='22' y='286' width='56' height='4' rx='2' fill='#ffe6d4'/>
<rect x='11' y='259' width='74' height='21' rx='5' fill='#ffc85c'/><rect x='17' y='265' width='62' height='4' rx='2' fill='#fff2d6'/>
<g transform='translate(62 257) rotate(-24)'><rect x='-6' y='-78' width='12' height='70' rx='2' fill='#d8ccfa'/>
<rect x='-6' y='-84' width='12' height='8' rx='2' fill='#ff9fb4'/><path d='M-6 -8 L6 -8 L0 6Z' fill='#ffe6d4'/><path d='M-2 -2 L2 -2 L0 6Z' fill='#5a3dc4'/></g>
<path d='M26 196 Q26 206 36 206 Q26 206 26 216 Q26 206 16 206 Q26 206 26 196Z' fill='#b9a8ef'/>
<circle cx='80' cy='150' r='4' fill='#ffb48a'/><circle cx='18' cy='242' r='3.5' fill='#d8ccfa'/>
</svg>""",
 'C_彩虹云朵': """<svg xmlns='http://www.w3.org/2000/svg' width='100' height='330' viewBox='0 0 100 330'>
<path d='M10 306 A40 40 0 0 1 90 306' fill='none' stroke='#ffb48a' stroke-width='8' stroke-linecap='round'/>
<path d='M19 306 A31 31 0 0 1 81 306' fill='none' stroke='#ffc85c' stroke-width='8' stroke-linecap='round'/>
<path d='M28 306 A22 22 0 0 1 72 306' fill='none' stroke='#b9a8ef' stroke-width='8' stroke-linecap='round'/>
<path d='M0 320 Q0 306 12 308 Q16 298 27 304 Q36 302 36 314 Q42 316 40 322 Z' fill='#ffffff' stroke='#d8ccfa' stroke-width='2'/>
<path d='M62 320 Q62 307 73 309 Q78 299 88 305 Q98 304 97 316 Q101 318 99 322 Z' fill='#ffffff' stroke='#d8ccfa' stroke-width='2'/>
<path d='M50 210 Q50 220 60 220 Q50 220 50 230 Q50 220 40 220 Q50 220 50 210Z' fill='#ffc85c'/>
<circle cx='20' cy='160' r='4' fill='#b9a8ef'/><circle cx='80' cy='240' r='3.5' fill='#ffb48a'/>
</svg>""",
}


def enc(svg):
    s = re.sub(r'\s*\n\s*', '', svg)
    assert '"' not in s
    return s.replace('#', '%23')


def main():
    css = THEME.read_text('utf-8')
    m = re.search(r"\.band\{left:0;top:0;right:0;bottom:0;width:auto;background:\n(.*?)\n  transparent\}", css, re.S)
    layers = m.group(1).split('\n')
    sprout = [i for i, l in enumerate(layers) if "%233f9c86" in l and 'left bottom' in l]
    assert len(sprout) == 1, sprout          # 恰好一层是绿色树苗
    for name, svg in SVG.items():
        new = list(layers)
        new[sprout[0]] = f'  url("data:image/svg+xml;utf8,{enc(svg)}") no-repeat left bottom,'
        body = '\n'.join(new).replace('#eef8f4 0%,rgba(238,248,244,0)', '#fdeee4 0%,rgba(253,238,228,0)')  # 左下角薄荷底色换成暖桃色
        assert '3f9c86' not in new[sprout[0]]
        (HERE / f'装饰_{name}.css').write_text(
            f'/* 柔彩插画 · 内容屏左下角装饰方案 {name}（接在 6_柔彩插画.css 之后加载；只替换绿色树苗那一层，其余不变） */\n'
            f'.band{{background:\n{body}\n  transparent}}\n', 'utf-8')
        print('写出', name)


if __name__ == '__main__':
    main()
