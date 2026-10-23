"""把 分屏建议.py --out 的结果按固定规则并入 专八的分屏方案（由 考研/tools/分屏定稿.py 复制，规则相同；不靠逐句人工挑选，规则写死、可复现）。
专八书卷水墨大字版（DZB_VARIANT=水墨）写 分屏_水墨.json、人工指定读 分屏手定_水墨.json；不设变体写 分屏.json、读 分屏手定.json。

    DZB_VARIANT=水墨 /opt/ttsenv/bin/python 专八/tools/分屏定稿.py 专八/大字版水墨/分屏方案.json [t02 …]     # 不写篇目 = 结果里的全部篇目

规则（虹吸：程序定、人只看例外）：
- 分屏手定.json 里人工指定的句子（分屏建议找不到可行切法时，写明理由）直接采用；“无停顿”的原因按音频实测重写（句中没有停顿 / 停顿处切不开）。
- 每句取 分屏建议 排第一的候选（刀数最少 → 中英对齐错得最少 → 各屏英文最均衡）。
- 中英对齐：译文锚点（生词释义、数字、缩写）落在与英文不同的那一屏的比例 > 1/3 时，改用“整句译文”（各屏都放整句中文，
  免得某一屏的中文讲的是另一屏的英文）；没有放得下的整句候选就保留切分并在输出里列出，留给审阅员看截图时重点看。
- 篇目整篇替换为 分屏建议 写出的方案（现有方案里本来就合格的句子保留；k02 试跑时只读不合格句子、把合格的旧方案丢了），其余篇目不动。
"""
import json
import sys
from pathlib import Path

import os

HERE = Path(__file__).resolve().parent
VAR = os.environ.get('DZB_VARIANT')
PLAN = HERE / (f'分屏_{VAR}.json' if VAR else '分屏.json')
HAND = HERE / (f'分屏手定_{VAR}.json' if VAR else '分屏手定.json')
TIM = json.loads((HERE.parent / 'audio' / 'timings.json').read_text('utf-8'))['cet4_male']


def main():
    res = json.loads(Path(sys.argv[1]).read_text('utf-8'))
    ids = sys.argv[2:] or res['done']
    plan = json.loads(PLAN.read_text('utf-8'))
    hand = json.loads(HAND.read_text('utf-8')) if HAND.exists() else {}
    stats = {'切分': 0, '整句': 0, '对不齐但无整句候选': []}
    for pid in ids:
        new = dict(res['plan'].get(pid, {}))           # 分屏建议写出的方案：现有方案里本来就合格的句子 + 不合格句子的第一候选；下面只按规则改不合格的句子
        for key, r in res['results'].items():
            p, k = key.split(':')
            if p != pid:
                continue
            if k in hand.get(pid, {}):                    # 人工指定（分屏手定.json，写明理由）优先
                new[k] = {x: y for x, y in hand[pid][k].items() if x != '理由'}
                if '无停顿' in new[k]:                    # 原因按音频实测写（音频重新生成后停顿数会变，手写的会过期；k36、k39、k44 踩过）
                    n = len(next(x for x in TIM[pid]['sentences'] if x['k'] == int(k))['parts'])
                    new[k]['无停顿'] = '句中没有停顿' if n == 1 else '停顿处切不开'
                stats.setdefault('人工指定', []).append(key)
                continue
            if not r.get('候选'):
                raise SystemExit(f'{key} 放不下且没有可行的分屏候选：{r}')
            c = r['候选'][0]
            wrong, right = c['对齐（错/对）']
            e = {'at': c['at'][0] if len(c['at']) == 1 else c['at']}
            full = r.get('整句译文候选') or []
            if wrong and wrong * 3 > wrong + right:
                if full:
                    f = full[0]
                    e = {'at': f['at'][0] if len(f['at']) == 1 else f['at'], 'zh': '整句'}
                    if f['无停顿']:
                        e['无停顿'] = f['无停顿']
                    stats['整句'] += 1
                    new[k] = e
                    continue
                stats['对不齐但无整句候选'].append(f'{key} 错/对 {wrong}/{right}')
            e['zh'] = c['zh']
            if c['无停顿']:
                e['无停顿'] = c['无停顿']
            stats['切分'] += 1
            new[k] = e
        for k, v in hand.get(pid, {}).items():           # 人工指定的句子不论这次结果里有没有都采用（水墨：t04 第 19 句等分屏本来放得下、但有一屏没有词条，不在分屏建议的结果里）
            if k not in new or {x: y for x, y in v.items() if x != '理由'} != {x: y for x, y in new[k].items() if x != '无停顿'} | ({'无停顿': v['无停顿']} if '无停顿' in v else {}):
                new[k] = {x: y for x, y in v.items() if x != '理由'}
                if '无停顿' in new[k]:
                    n = len(next(x for x in TIM[pid]['sentences'] if x['k'] == int(k))['parts'])
                    new[k]['无停顿'] = '句中没有停顿' if n == 1 else '停顿处切不开'
                stats.setdefault('人工指定', []).append(f'{pid}:{k}')
        plan[pid] = {k: new[k] for k in sorted(new, key=int)}
        if not plan[pid]:
            del plan[pid]
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    if stats.get('人工指定'):
        print('人工指定（分屏手定.json）：', ' '.join(stats['人工指定']))
    print(f'{len(ids)} 篇：切分 {stats["切分"]} 句，整句译文 {stats["整句"]} 句；对不齐但没有整句候选 {len(stats["对不齐但无整句候选"])} 句', *stats['对不齐但无整句候选'], sep='\n  ')


if __name__ == '__main__':
    main()
