"""高考读后续写原文精读：从 高考续写/续写题汇总.json 取 28 篇续写题的「原文」和两段「开头语」，统一排版、逐条订正，写成精读用的文章。

    python3 高考续写/精读/tools/extract.py            # 重新生成（封版后文字有变化会报错）
    python3 高考续写/精读/tools/extract.py --reseal   # 精校完成后封版

只读 原文、开头语（用户 2026-11-03：读原文全文 + 两段开头语；不读中文说明、注意事项，不读范文——本程序不碰“范文”字段）。
编号 x01—x28 = 汇总的编号 1—28（从新到旧，每年高考在前、联考在后）。
订正：先按六级的 tidy 统一排版（中文注释括号、破折号、弯引号），再按 原文订正.json 逐条替换（每条必须恰好匹配 1 处，写明类型与理由；
OCR 识别的 5 篇按 OCR 常见错误逐词核对，见 原文订正.json 的 type=OCR）。段落之间用换行，OCR 把一段拆成两段的，订正里用 “\\n” 合并。
开头语作为最后两段（各一句）。输出 阅读/passages.json（与考研同一格式，多 fname：文件名前缀）、每篇一个文本文件、README.md。
"""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                       # 高考续写/精读/
REPO = ROOT.parents[1]
OUT = ROOT / '阅读'
SRC = REPO / '高考续写' / '续写题汇总.json'
_spec = importlib.util.spec_from_file_location('cet6_extract_reading', REPO / '六级' / 'tools' / 'extract_reading.py')
_cet6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cet6)
tidy = _cet6.tidy
sys.path.insert(0, str(REPO / '四级' / 'tools'))
import check_text                        # noqa: E402  排版检查与四六级、考研共用
sys.path.insert(0, str(REPO / 'tools'))
import text_rules as TR                  # noqa: E402  词数规则只写一处（踩坑 74）

EDIT = json.loads((HERE / '原文订正.json').read_text('utf-8'))
EDIT = {k: v for k, v in EDIT.items() if not k.startswith('_')}

# 开头语句数存为 heads（不能叫 lead：引擎的 lead 是第一句开口时刻，x01 样片核查因此报“开头静音 2 秒”）
# 2022 浙江卷：汇总按文件名写“7月”，原卷卷首只写“2022年普通高等学校招生全国统一考试(浙江卷)”，即 6 月夏季高考（2022 年高考 6 月 7—10 日如期举行），按 6 月写
# 片头的试卷名（paper）与文件名前缀（fname，铁律 6：年份 试卷 读后续写 题目）；来源（高考 / T8联考 / 九省联考）写进 paper
PAPER = {
    1: '2026年高考 新课标Ⅰ卷', 2: '2026年高考 新课标Ⅱ卷', 3: '2026年高考 浙江卷（1月）', 4: '2026年4月 T8联考（2026届阶段练习）',
    5: '2025年高考 新课标Ⅰ卷', 6: '2025年高考 新课标Ⅱ卷', 7: '2025年12月 T8联考（2026届）', 8: '2025年1月 T8联考（2025届八省联考）',
    9: '2024年高考 新课标Ⅰ卷、Ⅱ卷', 10: '2024年高考 浙江卷（1月）', 11: '2024年12月 T8联考（2025届）', 12: '2024年3月 T8联考（2024届第二次）',
    13: '2024年1月 九省联考（2024届）', 14: '2023年高考 新课标Ⅰ卷、Ⅱ卷', 15: '2023年高考 浙江卷（1月）', 16: '2023年12月 T8联考（2024届第一次）',
    17: '2022年高考 浙江卷（6月）', 18: '2022年高考 新高考Ⅰ卷、Ⅱ卷', 19: '2022年高考 浙江卷（1月）', 20: '2022年12月 T8联考（2023届第一次）',
    21: '2021年高考 浙江卷（6月）', 22: '2021年高考 新高考Ⅰ卷、Ⅱ卷', 23: '2021年高考 浙江卷（1月）', 24: '2021年秋 T8联考（2022届第一次）',
    25: '2021年1月 T8联考（2021届八省联考）', 26: '2020年高考 浙江卷（7月）', 27: '2020年高考 新高考Ⅰ卷、Ⅱ卷', 28: '2020年高考 浙江卷（1月）',
}


def fname(paper):
    """2026年高考 新课标Ⅰ卷 → 2026 新课标Ⅰ卷 读后续写；2025年12月 T8联考（2026届） → 2025 T8联考（2026届 12月） 读后续写。"""
    m = re.fullmatch(r'(\d{4})年(?:高考|(\d+月|秋))? (\S+)', paper)
    y, mon, rest = m.groups()
    if mon:
        rest = rest[:-1] + f' {mon}）' if rest.endswith('）') else f'{rest}（{mon}）'
    return f'{y} {rest} 读后续写'


