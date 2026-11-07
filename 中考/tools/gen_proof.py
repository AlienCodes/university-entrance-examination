"""生成中考阅读精校用的审阅文件（每篇一个 zNN.txt + 试卷页面图片 + 整份试卷的文字），供多人查错使用（做法与专八 gen_proof.py 相同）。

    /opt/ttsenv/bin/python 中考/tools/gen_proof.py <输出目录> <试卷PDF目录> [--canary 埋雷位置.json]

试卷 PDF 由 Word 原件用 LibreOffice 转出（soffice --headless --convert-to pdf 中考/真题/*.docx）。
每个审阅文件：文件头（篇目、该篇所在的试卷页面图片、整份试卷文字、版式约定、已做的订正、已决定不改的条目），正文按段编号 ¶1 ¶2 …。
--canary：按埋雷文件复制指定篇目、植入故意错误，编号接在最后（z40、z41），用来检验查错人是否认真（必须全部查出）。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import extract_reading as X  # noqa: E402

P = json.loads((ROOT / '阅读' / 'passages.json').read_text('utf-8'))
EDIT = json.loads((HERE / '原文订正.json').read_text('utf-8'))
KEEP_F = HERE / '精校进度' / '已决定不改.json'
KEEP = json.loads(KEEP_F.read_text('utf-8')) if KEEP_F.exists() else {}
STYLE = ('版式约定（不是错误，不要报）：试卷里段首的 ①②… 段号已去掉（宁夏 C、湖南 C）；弯引号 “ ” ‘ ’ 和弯撇号 ’；破折号 — 两侧不留空格；'
         '试卷里的中文注释统一写成 word (中文)；表示停顿的三个句点统一为 …；文章里的插图（示意图、照片）只是配图，不是文字，不提取；'
         '斜体、加粗、下划线无法显示（题目里说的 underlined word 照常是普通文字）。')
AUTO = '程序统一处理（不必再报）：上述段号去掉、引号撇号破折号统一、多余空格合并、℃ 写成 °C、数字范围的 ~ 写成短横线 –。'


def page_texts(pdf):
    return subprocess.run(['pdftotext', '-layout', str(pdf), '-'], capture_output=True, text=True, check=True).stdout.split('\f')


def norm(s):
    return re.sub(r'[^a-z0-9]+', '', s.lower().replace('’', "'"))


def pages(pdf, paras):
    """该篇所在的页：第一段开头和最后一段结尾所在的页之间（含）。"""
    T = [norm(t) for t in page_texts(pdf)]
    T = T[:-1] if T and not T[-1] else T
    # 订正过的句子在原件里找不到：开头取前几个 6 词窗口、结尾取后几个 6 词窗口，用第一个能在原件里找到的
    ws, we = paras[0].split(), paras[-1].split()
    heads = [norm(' '.join(ws[i:i + 6])) for i in range(0, max(1, len(ws) - 5), 3)]
    tails = [norm(' '.join(we[max(0, len(we) - 6 - i):len(we) - i])) for i in range(0, max(1, len(we) - 5), 3)]
    a = next((i for h in heads for i, t in enumerate(T) if h in t), 0)
    b = next((i for x in tails for i in range(len(T) - 1, -1, -1) if x in T[i]), len(T) - 1)
    return list(range(a + 1, max(a, b) + 2))


def write(out, p, pid, paras, imgs, dump):
    tag = f"{p['paper']} {p['passage']}"
    L = [f"# {pid} 中考英语 {tag}（{p['source']}）",
         f"试卷页面图片（由 Word 原件转出；只看本篇，忽略题目和其他篇）：{'; '.join(imgs)}",
         f"整份试卷的文字（含题目；有的含答案和解析，解析里会引用原文，可用来核对段落和起止）：{dump}",
         STYLE, AUTO]
    es = EDIT.get(tag, [])
    L.append('已经做过的订正（故意改的，与试卷不同；请检查这些订正本身对不对，补入的句子是否通顺、是否符合上下文）：' + ('无' if not es else ''))
    L += [f"  - “{e['old'].strip()}” → “{e['new'].strip()}”（{e['why']}）" for e in es]
    ks = KEEP.get(tag, [])
    if ks:
        L.append('已经人工判断、决定不改的地方（不要再报，除非你有新的、确定的理由）：')
        L += [f"  - “{k['text']}”：{k['why']}" for k in ks]
    L.append('正文：')
    L += [f'¶{i} {s}' for i, s in enumerate(paras, 1)]
    (out / f'{pid}.txt').write_text('\n'.join(L) + '\n', 'utf-8')


def main():
    out, pdfdir = Path(sys.argv[1]), Path(sys.argv[2])
    (out / 'images').mkdir(parents=True, exist_ok=True)
    (out / 'dump').mkdir(exist_ok=True)
    by = {}
    for p in P:
        src = ROOT / p['source']
        pdf = pdfdir / (src.stem + '.pdf')
        dump = out / 'dump' / (src.stem + '.txt')
        if not dump.exists():
            dump.write_text('\n'.join(X.lines_of(src)) + '\n', 'utf-8')
        imgs = []
        for pg in pages(pdf, p['paras']):
            f = out / 'images' / f"{src.stem}_p{pg}.png"
            if not f.exists():
                subprocess.run(['pdftoppm', '-r', '110', '-png', '-singlefile', '-f', str(pg), '-l', str(pg), str(pdf), str(f)[:-4]], check=True)
            imgs.append(str(f))
        by[p['id']] = (p, imgs, str(dump))
        write(out, p, p['id'], p['paras'], imgs, str(dump))
    if '--canary' in sys.argv:
        plant = json.loads(Path(sys.argv[sys.argv.index('--canary') + 1]).read_text('utf-8'))
        for cid, spec in plant.items():
            if cid.startswith('_'):
                continue
            p, imgs, dump = by[spec['from']]
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
            write(out, p, cid, text.split('\n'), imgs, dump)
    print(f'{len(P)} 篇审阅文件 → {out}')


if __name__ == '__main__':
    main()
