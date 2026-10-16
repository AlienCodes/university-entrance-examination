"""专八样片（同一篇、多种画面）一条命令做到底（虹吸：程序能查的全由程序查，审阅员只看截图，审过的截图才许生成视频）。

    /opt/ttsenv/bin/python 专八/tools/样片.py t03 --styles C,1,2,3,4,5,6 --stills    # ① 截图 + 全部程序检查
    /opt/ttsenv/bin/python 专八/tools/样片.py t03 --styles C,1,2,3,4,5,6 --approve   # ② 审阅员看过截图后登记（协调人运行）
    /opt/ttsenv/bin/python 专八/tools/样片.py t03 --styles C,1,2,3,4,5,6 --video     # ③ 生成 4K 视频 + 全部成品核查（可无人值守、可续跑）

画面：C = 专八「书卷水墨」，1–6 = 共用背景（晴空校园、手账笔记本、教室黑板、活页单词卡、紫黄撞色、柔彩插画）。不写 --styles 就是全部 7 种。

① --stills：每种画面把全部屏（片头 + 每句，含分屏）按生成视频的同一排版（make_video.layout，4K 排版）画出来，缩成 1920×1080 存到
   专八/样片/截图/<编号_名称>/screenNN.png，逐屏跑全部程序检查（make_video.screen_checks：字号下限与放得下、layoutcheck 排版机械检查
   〔含整名不断行、字体回退、徽章撇号〕、字体加载、字形、横向出界、封面），另查：字号.json 与实测一致（字号标定.py --check）、
   中文人名都已登记、分屏方案合法（split_parts）、每个换屏时刻（语音识别）落在音频的句中停顿里。
   每种画面写一张总览图（总览.jpg）；全部结果写 专八/样片/截图/汇总.json（每种画面：屏数、英文与词汇栏字号的最小值和中位数、问题）；
   参考文字（每屏应有的英文、中文、生词）写 专八/样片/截图/参考_<篇目>.txt。有任何问题退出码非 0。
② --approve：只登记“截图是用现在的程序和数据画的（指纹一致）、程序检查全部通过、截图文件没动过”的画面，写进
   专八/tools/画面核查/样片审阅通过.json（指纹 + 每张截图的哈希）。
③ --video：只做已登记、且登记之后程序、样式、数据都没改过的画面（make_video.py --stills 再核对一遍，并逐屏与审过的截图比对，
   不一致就不编码）；成品 专八/样片/<年份> Passage <几> <题目>（<画面名称>）.mp4，生成后跑全部成品核查（verify_videos 的
   分辨率、流畅、声画等长、朗读与画面逐句一致、静音、停顿、响度，分屏换屏，电磁音，结尾静音，逐屏画面与截图一致），不通过就删除成品。
   已经做好并核查通过、指纹没变的画面直接跳过（中断后重跑同一条命令就从断处接着做）；日志在 专八/样片/日志/。
   结果写 专八/样片/汇总.json；任何一种画面没做成退出码非 0。适合 setsid nohup 脱离会话跑。
"""
import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent
OUT = C4 / '样片'
SHOTS = OUT / '截图'
PY = sys.executable
sys.path.insert(0, str(HERE))
import make_video as M  # noqa: E402


def folder(look):
    return SHOTS / f'{look}_{M.LOOKS[look]}'


