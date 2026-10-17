"""六级大字版（教室黑板，用户 2026-10-16：六级 60 篇全部改成专八样片选定的教室黑板）一条命令做到底：先截图、程序全查、审阅登记，
审过的截图才许生成视频（与 专八/tools/样片.py 同一套做法；样片按画面，这里按篇目）。引擎与专八共用：六级/tools/make_video.py（= 专八/tools/make_video.py --project 六级）。

    /opt/ttsenv/bin/python 六级/tools/大字版.py --stills [s01 …]     # ① 截图 + 全部程序检查（不写篇目 = 全部 60 篇；截过、指纹没变的篇目跳过，--force 重画）
    /opt/ttsenv/bin/python 六级/tools/大字版.py --approve [s01 …]    # ② 审阅员看过截图后登记（协调人运行）
    /opt/ttsenv/bin/python 六级/tools/大字版.py --video [s01 …]      # ③ 生成 4K 视频 + 全部成品核查（只做已登记的篇目；做好的跳过，可续跑）

① --stills：每篇把全部屏（片头 + 每句，含分屏）按生成视频的同一排版（make_video.layout，4K 排版）画出来，缩成 1920×1080 存到
   六级/样片/截图/<篇目>/screenNN.webp（无损 WebP：像素与 PNG 完全相同、存完读回核对，体积约 PNG 的 0.63 倍，见 save_still；不入库），逐屏跑全部程序检查（make_video.screen_checks：字号下限与放得下、分屏各屏字号相同、
   layoutcheck 排版机械检查〔含整名不断行、字体回退、徽章撇号、文字重叠、括注、短语断开、译文断词〕、字体加载、字形、横向出界、封面），另查：
   字号.json 与实测一致（字号标定.py --check）、中文人名都已登记（人名.json）、分屏方案合法（split_parts）、每个换屏时刻（语音识别）落在音频的句中停顿里
   （分屏.json 标了“无停顿”的，核对原因与音频相符：句中没有停顿 ↔ 音频里这句确实没有停顿，并在汇总里逐条列出，留给审阅员看）。
   每篇写总览图 <篇目>/总览.jpg、参考文字 ref/<篇目>.txt（每屏应有的英文、中文、生词；canary_layout.py --project 六级 --style 3 也用它）；
   全部结果写 六级/样片/截图/汇总.json（每篇：屏数、字号、问题、指纹、每张截图的哈希）。有任何问题退出码非 0。
   磁盘剩余不足 1 GB 就停下（踩坑 29；教室黑板的截图每张约 1.5 MB），腾出空间后重跑同一条命令接着做。
   可以分篇目开几个进程同时截（如 s01—s20、s21—s40、s41—s60），汇总.json 加锁合并，互不覆盖。
② --approve：只登记“截图是用现在的程序和数据画的（指纹一致）、程序检查全部通过、截图文件没动过”的篇目，写进
   六级/tools/画面核查/截图审阅通过.json（键 <篇目>@3，指纹 + 每张截图的哈希）。
③ --video：只做已登记、且登记之后程序、样式、数据都没改过的篇目（make_video.py 再核对一遍，并逐屏与审过的截图比对，不一致就不编码）；
   成品 六级/最终视频_黑板/<年份月份 第几套 Passage One/Two 题目>.mp4（与旧版同名；放新文件夹，不覆盖、不删除 六级/最终视频/ 里的旧版——2026-10-17 协调人要求），全部成品核查（verify_videos 全套、分屏换屏、电磁音、
   结尾静音、逐屏画面与截图一致、成品体积 ≤ 95 MB）不通过就删除成品；核查结果 六级/样片/成品核查/<文件名>_核查.json。
   已经做好并核查通过、指纹没变的篇目直接跳过（中断后重跑同一条命令就从断处接着做）；日志在 六级/样片/日志/<篇目>.log，汇总 六级/样片/汇总.json。
   适合 setsid nohup 脱离会话跑。全部做完后：/opt/ttsenv/bin/python 六级/tools/verify_all.py（核查 六级/最终视频_黑板/，报告 六级/核查报告_黑板.md）
"""
import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
C6 = HERE.parent
ROOT = C6.parent
OUT = C6 / '样片'
SHOTS = OUT / '截图'
VIDEOS = C6 / '最终视频_黑板'                 # 教室黑板成品（旧版 60 个仍在 六级/最终视频/，不动）
PY = sys.executable
sys.path.insert(0, str(HERE))
import make_video as M  # noqa: E402  六级入口：专八/tools/make_video.py 切到 --project 六级

