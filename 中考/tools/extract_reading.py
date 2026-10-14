"""从用户上传的 23 份中考英语试题（Word）中提取阅读文章（只要文章，不要题目），共 40 篇（用户：“凑个整数”）。

    python3 中考/tools/extract_reading.py            # 重新生成（封版后文字有变化会报错）
    python3 中考/tools/extract_reading.py --reseal   # 精校完成后封版

用户 2026-10-13/14：中考视频要适合初中生背单词；“尽全力、一丝不苟，把中考视频全都做出来”。
输入：中考/真题/*.docx（文件里主要是阅读理解 C、D 篇，个别是 B 篇、任务型阅读、七选五）。直接读 Word 的 document.xml（没有文本框、表格、修订）。
每份试卷有哪几篇写死在 PAPERS 里，任何一篇找不到起止都报错。文章里的插图（示意图、照片）只是配图，不是文字，视频不用。
排序：从新到旧；2026 年按省级行政区划代码（北京、河北、山西、辽宁、浙江、山东、河南、湖北、湖南、广东、广西、重庆、四川、云南、陕西、宁夏），
同一省先省卷后市卷；同一份试卷按 B、C、D、任务型阅读、七选五。编号 z01—z40（2025 年北京 D 篇为用户补充上传，按年份排在 2025 年济南之前）。
段首的 ①②… 段号去掉；选句填空的空格（▲、★、七选五的 21—25）按答案补全（原文订正.json，写明依据），补全后的文章才能朗读。
输出：中考/阅读/passages.json（与专八同一格式）、每篇一个文本文件、README.md 目录。
"""
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # 中考/
REPO = ROOT.parent
SRC = ROOT / '真题'
OUT = ROOT / '阅读'
EDIT_F = HERE / '原文订正.json'
EDIT = json.loads(EDIT_F.read_text('utf-8')) if EDIT_F.exists() else {}
ALLOW_ZH = {'2026年 湖北 阅读B': '水'}     # 文章本身就在讲汉字（“水 (shui) shows beauty…”），不是排版错误；朗读时只读 shui（读音修正）

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location('cet6_extract_reading', REPO / '六级' / 'tools' / 'extract_reading.py')
_cet6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cet6)
tidy = _cet6.tidy                          # 中文注释、破折号、引号的统一排版与六级、专八相同
sys.path.insert(0, str(REPO / '四级' / 'tools'))
import check_text                          # noqa: E402  排版检查与四六级、专八共用

# (年份, 显示的地区, 文件名, [(标题, 篇目名)])；标题 None = 试卷开头没有标题，第一篇从第一段英文开始
PAPERS = [
    (2026, '北京', '2026年北京市中考英语试题.docx', [('C篇', '阅读C'), ('D篇', '阅读D')]),
    (2026, '河北', '2026年河北省中考英语试题.docx', [('C篇', '阅读C'), ('D篇', '阅读D'), ('阅读下面短文，简略回答问题。', '任务型阅读')]),
    (2026, '山西', '2026年山西省中考英语试题.docx', [(None, '阅读')]),
    (2026, '辽宁', '2026年辽宁省中考英语试题.docx', [('D篇', '阅读D')]),
    (2026, '浙江', '2026年浙江省中考英语试题.docx', [('C篇', '阅读C'), ('D篇', '阅读D')]),
    (2026, '山东', '2026年山东省中考英语试题.docx', [('C篇', '阅读C'), ('D篇', '阅读D')]),
    (2026, '济南', '2026年山东省济南市中考英语试题.docx', [('C篇', '阅读C'), ('D篇', '阅读D')]),
    (2026, '烟台', '2026年山东省烟台市中考英语试题.docx', [('C篇', '阅读C'), ('D篇', '阅读D')]),
    (2026, '河南', '2026年河南省中考英语试题.docx', [('D篇', '阅读D')]),
    (2026, '湖北', '2026年湖北省中考英语试题.docx', [('B篇', '阅读B'), ('C篇', '阅读C')]),
    (2026, '武汉', '2026年湖北省武汉市中考英语试题.docx', [('C篇', '阅读C')]),
    (2026, '湖南', '2026年湖南省中考英语试题.docx', [('C篇', '阅读C')]),
    (2026, '长沙', '2026年湖南省长沙市中考英语试题.docx', [('B篇', '阅读B'), ('D篇', '阅读D')]),
    (2026, '深圳', '2026年广东省深圳市中考英语试题.docx', [('B篇', '阅读B'), ('C篇', '阅读C')]),
    (2026, '广西', '2026年广西中考英语试题.docx', [(None, '阅读'), ('任务型阅读', '任务型阅读')]),
    (2026, '重庆', '2026年重庆市中考英语试题.docx', [('D篇', '阅读D')]),
    (2026, '成都', '2026年四川省成都市中考英语试题.docx', [('C篇', '阅读C'), ('任务型阅读', '任务型阅读')]),
    (2026, '云南', '2026年云南省中考英语试题.docx', [('C篇', '阅读C'), ('D篇', '阅读D')]),
    (2026, '陕西', '2026年陕西省中考英语试题.docx', [('C篇', '阅读C')]),
    (2026, '宁夏', '2026年宁夏回族自治区中考英语试题.docx', [('C篇', '阅读C'), ('D篇', '阅读D')]),
    (2025, '北京', '2025年北京市中考英语真题.docx', [(None, '阅读D')]),          # 用户 2026-10-14 补充上传（文件里只有 D 篇文章）
    (2025, '济南', '2025年山东省济南市中考英语真题.docx', [('C篇', '阅读C'), ('D篇', '阅读D'), ('七选五', '七选五')]),
    (2024, '济南', '2024年山东省济南市中考英语真题.docx', [('C篇', '阅读C'), ('D篇', '阅读D')]),
]


