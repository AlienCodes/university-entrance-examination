"""专八成品视频总核查（由六级 verify_all.py 复制）。四级原说明：四级成品视频总核查：对 四级/最终视频/ 里的每个 MP4 重新实测，复用高考 verify_videos.check 的全部项目
（分辨率 ≥ 2K、16:9、30 帧恒定、声画等长、片头静音 1.5 秒、句间 0.8 秒、结尾静音 ≥ 2 秒、响度、朗读与画面逐句一致……），
再加上四级自己的文件名规则（年份月份 第几套 Passage One/Two 题目）、文件名不重复、视频与音频是同一版本。
专八大字版（2026-10-17 起，晴空校园）：核查 专八/最终视频_校园/，结果写到 专八/核查报告_校园.md（DZB_VARIANT=水墨：专八/最终视频_水墨/、核查报告_水墨.md）；另查成品体积 ≤ 95 MB（与六级大字版相同）。
旧版 10 个（专八/最终视频/，书卷水墨）的 专八/核查报告.md 不动。任何一项不通过，退出码非 0。可指定篇目：verify_all.py t01 t02 …
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent
ROOT = C4.parent
sys.path.insert(1, str(ROOT / '四级' / 'tools'))      # debuzz.py（电磁音检查）与四级共用
sys.path[:0] = [str(HERE), str(ROOT / 'tools' / 'video'), str(ROOT / 'tools' / 'tts')]
from make_video import video_name, VOICE, SPLIT, split_parts, switch_check, switch_time, buzz_check        # noqa: E402
import make_video as _M                          # noqa: E402
from verify_videos import check, duplicate_names                  # noqa: E402

FINAL = C4 / _M.PJ.get('videos', '最终视频_校园')   # 晴空校园成品（大字版.py --video 写这里）；DZB_VARIANT=水墨 时是 最终视频_水墨；旧版 10 个在 专八/最终视频/
REPORT = C4 / f"核查报告_{_M.PJ.get('variant', '校园')}.md"   # 核查报告_校园.md / 核查报告_水墨.md


def main():
    P = {p['id']: p for p in json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
    T = json.loads((C4 / 'audio' / 'timings.json').read_text('utf-8'))[VOICE]
    byname = {video_name(p): p for p in P.values()}
    dup = duplicate_names(P.values(), video_name)          # 踩坑 11：文件名重复会让一篇悄悄覆盖另一篇（防复发审计）
    if dup:
        print('文件名重复：', dup)
        return 1
    files = sorted(FINAL.glob('*.mp4'), key=lambda f: f.name, reverse=True)
    if sys.argv[1:]:                                   # 只核查指定篇目（如 c40 c39 …）
        want = {video_name(P[i]) for i in sys.argv[1:]}
        missing = want - {f.name for f in files}
        if missing:
            print('缺少视频：', missing)
            return 1
        files = [f for f in files if f.name in want]
    lines = ['# 专八最终视频核查报告', '', f'对 `专八/{FINAL.name}/` 里的 {len(files)} 个 MP4 成品逐个实测（解码音轨、读取每一帧时间戳），逐项核对。', '']
    allok = True
    for mp4 in files:
        p = byname.get(mp4.name)
        if not p:
            lines += [f'## ❌ {mp4.stem}', '', '- ❌ 文件名不符合“年份月份 第几套 Passage One/Two 题目”，或找不到对应文章', '']
            allok = False
            print('❌', mp4.name, flush=True)
            continue
        tm = T[p['id']]
        sents = [s for para in p['paras'] for s in para]
        sw = {}                                        # 专八一句可分多屏：每个换屏点都独立重新测（第 2、3…屏第一个词的开口时刻）
        for k in SPLIT.get(p['id'], {}):
            i = int(k) - 1
            sw[i] = [switch_time(C4 / 'audio' / tm['file'], tm['sentences'][i], sents[i]['en'], part[0])
                     for part in split_parts(p['id'], int(k), sents[i])[1:]]
        res = [r for r in check(mp4, p, tm) if not r[0].startswith('文件名') and not (sw and r[0].startswith('读完停留'))]
        if sw:
            res.append(switch_check(mp4, tm['sentences'], sw))
        res.append(buzz_check(mp4, tm['sentences']))
        size = mp4.stat().st_size                      # 大字版：成品体积 ≤ 95 MB（GitHub 单个文件上限 100 MB），与生成时的检查相同
        res.append(('成品体积 ≤ 95 MB', size <= 95 * 2**20, f'{size / 2**20:.1f} MB'))
        res.insert(0, ('文件名：年份 第几篇 题目', bool(re.fullmatch(r'20\d\d年 Passage (One|Two|Three) \S.*\.mp4', mp4.name)), mp4.name))
        good = all(r[1] for r in res)
        allok &= good
        print(('✅ ' if good else '❌ ') + mp4.name, flush=True)
        lines += [f"## {'✅' if good else '❌'} {mp4.stem}", '']
        lines += [f"- {'✅' if c else '❌'} {n}：{d}" for n, c, d in res]
        lines.append('')
    lines[3:3] = [f"**结论：{'全部通过' if allok else '有未通过的项目'}**", '']
    REPORT.write_text('\n'.join(lines), 'utf-8')
    print('全部通过' if allok else '有未通过的项目')
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