assert M.PROJ == '六级', M.PROJ
LOOK = M.PJ['look']


def passages():
    return {p['id']: p for p in json.loads((C6 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}


def write_json(f, d):
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    tmp.replace(f)


def merge_json(f, upd):
    """加锁读出、并入 upd、写回：几个进程分篇目同时截图（--stills s01 … 与 --stills s21 … 并行）时汇总不互相覆盖。返回合并后的内容。"""
    import fcntl
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f.with_suffix('.lock'), 'w') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        d = json.loads(f.read_text('utf-8')) if f.exists() else {}
        d.update(upd)
        write_json(f, dict(sorted(d.items())))
        return d


def split_pauses(p):
    """每个换屏时刻（语音识别找下一屏第一个词的开口，往前找能量最低处，与生成视频相同）必须落在音频的句中停顿里（timings.json 的 parts 之间）。"""
    tm = json.loads((C6 / 'audio' / 'timings.json').read_text('utf-8'))[M.VOICE][p['id']]
    audio = C6 / 'audio' / tm['file']
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
            c = M.SPLIT[p['id']][str(k)]
            why = c.get('无停顿')                    # 分屏建议.py 只在停顿处切不开时才选没有停顿的词间（标明原因）；原因与音频不符就不放行
            inside = it['start'] + 0.3 < t < it['end'] - 0.3
            out.append({'句': k, '屏': n + 1, '起': ' '.join(s['en'][lo:].split()[:4]), '换屏（句内秒）': round(t - it['start'], 2),
                        '停顿': [round(gap[0] - it['start'], 2), round(gap[1] - it['start'], 2)] if gap else None,
                        **({'无停顿': why} if why else {}), **({'中文': '整句'} if c['zh'] == '整句' else {})})
            if why and why not in ('句中没有停顿', '停顿处切不开'):
                bad.append(f'第 {k} 句：分屏.json 的“无停顿”原因只能是 句中没有停顿 / 停顿处切不开：{why}')
            elif why == '句中没有停顿' and len(it['parts']) > 1:
                bad.append(f'第 {k} 句：分屏.json 写“句中没有停顿”，音频里其实有 {len(it["parts"]) - 1} 处停顿')
            elif why == '停顿处切不开' and len(it['parts']) == 1:
                bad.append(f'第 {k} 句：分屏.json 写“停顿处切不开”，音频里句中没有停顿（应写 句中没有停顿）')
            elif not inside or not gap and not why:
                bad.append(f'第 {k} 句第 {n + 1} 屏的换屏时刻 {t - it["start"]:.2f}s 不在音频的句中停顿里（停顿：'
                           + '，'.join(f'{a - it["start"]:.2f}–{b - it["start"]:.2f}s' for a, b in gaps) + '）')
    return out, bad


def save_still(im, f):
    """截图存成无损 WebP（method 0）：像素与 PNG 完全相同（存完读回逐像素核对，不同就报错），体积约 PNG 的 0.63 倍——
    教室黑板的粉笔颗粒每张 PNG 约 2.1 MB，60 篇 1783 屏要 3.8 GB，本机磁盘只剩 4.8 GB（踩坑 29）；WebP 约 2.4 GB。"""
    import numpy as np
    from PIL import Image
    im.save(f, 'WEBP', lossless=True, method=0)
    if not np.array_equal(np.asarray(Image.open(f).convert('RGB')), np.asarray(im.convert('RGB'))):
        raise SystemExit(f'{f} 存成 WebP 后像素变了（应为无损）')


def ref_text(p):
    """参考文字：每屏应有的内容（审阅员对照用；与 样片.py 相同的写法）。"""
    sents = [s for pa in p['paras'] for s in pa]
    lines = [f'# {p["id"]} {p["paper"]} {p["passage"]} {p["title"]}：第 1 屏片头（CET-6 · READING · SECTION C、标题、大学英语六级 试卷 · 篇目、'
             f'体裁 {p.get("genre") or ""}、全文 {p["words"]} 词 · 逐句精读），之后每句一屏，共 {len(sents)} 句；长句分屏（页脚 PART m/n）。']
    i = 1
    for k, s in enumerate(sents, 1):
        for lo, hi, zh, tag in M.split_parts(p['id'], k, s):
            i += 1
            ws = [w for w in M.ordered(s) if any(lo <= a and b <= hi for a, b in w['sp'])]
            lines.append(f'\nscreen{i:02d}  第 {k} 句{tag}\n  英文：{s["en"][lo:hi].strip()}\n  中文：{zh}\n  生词：'
                         + '；'.join(f'{w["h"]} {w["m"]}' for w in ws))
    return '\n'.join(lines) + '\n'


def contact(d, pngs, sizes):
    """总览图：每屏缩成 384×216，8 列，标屏号和字号（与 样片.py 相同）。"""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(ROOT / 'tools' / 'video' / 'fonts' / 'NotoSansSC-Regular.ttf'), 17)
    cols, w, h = 8, 384, 216
    rows = (len(pngs) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * w, rows * (h + 26)), 'white')
    g = ImageDraw.Draw(sheet)
    for i, f in enumerate(pngs):
        x, y = i % cols * w, i // cols * (h + 26)
        sheet.paste(Image.open(f).convert('RGB').resize((w - 4, h - 4), Image.LANCZOS), (x + 2, y + 2))
        g.text((x + 6, y + h), f'{f.stem}  {sizes[i]}（英文/词汇栏 px）' if sizes[i] else f'{f.stem}  片头', fill='black', font=font)
    out = d / '总览.jpg'
    sheet.save(out, quality=88)
    return out


