"""把 分屏建议.py --out 的结果按固定规则并入 考研/tools/分屏.json（不靠逐句人工挑选，规则写死、可复现）。

    /opt/ttsenv/bin/python 考研/tools/分屏定稿.py 结果.json [k01 …]     # 不写篇目 = 结果里的全部篇目

规则（虹吸：程序定、人只看例外）：
- 每句取 分屏建议 排第一的候选（刀数最少 → 中英对齐错得最少 → 各屏英文最均衡）。
- 中英对齐：译文锚点（生词释义、数字、缩写）落在与英文不同的那一屏的比例 > 1/3 时，改用“整句译文”（各屏都放整句中文，
  免得某一屏的中文讲的是另一屏的英文）；没有放得下的整句候选就保留切分并在输出里列出，留给审阅员看截图时重点看。
- 篇目整篇替换（该篇旧方案全部丢弃，按新结果重写），其余篇目不动。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / '分屏.json'


def main():
    res = json.loads(Path(sys.argv[1]).read_text('utf-8'))
    ids = sys.argv[2:] or res['done']
    plan = json.loads(PLAN.read_text('utf-8'))
    stats = {'切分': 0, '整句': 0, '对不齐但无整句候选': []}
    for pid in ids:
        new = {}
        for key, r in res['results'].items():
            p, k = key.split(':')
            if p != pid:
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
        plan[pid] = {k: new[k] for k in sorted(new, key=int)}
        if not plan[pid]:
            del plan[pid]
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    print(f'{len(ids)} 篇：切分 {stats["切分"]} 句，整句译文 {stats["整句"]} 句；对不齐但没有整句候选 {len(stats["对不齐但无整句候选"])} 句', *stats['对不齐但无整句候选'], sep='\n  ')


if __name__ == '__main__':
    main()