def passage(pid):
    return next(x for x in json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages'] if x['id'] == pid)


def write_json(f, d):
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix('.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    tmp.replace(f)


def split_pauses(p):
    """每个换屏时刻（语音识别找第二屏第一个词的开口，往前找能量最低处，与生成视频相同）必须落在音频的句中停顿里（timings.json 的 parts 之间）。"""
    tm = json.loads((C4 / 'audio' / 'timings.json').read_text('utf-8'))[M.VOICE][p['id']]
    audio = C4 / 'audio' / tm['file']
    sents = [s for pa in p['paras'] for s in pa]
    out, bad = [], []
    for k, s in enumerate(sents, 1):
        for n, (lo, hi, zh, tag) in enumerate(M.split_parts(p['id'], k, s)):
            if not n:
                continue
            it = tm['sentences'][k - 1]
            t = M.switch_time(audio, it, s['en'], lo)
            gaps = list(zip([x[1] for x in it['parts']], [x[0] for x in it['parts'][1:]]))
            gap = next(((a, b) for a, b in gaps if a - 0.02 <= t <= b + 0.02), None)
            rec = {'句': k, '屏': n + 1, '第二屏起': ' '.join(s['en'][lo:].split()[:4]), '换屏（句内秒）': round(t - it['start'], 2),
                   '停顿': [round(gap[0] - it['start'], 2), round(gap[1] - it['start'], 2)] if gap else None}
            out.append(rec)
            if not gap or not it['start'] + 0.3 < t < it['end'] - 0.3:
                bad.append(f'第 {k} 句第 {n + 1} 屏的换屏时刻 {t - it["start"]:.2f}s 不在音频的句中停顿里（停顿：'
                           + '，'.join(f'{a - it["start"]:.2f}–{b - it["start"]:.2f}s' for a, b in gaps) + '）')
    return out, bad


def ref_text(p):
    """参考文字：每屏应有的内容（审阅员对照用）。"""
    sents = [s for pa in p['paras'] for s in pa]
    lines = [f'# {p["id"]} {p["paper"]} {p["passage"]} {p["title"]}：第 1 屏片头（标题、试卷、篇目、体裁、全文 {p["words"]} 词），之后每句一屏，长句分屏（页脚 PART m/n）。']
    i = 1
    for k, s in enumerate(sents, 1):
        for lo, hi, zh, tag in M.split_parts(p['id'], k, s):
            i += 1
            ws = [w for w in M.ordered(s) if any(lo <= a and b <= hi for a, b in w['sp'])]
            lines.append(f'\nscreen{i:02d}  第 {k} 句{tag}\n  英文：{s["en"][lo:hi].strip()}\n  中文：{zh}\n  生词：'
                         + '；'.join(f'{w["h"]} {w["m"]}' for w in ws))
    return '\n'.join(lines) + '\n'


def contact(look, pngs, sizes):
    """总览图：每屏缩成 384×216，8 列，标屏号和字号。"""
    from PIL import Image, ImageDraw
    cols, w, h = 8, 384, 216
    rows = (len(pngs) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * w, rows * (h + 26)), 'white')
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(pngs):
        x, y = i % cols * w, i // cols * (h + 26)
        sheet.paste(Image.open(f).convert('RGB').resize((w - 4, h - 4), Image.LANCZOS), (x + 2, y + 2))
        d.text((x + 6, y + h + 4), f'{f.stem}  {sizes[i]}', fill='black')
    out = folder(look) / '总览.jpg'
    sheet.save(out, quality=88)
    return out


def stills(p, looks):
    from playwright.sync_api import sync_playwright
    report = json.loads((SHOTS / '汇总.json').read_text('utf-8')) if (SHOTS / '汇总.json').exists() else {}
    common = []
    r = subprocess.run([PY, str(HERE / '字号标定.py'), '--check'], capture_output=True, text=True)
    if r.returncode:
        common.append('字号.json 与实测不一致：' + (r.stderr or r.stdout).strip()[-400:])
    try:
        M.check_names(p)
    except SystemExit as e:
        common.append(str(e))
    try:
        pauses, bad = split_pauses(p)
        common += bad
    except SystemExit as e:
        pauses = []
        common.append(str(e))
    SHOTS.mkdir(parents=True, exist_ok=True)
    (SHOTS / f'参考_{p["id"]}.txt').write_text(ref_text(p), 'utf-8')
    report['_共同'] = {'篇目': p['id'], '问题': common, '分屏换屏': pauses}
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': M.W, 'height': M.H}, device_scale_factor=2)      # 与生成 4K 视频相同的排版
        td = Path(td)
        for look in looks:
            t0 = time.time()
            M.set_style(look)
            d = folder(look)
            d.mkdir(parents=True, exist_ok=True)
            for x in list(d.glob('screen*.png')) + list(d.glob('总览.jpg')):
                x.unlink()
            probs, sizes, labels = [], [], []
            for i, label, fit, res in M.layout(pg, p, td / 'x.html'):
                probs += M.screen_checks(pg, label, fit, res)
                pg.screenshot(path=str(td / 'big.png'))
                M.small(td / 'big.png').save(d / f'screen{i + 1:02d}.png')
                sizes.append(list(res[:2]) if fit else None)
                labels.append(label)
            pngs = sorted(d.glob('screen*.png'))
            fs = [x[0] for x in sizes if x]
            vs = [x[1] for x in sizes if x]
            report[look] = {'名称': M.LOOKS[look], '目录': str(d.relative_to(C4.parent)), '屏数': len(pngs),
                            '字号设置': {k: M.SIZES[look][k] for k in ('fs0', 'vs0', 'min_fs', 'min_vs', 'zh_k', 'hw_k')},
                            '英文字号': {'最小': min(fs), '中位数': statistics.median(fs), '最大': max(fs)},
                            '词汇栏字号': {'最小': min(vs), '中位数': statistics.median(vs), '最大': max(vs)},
                            '低于起始字号的屏': [f'{labels[i]} {x[0]}/{x[1]}' for i, x in enumerate(sizes) if x and (x[0] < M.FS0 or x[1] < M.VS0)],
                            '问题': probs, '指纹': M.fingerprint(p['id'], look), '截图': {x.name: M.file_hash(x) for x in pngs},
                            '总览': str(contact(look, pngs, [x and f'{x[0]}/{x[1]}' for x in sizes]).relative_to(C4.parent)),
                            '时间': time.strftime('%Y-%m-%d %H:%M:%S')}
            print(f'画面 {look} {M.LOOKS[look]}：{len(pngs)} 屏，英文 {min(fs)}–{max(fs)}px，词汇栏 {min(vs)}–{max(vs)}px，'
                  f'问题 {len(probs)} 处（{time.time() - t0:.0f} 秒）', flush=True)
            for x in probs:
                print('  ', x, flush=True)
            write_json(SHOTS / '汇总.json', report)
        br.close()
    for x in common:
        print('  共同问题：', x, flush=True)
    n = len(common) + sum(len(report[k]['问题']) for k in looks)
    print('全部通过' if not n else f'共 {n} 处问题', flush=True)
    return n == 0


def approve(p, looks):
    rep = json.loads((SHOTS / '汇总.json').read_text('utf-8'))
    reg = json.loads(M.SAMPLE_REG.read_text('utf-8')) if M.SAMPLE_REG.exists() else {}
    bad = []
    for look in looks:
        r = rep.get(look)
        got = {x.name: M.file_hash(x) for x in sorted(folder(look).glob('screen*.png'))}
        why = ('没有截图' if not r else '程序检查有问题' if r['问题'] or rep['_共同']['问题'] else
               '截图之后程序、样式或数据改过（重新 --stills）' if r['指纹'] != M.fingerprint(p['id'], look) else
               '截图文件和截图时记录的不一致' if got != r['截图'] else '')
        if why:
            bad.append(f'{look}：{why}')
            continue
        reg[f'{p["id"]}@{look}'] = {'指纹': r['指纹'], '截图': got, '登记时间': time.strftime('%Y-%m-%d %H:%M:%S')}
        print('已登记', f'{p["id"]}@{look}', M.LOOKS[look])
    write_json(M.SAMPLE_REG, dict(sorted(reg.items())))
    if bad:
        print('没有登记：\n  ' + '\n  '.join(bad))
    return not bad


def video(p, looks):
    summary = json.loads((OUT / '汇总.json').read_text('utf-8')) if (OUT / '汇总.json').exists() else {}
    reg = json.loads(M.SAMPLE_REG.read_text('utf-8')) if M.SAMPLE_REG.exists() else {}
    (OUT / '日志').mkdir(parents=True, exist_ok=True)
    ok_all = True
    for look in looks:
        M.set_style(look)
        name = M.video_name(p, look)
        mp4, rep = OUT / name, OUT / (Path(name).stem + '_核查.json')
        key = f'{p["id"]}@{look}'
        fp = M.fingerprint(p['id'], look)
        if reg.get(key, {}).get('指纹') != fp:
            summary[look] = {'名称': M.LOOKS[look], '结果': '没做：截图还没审阅登记，或登记之后程序、样式、数据改过', '时间': time.strftime('%Y-%m-%d %H:%M:%S')}
            ok_all = False
            print(f'画面 {look}：{summary[look]["结果"]}', flush=True)
            write_json(OUT / '汇总.json', summary)
            continue
        if mp4.exists() and rep.exists():
            r = json.loads(rep.read_text('utf-8'))
            if r.get('ok') and r.get('指纹') == fp and r.get('size') == mp4.stat().st_size:
                print(f'画面 {look}：已做好并核查通过，跳过（{name}）', flush=True)
                summary[look] = {**summary.get(look, {}), '名称': M.LOOKS[look], '结果': '通过', '视频': name}
                write_json(OUT / '汇总.json', summary)
                continue
        t0 = time.time()
        log = OUT / '日志' / f'{look}_{M.LOOKS[look]}.log'
        print(f'画面 {look} {M.LOOKS[look]}：生成中（日志 {log}）', flush=True)
        with open(log, 'w', encoding='utf-8') as fh:
            rc = subprocess.run([PY, str(HERE / 'make_video.py'), p['id'], '--style', look, '--out', str(OUT), '--stills', str(folder(look))],
                                stdout=fh, stderr=subprocess.STDOUT).returncode
        r = json.loads(rep.read_text('utf-8')) if rep.exists() else None
        good = rc == 0 and mp4.exists() and r and r['ok'] and r['指纹'] == fp
        if not good and mp4.exists():
            mp4.unlink()                  # 核查不通过的成品不留
        tail = log.read_text('utf-8').strip().splitlines()[-6:]
        summary[look] = {'名称': M.LOOKS[look], '结果': '通过' if good else '不通过', '视频': name if good else None,
                         '核查': r['checks'] if r else None, '日志末尾': tail, '用时（秒）': round(time.time() - t0),
                         '时间': time.strftime('%Y-%m-%d %H:%M:%S')}
        ok_all = ok_all and good
        print(f'画面 {look}：{"通过" if good else "不通过"}（{time.time() - t0:.0f} 秒）', flush=True)
        if not good:
            print('  ' + '\n  '.join(tail), flush=True)
        write_json(OUT / '汇总.json', summary)
    return ok_all


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('pid')
    ap.add_argument('--styles', default=','.join(M.LOOKS), help='画面，逗号分开：' + '，'.join(f'{k} {v}' for k, v in M.LOOKS.items()))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--stills', action='store_true', help='截图 + 全部程序检查')
    g.add_argument('--approve', action='store_true', help='审阅通过后登记')
    g.add_argument('--video', action='store_true', help='生成 4K 视频 + 全部成品核查（只做已登记的画面，可续跑）')
    a = ap.parse_args()
    looks = a.styles.split(',')
    bad = [x for x in looks if x not in M.LOOKS]
    if bad:
        raise SystemExit(f'没有这种画面：{bad}（可选 {list(M.LOOKS)}）')
    p = passage(a.pid)
    ok = stills(p, looks) if a.stills else approve(p, looks) if a.approve else video(p, looks)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