def stills(ids, force):
    from playwright.sync_api import sync_playwright
    P = passages()
    report = json.loads((SHOTS / '汇总.json').read_text('utf-8')) if (SHOTS / '汇总.json').exists() else {}
    common = []
    r = subprocess.run([PY, str(ROOT / '专八' / 'tools' / '字号标定.py'), '--check'], capture_output=True, text=True)
    if r.returncode:
        common.append('字号.json 与实测不一致：' + (r.stderr or r.stdout).strip()[-400:])
    report['_共同'] = {'画面': f'{LOOK} {M.LOOKS[LOOK]}', '字号设置': {k: M.SIZES[LOOK][k] for k in ('fs0', 'vs0', 'min_fs', 'min_vs', 'zh_k', 'hw_k')},
                     '问题': common, '时间': time.strftime('%Y-%m-%d %H:%M:%S')}
    (SHOTS / 'ref').mkdir(parents=True, exist_ok=True)
    report = merge_json(SHOTS / '汇总.json', {'_共同': report['_共同']})
    stopped = None
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': M.W, 'height': M.H}, device_scale_factor=2)      # 与生成 4K 视频相同的排版
        td = Path(td)
        for pid in ids:
            p, d = P[pid], SHOTS / pid
            fp = M.fingerprint(pid, LOOK)
            old = report.get(pid)
            if not force and old and old['指纹'] == fp and old['截图'] == {x.name: M.file_hash(x) for x in M.still_files(d)}:
                print(f'{pid}：截图已是当前程序和数据画的，跳过（问题 {len(old["问题"])} 处）', flush=True)
                continue
            free = shutil.disk_usage(C6).free / 2**30
            if free < 1:
                stopped = f'磁盘剩余只有 {free:.1f} GB，停在 {pid} 之前（腾出空间后重跑同一条命令接着做）'
                print(stopped, flush=True)
                break
            t0 = time.time()
            probs = []
            try:
                M.check_names(p)
            except SystemExit as e:
                probs.append(str(e))
            try:
                pauses, bad = split_pauses(p)
                probs += bad
            except SystemExit as e:
                pauses = []
                probs.append(str(e))
            (SHOTS / 'ref' / f'{pid}.txt').write_text(ref_text(p), 'utf-8')
            d.mkdir(parents=True, exist_ok=True)
            for x in M.still_files(d) + list(d.glob('总览.jpg')):
                x.unlink()
            sizes, labels = [], []
            M._SPLIT_SIZES.clear()
            for i, label, fit, res in M.layout(pg, p, td / 'x.html'):
                probs += M.screen_checks(pg, label, fit, res)
                pg.screenshot(path=str(td / 'big.png'))
                save_still(M.small(td / 'big.png'), d / f'screen{i + 1:02d}.webp')
                sizes.append(list(res[:2]) if fit else None)
                labels.append(label)
            pngs = M.still_files(d)
            if M.fingerprint(pid, LOOK) != fp:          # 截图期间程序、样式或数据改过：这一篇不算数（指纹记开工时的，下次一定重画）
                probs.append('截图期间程序、样式或数据改过（重新 --stills）')
            fs = [x[0] for x in sizes if x]
            vs = [x[1] for x in sizes if x]
            sents = [s for pa in p['paras'] for s in pa]
            report[pid] = {'篇目': f'{p["paper"]} {p["passage"]} {p["title"]}', '视频': M.video_name(p), '句数': len(sents),
                           '屏数': len(pngs), '分屏': len(pngs) - 1 - len(sents),
                           '英文字号': {'最小': min(fs), '中位数': statistics.median(fs), '最大': max(fs)},
                           '词汇栏字号': {'最小': min(vs), '中位数': statistics.median(vs), '最大': max(vs)},
                           '低于起始字号的屏': [f'{labels[i]} {x[0]}/{x[1]}' for i, x in enumerate(sizes) if x and (x[0] < M.FS0 or x[1] < M.VS0)],
                           '分屏换屏': pauses, '问题': probs, '指纹': fp, '截图': {x.name: M.file_hash(x) for x in pngs},
                           '总览': str(contact(d, pngs, [x and f'{x[0]}/{x[1]}' for x in sizes]).relative_to(ROOT)),
                           '用时（秒）': round(time.time() - t0), '时间': time.strftime('%Y-%m-%d %H:%M:%S')}
            report = merge_json(SHOTS / '汇总.json', {pid: report[pid]})
            print(f'{pid}：{len(pngs)} 屏（分屏 {report[pid]["分屏"]}），英文 {min(fs)}–{max(fs)}px，词汇栏 {min(vs)}–{max(vs)}px，'
                  f'问题 {len(probs)} 处（{time.time() - t0:.0f} 秒）', flush=True)
            for x in probs:
                print('  ', x, flush=True)
        br.close()
    for x in common:
        print('  共同问题：', x, flush=True)
    n = len(common) + sum(len(report[k]['问题']) for k in ids if k in report)
    missing = [k for k in ids if k not in report or report[k]['指纹'] != M.fingerprint(k, LOOK)]
    print(('全部通过' if not n else f'共 {n} 处问题') + (f'；还没截图（或截图过期）：{missing}' if missing else ''), flush=True)
    return n == 0 and not missing and not stopped


