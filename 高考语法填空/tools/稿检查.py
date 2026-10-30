"""讲解稿的程序检查（有一处就退出码 1）：
① 稿里的答案表 = 答案文件（官方答案，原文目录）；每题“答案”段的配音文字里含答案（63 题 that、which 都要有；62 题 Drawn 大写）；
② 朗读段 en 是原文里连续的一段（逐字相同）；配音文字 = en 去掉中文注释、空格读作 blank（只比单词）；
③ 每题的步骤 读句→提示→词性→成分→形式→答案→口诀 全部出现且顺序不乱；答案段之前空格不显示答案；
④ 全文通读 = 原文填上答案、去掉中文注释（逐词相同）；
⑤ 中文段的配音文字里没有阿拉伯数字（题号写汉字，防止读成 five six）；
⑥ 问句干脆（用户 2026-10-30：“是不是谓语呢？”尾音轻飘）：？ 前不带 呢 / 吧 / 啊，问句后面是 ‖ 或段尾（停一下）；
⑦ 给了词的题：“提示”段里先单独说出词义，“X 的意思……。‖”自成一句（用户 2026-10-30：先说 hold 的意思是举办，停一下，再推理）；
   答案段的“答案”前面有 ‖ 或在段首。
用法：python 稿检查.py 稿.json [--自检]"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STEPS = ['读句', '提示', '词性', '成分', '形式', '答案', '口诀']
NOTE = re.compile(r'\s*\([^()]*[一-鿿][^()]*\)')


def words(s):
    return re.findall(r"[a-z]+(?:'[a-z]+)?", s.lower().replace('’', "'"))


def problems(doc):
    src = json.loads((ROOT / doc['原文']).read_text('utf-8'))
    ans_file = json.loads((ROOT / doc['原文']).with_name('答案_' + Path(doc['原文']).name).read_text('utf-8'))['answers']
    P, errs = src['paragraphs'], []
    if doc['answers'] != ans_file:
        errs.append(f'答案表与答案文件不同：{doc["answers"]} ≠ {ans_file}')
    segs = doc['segments']
    by_q = {}
    for s in segs:
        if s.get('q'):
            by_q.setdefault(s['q'], []).append(s)
        if s['lang'] == 'Chinese' and re.search(r'[0-9]', s['text']):
            errs.append(f"{s['id']} 中文配音文字里有阿拉伯数字：{s['text'][:30]}")
        if 'en' in s:
            if not any(s['en'] in p for p in P):
                errs.append(f"{s['id']} 朗读的原句不是原文里连续的一段：{s['en'][:50]}")
            exp = words(re.sub(r'___\d+___(\s*\([^()]*\))?', ' blank ', NOTE.sub('', s['en'])))
            if words(s['text']) != exp:
                errs.append(f"{s['id']} 配音文字与原句不一致：{' '.join(words(s['text']))} ≠ {' '.join(exp)}")
    for q in range(56, 66):
        ss = by_q.get(q, [])
        seq = [st for s in ss for st in s.get('steps', [])]
        if seq != STEPS:
            errs.append(f'{q} 题步骤不全或顺序不对：{seq}')
        if not any('en' in s for s in ss):
            errs.append(f'{q} 题没有朗读原句')
        a = [s for s in ss if '答案' in s.get('steps', [])]
        if a:
            if not a[0].get('answer'):
                errs.append(f'{q} 题答案段没有让空格显示答案')
            for w in doc['answers'][str(q)].split(' / '):
                if w not in a[0]['text']:
                    errs.append(f"{q} 题答案段没说出答案 {w}：{a[0]['text']}")
            first = next(i for i, s in enumerate(ss) if s.get('answer'))
            if ss[first] is not a[0]:
                errs.append(f'{q} 题答案在“答案”段之前就显示了')
    full = ' '.join(s['text'] for s in segs if s.get('full'))
    filled = ' '.join(NOTE.sub('', re.sub(r'___(\d+)___(\s*\([^()]*\))?',
                                          lambda m: doc['answers'][m.group(1)].split(' / ')[0], p)) for p in P)
    if words(full) != words(filled):
        errs.append('全文通读与原文（填上答案）不一致')
    for s in segs:
        if s['lang'] != 'Chinese':
            continue
        for m in re.finditer('？', s['text']):
            if re.search('[呢吧啊]$', s['text'][:m.start()]):
                errs.append(f"{s['id']} 问句带“{s['text'][m.start() - 1]}”：{s['text'][max(0, m.start() - 12):m.end()]}")
            rest = s['text'][m.end():]
            if rest and not rest.startswith('‖'):
                errs.append(f"{s['id']} 问句后面没有停顿标记 ‖：{s['text'][max(0, m.start() - 12):m.end() + 6]}")
        if '提示' in s.get('steps', []) and '给' in s['text'] and '没' not in s['text']:
            if not re.search(r"‖[A-Za-z]+ (?:在这里)?的意思[^。‖，]*。‖", s['text']):
                errs.append(f"{s['id']} 给了词，却没先单独说出词义（“‖X 的意思是……。‖”，中间不带逗号）：{s['text'][:40]}")
        if '答案' in s.get('steps', []):
            i = s['text'].find('答案')
            if i > 0 and s['text'][:i] != '所以' and '‖' not in s['text'][:i]:
                errs.append(f"{s['id']} “答案”前面没有停顿标记 ‖：{s['text'][:40]}")
    ids = [s['id'] for s in segs]
    if len(set(ids)) != len(ids):
        errs.append('段落 id 重复')
    return errs


def selftest(doc):
    import copy
    mines = []
    d = copy.deepcopy(doc); d['answers']['59'] = 'was'; mines.append(('答案表', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q62f')['text'] = '答案：drawn。'; mines.append(('大写', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q57b')['en'] = 'The exact date and ___57___ (frequent) of daji vary from region to region.'; mines.append(('原句', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q64d')['steps'] = []; mines.append(('步骤', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'f05')['text'] = 'As transportation and communication was underdeveloped at that time, it was very difficult for households to obtain daily necessities.'; mines.append(('通读', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q58a')['text'] = '第58题。'; mines.append(('数字', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q65e')['answer'] = True; mines.append(('答案提前显示', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q56d')['text'] = '那它在这句话里是不是谓语呢？我们找一下主干。'; mines.append(('问句带呢、问句后没停顿', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q56c')['text'] = '括号里给了一个词，hold，举办。给了词，一般都要变形。hold 是个动词。'; mines.append(('词义没单独成句', d))
    d = copy.deepcopy(doc); next(s for s in d['segments'] if s['id'] == 'q59f')['text'] = '过去时，再加上复数，就是 were。答案：were。'; mines.append(('答案前没停顿', d))
    ok = not problems(doc)
    for name, d in mines:
        e = problems(d)
        print(f'  雷 {name}：{"报出" if e else "漏查"}')
        ok &= bool(e)
    print('自检', '通过' if ok else '失败')
    return ok


if __name__ == '__main__':
    doc = json.loads(Path(sys.argv[1]).read_text('utf-8'))
    if '--自检' in sys.argv:
        sys.exit(0 if selftest(doc) else 1)
    e = problems(doc)
    for x in e:
        print('✗', x)
    print(f'稿检查：{len(e)} 处')
    sys.exit(1 if e else 0)