def main():
    OUT.mkdir(exist_ok=True)
    D = json.loads(SRC.read_text('utf-8'))['续写题']
    res, errs = [], []
    for x in D:
        n = x['编号']
        pid = f'x{n:02d}'
        if x['原文'] is None or len(x['开头语']) != 2:
            errs.append(f'{pid}：原文或开头语缺失')
            continue
        paras = [tidy(p).replace('...', '…') for p in x['原文'] + x['开头语']]
        text = '\n'.join(paras)
        for e in EDIT.get(pid, []):
            c = text.count(e['old'])
            if c != 1:
                errs.append(f'{pid}：订正 “{e["old"]}” 匹配到 {c} 处（必须恰好 1 处）')
            if not e.get('why') or not e.get('type'):
                errs.append(f'{pid}：订正 “{e["old"]}” 没写类型或理由')
            text = text.replace(e['old'], e['new'])
        paras = text.split('\n')
        words = TR.word_count(' '.join(paras))
        if any(re.search(r'[一-鿿]', re.sub(r'\([^()]*\)', '', p)) for p in paras):
            errs.append(f'{pid}：括号注释以外还有汉字')
        if re.search(r'[（）：，．]|_|\s[,.;:!?]|[,;:](?=[A-Za-z“])', text):
            errs.append(f'{pid}：残留全角标点 / 下划线 / 标点前空格 / 标点后缺空格：'
                        + str(re.findall(r'.{0,12}(?:[（）：，．]|_|\s[,.;:!?]|[,;:](?=[A-Za-z“])).{0,12}', text)[:5]))
        if text.count('“') != text.count('”'):
            errs.append(f'{pid}：左右双引号数目不同（{text.count("“")} / {text.count("”")}）')
        paper = PAPER[n].replace('Ⅰ', 'I').replace('Ⅱ', 'II')     # 片头字体（思源宋体网页子集）没有罗马数字字形 Ⅰ Ⅱ（预检：回退到系统字体），片头用拉丁字母；文件名仍写 Ⅰ Ⅱ
        if not paper.startswith(str(x['年份'])):
            errs.append(f'{pid}：试卷名 {paper} 与年份 {x["年份"]} 不符')
        res.append({'id': pid, 'year': x['年份'], 'month': x.get('考试月份'), 'set': 1, 'passage': 'Continuation Writing',
                    'paper': paper, 'fname': fname(PAPER[n]), 'part': '续写', 'paras': paras, 'words': words,
                    'heads': len(x['开头语']), 'source': x['题目来源文件'], 'category': x['类别']})
    if len(res) != 28:
        errs.append(f'篇数 {len(res)}，应为 28')
    if set(EDIT) - {r['id'] for r in res}:
        errs.append(f'原文订正.json 里有对不上篇目的条目：{sorted(set(EDIT) - {r["id"] for r in res})}')
    if len({r['fname'] for r in res}) != len(res):
        errs.append('文件名前缀重复')
    for r in res:
        heads = {f'第{k}段' for k, p in enumerate(r['paras'], 1) if not re.search(r'[.!?…][”’)]*$', p) and len(p.split()) <= 6}
        errs += [f"{r['id']} {e}" for e in check_text.check(r) if not (e.split(' ')[0] in heads and '段尾没有句末标点' in e)]   # 篇名（A Run to Remember）没有句号
    if errs:
        sys.exit('提取有问题，未输出：\n  ' + '\n  '.join(errs))
    seal_f = OUT / '封版.json'
    fp = {r['id']: hashlib.sha256('\n'.join(r['paras']).encode()).hexdigest()[:16] for r in res}
    if '--reseal' in sys.argv:
        seal_f.write_text(json.dumps({'说明': '高考读后续写 28 篇原文 + 开头语精校定稿的文字指纹。文字一改就必须重新精校、重新封版（--reseal）。', '指纹': fp},
                                     ensure_ascii=False, indent=1), 'utf-8')
    elif seal_f.exists():
        old = json.loads(seal_f.read_text('utf-8'))['指纹']
        diff = sorted(k for k in set(old) | set(fp) if old.get(k) != fp.get(k))
        if diff:
            sys.exit(f'文字与封版不一致（改动未经精校）：{diff}；确认已重新精校后用 --reseal 重新封版。')
    (OUT / 'passages.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), 'utf-8')
    for old in OUT.glob('x*.txt'):
        old.unlink()
    rows = []
    for r in res:
        (OUT / f"{r['id']} {r['fname']}.txt").write_text('\n\n'.join(r['paras']) + '\n', 'utf-8')
        rows.append(f"| {r['id']} | {r['paper']} | {r['words']} | {len(r['paras']) - 2} + 2 | {len(EDIT.get(r['id'], []))} |")
    (OUT / 'README.md').write_text(
        '# 高考读后续写原文精读（28 篇：高考真题 18、T8联考 9、九省联考 1）\n\n'
        '每篇 = 续写题原文全文 + 两段开头语（最后两段）。来源 `高考续写/续写题汇总.json`；订正见 `../tools/原文订正.json`。\n\n'
        '| 编号 | 试卷 | 词数 | 段数（原文 + 开头语） | 订正 |\n|---|---|---|---|---|\n' + '\n'.join(rows) + '\n', 'utf-8')
    print(f'{len(res)} 篇，共 {sum(r["words"] for r in res)} 词，订正 {sum(len(v) for v in EDIT.values())} 处 → {OUT}')


if __name__ == '__main__':
    main()
