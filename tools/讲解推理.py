"""讲解推理必须说完整（用户 2026-11-04：“我们直接说是过去的事，要用过去式……学生可能没有反应过来，应该这样说：
因为这件事情发生在过去，所以我们这个句子的时态要用过去式……如果要表示‘有’的话，我们就需要使用 there be 句型，
所以在这个地方我们用 there be……你刚讲的有点过于省略了”）。规则只写在这一处，续写检查 ⑫、稿检查 --口语 都调它。

problems(doc)：doc 是讲解稿（稿.json，segments 里中文段的 text）。按 。？！ 切成句子（‖ 不切：一句因果可以在中间停顿）：
  ① 决定句：一句里做了语法 / 用词 / 位置的决定（用、使用、放在、接在、变成、改成、换成、省掉、去掉、代替、过去式是……），
     又说到了英文或语法名词，却没有因果连接词（因为、所以、既然、如果、因此、由于、为了、要表示）——“名词短语，用 X”的省略写法；
     后面紧跟“为什么？”“因为……”两句的不算（先说做法、再自问自答，因果完整）；
  ② 词义省略：“X，就是 Y / X，用 Y”（Y 是英文）这种只丢一个对应、不成句的写法（“有，用 there be”“接着，就是 then”）。
  答案句（英文是：……）、纯英文段不查；讲评语的段（得分点 pt、可替换 alt、读整句、伏笔呼应 echo）和说原文怎么写的句子（含“原文”）不查——
  它们讲的是写得好在哪里，不是做决定。逻辑顺不顺、是不是最好懂的讲法，程序判断不了，交审阅员。
用法：python3 tools/讲解推理.py 稿.json      |   双向验证：python3 tools/防复发/验证/讲解推理.py"""
import json
import re
import sys
from pathlib import Path

SENT = re.compile(r'[^。？！]+[。？！]?')
DECIDE = re.compile(r'用|放在|放到|接在|挪到|提到|变成|改成|换成|省掉|去掉|代替|过去式是|过去分词是')
TERM = re.compile(r'[A-Za-z]|过去式|过去完成时|一般过去时|将来时|现在时|被动|副词|形容词|倒装|从句|状语|主语|宾语|谓语|分词|最高级|句尾|句首|时态')
CAUSE = re.compile(r'因为|所以|既然|如果|因此|由于|为了|要表示|想表示')
BARE = re.compile(r'(?:^|[，：])\s*[一-鿿]{1,8}，(?:就是|用)\s*[A-Za-z]')
ANSWER = re.compile(r'^\s*(?:英文是|先写最简单的)|原文')   # 用 search：答案句开头，或说的是原文
SKIP_PH = {'pt', 'alt', 'read', 'zh'}


def sentences(text):
    return [s.strip() for s in SENT.findall(text.replace('‖', '')) if s.strip()]


def problems(doc, name='稿'):
    E = []
    for g in doc.get('segments', []):
        if g.get('lang', 'Chinese') != 'Chinese' or g.get('ph') in SKIP_PH or g.get('screen') == 'echo':
            continue
        ss = sentences(g['text'])
        for i, s in enumerate(ss):
            nxt = ss[i + 1:i + 3]
            if len(nxt) == 2 and nxt[0].startswith('为什么') and nxt[1].startswith('因为'):
                continue                      # 先说做法、再自问“为什么？”、紧接“因为……”：因果是完整的
            if ANSWER.search(s):
                continue
            if BARE.search(s):
                E.append(f'讲解省略 {name} {g["id"]}：“{s}”——只丢了一个对应，要说成完整的话'
                         f'（如：要表示“有”，英语就要用 there be 句型 / “接着”这个意思，英语里用 then）')
            elif DECIDE.search(s) and TERM.search(s) and not CAUSE.search(s):
                E.append(f'讲解省略 {name} {g["id"]}：“{s}”——做了决定却没说为什么，要说出因果'
                         f'（因为……所以……；如果要表示……就要……；既然……就……）')
    return E


if __name__ == '__main__':
    E = problems(json.loads(Path(sys.argv[1]).read_text('utf-8')), Path(sys.argv[1]).name)
    print('\n'.join(E))
    print(f'讲解推理检查：{len(E)} 处')
    sys.exit(1 if E else 0)
