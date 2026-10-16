"""分屏建议（不花 token 的那一半）：找出在任何一种画面里一屏放不下或字号低于下限的句子，并给出分屏点候选。

    /opt/ttsenv/bin/python 专八/tools/分屏建议.py t03 [--styles C,1,2,3,4,5,6]
    /opt/ttsenv/bin/python 专八/tools/分屏建议.py --project 六级 [s01 s02 …] [--out 方案.json]     （六级：默认只看画面 3；不写篇目 = 全部）

做法：
1. 按 分屏.json 现有方案，用生成视频的同一排版（各屏统一取最小字号，与 make_video.layout 相同）把每种画面的每一屏排一遍，
   列出不合格的句子（放不下、英文或词汇栏低于下限）。
2. 对每个不合格的句子，在英文的句中停顿处（逗号、分号、冒号、破折号、右括号、右引号后面）逐个试切：一刀不够就试两刀，再不够试三刀。
   换屏时刻必须落在音频的句中停顿里：语音识别找第二屏第一个词的开口、往前找能量最低处（make_video.switch_time，与生成视频相同），
   必须落在 timings.json 的 parts 之间（朗读真正停下来的地方）；不在停顿里、或识别不到那个词的切点不要（截图检查 split_pauses 也这样查）。
3. 中文在句中标点（，；：和——）后面切，按“意思对齐”选：英文每个生词的释义（去掉括注，按；，、分成几个意思，取在译文里只出现一次的最长片段，
   至少两个字）、英文里的数字和大写缩写，在译文里落在哪一屏，与英文那一屏一致的算对、不一致的算错；错得最少、其次对得最多、
   再其次中英文切分比例最接近的中文切法入选（正式方案仍要人按意思核对，split_parts 逐字核对是定稿译文的原样片段）。
   全部画面放得下、字号不低于下限的才算可行；候选按 刀数少 → 对齐错得少 → 各屏英文长度最均衡 排序。
输出：每句的候选（第二屏从哪几个词开始、中文切分、对齐、各画面字号、换屏时刻落在哪个停顿）。
--out：把每句排第一的候选按 分屏.json 的格式写出（并保留现有方案里本来就合格的句子），人按意思核对后再并入 分屏.json，
最后跑 样片.py / 大字版.py --stills 全查。
"""
import bisect
import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_video as M  # noqa: E402

ZPUN = '，；：'
STOP = {'一个', '一种', '我们', '他们', '它们', '你们', '这些', '那些', '这种', '那种', '可以', '进行', '没有', '自己', '因为', '所以',
        '如果', '但是', '以及', '或者', '人们', '的人', '就是', '这样', '那样', '已经', '一些', '还是', '而且', '不是', '什么'}


def zh_cuts(zh):
    """中文可切的位置（标点留在前一段）：，；：之后、破折号——之后。"""
    out = [i + 1 for i, c in enumerate(zh[:-1]) if c in ZPUN]
    out += [m.end() for m in re.finditer('—+', zh) if m.end() < len(zh)]
    return sorted(set(out))


def en_cuts(en, s):
    """英文的句中停顿处：标点（, ; : — ) ”）后面、下一个词开头；不切断生词，两头各留 12 个字符以上。"""
    out = []
    for m in re.finditer(r'[,;:)”]\s+(?=\S)|—\s*(?=\S)', en):
        c = m.end()
        if 12 < c < len(en) - 12 and not any(a < c < b for w in s['w'] for a, b in w['sp']):
            out.append(c)
    return sorted(set(out))


def anchors(s):
    """英文里能在译文里找到对应的“锚”：[(英文位置, 在译文里的位置)]。生词释义取在译文里只出现一次的最长片段（≥2 字，不是常用虚词），数字和大写缩写原样找。"""
    zh, out = s['zh'], []
    for w in s['w']:
        m = M.POS.match(w['m'])
        mean = re.sub(r'（[^）]*）|\([^)]*\)', '', m.group(2) if m else w['m'])
        best = None
        for alt in re.split(r'[；;，,、/…]+', mean):
            for L in range(len(alt), 1, -1):
                for i in range(len(alt) - L + 1):
                    sub = alt[i:i + L]
                    if sub in STOP or not re.fullmatch(r'[一-鿿]+', sub) or zh.count(sub) != 1:
                        continue
                    if best is None or L > best[0]:
                        best = (L, zh.index(sub))
        if best:
            out.append((w['sp'][0][0], best[1]))
    for m in re.finditer(r'\d[\d,.]*\d|\d|\b[A-Z]{2,}\b', s['en']):
        if zh.count(m.group(0)) == 1:
            out.append((m.start(), zh.index(m.group(0))))
    return out


