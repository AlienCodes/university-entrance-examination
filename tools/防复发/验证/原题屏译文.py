"""踩坑 82 双向验证：四级作文视频原题屏的「题目译文」（专八/tools/make_video.py：prompt_zh_problems、PROMPT_JS 的译文检查、PO_JS）。
① 画面文字与讲义 题目译文 逐字相同：完整 0 处；拿掉一条、改一个字都要报出（纯 Python）。
② 排版（要浏览器）：现在 32 篇 0 处；英文整段不断开（旧规则）时报“题目译文短行”；不跑 PO_JS 时报“行首没有去掉左半空白”。"""
import importlib.util, json, os, sys, tempfile
from pathlib import Path
R = Path(__file__).resolve().parents[3]
PY = '/opt/ttsenv/bin/python'
if sys.executable != PY and Path(PY).exists() and not os.environ.get('YT_REEXEC'):
    os.environ['YT_REEXEC'] = '1'
    os.execv(PY, [PY, __file__] + sys.argv[1:])
spec = importlib.util.spec_from_file_location('make_video', R / '专八/tools/make_video.py')
M = importlib.util.module_from_spec(spec); sys.modules['make_video'] = M; spec.loader.exec_module(M)
M.set_project('四级作文'); M.set_style(M.PJ['look'])
P = {p['id']: p for p in json.loads((M.C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
ok = True
ls = M.prompt_zh_lines(P['c32'])
for name, shown, want in (('完整', ''.join(ls), 0), ('拿掉一条', ''.join(ls[1:]), 1), ('改一个字', ''.join(ls).replace('暴力', '暴利', 1), 1)):
    n = len(M.prompt_zh_problems(shown, ls))
    print(f'文字「{name}」：{n} 处'); ok &= (n > 0) == bool(want)
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print('没有 playwright，排版部分跳过'); sys.exit(0 if ok else 1)


def run(pids):
    n = 0
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(); pg = br.new_page(viewport={'width': 1920, 'height': 1080})
        for pid in pids:
            for i, label, fit, res in M.layout(pg, P[pid], Path(td) / 'x.html'):
                if label == '原题':
                    n += len([x for x in M.screen_checks(pg, label, fit, res) if '题目译文' in x]); break
        br.close()
    return n


ALL = sorted(P)
n = run(ALL); print(f'现在 {len(ALL)} 篇：{n} 处'); ok &= n == 0
zh0 = M.zh_html
M.zh_html = lambda s, gloss=False, latin_words=False: zh0(s, gloss)          # 旧规则：英文整段不断开
n = run(['c03', 'c11', 'c32']); print(f'雷「英文整段不断开」：{n} 处'); ok &= n > 0
M.zh_html, po0 = zh0, M.PO_JS
M.PO_JS = '() => 0'                                                          # 不去行首左半空白
n = run(ALL); print(f'雷「不跑 PO_JS」：{n} 处'); ok &= n > 0
print('自检通过' if ok else '自检失败')
sys.exit(0 if ok else 1)
