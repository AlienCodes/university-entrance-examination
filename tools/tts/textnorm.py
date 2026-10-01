"""把试卷原文转换成“朗读文本”：去掉中文注释，把数字、符号、缩写写成美式英语的读法。

规则只覆盖这 70 篇文章里真实出现的写法；人名、多音词等逐词逐句的特殊读法放在 pronunciations.json 里。
"""
import re
from num2words import num2words

CJK = r'\u3000-\u303f\u4e00-\u9fff\uff00-\uffef'


def card(n):
    """美式基数词：去掉英式的 and。"""
    s = num2words(n)
    return s.replace(' and ', ' ').replace(',', '')


def ordinal(n):
    return num2words(n, to='ordinal').replace(' and ', ' ').replace(',', '')


def decimal(s):
    """0.76 -> zero point seven six；1.2 -> one point two"""
    whole, frac = s.split('.')
    head = card(int(whole)) if whole else 'zero'
    return head + ' point ' + ' '.join(card(int(d)) for d in frac)


def number(s):
    s = s.replace(',', '')
    return decimal(s) if '.' in s else card(int(s))


def year(n):
    if 2000 <= n <= 2009:
        return card(n)
    hi, lo = divmod(n, 100)
    if lo == 0:
        return card(hi) + ' hundred'
    if lo < 10:
        return card(hi) + ' oh ' + card(lo)
    return card(hi) + ' ' + card(lo)


def decade(n):
    """1960 -> nineteen sixties；60 -> sixties"""
    tens = {20: 'twenties', 30: 'thirties', 40: 'forties', 50: 'fifties', 60: 'sixties',
            70: 'seventies', 80: 'eighties', 90: 'nineties'}
    if n < 100:
        return tens[n]
    hi, lo = divmod(n, 100)
    return card(hi) + ' ' + (tens[lo] if lo else 'hundreds')


UNITS = {'mm': 'millimeters', 'ml': 'milliliters', 'kg': 'kilograms', 'g': 'grams', 'L': 'liters',
         'm': 'million', 'p': 'p'}
SINGULAR = {'millimeters': 'millimeter', 'milliliters': 'milliliter', 'kilograms': 'kilogram',
            'grams': 'gram', 'liters': 'liter'}

ABBR = [
    (r'\bDr\.\s', 'Doctor '), (r'\bMr\.\s', 'Mister '), (r'\bMrs\.\s', 'Missus '),
    (r'\bProf\.\s', 'Professor '), (r'\bSt\.\s(?=Louis|Andrews)', 'Saint '),
    (r'\be\.\s?g\.\s?', 'for example, '), (r'\bi\.e\.\s?', 'that is, '),
    (r'\bNov\.\s(\d+)\b', lambda m: 'November ' + ordinal(int(m.group(1)))),
    (r'\betc\.', 'et cetera.'),
]
MONTHS = 'January|February|March|April|May|June|July|August|September|October|November|December'


def normalize(text):
    t = text
    # 1. 中文注释 (臭氧) / 全角括号 → 删除；其余中文字符也删除
    t = re.sub(r'\s*[（(][^()（）]*[' + CJK + r'][^()（）]*[)）]', '', t)
    t = re.sub(r'[' + CJK + r']+', '', t)
    # 2. 缩写
    for pat, rep in ABBR:
        t = re.sub(pat, rep, t)
    # 3. 化学式、特殊写法
    t = t.replace('CO₂', 'C O two').replace('24/7', 'twenty-four seven').replace(' & ', ' and ')
    t = re.sub(r'(?<=[A-Za-z])\(', ' (', t)
    t = re.sub(r'\b(\d+)-or\b', r'\1 or', t)
    # 日期：March 7, 1907 -> March seventh, 1907
    t = re.sub(r'\b(' + MONTHS + r')\s+(\d{1,2})\b(?!,\d)', lambda m: m.group(1) + ' ' + ordinal(int(m.group(2))), t)
    # 4. 分数 1/1000th
    t = re.sub(r'\b1/(\d+)th\b', lambda m: 'one ' + re.sub(r'^one ', '', ordinal(int(m.group(1)))).replace(' ', '-'), t)
    # 5. 货币 £520m / $2 million / $1,000
    t = re.sub(r'£(\d[\d,]*)m\b', lambda m: number(m.group(1)) + ' million pounds', t)
    t = re.sub(r'£(\d[\d,.]*)', lambda m: number(m.group(1)) + ' pounds', t)
    t = re.sub(r'\$(\d[\d,.]*)\s+(million|billion)', lambda m: number(m.group(1)) + ' ' + m.group(2) + ' dollars', t)
    t = re.sub(r'\$(\d[\d,.]*)', lambda m: number(m.group(1)) + ' dollars', t)
    # 6. 百分比
    t = re.sub(r'(\d[\d,]*(?:\.\d+)?)%', lambda m: number(m.group(1)) + ' percent', t)
    # 7. 年代 1960s / pre-1970s / 50s
    t = re.sub(r'\b(1[5-9]\d0|20[0-2]0)s\b', lambda m: decade(int(m.group(1))), t)
    t = re.sub(r'(?<![\d,.])([2-9]0)s\b', lambda m: decade(int(m.group(1))), t)
    # 8. 序数 21st / 18th-century
    t = re.sub(r'\b(\d+)(st|nd|rd|th)\b', lambda m: ordinal(int(m.group(1))), t)
    # 9. 数字+单位 0.5mm / 3L / 100ml / 5g / 18p / 1m litres
    def unit(m):
        n, u = m.group(1), m.group(2)
        word = UNITS[u]
        if word in SINGULAR and n in ('1', '1.0'):
            word = SINGULAR[word]
        return number(n) + ' ' + word
    t = re.sub(r'\b(\d[\d,]*(?:\.\d+)?)(mm|ml|kg|g|L|m|p)\b', unit, t)
    # 9b. 海拔写法 "6,263 m;" -> meters
    t = re.sub(r'\b(\d[\d,]*)\s+m(?=[;,.]|$)', lambda m: number(m.group(1)) + ' meters', t)
    # 10. 年份：1500–2099 的四位数（后面跟 years 时按基数读）
    t = re.sub(r'(?<![\d,.$£])\b(1[5-9]\d\d|20\d\d)\b(?!\s*(?:years|people|commodities)\b)(?!\d)(?!,\d)',
               lambda m: year(int(m.group(1))), t)
    # 11. 其余数字
    t = re.sub(r'(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?![\d])',
               lambda m: number(m.group(0)), t)
    # 12. 标点：省略号、破折号统一；去掉多余空格
    t = t.replace('…', '...').replace('–', '—')
    t = re.sub(r'\s+([,.;:?!])', r'\1', t)
    t = re.sub(r'\s{2,}', ' ', t).strip()
    return t


if __name__ == '__main__':
    import json, sys
    S = json.load(open(sys.argv[1]))
    for o in S:
        for p in o['sents']:
            for s in p:
                n = normalize(s)
                if n != s:
                    print(o['id'], '|', s, '\n   ->', n)