def lines_of(f):
    """Word 正文逐段的文字（只看 w:t；图片段落记为 [IMG]）。"""
    x = zipfile.ZipFile(f).read('word/document.xml').decode('utf-8')
    assert '<w:txbxContent' not in x and '<w:tbl' not in x and '<w:ins ' not in x, f'{f.name}：有文本框、表格或修订，需要单独处理'
    out = []
    for p in re.findall(r'<w:p[ >].*?</w:p>', x, re.S):
        t = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p))
        if t.strip():
            out.append(t)
        elif re.search(r'<(?:w:drawing|w:pict)\b', p):
            out.append('[IMG]')
    return out


def norm_head(s):
    return re.sub(r'\s+', '', s)


def is_english_para(s):
    return len(re.findall(r'[A-Za-z]+', s)) >= 5 and not re.match(r'^\s*\d{1,2}\s*[．.、]|^\s*[A-G]\s*[．.]', s)


def blocks(lines, secs):
    """每篇的原始段落：从标题下一行起，到第一道题、选项或中文说明之前。"""
    heads = [norm_head(h) if h else None for h, _ in secs]
    out = []
    for (h, label), nh in zip(secs, heads):
        if nh is None:
            i = next(k for k, l in enumerate(lines) if is_english_para(l)) - 1
        else:
            i = next(k for k, l in enumerate(lines) if norm_head(l) == nh)
        body, imgs = [], 0
        for l in lines[i + 1:]:
            s = l.strip()
            if s == '[IMG]':
                imgs += 1
                continue
            if re.match(r'^\d{1,2}\s*[．.、]|^[A-G]\s*[．.]', s) or norm_head(s) in {x for x in heads if x} or not re.search(r'[A-Za-z]{3}', s):
                break
            body.append(s)
        out.append((label, body, imgs))
    return out


def clean(p):
    p = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*', '', p.strip())          # 段首段号
    p = p.replace('　', ' ').replace('\xa0', ' ')
    # 中文排版的度数和范围改成英文排版（第一轮精校 z13）：℃ → °C；数字之间的 ~ → 短横线 –（1 ~ 3℃ → 1–3°C，朗读为 1 to 3 degrees Celsius）
    p = re.sub(r'(?<=\d)\s*~\s*(?=\d)', '–', p.replace('℃', '°C'))
    return re.sub(r'\s{2,}', ' ', p).strip()


def post(p):
    """tidy 之后再补两处（与专八相同）：中文注释后的全角逗号、注释后紧接下一句。"""
    p = re.sub(r'\s*，\s*(?=[A-Za-z“‘])', ', ', p)
    return re.sub(r'(?<=\))\.(?=[A-Z][a-z])', '. ', p)


