"""作文范文的程序检查（考研写作、六级写作共用，规则只写一处）。
check(e) 返回问题列表；字数上下限由调用方给。
用法：python3 tools/作文规则.py 考研/作文 六级/作文  （逐篇报，有一处退出码 1）
      python3 tools/作文规则.py --自检                （双向验证：埋错必报，原文 0）"""
import json, re, sys, pathlib
WRE = re.compile(r"[A-Za-z0-9]+(?:[’'\-.][A-Za-z0-9]+)*%?")
def wc(t): return len(WRE.findall(t))
# 美式拼写为准：出现英式拼写就报（题目原文不查，只查范文）
BRIT = re.compile(r"\b(\w*(?:colour|favour|honour|labour|behaviour|neighbour|harbour|rumour|humour|vapour|endeavour)\w*|\w+(?:ise|ised|ises|ising|isation|isations)|centre|centres|metre|metres|theatre|programme|programmes|towards|afterwards|onwards|upwards|downwards|backwards|forwards|amongst|whilst|learnt|spelt|travell\w+|cancell\w+|enrol|enrolment|enrolments|fulfil|fulfilment|judgement|ageing|defence|offence|licence|practise|practised|practising|analyse|analysed|catalogue|dialogue|grey|cheque|tyre|kerb|mum|sceptic\w*|aluminium|heart-warming)\b", re.I)
# -ise 结尾但美式也这样拼的词
ISE_OK = {'rise','rises','arise','arises','arising','raise','raises','raised','raising','wise','otherwise','likewise','clockwise','precise','concise','advise','advised','advises','advising','devise','devised','revise','revised','revising','supervise','supervised','supervising','surprise','surprised','surprises','surprising','exercise','exercised','exercises','exercising','enterprise','enterprises','expertise','promise','promised','promises','promising','compromise','compromised','premise','premises','franchise','merchandise','televise','televised','improvise','improvised','despise','despised','disguise','disguised','comprise','comprises','comprising','advertise','advertised','advertising','chastise','demise','noise','noises','poise','praise','praised','praises','praising','cruise','bruise','treatise','paradise','reprise','incise','excise','circumcise','apprise','uprise','sunrise','anise','mortise','tortoise','porpoise','vise','guise','prise','arose','rising','risings'}
def spelling(t):
    return [m[0] for m in BRIT.finditer(t) if m[0].lower() not in ISE_OK and not m[0].lower().endswith('wise')]
def punct(t):
    bad = []
    if re.search(r'["\']', t.replace('’', '')): bad.append('直引号/直撇号')
    for pat, why in [(r'\s[,.;:?!]', '标点前有空格'), (r'[,;:?!][A-Za-z“]', '标点后缺空格'),
                     (r'(?<![A-Z.])(?<!\d)(?<!\b[a-z])\.[A-Za-z“]', '句点后缺空格'), (r'  ', '多余空格'),
                     (r'[一-鿿，。；：？！（）]', '范文里有中文字符'), (r'\s’|“\s|\s”', '引号内侧空格'),
                     (r'\b(\w+) \1\b', '重复词')]:
        for m in re.finditer(pat, t):
            if why == '重复词' and m[1].lower() in {'that', 'had'}: continue
            bad.append(f'{why}：{t[max(0, m.start()-12):m.end()+12]!r}')
    return bad
def numbers(prompt, body, allow=()):
    """正文里带 % 的数字、四位年份必须出现在题目里（推算值写进 allow）。"""
    src = {float(x) for x in re.findall(r'\d+(?:\.\d+)?', prompt)}
    out = []
    for m in re.finditer(r'\b(\d+(?:\.\d+)?)(?=%| percent)|\b(1[89]\d\d|20\d\d)\b', body):
        n = m[1] or m[2]
        if float(n) not in src and n not in allow: out.append(f'数字不在题目里：{n}')
    return out
def word_range(limit):
    """用户 2026-10-26 澄清：题目给了上限 → [下限, 上限]；只给下限（at least N / about N）→ [N, ⌊N × 1.2⌋]。"""
    m = re.search(r'at least (\d+)', limit) or re.search(r'about (\d+)', limit)
    lo = int(m[1]); top = re.search(r'no more than (\d+)', limit)
    return lo, int(top[1]) if top else lo * 12 // 10
def check(e, lo=None, hi=None):
    body = ' '.join(e['body'])
    own = body[len(e['first']):] if e.get('first') and body.startswith(e['first']) else body  # 照抄的题目首句不查拼写
    out = [f'英式拼写：{w}' for w in spelling(own)]
    for t in e['body'] + [e[k] for k in ('title', 'salutation', 'closing', 'signature') if e.get(k)]: out += punct(t)
    if '【图表】' in e['prompt']: out += numbers(e['prompt'], body, e.get('allow_numbers', ()))
    if e.get('first'):
        if not e['body'][0].startswith(e['first']): out.append('首句没有逐字照抄题目给定的句子')
    n = wc(body)
    if 'not including' in e.get('limit', '') and e.get('first'): n -= wc(e['first'])
    if lo and not (lo <= n <= hi): out.append(f'字数 {n} 不在 {lo}—{hi}')
    return out
# 考研作文里不在题目中的数字：推算值与虚构细节（考研/作文/复核记录.md 已逐个复核）
ALLOW = {'w2022-2B': {'63'}, 'w2023-2B': {'2030'}, 'w2024-1B': {'65'}, 'w2026-1B': {'70'}}
def run(dirs, lims=None):
    total = 0
    for d in dirs:
        for p in sorted(pathlib.Path(d).glob('20??.json')):
            for e in json.loads(p.read_text()):
                if not e['body']: continue
                lo, hi = (lims or {}).get(d, (None, None))
                if lo == 'word_range': lo, hi = word_range(e['limit'])
                e.setdefault('allow_numbers', ALLOW.get(e['id'], ()))
                for x in check(e, lo, hi): print(e['id'], x); total += 1
    return total
def selftest():
    e = {'id': 't', 'prompt': '【图表】 39.3% 2019', 'first': 'It is true.', 'limit': '',
         'body': ['It is true. The colour rose to 39.3% in 2019, towards 40%.', 'He said "hi" ,and left.Then the the end。']}
    got = check(e)
    need = ['英式拼写：colour', '英式拼写：towards', '直引号', '标点前有空格', '标点后缺空格', '句点后缺空格', '中文字符', '重复词', '数字不在题目里：40']
    miss = [k for k in need if not any(k in g for g in got)]
    e2 = {'id': 't', 'prompt': '【图表】 39.3% 2019', 'first': 'It is true.', 'limit': '',
          'body': ['It is true. The color rose to 39.3% in 2019, toward the U.S. average. He realized that otherwise exercise helps.']}
    extra = check(e2)
    e3 = dict(e2, body=['It was true. Fine.'])
    if '首句没有逐字照抄题目给定的句子' not in check(e3): miss.append('首句')
    print('自检：埋错', len(need) + 1, '处，漏报', miss, '；正确文本误报', extra)
    return not miss and not extra
if __name__ == '__main__':
    if sys.argv[1:] == ['--自检']: sys.exit(0 if selftest() else 1)
    n = run(sys.argv[1:]); print('问题', n, '处'); sys.exit(1 if n else 0)
