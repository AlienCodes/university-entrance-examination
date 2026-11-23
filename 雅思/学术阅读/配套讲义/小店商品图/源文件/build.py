"""Render the square shop gallery using only pages from the verified student ZIP."""
import argparse
import base64
import hashlib
from html import escape
import json
import re
from pathlib import Path
import shutil
import tempfile
import zipfile

import fitz
from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
FILES = ('01-商品主图.jpg', '02-视频同款PDF.jpg', '03-逐题解析.jpg', '04-长难句与写作句式.jpg', '05-打开后的文件.jpg')
ZIP = 'IELTS-21-14-Shop-Images.zip'
SIDE = 1600


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def header():
    return '<div class="cap"><span>剑桥雅思学术阅读讲义</span><span>第 21–14 册</span></div>'


def heading(document, title, lead):
    return (header() + '<div class="dhead"><div class="file">' + document +
            '</div><h1>' + title + '</h1><p class="lead">' + lead + '</p></div>')


def specimen(image, label, locator):
    return (f'<div class="specimen"><div class="spec-head"><span>{label}</span>'
            f'<span class="loc">{locator}</span></div><img class="crop" src="{image}"></div>')


def bottom(left, right):
    return f'<div class="bottom"><span>{left}</span><span>{right}</span></div>'


def export_pdf(doc, page, crop, dest, scale=2.8):
    pg = doc[page]
    clip = fitz.Rect(crop) if crop else pg.rect
    if not pg.rect.contains(clip):
        raise ValueError(f'PDF crop outside page: {dest.name}')
    pg.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False).save(dest)


def source_images(archive, ledger, work):
    index = {row['lesson']: row for row in ledger['contents']}
    docs = {}
    for pid, names in [('C21T1P1', ('逐题解析', '长难句与写作句式', '视频逐屏讲义')),
                       ('C20T1P1', ('视频逐屏讲义',))]:
        row = index[pid]
        for name in names:
            filename = name + '.pdf'
            meta = next(f for f in row['files'] if f['name'] == filename)
            data = archive.read(row['folder'] + '/' + filename)
            if hashlib.sha256(data).hexdigest() != meta['sha256']:
                raise ValueError('Student PDF differs from published ledger: ' + filename)
            doc = fitz.open(stream=data, filetype='pdf')
            if len(doc) != meta['pages']:
                raise ValueError('Unexpected page count: ' + filename)
            docs[pid, name] = doc
    one = docs['C21T1P1', '逐题解析']
    two = docs['C21T1P1', '长难句与写作句式']
    if 'mining' not in one[0].get_text() or 'evidence now suggests' not in two[0].get_text():
        raise ValueError('Page content changed')
    export_pdf(one, 0, (38, 157, 557, 364), work / 'answer.png')
    export_pdf(two, 0, (39, 335, 555, 563), work / 'syntax.png')
    export_pdf(docs['C20T1P1', '视频逐屏讲义'], 55, None, work / 'parrot.jpg', 1.7)
    for i, name in enumerate(('逐题解析', '长难句与写作句式', '视频逐屏讲义')):
        export_pdf(docs['C21T1P1', name], 1 if i == 2 else 0, None, work / f'thumb{i}.jpg', .75)
    for doc in docs.values():
        doc.close()
    return index


