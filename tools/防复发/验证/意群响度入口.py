"""双向验证 + 静态检查：每个会产出音频 / 视频的入口都接上了意群级电平统一和意群检查（踩坑 85，用户 2026-10-29：
“修好之后这套机制必须真的用起来、真的生效，不能做出来却没接上”）。以后新项目复制旧脚本漏接，这里拦下。

入口自动发现（不靠名单）：
  音频：仓库里任何直接调用 TTS 合成（.synth(）或输出 MP3（render_passage / encode_mp3 / write_mp3）的 .py；
  视频：*/tools/make_video.py、tools/video/make_video.py（只转发到别的引擎的 sys.modules 别名除外）。
规则：
  ① 调用 .synth( 的文件必须经过 segment(（gaokao_tts：段内电平统一 even + 每段 BS.1770 统一），不许再写 fade(level(…)) 旁路；
  ② gaokao_tts.segment 必须含 even 与 level_clause；verify_loudness 默认 fine=True；render_passage 写合格证；
  ③ 任何地方都不许给 verify_loudness 传 fine=False（双向验证里的除外）；
  ④ verify_videos 与每个视频引擎都核对合格证（certificate_problems）；
  ⑤ 豁免（历史一次性排查工具、诊断脚本）写明理由，只许减少。
    python3 tools/防复发/验证/意群响度入口.py"""
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
EXEMPT = {      # 路径 → 理由（只许减少）
    'tools/pipeline/audio_debug/tail2.py': '读音诊断：测词尾摩擦段时长，不产出给用户的音频',
    'tools/pipeline/audio_debug/tail3.py': '读音诊断：同上',
    '四级/电磁音排查/生成试听.py': '2026-10-08 电磁音排查的一次性对照（只改一个因素的原始合成），已结束，不再使用',
    '四级/音色试听/生成试听.py': '2026-10-07 选音色的一次性试听，已结束，不再使用',
}
SKIP_DIRS = ('tools/防复发/',)
LEGACY_MAX = 438     # 2026-10-29 已发布、不追溯的成品条数（只许减少）


def files(over):
    out = {}
    for p in R.rglob('*.py'):
        rel = p.relative_to(R).as_posix()
        if any(rel.startswith(d) for d in SKIP_DIRS) or '/.git/' in rel or rel.startswith('.git/'):
            continue
        try:
            out[rel] = p.read_text('utf-8')
        except (UnicodeDecodeError, OSError):
            continue
    out.update(over)
    return out


def check(over=None):
    F = files(over or {})
    errs = []
    audio = [f for f, s in F.items() if re.search(r'\.synth\(|render_passage\(|encode_mp3\(|write_mp3\(', s)]
    for f in audio:
        if f in EXEMPT:
            continue
        s = F[f]
        if '.synth(' in s and 'segment(' not in s:
            errs.append(f'{f}：直接合成却没经过 segment（意群级电平统一）')
        if re.search(r'fade\((G\.)?level\(', s):
            errs.append(f'{f}：还在用 fade(level(…)) 旁路，没走 segment')
    for f, s in F.items():
        if re.search(r'verify_loudness\([^)]*fine\s*=\s*False', s):
            errs.append(f'{f}：给 verify_loudness 传了 fine=False（关掉意群检查）')
    g = F.get('tools/tts/gaokao_tts.py', '')
    seg = re.search(r'def segment\(x\):(.*?)\n\n\n', g, re.S)
    if not seg or 'even(' not in seg.group(1) or 'level_clause(' not in seg.group(1):
        errs.append('gaokao_tts.segment 没有同时做 even 与 level_clause')
    if not re.search(r'def verify_loudness\([^)]*fine=True', g):
        errs.append('gaokao_tts.verify_loudness 的意群检查不是默认打开')
    rp = re.search(r'def render_passage\(.*?\n(?=def )', g, re.S)
    if not rp or 'certificate(' not in rp.group(0) or "'clause_check': CHAIN" not in rp.group(0):
        errs.append('gaokao_tts.render_passage 没写合格证 / clause_check')
    v = F.get('tools/video/verify_videos.py', '')
    if 'certificate_problems(tm)' not in v or 'fine=not is_legacy(tm)' not in v:
        errs.append('verify_videos 没核对合格证或没开意群检查')
    engines = [f for f in F if re.fullmatch(r'[^/]+/tools/make_video\.py|tools/video/make_video\.py', f)]
    for f in engines:
        s = F[f]
        if 'sys.modules[__name__]' in s:            # 只是别名（如 六级 → 专八引擎）
            continue
        if 'certificate_problems(' not in s:
            errs.append(f'{f}：视频引擎生成前没核对音频合格证')
    import json
    leg = json.loads(F.get('tools/tts/响度旧成品清单.json') or (R / 'tools/tts/响度旧成品清单.json').read_text('utf-8'))
    if leg['count'] > LEGACY_MAX or len(leg['keys']) > LEGACY_MAX:
        errs.append(f"响度旧成品清单 {len(leg['keys'])} 条，超过 2026-10-29 的界线 {LEGACY_MAX} 条（只许减少：新音频必须带合格证）")
    return errs, len(audio), len(engines)


