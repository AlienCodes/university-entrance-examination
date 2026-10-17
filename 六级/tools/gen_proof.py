"""生成精校用的审阅文件（每篇一个 sNN.txt + 试卷 Section C 页面图片），供多人查错使用。

    python3 六级/tools/gen_proof.py <输出目录> [--canary 埋雷位置.json]

每个审阅文件：文件头（篇目、试卷页面图片路径、已做的订正、版式约定、已决定不改的条目），正文按段编号 ¶1 ¶2 …
--canary：按埋雷文件复制指定篇目、植入故意错误，编号接在最后（s59、s60），用来检验查错人是否认真（必须全部查出）。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
C6 = HERE.parent
P = json.loads((C6 / '仔细阅读' / 'passages.json').read_text('utf-8'))
EDIT = json.loads((HERE / '原文订正.json').read_text('utf-8'))
KEEP_F = HERE / '精校进度' / '已决定不改.json'
KEEP = json.loads(KEEP_F.read_text('utf-8')) if KEEP_F.exists() else {}
STYLE = ('版式约定（不是错误，不要报）：弯引号 “ ” ‘ ’ 和弯撇号 ’；破折号 — 两侧不留空格；数值范围用 –；'
         '试卷里的中文注释统一写成 word (中文)；斜体无法显示（书名、报刊名照常拼写）。')


def pages(pdf, name):
    """Section C 中该篇所在的页（从 “Passage One/Two” 所在页到下一篇开始或翻译部分所在页）。"""
    txt = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], capture_output=True, text=True, check=True).stdout.split('\f')
    one = next(i for i, t in enumerate(txt, 1) if re.search(r'^\s*Passage One\s*$', t, re.M))
    two = next(i for i, t in enumerate(txt, 1) if re.search(r'^\s*Passage Two\s*$', t, re.M))
    end = next((i for i, t in enumerate(txt, 1) if i >= two and re.search(r'Part\s*IV|Translation', t)), len(txt))
    return list(range(one, two + 1)) if name == 'Passage One' else list(range(two, end + 1))


def write(out, p, pid, paras, imgs, extra=''):
    tag = f"{p['paper']} {p['passage']}"
    L = [f"# {pid} 大学英语六级 {tag}（Section C 仔细阅读）",
         f"试卷页面图片（只看本篇，忽略题目和另一篇）：{'; '.join(imgs)}",
         STYLE]
    es = EDIT.get(tag, [])
    L.append('已经做过的订正（故意改的，与试卷印刷不同；请检查这些订正本身对不对）：' + ('无' if not es else ''))
    L += [f"  - “{e['old'].strip()}” → “{e['new'].strip()}”（{e['why']}）" for e in es]
    ks = KEEP.get(tag, [])
    if ks:
        L.append('已经人工判断、决定不改的地方（不要再报，除非你有新的、确定的理由）：')
        L += [f"  - “{k['text']}”：{k['why']}" for k in ks]
    L.append(extra)
    L.append('正文：')
    L += [f'¶{i} {s}' for i, s in enumerate(paras, 1)]
    (out / f'{pid}.txt').write_text('\n'.join(L) + '\n', 'utf-8')


def main():
    out = Path(sys.argv[1])
    img = out / 'images'
    img.mkdir(parents=True, exist_ok=True)
    by = {}
    for p in P:
        pdf = C6 / p['source']
        imgs = []
        for pg in pages(pdf, p['passage']):
            f = img / f"{p['year']}-{p['month']:02d}-{p['set']}_p{pg}.png"
            if not f.exists():
                subprocess.run(['pdftoppm', '-r', '120', '-png', '-singlefile', '-f', str(pg), '-l', str(pg), str(pdf), str(f)[:-4]], check=True)
            imgs.append(str(f))
        by[p['id']] = (p, imgs)
        write(out, p, p['id'], p['paras'], imgs)
    if '--canary' in sys.argv:
        plant = json.loads(Path(sys.argv[sys.argv.index('--canary') + 1]).read_text('utf-8'))
        for cid, spec in plant.items():
            p, imgs = by[spec['from']]
            text = '\n'.join(p['paras'])
            for old, new, _ in spec['errors']:
                if old.startswith('PARA_MERGE_'):
                    a = int(old.split('_')[2]) - 1
                    ps = text.split('\n')
                    ps[a:a + 2] = [ps[a] + ' ' + ps[a + 1]]
                    text = '\n'.join(ps)
                    continue
                assert text.count(old) == 1, (cid, old)
                text = text.replace(old, new)
            write(out, p, cid, text.split('\n'), imgs)
    print(f'{len(P)} 篇审阅文件 → {out}')


if __name__ == '__main__':
    main()
