"""从交付ZIP和最终PDF截取真实内容，排成小店商品展示图。

不生成或重写PDF内页；真实页面及局部由PyMuPDF直接渲染，外框由浏览器截图。
python 真实展示.py --sample | --build
"""
import argparse
import functools
import hashlib
import html
import http.server
import json
import re
import shutil
import threading
import zipfile
from contextlib import contextmanager
from pathlib import Path

import fitz
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
D = HERE.parent
ROOT = D.parents[1]
WORK = HERE / 'work' / '真实展示'
PNG = WORK / '原始截图'
PENDING = WORK / '新商品图'
SIZE = 2000
M = json.loads((D / '分套资料清单与核验.json').read_text('utf-8')) if (D / '分套资料清单与核验.json').exists() else None
CASE = None if M is None else next(r for r in M['cases'] if r['id']=='2026-xkb1')
E = html.escape
ORDER = [
    ('cards', '04_真实内页_汉译英听写卡.png', '汉译英听写卡', 1, 1, (43, 220, 555, 730)),
    ('vocab', '05_真实内页_词汇与短语讲解.png', '词汇与短语讲解', 1, 1, (43, 228, 510, 728)),
    ('reading', '06_真实内页_原文双语精读.png', '原文双语精读', 1, 1, (43, 198, 410, 729)),
    ('practice', '07_真实内页_听力练习册.png', '听力练习册', 1, 1, (43, 222, 410, 740)),
    ('dictation', '08_真实内页_听写训练本.png', '原文听写训练本', 1, 1, (43, 152, 410, 683)),
    ('cardanswers', '09_真实内页_汉译英听写答案.png', '汉译英听写卡答案', 1, 1, (43, 220, 555, 730)),
    ('dictanswers', '10_真实内页_听写训练答案.png', '原文听写答案', 1, 1, (43, 151, 410, 682)),
    ('details', '11_真实内页_听力逐题详解.png', '听力逐题详解', 1, 1, (43, 198, 555, 790)),
    ('plan', '12_真实内页_本套复习记录表.png', '本套复习记录表', 1, 1, (43, 198, 510, 691)),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def source_files():
    assert M is not None and CASE is not None, '须先核对分套资料'
    for key, row in CASE['files'].items():
        p = D / '分套资料' / CASE['folder'] / row['file']
        assert p.is_file() and sha(p) == row['sha256'], key
    package = D / '下载包/GAOKAO-listening-materials.zip'
    assert package.exists(), '先运行讲义/tools/打包.py，取得实际交付ZIP'
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        rows = []
        pdfs = {r['file']: r for r in CASE['files'].values()}
        groups = {}
        for i in z.infolist():
            parts = Path(i.filename).parts
            name = Path(i.filename).name
            if len(parts) > 2:
                g = groups.setdefault(parts[1], {'name': parts[1], 'bytes': 0, 'pages': None, 'type': '文件夹', 'documents': 0})
                g['bytes'] += i.file_size
                g['documents'] += 1
                if parts[1]==CASE['folder']:
                    if name in pdfs:assert hashlib.sha256(z.read(i)).hexdigest() == pdfs[name]['sha256']
                    rows.append({'name':name,'bytes':i.file_size,'pages':pdfs[name]['pages'] if name in pdfs else None,'type':'PDF' if name in pdfs else Path(name).suffix[1:].upper()})
                continue
    pdf_rows = [r for r in rows if r['type'] == 'PDF']
    support = [r for r in rows if r['type'] != 'PDF']
    assert len(pdf_rows) == 9 and len(groups) == 50
    order={r['file']:i for i,r in enumerate(CASE['files'].values())}
    pdf_rows.sort(key=lambda r:order[r['name']])
    return pdf_rows + support, list(groups.values()), sha(package)


def render_source(key, page, detail_page, clip):
    row = CASE['files'][key]
    p = D / '分套资料' / CASE['folder'] / row['file']
    PNG.mkdir(parents=True, exist_ok=True)
    full = PNG / f'{key}_第{page}页.png'
    detail = PNG / f'{key}_第{detail_page}页_局部.png'
    with fitz.open(p) as d:
        assert len(d) == row['pages'] and 1 <= page <= len(d) and 1 <= detail_page <= len(d)
        rect = fitz.Rect(clip)
        assert d[detail_page - 1].rect.contains(rect)
        d[page - 1].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(full)
        d[detail_page - 1].get_pixmap(matrix=fitz.Matrix(2.5, 2.5), clip=rect, alpha=False).save(detail)
    return {'key': key, 'case_id': CASE['id'], 'case_folder': CASE['folder'], 'pdf': row['file'], 'pdf_sha256': row['sha256'], 'pages': row['pages'], 'page': page, 'detail_page': detail_page, 'clip': list(clip),
            'full_png': str(full.relative_to(HERE)), 'full_sha256': sha(full), 'detail_png': str(detail.relative_to(HERE)), 'detail_sha256': sha(detail)}


CSS = '''
*{box-sizing:border-box}html,body{margin:0;width:2000px;height:2000px;overflow:hidden}
body{font-family:'Noto Sans SC',sans-serif;background:#f6f3fa;color:#332b43}
.poster{width:2000px;height:2000px;padding:68px 70px 48px;position:relative;background:linear-gradient(150deg,#fbf9fd,#f2edf8)}
.top{display:flex;align-items:center;justify-content:space-between;color:#756385;font-size:27px;line-height:1.2}
.brand{font-weight:700;letter-spacing:3px}.label{border:1px solid #cbbedd;border-radius:999px;padding:10px 23px;font-size:25px;background:#ffffff99}
h1{font-size:67px;line-height:1.3;letter-spacing:1px;margin:23px 0 12px;font-weight:700}
.sub{font-size:30px;line-height:1.5;color:#7f728d;margin:0 0 28px}
.panes{display:grid;grid-template-columns:1015px 810px;gap:33px;height:1484px}
.pane{background:#fff;border:1px solid #d9d0e4;border-radius:19px;overflow:hidden;box-shadow:0 9px 35px #56436e10}
.toolbar{display:flex;align-items:center;justify-content:space-between;background:#fdfbff;border-bottom:1px solid #e5dfea;height:69px;padding:0 26px;color:#756383;font-size:26px}
.toolbar b{font-weight:500;color:#51415f}.dots{letter-spacing:8px;color:#b8a7c9}
.full{height:1410px;display:flex;align-items:center;justify-content:center;padding:0 10px;background:#eae7ef}
.full img{display:block;width:992px;height:1403px;object-fit:contain;box-shadow:0 2px 12px #44334d18;background:#fff}
.zoom{height:1170px;overflow:hidden;display:flex;align-items:flex-start;justify-content:flex-start;background:white}
.zoom img{display:block;width:808px;height:auto}
.detail-meta{padding:25px 28px;border-top:1px solid #e7dfee;background:#fbf9fd;height:244px}
.detail-meta p{margin:0 0 14px;line-height:1.5;font-size:28px;color:#7d6b8b}.detail-meta strong{display:block;color:#493653;font-size:33px;margin-bottom:15px}
.bottom{display:flex;justify-content:space-between;gap:35px;align-items:center;margin-top:27px;padding:22px 0 0;border-top:1px solid #dcd1e4;font-size:26px;color:#7c6b89}
.filename{max-width:1350px;white-space:nowrap}.pill{white-space:nowrap;background:#ede5f6;border-radius:10px;padding:12px 22px;font-size:24px;color:#715584}
/* 目录按实际ZIP文件生成，不虚构操作系统窗口。 */
.folder{height:1455px;background:white;border:1px solid #d6cbdf;border-radius:20px;overflow:hidden;box-shadow:0 12px 40px #5542680c}
.path{height:97px;display:flex;align-items:center;gap:24px;background:#fcfaff;padding:0 40px;border-bottom:1px solid #e3dbe9;font-size:34px;color:#665074}
.folder-icon{width:45px;height:31px;background:#c4b0dc;border-radius:5px;position:relative;display:inline-block}.folder-icon:before{content:'';position:absolute;top:-9px;left:0;width:23px;height:13px;background:#c4b0dc;border-radius:5px 5px 0 0}
.columns,.file-row{display:grid;grid-template-columns:1fr 115px 110px 150px;align-items:center;column-gap:15px;margin:0 42px}
.columns{height:75px;border-bottom:1px solid #e1d9e8;font-size:26px;color:#9988a6}
.file-row{height:91px;border-bottom:1px solid #f0eaf4;font-size:29px;color:#665872}
.file-row.support{height:62px;background:#fdfcfe;color:#9585a0;font-size:26px}
.file-row .name{display:flex;align-items:center;gap:18px;color:#493b56;white-space:nowrap}
.file-icon{display:inline-flex;width:55px;height:63px;border:1px solid #d4cadf;border-radius:6px;align-items:center;justify-content:center;font-family:Arial,sans-serif;font-size:18px;font-weight:700;color:#8b65a4;background:#f8f5fb}
.file-icon.pdf{color:#d95a35;background:#fff3ee;border-color:#efc2b6}
.num{text-align:right;font-size:25px}.kind{font-family:Arial,sans-serif;font-size:24px;color:#a28bad}
.folder-note{height:128px;border-top:1px solid #e9e1ef;background:#faf7fd;display:flex;align-items:center;justify-content:space-between;padding:0 43px;font-size:29px;color:#6e587f}
.folder-note span{font-size:25px;color:#9a89a7}
.suite-grid{display:grid;grid-template-columns:repeat(4,1fr);padding:24px 28px;gap:8px 12px}
.suite{height:81px;display:flex;gap:18px;align-items:center;border:1px solid #eee5f5;border-radius:11px;padding:8px 17px;background:#fdfbff}
.suite .folder-icon{flex:none;width:35px;height:27px}.suite .title{font-size:25px;line-height:1.25;white-space:nowrap;color:#584267}
.suite .year{font-size:22px;color:#a08aad}.aggregate{margin:0 40px;border-top:1px solid #e7dfee;padding:15px 5px;line-height:1.7;font-size:27px;color:#78618a}
'''


def page_shell(body, base):
    fonts = base + 'tools/video/themes/fonts/fonts.css'
    return '<!doctype html><html lang="zh"><head><meta charset="utf-8"><link rel="stylesheet" href="' + fonts + '"><style>' + CSS + '</style></head><body>' + body + '</body></html>'


def top(title, subtitle, label):
    return f'<div class="top"><span class="brand">朋克英语</span><span class="label">{E(label)}</span></div><h1>{E(title)}</h1><p class="sub">{E(subtitle)}</p>'


def source_url(base, relative):
    return base + (HERE / relative).relative_to(ROOT).as_posix()


def pdf_poster(row, title, base):
    different = row['page'] != row['detail_page']
    right = f'另一页：第{row["detail_page"]}页 · 错题复盘' if different else '同一页 · 局部放大'
    note = '计划表和错题记录来自同一份PDF的不同页面。' if different else '右侧直接放大左侧PDF页面的一部分。'
    display_filename = re.sub(r'^\d+\s+', '', row['pdf'])
    return '<main class="poster">' + top(title + '，打开后就是这样', CASE['folder']+' · 直接展示本套实际交付PDF的整页与局部。', '真实内页') + f'''
    <div class="panes">
      <section class="pane"><div class="toolbar"><b>整页预览</b><span>第{row['page']}页 / 共{row['pages']}页</span></div>
        <div class="full"><img class="source-image" src="{source_url(base,row['full_png'])}" alt="真实PDF整页"></div></section>
      <section class="pane"><div class="toolbar"><b>{E(right)}</b><span class="dots">···</span></div>
        <div class="zoom"><img class="source-image" src="{source_url(base,row['detail_png'])}" alt="真实PDF局部放大"></div>
        <div class="detail-meta"><strong>截图直接取自交付PDF</strong><p>{E(note)}</p><p>页面文字与文件内容一致。</p></div></section>
    </div>
    <div class="bottom"><span class="filename">{E(display_filename)}</span><span class="pill">PDF电子资料 · 可自行打印</span></div></main>'''


def size_label(n):
    return f'{n/1048576:.2f} MB' if n >= 1048576 else f'{max(1,round(n/1024))} KB'


def folder_poster(files):
    body = '<main class="poster">' + top('打开一套，这些资料都为你配齐', '下方文件名、格式、页数与大小均来自实际交付包。', '本套文件清单')
    body += '<section class="folder"><div class="path"><span class="folder-icon"></span>'+E(CASE['folder'])+'</div><div class="columns"><span>文件名称</span><span>格式</span><span class="num">页/份</span><span class="num">大小</span></div>'
    for r in files:
        is_pdf = r['type'] == 'PDF'
        is_dir = r['type'] == '文件夹'
        icon = 'Word' if is_dir else r['type']
        count = str(r['pages'])+'页' if is_pdf else str(r['documents'])+'份' if is_dir else '—'
        body += f'<div class="file-row {"" if is_pdf or is_dir else "support"}"><span class="name"><i class="file-icon {"pdf" if is_pdf else ""}">{E(icon)}</i>{E(r["name"])}</span><span class="kind">{E(r["type"])}</span><span class="num">{count}</span><span class="num">{size_label(r["bytes"])}</span></div>'
    body += '<div class="folder-note">9份配套PDF · 含两种听写各自的答案<span>另附对应原始Word与本套使用说明</span></div></section>'
    body += '<div class="bottom"><span>后续图片展示每一种PDF的真实内页。</span><span class="pill">电子文件交付 · 无纸质邮寄</span></div></main>'
    return body


def directory_poster(groups):
    body='<main class="poster">'+top('打开后，你会看到这些文件夹', '按年份、卷别与场次分套整理，练习到哪套，就打开哪套。', '实际交付目录')
    body+='<section class="folder"><div class="path"><span class="folder-icon"></span>高考英语听力资料包 · 本次50个对应文件夹</div><div class="suite-grid">'
    for r in groups:
        year,rest=r['name'].split('年 ',1)
        body+=f'<div class="suite"><span class="folder-icon"></span><div class="title"><span class="year">{E(year)}年</span><br>{E(rest)}</div></div>'
    body+='</div><div class="aggregate">另附：历年真题与解析_完整原始资料.zip<br>完整保留所供真题原卷、配套解析与补充听力原文；另有使用说明与实际收录清单。</div></section>'
    return body+'<div class="bottom"><span>2019—至今 · 持续更新</span><span class="pill">每套资料对应同一年份与卷别</span></div></main>'


@contextmanager
def server():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(ROOT)))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_port}/'
    finally:
        httpd.shutdown()


