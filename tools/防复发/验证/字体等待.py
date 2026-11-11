"""双向验证 + 检查：听力引擎等网页字体不许用 wait_for_function（踩坑 130）。
高考听力 GitHub precheck（run 42918571749）2019-shc、2019-xkb3、2020-shc 在 layout 里
pg.wait_for_function('document.fonts.status === "loaded"') 超时 30 秒；本机实测卡住时 document.fonts.status 早已是 loaded，
慢的是 wait_for_function 本身（偶尔 3—11 秒，GitHub 上 > 30 秒）。改成专八底座 fonts_loaded(pg)：
evaluate 等 document.fonts.ready、再核状态 = loaded（版式结果逐套不变，一套 layout 从 3—4 分钟降到约 1 分钟）。
  ① 专八底座与高考听力引擎里不许出现 wait_for_function 等字体；底座必须有 fonts_loaded 且用 document.fonts.ready；
  ② 旧写法（5ba6f7d 的两个文件）必须报出，现在 0 处；
  ③ 浏览器整页卡住（run 42929283819 的 2019-shq：goto 等 load 30 秒超时）：底座 Pager.load 超时就换新标签页重来。
     用一个会卡死的网页实测（要 /opt/ttsenv 的 playwright）：旧写法 goto 必须超时；卡一次后恢复 → Pager 重来 1 次成功；
     一直卡 → 重来 3 次后停下（SystemExit）。高考引擎的 layout、--自检 与底座 stills 都必须用 Pager.load。
    /opt/ttsenv/bin/python tools/防复发/验证/字体等待.py"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILES = ['专八/听力/tools/听力视频.py', '高考听力/tools/听力视频.py']
BAD = re.compile(r"""wait_for_function\(\s*['"][^'"]*document\.fonts\.status""")


def problems(texts):
    out = []
    for name, t in texts.items():
        for n, line in enumerate(t.splitlines(), 1):
            if BAD.search(line) and not line.lstrip().startswith('#'):
                out.append(f'{name}:{n}：用 wait_for_function 等字体（改用底座 fonts_loaded）')
    base = texts.get(FILES[0], '')
    m = re.search(r'\ndef fonts_loaded\(pg\):(.*?)\n(?=\S)', base, re.S)
    if not m or 'document.fonts.ready' not in m.group(1) or "'loaded'" not in m.group(1):
        out.append(f'{FILES[0]}：缺 fonts_loaded（evaluate document.fonts.ready 并核 loaded）')
    for name, fn in ((FILES[1], 'def layout'), (FILES[1], 'def selftest'), (FILES[0], 'def stills')):
        t = texts.get(name, '')
        m = re.search(r'\n' + fn + r'\(.*?(?=\ndef |\Z)', t, re.S)
        if not m or 'Pager(' not in m.group(0) or '.load(' not in m.group(0) or '.goto(' in m.group(0):
            out.append(f'{name}：{fn[4:]} 没用 Pager.load 打开网页')
    return out


def hang_test():
    sys.path.insert(0, str(ROOT / '专八/听力/tools'))
    sys.argv = ['x', '--自检']
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    import importlib.util
    spec = importlib.util.spec_from_file_location('base8', ROOT / FILES[0]); base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
    import tempfile
    d = Path(tempfile.mkdtemp()); f = d / 'p.html'
    HANG = '<!doctype html><body>x<script>for(;;){}</script>'
    OK = '<!doctype html><body>ok'
    bad = []

    class T(base.Pager):
        def new(self):
            super().new(); self.pg.set_default_timeout(1500)
            if self.heal and self.retries >= 1: f.write_text(OK)
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        f.write_text(HANG)
        pg = br.new_page(); pg.set_default_timeout(1500)
        try: pg.goto(f.as_uri()); bad.append('旧写法：卡死的网页 goto 没超时（测不出）')
        except PWTimeout: print('③ 旧写法 goto 超时 ✅')
        T.heal = True; P = T(br)
        try:
            P.load(f.as_uri()); print(f'③ 卡一次后恢复：重来 {P.retries} 次成功', '✅' if P.retries == 1 else '❌')
            if P.retries != 1: bad.append(f'卡一次重来 {P.retries} 次')
        except SystemExit: bad.append('卡一次后恢复却停下了')
        f.write_text(HANG); T.heal = False; P = T(br)
        try: P.load(f.as_uri()); bad.append('一直卡却加载成功')
        except SystemExit: print(f'③ 一直卡：重来 {P.retries} 次后停下', '✅' if P.retries == 3 else '❌'); bad += [] if P.retries == 3 else ['重来次数不对']
        br.close()
    return bad


def main():
    now = {f: (ROOT / f).read_text('utf-8') for f in FILES}
    old = {f: subprocess.run(['git', '-C', str(ROOT), 'show', f'5ba6f7d:{f}'], capture_output=True, text=True, check=True).stdout
           for f in FILES}
    pn, po = problems(now), problems(old)
    print(f'旧写法（5ba6f7d）{len(po)} 处（应 ≥ 5），现在 {len(pn)} 处（应 0）')
    for p in pn: print('  ', p)
    hb = hang_test()
    for p in hb: print('  ', p)
    sys.exit(0 if len(po) >= 5 and not pn and not hb else 1)


if __name__ == '__main__':
    main()