def align(anc, ecuts, zcuts):
    """(错, 对)：锚在英文落在第几屏、在译文落在第几屏是否一致。"""
    right = sum(bisect.bisect_right(ecuts, a) == bisect.bisect_right(zcuts, b) for a, b in anc)
    return len(anc) - right, right


def best_zh(s, ecuts):
    """给定英文切点，选中文切法：错最少、对最多、比例最接近。没有可用的中文标点返回 None。"""
    en, zh = s['en'], s['zh']
    zc, anc = zh_cuts(zh), anchors(s)
    best = None

    def rec(prefix, start):
        nonlocal best
        if len(prefix) == len(ecuts):
            wrong, right = align(anc, ecuts, prefix)
            prop = sum(abs(z / len(zh) - e / len(en)) for z, e in zip(prefix, ecuts))
            key = (wrong, -right, prop)
            if best is None or key < best[0]:
                best = (key, list(prefix))
            return
        for z in zc:
            if z > start:
                rec(prefix + [z], z)
    rec([], 0)
    return best


def load(pg, f, h, st=None):
    f.write_text(h, 'utf-8')
    pg.goto(f.as_uri())
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(150)          # 与 make_video.layout 相同
    return pg.evaluate(M.FIT, st)


def fit_parts(pg, f, p, k, s, n, parts):
    """一种画面下，这句按 parts 分屏后的统一字号（取各屏最小，与 make_video.layout 相同）和是否都放得下、不低于下限。"""
    got = [load(pg, f, M.sentence_slide(p, s, k, n, part)) for part in parts]
    st = [min(g[0] for g in got), min(g[1] for g in got)]
    ok = True
    if len(parts) > 1:
        got = [load(pg, f, M.sentence_slide(p, s, k, n, part), st) for part in parts]
    for fs, vs, fits in got:
        ok = ok and fits and fs >= M.MIN_FS and vs >= M.MIN_VS and (len(parts) == 1 or [fs, vs] == st)
    return st, ok


def pause_ok(audio, it, en, cut):
    """换屏时刻（与生成视频相同的算法）是否落在音频的句中停顿里。返回 (是否, 句内秒, 停顿)。"""
    try:
        t = M.switch_time(audio, it, en, cut)
    except SystemExit:
        return False, None, None
    gaps = list(zip([x[1] for x in it['parts']], [x[0] for x in it['parts'][1:]]))
    gap = next(((a, b) for a, b in gaps if a - 0.02 <= t <= b + 0.02), None)
    ok = bool(gap) and it['start'] + 0.3 < t < it['end'] - 0.3
    return ok, round(t - it['start'], 2), gap and [round(gap[0] - it['start'], 2), round(gap[1] - it['start'], 2)]


def at_of(en, c):
    """分屏点文字：从切点起的前几个词，在整句里唯一。"""
    ws = en[c:].split(' ')
    for n in range(4, len(ws) + 1):
        at = ' '.join(ws[:n])
        if en.count(at) == 1:
            return at
    raise SystemExit(f'找不到唯一的分屏点文字：{en[c:c + 30]}')