def pages(index):
    cover = """<div class="cover-top"><img class="glass" src="glass-cover.jpg">
<div class="cap"><span>剑桥雅思 · 学术阅读</span><span class="series-badge">第 21–14 册</span></div>
<div class="cover-title"><h1>视频同款 <b>PDF</b></h1><div class="subtitle">逐屏精读讲义</div><p class="pitch">视频一屏，讲义一页。<br>英文原文、译文和词义同页对照。</p></div>
<figure class="front-page"><figcaption>交付版 PDF · 真实内页</figcaption><img src="parrot.jpg"><div>《鸮鹦鹉》 · 精读第 51 句</div></figure></div>
<div class="stats"><div><strong>90</strong><span>篇阅读</span></div><div><span>每篇</span><strong>3</strong><span>份 PDF</span></div></div>
<section class="index first-delivery"><div class="folder-reveal"><div class="folder-preface"><div class="folder-caption">真实文件夹截图</div><h2>打开一篇，<br>就是这三份。</h2><p>以《戴维斯姐妹》为例</p></div><img class="folder-image" src="folder-student.png"></div>
<div class="uses"><div><h3>视频同款 PDF</h3><p>对照视频原画面，<br>复习原句、译文和词义。</p></div><div><h3>逐题解析</h3><p>按题干找到原文，<br>看懂答案的推理过程。</p></div><div><h3>长难句与写作句式</h3><p>拆出主干，理清从句，<br>跟着双语例句练仿写。</p></div></div></section>
<div class="cover-foot"><span>按册号、Test 和 Passage 查找</span><span>每篇独立文件夹</span></div>"""
    answer = heading('逐题解析.pdf', '这一空为什么填 <em>mining</em>？', '从题干的同义改写，找到原文里被问到的那一项。')
    answer += specimen('answer.png', '交付版内页 · 第 1 页节选', '21-1-1 戴维斯姐妹 · 第 1 题')
    answer += """<div class="hinge"><h2>这道题的关键</h2><p>题干的 <b>transportation businesses</b> 对应原文的 <b>shipping</b>。<br>祖父的财富来自两个行业，空格要填另一项 <b>mining</b>。</p></div>"""
    answer += bottom('适合做完一篇后订正错题', '每道题沿用原书题号')
    syntax = heading('长难句与写作句式.pdf', '读懂长句，再写进作文', '同一个句式，从阅读原句走到具体的 Task 2 写作场景。')
    syntax += specimen('syntax.png', '交付版内页 · 第 1 页节选', '21-1-1 戴维斯姐妹 · 精读第 9 句')
    syntax += """<div class="lesson-note"><h2>试着用这个结构表达“过去与现在的认识”</h2><p><b>While</b> 引出过去的看法，主句交代新的认识。例句讨论偏远地区的网课，用 <b>may</b> 保留推测的语气。</p></div>"""
    syntax += bottom('含主从句关系、可复用句式、例句与中译', '适合精读后做仿写')
    slides = heading('视频同款 PDF · 视频逐屏讲义.pdf', '视频一屏，PDF 一页', '英文高亮、下方译文和右栏词义，都和视频画面一样。')
    slides += specimen('parrot.jpg', '交付版原画面 · 第 56 / 57 页', '20-1-1 鸮鹦鹉 · 精读第 51 句')
    slides += """<div class="lesson-note"><p>例如 <b>accommodate</b> 在这里是“为……留出空间”，可直接对照译文里的“为鸮鹦鹉种群的预期增长留出空间”。</p></div>"""
    slides += bottom('可以边看边跟读，也可以单独翻页复习', '长句按视频意群分屏')
    library = heading('真实文件夹截图', '打开一篇，三个文件都在这里', '以「21-1-1 戴维斯姐妹」为例，下面是直接打开交付文件夹的画面。')
    library += specimen('folder-student.png', '文件夹原样 · 按大小排列', '21-1-1 戴维斯姐妹')
    library += '<div class="file-gallery"><h2>打开这三个文件，分别是这些页面</h2><div class="file-previews">'
    for i, label, purpose in ((2,'视频逐屏讲义','跟视频看原文、译文和词义'),(0,'逐题解析','定位证据，订正错题'),(1,'长难句与写作句式','拆句并练习写作')):
        f = index['C21T1P1']['files'][i]
        if f['name'] != label + '.pdf':
            raise ValueError('Actual student filenames changed')
        library += (f'<div><div class="page-piece"><img src="thumb{i}.jpg"></div>'
                    f'<h3>{escape(label)}<span> · {f["pages"]}页</span></h3><p>{purpose}</p></div>')
    library += '</div></div>'
    library += bottom('21-1-1 即第 21 册 · Test 1 · Passage 1', '所示页数为本篇实数')
    return zip(('', 'detail wordflow', 'detail answer', 'detail structure', 'detail directory'),
               (cover, slides, answer, syntax, library), strict=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--ledger', type=Path, default=HERE.parent.parent / '讲义打包核验.json')
    parser.add_argument('--output', type=Path, default=HERE.parent)
    args = parser.parse_args()
    ledger = json.loads(args.ledger.read_text())
    if (ledger['passages'], ledger['questions'], ledger['files']) != (96,1280,288) or sha(args.archive) != ledger['zip_sha256']:
        raise ValueError('Unexpected student edition')
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td, zipfile.ZipFile(args.archive) as archive, sync_playwright() as pw:
        work = Path(td)
        shutil.copy(HERE / 'glass-cover.jpg', work)
        shutil.copy(HERE / 'folder-student.png', work)
        shutil.copy(HERE / 'gallery.css', work)
        index = source_images(archive, ledger, work)
        browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1000,'height':1000},device_scale_factor=SIDE/1000)
        items = []
        layout_issues = []
        for name, (css, body) in zip(FILES, pages(index), strict=True):
            def inline(match):
                photo = work / match[1]
                mime = 'image/png' if photo.suffix == '.png' else 'image/jpeg'
                data = base64.b64encode(photo.read_bytes()).decode('ascii')
                return f'src="data:{mime};base64,{data}"'
            content = re.sub(r'src="([^"]+)"', inline, body)
            sheet = (work / 'gallery.css').read_text()
            page.set_content(f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>{sheet}</style><main class="{css}">{content}</main></html>', wait_until='load')
            page.evaluate('document.fonts.ready')
            geometry = page.evaluate("""() => {
              const rect = e => e.getBoundingClientRect();
              const footer = document.querySelector('.bottom,.cover-foot'), mainBody=document.querySelector('.lesson-note,.hinge,.index,.file-gallery');
              return {missing:[...document.images].filter(i=>!i.complete || !i.naturalWidth).length,
                gap:rect(footer).top-rect(mainBody).bottom,overflow:[...document.querySelectorAll('.cap,.dhead,.file-row,.library,.index,.row,.lesson-note,.hinge,.stats,.openfolder')].filter(e=>e.scrollWidth>e.clientWidth+2).map(e=>e.className)};
            }""")
            if geometry['missing'] or geometry['gap'] < 6 or geometry['overflow']:
                layout_issues.append(f'{name}: {geometry}')
            dest = args.output / name
            page.screenshot(path=str(dest), type='jpeg', quality=94)
            with Image.open(dest) as frame:
                if frame.size != (SIDE, SIDE) or frame.format != 'JPEG':
                    raise ValueError('Unexpected image size or format')
                frame.verify()
            items.append(dict(file=name,width=SIDE,height=SIDE,bytes=dest.stat().st_size,sha256=sha(dest)))
            print(name, geometry['gap'], dest.stat().st_size, flush=True)
        browser.close()
        if layout_issues:
            raise ValueError(layout_issues)
    with zipfile.ZipFile(args.output / ZIP, 'w', compression=zipfile.ZIP_STORED) as packed:
        for name in FILES:
            info=zipfile.ZipInfo(name,(2026,11,23,0,0,0))
            info.external_attr=0o100644<<16
            packed.writestr(info,(args.output/name).read_bytes())
    with zipfile.ZipFile(args.output/ZIP) as packed:
        if packed.namelist()!=list(FILES) or packed.testzip() is not None:
            raise ValueError('Invalid image gallery ZIP')
    (args.output / '核验.json').write_text(json.dumps(dict(source_sha256=ledger['zip_sha256'], displayed_passages=90, delivered_passages=ledger['passages'], folder_capture={'app':'Thunar', 'source':index['C21T1P1'], 'capture_sha256':sha(HERE/'folder-student.png')}, images=items, zip_sha256=sha(args.output/ZIP)),ensure_ascii=False,indent=2)+'\n')


if __name__ == '__main__':
    main()
