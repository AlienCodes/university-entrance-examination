"""字号标定：按实际用的字体实测，定出专八每种画面（C、1–6）的起始字号、下限和译文、词条的相对字号，写进 字号.json（make_video.py 读取）。

用户 2026-10-16：专八的字要放大，“跟中考差不多大”。同样 64px，不同字体看上去大小差很多（EB Garamond 的 x 高度只有字号的 0.42，
中考的 Nunito 是 0.52），所以不按字号、按“看上去的大小”对齐：
  英文、词条   x 高度（小写 x 的高度，决定西文看上去多大）
  译文、释义   中文字面（常用字 100 个的墨迹高、宽的平均，楷体字面小、黑体字面大）
参照：中考典型的一屏（40 篇全部句子屏实测：英文字号、词汇栏字号取中位数，紫黄撞色样式）。
每种画面每类文字取：max(与中考看上去一样大, 这种画面原来的设计大小)——只放大、不缩小：
  英文起始字号 fs0 = max(中考英文 x 高度 ÷ 本样式英文字体 x 高度比, 64)
  词汇栏起始字号 vs0 = max(中考释义字面 ÷ 本样式释义字体字面比, 40)
  译文 = max(中考译文字面 ÷ 本样式译文字体字面比, 原设计倍数 × 64)，写成英文字号的倍数 zh_k
  词条 = max(中考词条 x 高度 ÷ 本样式词条字体 x 高度比, 原设计倍数 × 40)，写成词汇栏字号的倍数 hw_k
下限：英文 min_fs = fs0（英文从不缩小，与中考一样每屏同样大；放不下就分屏），词汇栏 min_vs = round(0.85 × vs0)（中考 95% 的屏不小于中位数的 0.85）。

    /opt/ttsenv/bin/python 专八/tools/字号标定.py            # 用 字号.json 里存的中考实测中位数，重新量专八各画面的字体，重写 字号.json
    /opt/ttsenv/bin/python 专八/tools/字号标定.py --sweep    # 先把中考 40 篇全部句子屏重新适配一遍，重新取中位数（约 4 分钟）
    /opt/ttsenv/bin/python 专八/tools/字号标定.py --check    # 只核对 字号.json 与实测一致（样片.py 每次截图前调用，字体或样式改了就报错）
"""
import importlib.util
import json
import statistics
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[1]
OUT = HERE / '字号.json'
SAMPLE = ('的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动同工也能下过子说产种面而方后多定行学法所民得经'
          '十三之进着等部度家电力里如水化高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那社义事平形相全')
# 量字体（按 1000px 量，canvas 的墨迹量到整像素，100px 时只有 1% 精度）：x 高度比（字号 1px 时 x 的墨迹高度）、中文字面比（常用字墨迹高、宽平均）；el 的计算样式决定用哪个字体（与画面完全相同）
MEASURE = """async ([sel, sample]) => { const e = document.querySelector(sel), cs = getComputedStyle(e), px = parseFloat(cs.fontSize);
  const font = `${cs.fontStyle} ${cs.fontWeight} 1000px ${cs.fontFamily}`; await document.fonts.load(font, 'x' + sample);
  const g = document.createElement('canvas').getContext('2d'); g.font = font;
  const x = g.measureText('x'); let f = 0;
  for (const c of sample) { const m = g.measureText(c); f += ((m.actualBoundingBoxAscent + m.actualBoundingBoxDescent) + (m.actualBoundingBoxRight + m.actualBoundingBoxLeft)) / 2; }
  return {family: cs.fontFamily, weight: cs.fontWeight, px, xh: x.actualBoundingBoxAscent / 1000, face: f / sample.length / 1000}; }"""
SEL = {'en': '.en', 'zh': '.zh', 'hw': '.v b', 'gl': '.v span[lang]'}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).parent))
    spec.loader.exec_module(m)
    sys.path.pop(0)
    return m


def open_page(pg, f, h, fs, vs, drop_sizes=False):
    f.write_text(h, 'utf-8')
    pg.goto(f.as_uri())
    pg.evaluate('document.fonts.ready')
    if drop_sizes:            # 量原设计倍数时去掉 字号.json 的覆盖
        pg.evaluate("() => { const s = document.getElementById('sizes'); if (s) s.remove(); }")
    pg.evaluate(f"() => {{ document.documentElement.style.setProperty('--fs', '{fs}px'); document.documentElement.style.setProperty('--vs', '{vs}px'); }}")
    return {k: pg.evaluate(MEASURE, [s, SAMPLE]) for k, s in SEL.items()}


