"""先审截图，后生成视频（CLAUDE.md 踩坑 36）：视频生成最费时间，排版问题必须在截图阶段查完，不能等视频做好再返工。

    shots   <截图目录> z01 …   用生成视频的同一程序画出每一屏的截图（1920×1080，与 extract.py 截的视频画面同尺寸），并写参考文件 ref/zNN.txt，
                                交给排版审阅员（zk-frame-qa.js 的 frames/ref 参数）和 canary_layout.py（埋雷）
    approve z01 …              截图审阅通过后登记：记下每篇的“程序指纹”（make_video.py、样式.css、字体、分屏方案、该篇定稿数据）
    check   z01 …              make_video.py 生成前自动调用：指纹没有登记（程序或数据改过、截图还没审）就拒绝生成

指纹登记在 中考/tools/画面核查/截图审阅通过.json。
专八（大字版，2026-10-16 起与中考共用本程序）：加 --project 专八，如 screens_fp.py --project 专八 shots <目录> t03；
专八的登记在 专八/tools/画面核查/截图审阅通过.json，专八 make_video.py 生成前自动调用 check。
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]
PROJ = '中考'
T = R / PROJ / 'tools'
REG = T / '画面核查' / '截图审阅通过.json'


def fingerprint(pid):
    h = hashlib.sha256()
    for f in [T / 'make_video.py', T / '样式.css', T / 'fonts' / 'fonts.css']:
        h.update(f.read_bytes())
    P = {p['id']: p for p in json.loads((R / PROJ / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
    split = json.loads((T / '分屏.json').read_text('utf-8')).get(pid, {})
    h.update(json.dumps([P[pid], split], ensure_ascii=False, sort_keys=True).encode())
    return h.hexdigest()[:16]


def main():
    global PROJ, T, REG
    from layoutcheck import project
    PROJ, T, argv = project(sys.argv[1:])
    REG = T / '画面核查' / '截图审阅通过.json'
    cmd, args = argv[0], argv[1:]
    reg = json.loads(REG.read_text('utf-8')) if REG.exists() else {}
    if cmd == 'check':
        bad = [pid for pid in args if reg.get(pid) != fingerprint(pid)]
        if bad:
            raise SystemExit(f'{bad} 的截图还没有审阅通过（程序或数据改过之后必须先审截图）：\n'
                             f'  screens_fp.py shots <目录> {" ".join(bad)} → 排版审阅员 + 埋雷 + 大写 I 等改动处放大逐个看 → screens_fp.py approve {" ".join(bad)}')
    elif cmd == 'approve':
        for pid in args:
            reg[pid] = fingerprint(pid)
        REG.write_text(json.dumps(dict(sorted(reg.items())), ensure_ascii=False, indent=1) + '\n', 'utf-8')
        print('已登记', args)
    elif cmd == 'shots':
        sys.path.insert(0, str(T))
        import make_video as M
        from playwright.sync_api import sync_playwright
        from layoutcheck import screens
        out, ids = Path(args[0]), args[1:]
        P = {p['id']: p for p in json.loads((R / PROJ / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
        with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
            br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
            pg = br.new_page(viewport={'width': M.W, 'height': M.H})
            f = Path(td) / 'x.html'
            for pid in ids:
                d = out / pid
                d.mkdir(parents=True, exist_ok=True)
                for x in d.glob('screen*.png'):
                    x.unlink()
                for n, (_, h, fit) in enumerate(screens(M, P[pid]), 1):
                    f.write_text(h, 'utf-8')
                    pg.goto(f.as_uri())
                    pg.evaluate('document.fonts.ready')
                    if fit:
                        pg.evaluate(M.FIT)
                    pg.screenshot(path=str(d / f'screen{n:02d}.png'))
                print(pid, n, '屏', flush=True)
            br.close()
        subprocess.run([sys.executable, str(HERE / 'prep.py'), '--project', PROJ, str(out), *ids, '--ref-only'], check=True)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