def main():
    argv = sys.argv[1:]
    if '--project' in argv:
        j = argv.index('--project')
        M.set_project(argv[j + 1])
        argv = argv[:j] + argv[j + 2:]
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None
    looks = opt('--styles').split(',') if opt('--styles') else (list(M.LOOKS) if M.PROJ == '专八' else [M.PJ['look']])
    out = Path(opt('--out')) if opt('--out') else None
    ids = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or argv[i - 1] not in ('--styles', '--out'))]
    P = {x['id']: x for x in json.loads((M.C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
    ids = ids or sorted(P)
    tms = json.loads((M.C4 / 'audio' / 'timings.json').read_text('utf-8'))[M.VOICE]
    from playwright.sync_api import sync_playwright
    res, plan = {}, {}
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': M.W, 'height': M.H}, device_scale_factor=2)
        f = Path(td) / 'x.html'
        for pid in ids:
            p = P[pid]
            sents = [s for pa in p['paras'] for s in pa]
            n = len(sents)
            tm = tms[pid]
            audio = M.C4 / 'audio' / tm['file']
            bad, cur = {}, {}
            for look in looks:
                M.set_style(look)
                for k, s in enumerate(sents, 1):
                    st, ok = fit_parts(pg, f, p, k, s, n, M.split_parts(pid, k, s))
                    cur.setdefault(k, {})[look] = st
                    if not ok:
                        bad.setdefault(k, []).append(f'{look}:{st[0]}/{st[1]}')
            keep = {k: v for k, v in M.SPLIT.get(pid, {}).items() if int(k) not in bad}
            print(f'{pid}（画面 {",".join(looks)}，下限 {M.MIN_FS}/{M.MIN_VS}）：不合格 {sorted(bad)}；现有分屏合格 {sorted(keep, key=int)}', flush=True)
            for k in sorted(bad):
                s = sents[k - 1]
                en, zh, it = s['en'], s['zh'], tm['sentences'][k - 1]
                cs = en_cuts(en, s)
                pz = {c: pause_ok(audio, it, en, c) for c in cs}
                cs = [c for c in cs if pz[c][0]]
                good = []
                for m in (1, 2, 3):
                    if good:
                        break                                        # 少刀可行就不试多刀
                    trials = [list(x) for x in __import__('itertools').combinations(cs, m)]
                    for cuts in trials:
                        if any(b - a < 12 for a, b in zip([0] + cuts, cuts + [len(en)])):
                            continue
                        z = best_zh(s, cuts)
                        if not z:
                            continue
                        zb = [0] + z[1] + [len(zh)]
                        b = [0] + cuts + [len(en)]
                        parts = [(b[x], b[x + 1], zh[zb[x]:zb[x + 1]], f' · PART {x + 1}/{len(b) - 1}') for x in range(len(b) - 1)]
                        sizes, ok = {}, True
                        for look in looks:
                            M.set_style(look)
                            st, o = fit_parts(pg, f, p, k, s, n, parts)
                            sizes[look] = st
                            ok = ok and o
                            if not ok:
                                break
                        if ok:
                            good.append({'cuts': cuts, 'at': [at_of(en, c) for c in cuts], 'zh': [x[2] for x in parts],
                                         '对齐（错/对）': [z[0][0], -z[0][1]], '字号': sizes, '换屏（句内秒）': [pz[c][1] for c in cuts],
                                         '停顿': [pz[c][2] for c in cuts], '_key': (z[0][0], max(y - x for x, y in zip(b, b[1:])), z[0][1])})
                good.sort(key=lambda g: g['_key'])
                res[f'{pid}:{k}'] = {'不合格': bad[k], '现在': cur[k], '英文': en, '中文': zh, '停顿处切点': len(cs),
                                     '候选': [{x: y for x, y in g.items() if not x.startswith('_') and x != 'cuts'} for g in good[:4]]}
                print(f'  第 {k} 句（{len(en)} 字符）不合格：{bad[k]}；停顿处可切 {len(cs)} 处', flush=True)
                for g in good[:4]:
                    print('    第二屏起：', ' | '.join(f'“{a}”' for a in g['at']), ' 对齐（错/对）', g['对齐（错/对）'], ' 字号', g['字号'],
                          ' 中文：', ' ‖ '.join(g['zh']), flush=True)
                if good:
                    keep[str(k)] = {'at': good[0]['at'] if len(good[0]['at']) > 1 else good[0]['at'][0], 'zh': good[0]['zh']}
                else:
                    print('    没有找到可行的切法（试过一刀到三刀）', flush=True)
            if keep:
                plan[pid] = dict(sorted(keep.items(), key=lambda x: int(x[0])))
        br.close()
    if out:
        out.write_text(json.dumps({'results': res, 'plan': plan}, ensure_ascii=False, indent=1) + '\n', 'utf-8')
        print('写出', out)
    else:
        print('\n详细结果（JSON）：')
        print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
