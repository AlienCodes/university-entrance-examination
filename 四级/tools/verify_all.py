"""四级成品视频总核查：对 四级/最终视频/ 里的每个 MP4 重新实测，复用高考 verify_videos.check 的全部项目
（分辨率 ≥ 2K、16:9、30 帧恒定、声画等长、片头静音 1.5 秒、句间 0.8 秒、结尾静音 ≥ 2 秒、响度、朗读与画面逐句一致……），
再加上四级自己的文件名规则（年份月份 第几套 Passage One/Two 题目）、文件名不重复、视频与音频是同一版本。
结果写到 四级/核查报告.md；任何一项不通过，退出码非 0。可指定篇目：verify_all.py c40 c39 …
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent
ROOT = C4.parent
sys.path[:0] = [str(HERE), str(ROOT / 'tools' / 'video'), str(ROOT / 'tools' / 'tts')]
from make_video import video_name, VOICE, SPLIT, split_parts, switch_check, switch_time, tone_check        # noqa: E402
from verify_videos import check                  # noqa: E402

FINAL = C4 / '最终视频'


def main():
    P = {p['id']: p for p in json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
    T = json.loads((C4 / 'audio' / 'timings.json').read_text('utf-8'))[VOICE]
    byname = {video_name(p): p for p in P.values()}
    files = sorted(FINAL.glob('*.mp4'), key=lambda f: f.name, reverse=True)
    if sys.argv[1:]:                                   # 只核查指定篇目（如 c40 c39 …）
        want = {video_name(P[i]) for i in sys.argv[1:]}
        missing = want - {f.name for f in files}
        if missing:
            print('缺少视频：', missing)
            return 1
        files = [f for f in files if f.name in want]
    lines = ['# 四级最终视频核查报告', '', f'对 `四级/最终视频/` 里的 {len(files)} 个 MP4 成品逐个实测（解码音轨、读取每一帧时间戳），逐项核对。', '']
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
        sw = {int(k) - 1: switch_time(C4 / 'audio' / tm['file'], tm['sentences'][int(k) - 1], sents[int(k) - 1]['en'],
                                      split_parts(p['id'], int(k), sents[int(k) - 1])[1][0]) for k in SPLIT.get(p['id'], {})}
        res = [r for r in check(mp4, p, tm) if not r[0].startswith('文件名') and not (sw and r[0].startswith('读完停留'))]
        if sw:
            res.append(switch_check(mp4, tm['sentences'], sw))
        res.append(tone_check(mp4, tm['sentences']))
        res.insert(0, ('文件名：年份月份 第几套 第几篇 题目', bool(re.fullmatch(r'20\d\d年(6|12)月 第[123]套 Passage (One|Two) \S.*\.mp4', mp4.name)), mp4.name))
        good = all(r[1] for r in res)
        allok &= good
        print(('✅ ' if good else '❌ ') + mp4.name, flush=True)
        lines += [f"## {'✅' if good else '❌'} {mp4.stem}", '']
        lines += [f"- {'✅' if c else '❌'} {n}：{d}" for n, c, d in res]
        lines.append('')
    lines[3:3] = [f"**结论：{'全部通过' if allok else '有未通过的项目'}**", '']
    (C4 / '核查报告.md').write_text('\n'.join(lines), 'utf-8')
    print('全部通过' if allok else '有未通过的项目')
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