def screenshot(pg, base, name, body):
    assert '解压后' not in body
    document = WORK / (name + '.html')
    document.write_text(page_shell(body, base), 'utf-8')
    pg.goto(base + document.relative_to(ROOT).as_posix(), wait_until='load')
    pg.evaluate('document.fonts.ready')
    pg.wait_for_function('Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)')
    failures = pg.evaluate('''() => {
      const out=[];for(const e of document.querySelectorAll('h1,.filename,.file-row,.file-row .name,.columns,.bottom,.toolbar,.suite,.suite .title,.aggregate')){
        const r=e.getBoundingClientRect();if(e.scrollWidth>e.clientWidth+1||r.left<0||r.top<0||r.right>2001||r.bottom>2001)out.push(e.textContent.slice(0,80));
      }for(const e of document.querySelectorAll('.folder')){if(e.scrollHeight>e.clientHeight+1)out.push('目录容器截断');}return out;
    }''')
    assert not failures, (name, failures)
    assert not pg.locator('.filename').count() or not re.match(r'^\d+\s', pg.locator('.filename').inner_text()), '图片左下角不显示排序序号'
    target = PENDING / name
    pg.screenshot(path=str(target))
    return target


def build(sample=False):
    files, groups, package_sha = source_files()
    PENDING.mkdir(parents=True, exist_ok=True)
    PNG.mkdir(parents=True,exist_ok=True)
    if not sample:
        for parent in [PENDING,PNG]:
            for stale in parent.glob('*.png'):stale.unlink()
    records, images = [], []
    with server() as base, sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        pg = browser.new_page(viewport={'width': SIZE, 'height': SIZE}, device_scale_factor=1)
        name = '02_打开后_50个对应文件夹.png'
        screenshot(pg,base,name,directory_poster(groups))
        images.append({'file':name,'reviewed':False,'review':'50个文件夹名来自本次实际ZIP，完整原始资料单独ZIP附根目录','source':'实际交付ZIP目录'})
        name = '03_打开一套_实际文件清单.png'
        screenshot(pg, base, name, folder_poster(files))
        images.append({'file': name, 'reviewed': False, 'review': '单套九份PDF及原始Word、使用说明均来自实际ZIP','source':'实际交付ZIP清单'})
        for key, name, title, page, dp, clip in ORDER[:1] if sample else ORDER:
            record = render_source(key, page, dp, clip)
            screenshot(pg, base, name, pdf_poster(record, title, base))
            records.append(record)
            images.append({'file': name, 'reviewed': False, 'review': '最终交付PDF整页与局部直接渲染，未改写截图内文字', 'source': record})
        browser.close()
    if sample:
        print('样张目录：', PENDING)
        return
    old = HERE / '成品'
    main = old / '01_主图_高考英语听力资料包.png'
    final = old / '13_电子资料交付与使用说明.png'
    for src, name in [(main, '01_主图_高考英语听力资料包.png'), (final, '13_电子资料交付与使用说明.png')]:
        shutil.copyfile(src, PENDING / name)
        images.append({'file': name, 'reviewed': True, 'review': '保留已确认的主图或电子交付说明，原图字节不改', 'source_sha256': sha(src)})
    images.sort(key=lambda row: row['file'])
    assert len(images) == 13
    for row in images:
        row['sha256'] = sha(PENDING / row['file'])
        row['bytes'] = (PENDING / row['file']).stat().st_size
    proof = {'version': '50套文件夹与汉译英听写卡版', 'materials_sha256': package_sha, 'image_count': 13, 'pdf_source_count': 9, 'sample_case':CASE['id'],'render_method': '最终PDF由PyMuPDF原样栅格化，浏览器只渲染外框与文件信息，不生成或重写PDF中的文字', 'folder_files': files,'suite_folders':groups,'images': images, 'pdf_sources': records}
    dump(WORK / '图文核对_待审.json', proof)
    print('待审：', len(images), '张商品图，单套九份PDF均有真实整页及局部展示。')
    print('确认截图后将新商品图替换成品，并写图文核对.json。')


