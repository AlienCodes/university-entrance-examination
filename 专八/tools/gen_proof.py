"""生成专八阅读精校用的审阅文件（每篇一个 tNN.txt + 试卷页面图片），供多人查错使用（做法与六级 gen_proof.py 相同）。

    python3 专八/tools/gen_proof.py <输出目录> [--canary 埋雷位置.json]

每个审阅文件：文件头（篇目、试卷页面图片、版式约定、已做的订正、已决定不改的条目），正文按段编号 ¶1 ¶2 …（¶k 对应试卷上的段号 (k)）。
--canary：按埋雷文件复制指定篇目、植入故意错误，编号接在最后（t28、t29），用来检验查错人是否认真（必须全部查出）。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
P = json.loads((ROOT / '阅读' / 'passages.json').read_text('utf-8'))
EDIT = json.loads((HERE / '原文订正.json').read_text('utf-8'))
KEEP_F = HERE / '精校进度' / '已决定不改.json'
KEEP = json.loads(KEEP_F.read_text('utf-8')) if KEEP_F.exists() else {}
HEAD = {'Passage One': r'PASSAGE\s+(?:ONE|1)', 'Passage Two': r'PASSAGE\s+(?:TWO|2)', 'Passage Three': r'PASSAGE\s+(?:THREE|3)'}
STYLE = ('版式约定（不是错误，不要报）：试卷每段开头的段号 (1)(2)… 已去掉，¶k 就是试卷的第 (k) 段；弯引号 “ ” ‘ ’ 和弯撇号 ’；'
         '破折号 — 两侧不留空格（试卷里的 “ - ”“ — ” 都统一成了 —）；数值范围用 –；试卷里的中文注释统一写成 word (中文)；'
         '引文省略号统一为 …；斜体无法显示（书名、报刊名照常拼写）；试卷文字层丢失的空格（10%tax、2014.When、&Eating、Association(AMA)urged）已按规则补回。')
AUTO = '程序统一处理（不必再报）：上述空格补回、“ - ” 改为破折号、去掉段末的字数统计 “(1023 words)”、中文注释后的全角逗号改为英文逗号。'


def pages(pdf, name):
    """该篇所在的页：从篇名所在页到该篇第一道题所在页（只在 Part II Section A 里找）。"""
    txt = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], capture_output=True, text=True, check=True).stdout.split('\f')
    p2 = next(i for i, t in enumerate(txt) if re.search(r'PART\s+II\b.*READING', t, re.I))
    start = next(i for i in range(p2, len(txt)) if re.search(rf'^\s*{HEAD[name]}\s*$', txt[i], re.I | re.M))
    for end in range(start, len(txt)):
        body = txt[end]
        if end == start:
            body = body[re.search(rf'^\s*{HEAD[name]}\s*$', body, re.I | re.M).end():]
        if re.search(r'^\s*\d{1,2}\s*[.．]\s*(?=[A-Z])', body, re.M):
            break
    return list(range(start + 1, end + 2))


def write(out, p, pid, paras, imgs):
    tag = f"{p['paper']} {p['passage']}"
    L = [f"# {pid} 英语专业八级 {tag}（Part II Reading Comprehension · Section A）",
         f"试卷页面图片（只看本篇，忽略题目和其他篇）：{'; '.join(imgs)}",
         STYLE, AUTO]
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
    img = out / 'images'
    img.mkdir(parents=True, exist_ok=True)
    by = {}
    for p in P:
        pdf = ROOT / p['source']
        imgs = []
        for pg in pages(pdf, p['passage']):
            f = img / f"{p['year']}_p{pg}.png"
            if not f.exists():
                subprocess.run(['pdftoppm', '-r', '110', '-png', '-singlefile', '-f', str(pg), '-l', str(pg), str(pdf), str(f)[:-4]], check=True)
            imgs.append(str(f))
        by[p['id']] = (p, imgs)
        write(out, p, p['id'], p['paras'], imgs)
    if '--canary' in sys.argv:
        plant = json.loads(Path(sys.argv[sys.argv.index('--canary') + 1]).read_text('utf-8'))
        for cid, spec in plant.items():
            p, imgs = by[spec['from']]
            text = '\n'.join(p['paras'])
            todo = []
            for old, new, _ in spec['errors']:
                if old.startswith('PARA_MERGE_'):
                    todo.append(('merge', int(old.split('_')[2]) - 1))
                else:
                    assert text.count(old) == 1, (cid, old, text.count(old))
                    todo.append(('rep', old, new))
            for t in todo:
                if t[0] == 'rep':
                    text = text.replace(t[1], t[2])
            for t in sorted((t for t in todo if t[0] == 'merge'), key=lambda t: -t[1]):
                ps = text.split('\n')
                ps[t[1]:t[1] + 2] = [ps[t[1]] + ' ' + ps[t[1] + 1]]
                text = '\n'.join(ps)
            write(out, p, cid, text.split('\n'), imgs)
    print(f'{len(P)} 篇审阅文件 → {out}')


if __name__ == '__main__':
    main()
