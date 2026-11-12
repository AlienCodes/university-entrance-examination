"""只查给定几套的标注（ann_lib.check 同一套规则，零 token）：句子直接从 原文.txt 读，不写 vocab.json、不碰别的套——几个标注员并行时各查各的。

    python3 四级/听力/精读/tools/标注检查.py 201812-1 [201812-2 …]      0 处问题时最后一行“全部通过”
正式汇总仍以 build_vocab（流水线里）为准。
"""
import os
import sys
from pathlib import Path

C4 = Path(__file__).resolve().parents[1]
os.environ['ZB_ROOT'] = str(C4)
sys.path.insert(0, str(C4.parents[2] / '专八' / 'tools'))
sys.path.insert(0, str(C4.parents[2] / 'tools'))
import ann_lib as A  # noqa: E402
import 中文地道 as ZD  # noqa: E402


def text_R():
    R = {}
    for blk in (C4 / '原文.txt').read_text('utf-8').split('\n## ')[1:]:
        sid, body = blk.split('\n', 1)
        paras = [[s for s in p.split('\n') if s.strip()] for p in body.strip().split('\n\n')]
        R[sid.strip()] = {'id': sid.strip(), 'sents': [p for p in paras if p]}
    return R


def main():
    R = text_R()
    bad = 0
    for sid in sys.argv[1:]:
        f = C4 / 'ann' / f'{sid}.txt'
        e, t, n = A.check(sid, f, R)
        zd = [f'中文地道：{p}' for p in ZD.problems([(line[:12], line) for line in f.read_text('utf-8').split('\n')
                                                  if line[:1].isdigit() or line.startswith(('S:', '= '))])]
        for x in e + t + zd:
            print(f'{sid} {x}')
        bad += len(e) + len(t) + len(zd)
        print(f'{sid}：词条 {n} 个，问题 {len(e) + len(t) + len(zd)} 处')
    print('全部通过' if not bad else f'共 {bad} 处问题')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