def finalize():
    """仅在已逐张实看待审成品后调用；复制原图并登记核对结果。"""
    proof=json.loads((WORK/'图文核对_待审.json').read_text('utf-8'))
    assert proof['materials_sha256']==sha(D/'下载包/GAOKAO-listening-materials.zip')
    assert len(proof['images'])==13 and len(proof['pdf_sources'])==9
    assert {p.name for p in PENDING.glob('*.png')}=={r['file'] for r in proof['images']}
    for r in proof['images']:assert sha(PENDING/r['file'])==r['sha256']
    for row in proof['pdf_sources']:
        assert row['pdf_sha256']==CASE['files'][row['key']]['sha256']
    for parent in [HERE/'成品',HERE/'真实内页']:
        if parent.exists():shutil.rmtree(parent)
        parent.mkdir()
    for p in PENDING.glob('*.png'):shutil.copyfile(p,HERE/'成品'/p.name)
    real=HERE/'真实内页/本次展示原始截图';shutil.copytree(PNG,real)
    for row in proof['pdf_sources']:
        for field in ['full_png','detail_png']:
            row[field]=str((real/Path(row[field]).name).relative_to(HERE))
    by_key={r['key']:r for r in proof['pdf_sources']}
    for row in proof['images']:
        row['reviewed']=True
        row['review']+='；已实看字形、文字、裁切与对应文件信息'
        if isinstance(row.get('source'),dict):row['source']=by_key[row['source']['key']]
    dump(HERE/'图文核对.json',proof)
    doc=fitz.open()
    for row in proof['pdf_sources']:
        for field in ['full_png','detail_png']:
            page=doc.new_page(width=595.28,height=841.89)
            page.insert_image(fitz.Rect(24,24,571.28,817.89),filename=str(HERE/row[field]),keep_proportion=True)
    doc.set_metadata({'title':'高考英语听力九种PDF真实内页预览','author':'朋克英语'})
    doc.save(HERE/'真实内页预览.pdf',garbage=4,deflate=True)
    assert len(doc)==18
    print('已复制13张成品及18份真实截图，生成18页预览与核对记录。')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sample', action='store_true')
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--finalize',action='store_true',help='已逐张检查后复制待审图并登记核对')
    a = ap.parse_args()
    if a.finalize:finalize()
    else:build(sample=a.sample)
