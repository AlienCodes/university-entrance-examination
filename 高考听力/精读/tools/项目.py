"""高考原文精读的项目入口：复用共用排版，只在本进程注册热气球A，不修改旧项目。"""
import importlib.util
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
C = HERE.parent
ROOT = C.parents[1]


def engine():
    old = os.environ.pop('DZB_PROJECT', None)
    variant = os.environ.pop('DZB_VARIANT', None)
    try:
        spec = importlib.util.spec_from_file_location('make_video', ROOT / '专八/tools/make_video.py')
        m = importlib.util.module_from_spec(spec)
        sys.modules['make_video'] = m
        spec.loader.exec_module(m)
    finally:
        if old is not None:
            os.environ['DZB_PROJECT'] = old
        if variant is not None:
            os.environ['DZB_VARIANT'] = variant
    overlay = ROOT / '高考精读/主题方案/装饰_A_热气球.css'
    cover_css = HERE / '封面.css'
    cover_image = HERE / '素材/热气球封面.png'
    m.PROJECTS['高考原文精读'] = {
        'dir': '高考听力/精读', 'audio': '原音',
        'tag': 'GAOKAO · ENGLISH · ORIGINAL TEXT', 'top': 'GAOKAO ENGLISH',
        'exam': '', 'look': '6', 'stills': '大字版/截图/{pid}', 'work': '大字版',
        'reg': '截图审阅通过.json', 'videos': '最终视频', 'max_mb': 1900,
        'name_re': r'20\d\d年 \S+ 高考英语真题 原文精读\.mp4',
        'badge_css': overlay.read_text('utf-8') + "\n.gk-roman{font-family:'EB Garamond';font-style:normal;font-weight:700}" +
                     f"\n:root{{--gk-cover-image:url('{cover_image.as_uri()}')}}\n" + cover_css.read_text('utf-8'),
    }
    m.set_project('高考原文精读')
    m.EXAM_WORDS['高考原文精读'] = ['高考', 'GAOKAO']
    original = m.look_files
    m.look_files = lambda look=None: [*original(look), Path(__file__), overlay, cover_css, cover_image]
    original_page = m.page
    def page(body):
        # 卷名罗马数字用网页字体的 I / II / III 排，避免字体子集缺字落到系统字体。
        pieces = re.split(r'(<[^>]*>)', body)
        for i in range(0, len(pieces), 2):
            pieces[i] = re.sub('[ⅠⅡⅢ]', lambda x: '<span class="gk-roman">' +
                               {'Ⅰ':'I','Ⅱ':'II','Ⅲ':'III'}[x.group()] + '</span>', pieces[i])
        rendered = original_page(''.join(pieces)).replace('&#x27;', '’')
        # 只改转义后的正文引号，不碰HTML属性、CSS或原始ASR文字；字符/高亮位置不变。
        rendered = re.sub(r'&quot;(?=\w)', '“', rendered).replace('&quot;', '”')
        return rendered
    m.page = page
    def cover(p):
        name = p.get('paper_title') or p['paper'].replace(' 高考英语真题', '')
        year, paper = name.split(' ', 1)
        paper_class='gk-paper gk-paper-short' if len(paper)<=4 else 'gk-paper'
        return page(f'<div class="ttl gk-cover">'
                    f'<h1><span class="gk-year">{m.esc(year)}</span><span class="{paper_class}">{m.esc(paper)}</span></h1>'
                    '<div class="sub">高考英语真题<b>原文精读</b></div>'
                    '<div class="meta">真题原声 · 逐句翻译 · 词汇短语</div></div>' +
                    '<script>document.fonts.ready.then(' + m.GK_COVER_FIT + ');</script>')
    m.title_slide = cover
    m.GK_COVER_FIT = """() => {const e=document.querySelector('.gk-paper');if(!e)return;
      const limit=930;let size=174;const r=document.createRange();r.selectNodeContents(e);
      while(r.getBoundingClientRect().width>limit&&size>76){size-=2;e.style.setProperty('--gk-paper-size',size+'px');}
      return size;}"""
    def switch_time(audio, it, en, cut):
        # 高考定稿直接绑定原始逐词ASR下标，不在每次试排时重新识别同一句。
        aligned = it.get('word_alignment') or []
        later = [w for w in aligned if w['char'] >= cut]
        if not later:
            raise SystemExit(f'分屏起点无法定位：{en[cut:cut+30]}')
        t = later[0]['start']
        gaps = list(zip([x[1] for x in it['parts']], [x[0] for x in it['parts'][1:]]))
        near = [(a+b)/2 for a,b in gaps if abs((a+b)/2-t) <= .35]
        return min(near, key=lambda x: abs(x-t)) if near else t
    m.switch_time = switch_time
    return m
