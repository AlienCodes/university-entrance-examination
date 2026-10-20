"""生成考研阅读精校用的审阅文件（每篇一个 kNN.txt），供多人查错使用（做法与专八 gen_proof.py 相同）。

    /opt/ttsenv/bin/python 考研/tools/gen_proof.py <输出目录> [--canary 埋雷位置.json]

考研 12 份试卷都是文字版 PDF（不是扫描件），原文直接取自 PDF 文字层（pdftotext），所以不派人对照试卷图片逐字核对（专八有这一项）；
查错只看试卷本身的错误：拼写标点、语法、用词逻辑。
每个审阅文件：文件头（篇目、版式约定、已做的订正、已决定不改的条目），正文按段编号 ¶1 ¶2 …。
--canary：按埋雷文件复制指定篇目、植入故意错误，编号接在最后（k49、k50），用来检验查错人是否认真（必须全部查出）。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
P = json.loads((ROOT / '阅读' / 'passages.json').read_text('utf-8'))
EDIT = json.loads((HERE / '原文订正.json').read_text('utf-8'))
KEEP_F = HERE / '精校进度' / '已决定不改.json'
KEEP = json.loads(KEEP_F.read_text('utf-8')) if KEEP_F.exists() else {}
STYLE = ('版式约定（不是错误，不要报）：弯引号 “ ” ‘ ’ 和弯撇号 ’；破折号 — 两侧不留空格（试卷里的 “ - ”“ — ” 都统一成了 —）；数值范围用 –；'
         '斜体无法显示（书名、报刊名照常拼写）；段落按试卷的缩进分段。')


def write(out, p, pid, paras):
    tag = f"{p['paper']} {p['passage']}"
    L = [f"# {pid} 全国硕士研究生招生考试 {tag}（Section II Reading Comprehension · Part A）", STYLE]
    es = EDIT.get(tag, [])
    L.append('已经做过的订正（故意改的，与试卷印刷不同；请检查这些订正本身对不对）：' + ('无' if not es else ''))
    L += [f"  - “{e['old'].strip()}” → “{e['new'].strip()}”（{e['why']}）" for e in es]
    ks = KEEP.get(tag, [])
    if ks:
        L.append('已经人工判断、决定不改的地方（不要再报，除非你有新的、确定的理由）：')
        L += [f"  - “{k['text']}”：{k['why']}" for k in ks]
    L.append('正文：')
    L += [f'¶{i} {s}' for i, s in enumerate(paras, 1)]
    (out / f'{pid}.txt').write_text('\n'.join(L) + '\n', 'utf-8')


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    by = {p['id']: p for p in P}
    for p in P:
        write(out, p, p['id'], p['paras'])
    if '--canary' in sys.argv:
        plant = json.loads(Path(sys.argv[sys.argv.index('--canary') + 1]).read_text('utf-8'))
        for cid, spec in plant.items():
            p = by[spec['from']]
            text = '\n'.join(p['paras'])
            for old, new, _ in spec['errors']:
                assert text.count(old) == 1, (cid, old, text.count(old))
                text = text.replace(old, new)
            write(out, p, cid, text.split('\n'))
    print(f'{len(P)} 篇审阅文件 → {out}')


if __name__ == '__main__':
    main()