def main():
    sweep, check = '--sweep' in sys.argv, '--check' in sys.argv
    old = json.loads(OUT.read_text('utf-8'))
    ZK = load('zk_make_video', R / '中考' / 'tools' / 'make_video.py')
    M = load('tem8_make_video', HERE / 'make_video.py')
    from playwright.sync_api import sync_playwright
    zkp = [p for p in json.loads((R / '中考' / 'data' / 'vocab.json').read_text('utf-8'))['passages'] if p.get('done', True)]
    t03 = next(p for p in json.loads((HERE.parent / 'data' / 'vocab.json').read_text('utf-8'))['passages'] if p['id'] == 't03')
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2)
        f = Path(td) / 'x.html'
        if sweep:                 # 中考 40 篇全部句子屏的实际字号（与中考 make_video.py 生成视频时相同的适配）
            fss, vss = [], []
            for p in zkp:
                sents = [s for pa in p['paras'] for s in pa]
                for k, s in enumerate(sents, 1):
                    for part in ZK.split_parts(p['id'], k, s):
                        f.write_text(ZK.sentence_slide(p, s, k, len(sents), part), 'utf-8')
                        pg.goto(f.as_uri())
                        pg.evaluate('document.fonts.ready')
                        fs, vs, _ = pg.evaluate(ZK.FIT)
                        fss.append(fs)
                        vss.append(vs)
            zk = {'screens': len(fss), 'fs_median': statistics.median(fss), 'vs_median': statistics.median(vss),
                  'fs_min': min(fss), 'vs_min': min(vss), 'vs_p5': sorted(vss)[len(vss) // 20]}
            print('中考', zk, flush=True)
        else:
            zk = old['zk']
        s1 = [s for pa in zkp[0]['paras'] for s in pa][0]
        ref = open_page(pg, f, ZK.sentence_slide(zkp[0], s1, 1, 9, None), zk['fs_median'], zk['vs_median'])
        target = {'en': ref['en']['xh'] * ref['en']['px'], 'zh': ref['zh']['face'] * ref['zh']['px'],
                  'hw': ref['hw']['xh'] * ref['hw']['px'], 'gl': ref['gl']['face'] * ref['gl']['px']}
        s = [s for pa in t03['paras'] for s in pa][0]
        looks = {}
        base = {k: v for k, v in M.PROJECTS['专八'].items() if k != 'variants'}
        # 各画面按原样量；专八的项目变体（如 水墨：书卷水墨 + 英文加粗）在自己的画面上另量一份，键 <画面>@<变体>
        todo = [(look, look, base) for look in M.LOOKS] + [(f"{v['look']}@{n}", v['look'], {**base, **v, 'variant': n})
                                                          for n, v in M.PROJECTS['专八'].get('variants', {}).items()]
        for key_, look, pj in todo:
            M.PJ = pj
            M.STYLE = look
            m = open_page(pg, f, M.sentence_slide(t03, s, 1, 9), 100, 100, drop_sizes=True)
            zh_design, hw_design = m['zh']['px'] / 100, m['hw']['px'] / 100
            fs0 = max(64, round(target['en'] / m['en']['xh']))
            vs0 = max(40, round(target['gl'] / m['gl']['face']))
            zh_px = max(target['zh'] / m['zh']['face'], zh_design * 64) * pj.get('zh_scale', 1)      # 变体可以要求译文更大（水墨：1.1）
            hw_px = max(target['hw'] / m['hw']['xh'], hw_design * 40)
            looks[key_] = {'fs0': fs0, 'vs0': vs0, 'min_fs': fs0, 'min_vs': round(0.85 * vs0),
                           'zh_k': round(zh_px / fs0, 3), 'hw_k': round(hw_px / vs0, 3),
                           '实测': {k: {'字体': f'{v["family"].split(",")[0]} {v["weight"]}', 'x高度比': round(v['xh'], 4), '字面比': round(v['face'], 4)}
                                   for k, v in m.items()},
                           '原设计倍数': {'译文': round(zh_design, 3), '词条': round(hw_design, 3)},
                           '看上去的大小（像素）': {'英文x高度': round(fs0 * m['en']['xh'], 1), '译文字面': round(zh_px * m['zh']['face'], 1),
                                            '词条x高度': round(hw_px * m['hw']['xh'], 1), '释义字面': round(vs0 * m['gl']['face'], 1)}}
            print(key_, M.LOOKS[look], {k: looks[key_][k] for k in ('fs0', 'vs0', 'min_fs', 'min_vs', 'zh_k', 'hw_k')}, looks[key_]['看上去的大小（像素）'], flush=True)
        br.close()
    new = {'_说明': __doc__.split('\n\n')[1].strip() + ' 由 字号标定.py 生成，不要手改。',
           'zk': zk, '中考参照（像素）': {'英文x高度': round(target['en'], 1), '译文字面': round(target['zh'], 1), '词条x高度': round(target['hw'], 1),
                                    '释义字面': round(target['gl'], 1),
                                    '字体': {k: f'{v["family"].split(",")[0]} {v["weight"]} {v["px"]}px' for k, v in ref.items()}},
           'looks': looks}
    key = lambda d: {k: {x: v[x] for x in ('fs0', 'vs0', 'min_fs', 'min_vs', 'zh_k', 'hw_k')} for k, v in d['looks'].items()}
    if check:
        if key(new) != key(old) or new['zk'] != old['zk']:
            raise SystemExit(f'字号.json 与实测不一致（字体或样式改过）：先运行 字号标定.py 重写，再重新截图审阅\n  实测 {key(new)}\n  文件 {key(old)}')
        print('字号.json 与实测一致')
        return
    OUT.write_text(json.dumps(new, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    print('已写入', OUT)


if __name__ == '__main__':
    main()
