"""把每篇文章做成与视频画面一模一样的 PDF（片头一页 + 每句一页，16:9）。

    /opt/ttsenv/bin/python tools/dictation/make_reading_pdf.py all       # 全部 70 篇
    /opt/ttsenv/bin/python tools/dictation/make_reading_pdf.py p01 …

直接调用 tools/video/make_video.py 里生成视频画面的同一套函数（title_slide、sentence_slide、
字号自动适配 FIT），所以版式、字体、颜色、高亮、生词条与视频完全一致。
输出到 听写卡/序号 年份 试卷 阅读C 题目/… - 0 逐句精读.pdf
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'video'), str(HERE)]
import make_video as mv                      # noqa: E402
from make_dictation import OUT, folder_name  # noqa: E402

PAGE = '<style>@page{size:1920px 1080px;margin:0}</style>'


def main():
    import json
    from playwright.sync_api import sync_playwright
    data = json.loads((mv.ROOT / 'data' / 'vocab.json').read_text('utf-8'))
    P = {p['id']: p for p in data['passages']}
    order = [p['id'] for p in data['passages'] if p.get('done')]
    pids = order if sys.argv[1:] == ['all'] else sys.argv[1:]
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        td = Path(td)
        exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': mv.W, 'height': mv.H})
        for pid in pids:
            p = P[pid]
            sents = [s for para in p['paras'] for s in para]
            slides = [mv.title_slide(p)] + [mv.sentence_slide(p, s, i + 1, len(sents)) for i, s in enumerate(sents)]
            parts = []
            for i, h in enumerate(slides):
                f = td / f'{pid}_{i:03d}.html'
                f.write_text(h.replace('</head>', PAGE + '</head>'), 'utf-8')
                pg.goto(f.as_uri())
                pg.evaluate('document.fonts.ready')
                if i:
                    pg.evaluate(mv.FIT)
                    fits = pg.evaluate("() => document.getElementById('box').scrollHeight <= document.querySelector('.stage').clientHeight")
                    if not fits:
                        raise SystemExit(f'{pid} 第 {i} 句放不下')
                out = td / f'{pid}_{i:03d}.pdf'
                pg.pdf(path=str(out), width='1920px', height='1080px', print_background=True,
                       margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'}, page_ranges='1')
                parts.append(str(out))
            folder = OUT / folder_name(p, order.index(pid) + 1)
            folder.mkdir(exist_ok=True)
            dst = folder / f'{folder_name(p)} - 0 逐句精读.pdf'
            subprocess.run(['pdfunite', *parts, str(dst)], check=True)
            print('已生成', dst, f'（{len(parts)} 页）', flush=True)
        br.close()


if __name__ == '__main__':
    main()
