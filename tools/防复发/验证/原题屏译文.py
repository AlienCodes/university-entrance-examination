"""踩坑 82、83 双向验证：四级作文、六级作文视频原题屏「原题（排版英文 + 图表截图）+ 题目译文」（专八/tools/make_video.py：
prompt_zh_problems、prompt_en_problems、PZ_FIT、PZ_JS）。
① 文字（纯 Python）：译文与讲义 题目译文、英文与题目数据 prompt 逐字相同 → 0 处；拿掉一条 / 一段、改一个字、改引号都要报出。
② 排版（要浏览器）：现在两个项目全部篇目 0 处；把字缩小（原题英文低于下限）、不避开短行、不去行首左半空白、图表放小，都要报出。"""
import importlib.util, json, os, sys, tempfile
from pathlib import Path
R = Path(__file__).resolve().parents[3]
PY = '/opt/ttsenv/bin/python'
if sys.executable != PY and Path(PY).exists() and not os.environ.get('YT_REEXEC'):
    os.environ['YT_REEXEC'] = '1'
    os.execv(PY, [PY, __file__] + sys.argv[1:])
spec = importlib.util.spec_from_file_location('make_video', R / '专八/tools/make_video.py')
M = importlib.util.module_from_spec(spec); sys.modules['make_video'] = M; spec.loader.exec_module(M)
ok = True


def proj(name):
    M.set_project(name); M.set_style(M.PJ['look'])
    return {p['id']: p for p in json.loads((M.C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}


def want(name, n, exp):
    global ok
    good = (n > 0) == exp
    print(f'{name}：{n} 处{"" if good else "  ← 不对！"}'); ok &= good


P = proj('四级作文')
ls = M.prompt_zh_lines(P['c32'])
for name, shown, exp in (('完整', ''.join(ls), False), ('拿掉一条', ''.join(ls[1:]), True), ('改一个字', ''.join(ls).replace('暴力', '暴利', 1), True)):
    want(f'译文「{name}」', len(M.prompt_zh_problems(shown, ls)), exp)
bl = M.prompt_en_blocks(P['c32'])[0]
for name, shown, exp in (('完整', bl, False), ('拿掉一段', bl[:1], True), ('改一个字', [bl[0].replace('violent', 'violet', 1)] + bl[1:], True),
                         ('弯引号改直引号', [bl[0].replace('“', '"', 1)] + bl[1:], True)):
    want(f'英文「{name}」', len(M.prompt_en_problems(shown, bl)), exp)
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print('没有 playwright，排版部分跳过'); sys.exit(0 if ok else 1)


def run(name, pids=None, key='原题屏'):
    P = proj(name); n = 0
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(); pg = br.new_page(viewport={'width': 1920, 'height': 1080})
        for pid in pids or sorted(P):
            for i, label, fit, res in M.layout(pg, P[pid], Path(td) / 'x.html'):
                if label == '原题':
                    n += len([x for x in M.screen_checks(pg, label, fit, res) if key in x]); break
        br.close()
    return n


for name in ('四级作文', '六级作文'):
    want(f'现在 {name} 全部', run(name), False)
FIT0 = M.PZ_FIT
M.PZ_FIT = FIT0.replace('hi = 90', 'hi = 30')                         # 字缩小：英文最大 30px
want('雷「原题字缩小」（六级 c01、四级 c24）', run('六级作文', ['c01'], '低于下限') + run('四级作文', ['c24'], '低于下限'), True)
M.PZ_FIT = FIT0.replace('if (!shorts())', 'if (true)')                # 不避开短行
want('雷「不避开短行」（六级 c11、c29）', run('六级作文', ['c11', 'c29'], '短行'), True)
M.PZ_FIT = FIT0.replace(M.PO_JS, '() => 0')                           # 不去行首左半空白
want('雷「不跑 PO_JS」（四级、六级全部）', run('四级作文', key='左半空白') + run('六级作文', key='左半空白'), True)
M.PZ_FIT = FIT0.replace(f'{M.PZ_CHMIN} * G.width - 0.5); }};', '0); };')       # 排版时不管图表大小
want('雷「图表放小」（六级 c30、c31）', run('六级作文', ['c30', 'c31'], '图表截图太小'), True)
M.PZ_FIT = FIT0
print('自检通过' if ok else '自检失败')
sys.exit(0 if ok else 1)