def approve(ids):
    rep = json.loads((SHOTS / '汇总.json').read_text('utf-8'))
    reg = json.loads(M.SAMPLE_REG.read_text('utf-8')) if M.SAMPLE_REG.exists() else {}
    bad = []
    for pid in ids:
        r = rep.get(pid)
        got = {x.name: M.file_hash(x) for x in M.still_files(SHOTS / pid)}
        why = ('没有截图' if not r else '程序检查有问题' if r['问题'] or rep['_共同']['问题'] else
               '截图之后程序、样式或数据改过（重新 --stills）' if r['指纹'] != M.fingerprint(pid, LOOK) else
               '截图文件和截图时记录的不一致' if got != r['截图'] else '')
        if why:
            bad.append(f'{pid}：{why}')
            continue
        reg[f'{pid}@{LOOK}'] = {'指纹': r['指纹'], '截图': got, '登记时间': time.strftime('%Y-%m-%d %H:%M:%S')}
    write_json(M.SAMPLE_REG, dict(sorted(reg.items())))
    print(f'已登记 {len(ids) - len(bad)} 篇')
    if bad:
        print('没有登记：\n  ' + '\n  '.join(bad))
    return not bad


def video(ids):
    P = passages()
    summary = json.loads((OUT / '汇总.json').read_text('utf-8')) if (OUT / '汇总.json').exists() else {}
    reg = json.loads(M.SAMPLE_REG.read_text('utf-8')) if M.SAMPLE_REG.exists() else {}
    (OUT / '日志').mkdir(parents=True, exist_ok=True)
    ok_all = True
    for pid in ids:
        p = P[pid]
        name = M.video_name(p)
        mp4, rep = VIDEOS / name, OUT / '成品核查' / (Path(name).stem + '_核查.json')
        fp = M.fingerprint(pid, LOOK)
        if reg.get(f'{pid}@{LOOK}', {}).get('指纹') != fp:
            summary[pid] = {'视频': name, '结果': '没做：截图还没审阅登记，或登记之后程序、样式、数据改过', '时间': time.strftime('%Y-%m-%d %H:%M:%S')}
            ok_all = False
            print(f'{pid}：{summary[pid]["结果"]}', flush=True)
            write_json(OUT / '汇总.json', summary)
            continue
        if mp4.exists() and rep.exists():
            r = json.loads(rep.read_text('utf-8'))
            if r.get('ok') and r.get('指纹') == fp and r.get('size') == mp4.stat().st_size:
                print(f'{pid}：已做好并核查通过，跳过（{name}）', flush=True)
                summary[pid] = {**summary.get(pid, {}), '视频': name, '结果': '通过'}
                write_json(OUT / '汇总.json', summary)
                continue
        t0 = time.time()
        log = OUT / '日志' / f'{pid}.log'
        print(f'{pid}：生成中（日志 {log}）', flush=True)
        if rep.exists():
            rep.unlink()                  # 旧的核查结果作废，免得失败后误判
        with open(log, 'w', encoding='utf-8') as fh:
            rc = subprocess.run([PY, str(HERE / 'make_video.py'), pid, '--out', str(VIDEOS)], stdout=fh, stderr=subprocess.STDOUT).returncode
        r = json.loads(rep.read_text('utf-8')) if rep.exists() else None
        good = rc == 0 and mp4.exists() and r and r['ok'] and r['指纹'] == fp
        tail = log.read_text('utf-8').strip().splitlines()[-6:]
        summary[pid] = {'视频': name, '结果': '通过' if good else '不通过', '体积（MB）': round(mp4.stat().st_size / 2**20, 1) if good else None,
                        '核查': r['checks'] if r else None, '日志末尾': tail, '用时（秒）': round(time.time() - t0),
                        '时间': time.strftime('%Y-%m-%d %H:%M:%S')}
        ok_all = ok_all and good
        print(f'{pid}：{"通过" if good else "不通过"}（{time.time() - t0:.0f} 秒）', flush=True)
        if not good:
            print('  ' + '\n  '.join(tail), flush=True)
        write_json(OUT / '汇总.json', summary)
    return ok_all


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('ids', nargs='*', help='篇目（不写 = 全部 60 篇，s01—s60）')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--stills', action='store_true', help='截图 + 全部程序检查')
    g.add_argument('--approve', action='store_true', help='审阅通过后登记')
    g.add_argument('--video', action='store_true', help='生成 4K 视频 + 全部成品核查（只做已登记的篇目，可续跑）')
    ap.add_argument('--force', action='store_true', help='--stills：指纹没变也重画')
    a = ap.parse_args()
    P = passages()
    ids = a.ids or sorted(P)
    bad = [x for x in ids if x not in P]
    if bad:
        raise SystemExit(f'没有这些篇目：{bad}')
    ok = stills(ids, a.force) if a.stills else approve(ids) if a.approve else video(ids)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