def main():
    bad = []

    def case(name, errs, want):
        ok = (not errs) if want is None else any(want in e for e in errs)
        print(f"  {'✅' if ok else '❌'} {name}：{errs[:3] or '0 处'}")
        if not ok:
            bad.append(name)

    errs, na, ne = check()
    print(f'入口：音频 {na} 个（豁免 {len(EXEMPT)}），视频引擎 {ne} 个')
    case('现在 → 0', errs, None)
    k = '考研/tools/make_audio.py'
    s = (R / k).read_text('utf-8')
    case('考研 make_audio 改回 fade(level(…)) → 报出', check({k: s.replace('G.segment(', 'G.fade(G.level(').replace(
        'G.segment(engine.synth(pron.phonemes(x, key), style, speed))', 'G.fade(G.level(engine.synth(pron.phonemes(x, key), style, speed)))')})[0], 'fade(level')
    case('新项目复制旧脚本、没走 segment → 报出', check({'新项目/tools/make_audio.py':
                                                   'seg = G.level(engine.synth(ph, style, 1.0))\nG.render_passage(p)\n'})[0], '新项目/tools/make_audio.py')
    case('有人传 fine=False → 报出', check({'中考/tools/x.py': 'verify_loudness(mp3, items, -16.0, fine=False)'})[0], 'fine=False')
    g = (R / 'tools/tts/gaokao_tts.py').read_text('utf-8')
    case('segment 去掉 even → 报出', check({'tools/tts/gaokao_tts.py': g.replace('return fade(level_clause(even(x)))', 'return fade(level_clause(x))')})[0], 'even')
    v = (R / 'tools/video/verify_videos.py').read_text('utf-8')
    case('verify_videos 去掉合格证核对 → 报出', check({'tools/video/verify_videos.py': v.replace('certificate_problems(tm)', 'list()')})[0], 'verify_videos')
    m = (R / '中考/tools/make_video.py').read_text('utf-8')
    case('中考视频引擎去掉合格证核对 → 报出', check({'中考/tools/make_video.py': m.replace('certificate_problems', 'cp_removed')})[0], '中考/tools/make_video.py')
    import json
    leg = json.loads((R / 'tools/tts/响度旧成品清单.json').read_text('utf-8'))
    leg['keys'].append('新音频.mp3|1|2|3|4')
    case('往旧成品清单里塞新音频 → 报出', check({'tools/tts/响度旧成品清单.json': json.dumps(leg)})[0], '旧成品清单')
    if bad:
        sys.exit(f'意群响度入口双向验证失效：{bad}')
    print('意群响度入口双向验证：全部通过')


if __name__ == '__main__':
    main()
