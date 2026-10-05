"""四级仔细阅读文章的排版与标点检查（程序检查，任何一条不通过都报错）。

    python3 四级/tools/check_text.py          # 检查 四级/仔细阅读/passages.json

extract_reading.py 生成文章后自动调用。规则与高考 tools/build.py 的排版检查一致，并针对 PDF 提取补充了几条：
直引号、引号内侧空格、标点前多空格、标点后缺空格、括号前后空格、重复单词、重复标点、
带空格的连字符、拆开的缩写（U. S.）、句末小写开头、段尾无标点、引号/括号不配对、括号外残留汉字、
可疑字符（全角标点、OCR 常见的 0/O、1/l 混淆）、行尾连字符拆词。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ABBR = r'(?:Mr|Mrs|Ms|Dr|Prof|St|Jr|Sr|vs|etc|e\.g|i\.e|U\.S|U\.K|Ph\.D|a\.m|p\.m|No|Inc|Co|Ltd|Jan|Feb|Mar|Apr|Aug|Sept|Oct|Nov|Dec)'
RULES = [
    (r'["\']', '直引号或直撇号'),
    (r'[“‘]\s|\s[”]', '引号内侧空格'),
    (r'\s[,.;:?!)]', '标点前有空格'),
    (r'(?<=[A-Za-z])[,;:?!](?=[A-Za-z“‘(])', '标点后缺空格'),
    (r'(?<=[a-z])\.(?=[A-Z][a-z])', '句号后缺空格'),
    (r'(?<=[A-Za-z0-9])\((?=[A-Za-z])', '括号前缺空格'),
    (r'\)(?=[A-Za-z0-9])', '括号后缺空格'),
    (r'\(\s|\s\)', '括号内侧空格'),
    (r'\b(\w+) \1\b', '重复单词'),
    (r'([,;:!?])\1|(?<!\.)\.\.(?!\.)|[,;:]\.|\.,', '重复或叠加标点'),
    (r'\s-\s|\s-(?=[A-Za-z])|(?<=[A-Za-z])-\s(?!(?:and|or|to) )', '带空格的连字符（应为破折号或复合词；four- and five-year-olds 这类悬空连字符除外）'),
    (r'\s[—–]|[—–]\s', '破折号两侧有空格'),
    (r'\b[A-Z]\. [A-Z]\.(?= |$)', '拆开的缩写（如 U. S.）'),
    (r'[，。；：？！（）、]', '全角标点'),
    (r'\s{2,}', '多余空格'),
    (r'(?<=[A-Za-z])0|0(?=[A-Za-z]{2})|(?<=\d)[Oo](?=\d)|(?<=\d)[lI](?=\d)', '数字与字母混淆（0/O、1/l）'),
    (r'\s’(?=[A-Za-z])', '单引号开头用了右引号'),
]


def check(p):
    probs = []
    paras = p['paras']
    for k, s in enumerate(paras, 1):
        bare = re.sub(r' \([^()]*[一-鿿][^()]*\)', '', s)      # 去掉中文注释后再查
        for pat, name in RULES:
            m = re.search(pat, bare)
            if m and not (name == '重复单词' and m.group(1).lower() in ('that', 'had', 'is')):
                probs.append(f'第{k}段 {name}：…{bare[max(0, m.start() - 25):m.end() + 25]}…')
        if re.search(r'[一-鿿]', bare):
            probs.append(f'第{k}段 括号注释以外有汉字')
        for m in re.finditer(r'(?:[.!?]|[.!?]["”’)]+) +([a-z])', bare):
            if re.match(r'[?!]["”’)]', bare[m.start():]):      # “… work?” said Dr Matous / (on fashion!) is：引语或括号内的问号叹号，后面接小写是对的
                continue
            before = bare[:m.start() + 1]
            if not re.search(rf'\b{ABBR}\.$', before) and not bare[m.start() - 1:m.end() + 3].startswith('E. coli'):     # 学名缩写 E. coli
                probs.append(f'第{k}段 句号后小写开头：…{bare[max(0, m.start() - 25):m.end() + 15]}…')
        if not re.search(r'[.!?]["”’)]*$|[.!?]’”$', bare):
            probs.append(f'第{k}段 段尾没有句末标点：…{bare[-40:]}')
        if not re.match(r'["“‘(]?[A-Z0-9]', bare):
            probs.append(f'第{k}段 段首不是大写字母：{bare[:40]}…')
        if bare.count('(') != bare.count(')'):
            probs.append(f'第{k}段 括号不配对')
    # 双引号按全文配对；跨段引语（段尾不收引号、下段以 “ 开头）是英文的正规写法
    allt = ' '.join(paras)
    o, c = allt.count('“'), allt.count('”')
    if o != c:
        probs.append(f'全文双引号不配对（“ {o} 个，” {c} 个）')
    depth = 0
    for ch in allt:
        if ch in '“”':
            depth += 1 if ch == '“' else -1
            if depth not in (0, 1):
                probs.append('双引号嵌套或顺序错误')
                break
    return probs


def main(path=ROOT / '仔细阅读' / 'passages.json'):
    P = json.loads(Path(path).read_text('utf-8'))
    n = 0
    for p in P:
        for x in check(p):
            print(f"{p['id']} {p['paper']} {p['passage']} {x}")
            n += 1
    return n


if __name__ == '__main__':
    n = main(*sys.argv[1:])
    if n:
        sys.exit(f'排版检查未通过：{n} 处')
    print('排版检查通过')