def main():
    OUT.mkdir(exist_ok=True)
    res, errs = [], []
    for year, region, fname, secs in PAPERS:
        f = SRC / fname
        try:
            bs = blocks(lines_of(f), secs)
        except StopIteration:
            errs.append(f'{fname}：找不到某一篇的标题或正文')
            continue
        for label, raw, imgs in bs:
            tag = f'{year}年 {region} {label}'
            paras = [post(tidy(clean(p))) for p in raw]
            text = '\n'.join(paras)
            for e in EDIT.get(tag, []):
                c = text.count(e['old'])
                if c != 1:
                    errs.append(f'{tag}：订正 “{e["old"]}” 匹配到 {c} 处（必须恰好 1 处）')
                text = text.replace(e['old'], e['new'])
            paras = text.split('\n')
            # 词数不算试卷的中文注释（画面核查发现片头“全文 N 词”把 (包裹) 这类注释也算成词，40 篇都多 1—7 个）
            words = len(re.sub(r'\s*\([^()]*[\u4e00-\u9fff][^()]*\)', '', ' '.join(paras)).split())
            if any(re.search(r'[一-鿿]', re.sub(r'\([^()]*\)', '', p).replace(ALLOW_ZH.get(tag, '\0'), '')) for p in paras):
                errs.append(f'{tag}：括号注释以外还有汉字')
            if re.search(r'[▲★_＿]', text) or (label == '七选五' and re.search(r'(?<![\w.,$])2[1-5](?![\w.,%])', text)):
                errs.append(f'{tag}：还有没补全的空格')
            if not (150 <= words <= 500) or len(paras) < 2:
                errs.append(f'{tag}：{len(paras)} 段、{words} 词，疑似提取异常')
            res.append({'id': f'z{len(res) + 1:02d}', 'year': year, 'region': region, 'passage': label, 'paper': f'{year}年 {region}',
                        'part': label, 'paras': paras, 'words': words, 'images': imgs, 'source': str(f.relative_to(ROOT))})
    if len(res) != 40:
        errs.append(f'文章总数 {len(res)} 篇，应为 40 篇')
    tags = {f"{r['paper']} {r['passage']}" for r in res}
    if len(tags) != len(res):
        errs.append('篇目名有重复')
    if set(EDIT) - tags:
        errs.append(f'原文订正.json 里有对不上篇目的条目：{sorted(set(EDIT) - tags)}')
    for r in res:
        colon = {f'第{k}段' for k, p in enumerate(r['paras'][:-1], 1) if re.search(r'[:：][”’)]*$', p)}
        errs += [f"{r['paper']} {r['passage']} {x}" for x in check_text.check(r)
                 if not (x.split(' ')[0] in colon and '段尾没有句末标点' in x) and not (f"{r['paper']} {r['passage']}" in ALLOW_ZH and '括号注释以外有汉字' in x)]
    if errs:
        sys.exit('提取有问题，未输出：\n  ' + '\n  '.join(errs))
    seal_f = OUT / '封版.json'
    # 按篇封版（用户 2026-10-14：先把前 20 篇做出来）：--reseal 后面列出编号只登记这些篇，不列就登记全部；
    # 已封版的篇目文字一变就报错；未封版的篇目照常输出，但还不能进入翻译标注（split_sents 只输出已封版的篇目给下游时会核对）
    fp = {f"{r['paper']} {r['passage']}": hashlib.sha256('\n'.join(r['paras']).encode()).hexdigest()[:16] for r in res}
    old = json.loads(seal_f.read_text('utf-8'))['指纹'] if seal_f.exists() else {}
    if '--reseal' in sys.argv:
        ids = [a for a in sys.argv[sys.argv.index('--reseal') + 1:] if re.fullmatch(r'z\d\d', a)]
        tags = {f"{r['paper']} {r['passage']}" for r in res if not ids or r['id'] in ids}
        old.update({t: fp[t] for t in tags})
        seal_f.write_text(json.dumps({'说明': '中考阅读精校定稿的文字指纹（按篇登记）。文字一改就必须重新精校、重新封版（--reseal 编号…）。', '指纹': old},
                                     ensure_ascii=False, indent=1), 'utf-8')
        print(f'封版 {len(tags)} 篇，已封版共 {len(old)} 篇')
    else:
        diff = sorted(t for t in old if old[t] != fp.get(t))
        if diff:
            sys.exit('文字与封版不一致（改动未经精校）：\n  ' + '\n  '.join(diff) + '\n确认已重新精校后，用 --reseal 编号… 重新封版。')
    for r in res:
        r['sealed'] = f"{r['paper']} {r['passage']}" in old and '--reseal' not in sys.argv or f"{r['paper']} {r['passage']}" in (json.loads(seal_f.read_text('utf-8'))['指纹'] if seal_f.exists() else {})
    (OUT / 'passages.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), 'utf-8')
    for old in OUT.glob('z*.txt'):
        old.unlink()
    rows = []
    for r in res:
        (OUT / f"{r['id']} {r['paper']} {r['passage']}.txt").write_text('\n\n'.join(r['paras']) + '\n', 'utf-8')
        first = r['paras'][0][:60].rsplit(' ', 1)[0] + ' …'
        rows.append(f"| {r['id']} | {r['year']} | {r['region']} | {r['passage']} | {r['words']} | {len(r['paras'])} | {r['images'] or ''} | {first} |")
    (OUT / 'README.md').write_text(
        '# 中考英语阅读（23 份试卷，共 40 篇）\n\n'
        '用户 2026-10-13 上传；2026-10-14 要求全部做成适合初中生背单词的逐句精读视频。从新到旧，2026 年按省级行政区划代码排列，同一省先省卷后市卷。\n'
        '段首 ①②… 段号已去掉；选句填空的空格已按答案补全（`../tools/原文订正.json`）。“配图”是文章中的插图数（示意图、照片），只是配图，视频不用。\n\n'
        '| 编号 | 年份 | 地区 | 篇目 | 词数 | 段数 | 配图 | 开头 |\n|---|---|---|---|---|---|---|---|\n' + '\n'.join(rows) + '\n', 'utf-8')
    print(f'{len(res)} 篇，共 {sum(r["words"] for r in res)} 词 → {OUT}')


if __name__ == '__main__':
    main()
