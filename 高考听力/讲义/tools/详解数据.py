"""逐题详解的材料、逐字引用检查及完全相同试卷的精确复用。
python 详解数据.py prepare | check [套号...]
"""
import collections
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
import 制作 as M

D = M.D
OUT = D / '逐题详解'
PACKS = D / '工作材料/详解分组'
PLAN = D / '详解审校分组.json'
OVERRIDES = {'2024-jia': {'3': 'B'}, '2020-shc': {'12': 'C', '13': 'B'}, '2025-xkb2': {'15': 'A', '20': 'C'}}
RULE = '''# 高考听力逐题详解整理
用户已授权6个并行审校助手。本批是同50套配套纸质学习资料的新“逐题详解”，不是另做一轮盲解题。根据给出的正确选项、已审校原文与中文，逐题讲清答案依据与排除思路；明显冲突不要编理由，写入待核。
只读本材料包，直接写指定JSON。不要改题目、源原文、译注、音视频或别人的文件；不要再开子代理。
每套输出到 高考听力/讲义/逐题详解/<id>.json，格式：
{"id":"<id>","题":{"1":{"答案":"C","题干译":"男士是什么身份？","选项译":{"A":"...","B":"...","C":"..."},"依据":[1,2],"讲解":"先说明原文关键线索的含义，再解释如何与正确选项对应。约60—160汉字；计算题明确算式，推断题明确推理桥梁。不要只把答案翻译一遍。","错项":{"A":"15—65字，说明该选项与原文哪里不符或缺少依据。","B":"..."}},...},"待核":[]}
每套恰好20题。答案字母按提供的当前教案答案；上海4选项，其余3选项，选项中文不得漏。依据是“逐句编号”sid，1—4句，必须来自对应题组；不逐字重抄原句，程序会按sid原样排出英文与中文。
讲解要像认真教学生的老师：定位线索→理解意思→联系题干→得出结论。错项具体到人、时间、对象、原因、态度或推断范围；不要无依据说“原文没提到”。不要强行虚构说话人的性别；未标M/W时，可说“原文先说”“对话随后提到”。
题干为空时，从题组末尾口述Question句确定题意；不得凭选项臆造题目。若真的缺口述题干，标待核并说明，不瞎写。
同一个短对话可能读了两遍，选一遍的依据即可。引用sid均属于本套原文，选项顺序不可沿用其他卷字母。
2019-shq第10题采用A：具体动作是反复相加、查看数字，trying to balance最贴切；B“处理预算”只笼统描述，注意区分。2024-jia第3题当前教案采用B，来自已经留存的原始解析与通话内容核定，不沿用旧视频答案页A。
完成后运行：/workspace/work/venv/bin/python 高考听力/讲义/tools/详解数据.py check <你负责的id...>，有结构或引用错误自行改好。只报告完成数、待核点与文件路径；不要输出全文。
'''


def cases():
    result = copy.deepcopy(M.data(False))
    for c in result:
        for n, letter in OVERRIDES.get(c['id'], {}).items():
            c['questions'][int(n)-1]['answer'] = letter
    return result


def fingerprint(c):
    payload = {'q': [{k:q[k] for k in ['n','stem','options','answer']} for q in c['questions']],
               'g': [(g['qs'],[M.normal(s['en']) for s in g['sentences']]) for g in c['groups']]}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def source_hints(sid):
    papers = json.loads((M.G/'套.json').read_text('utf-8'))
    originals = json.loads((M.G/'原始材料/清单.json').read_text('utf-8'))
    hints = {}
    for row in originals.get(papers[sid]['题目'],{}).get('解析',[]):
        p = M.G/'精读/准备/解析文本'/(Path(row['文件']).stem+'.txt')
        if not p.exists():continue
        text=p.read_text('utf-8')
        cut=re.search(r'(?m)^\s*21[.．]',text)
        if cut:text=text[:cut.start()]
        for m in re.finditer(r'【(\d{1,2})题详解】\s*([^\n]+)',text):
            if 1<=int(m[1])<=20:hints[m[1]]=m[2][:650]
    return hints


def prepare():
    all_cases=cases();groups={}
    for c in all_cases:groups.setdefault(fingerprint(c),[]).append(c)
    canonical=[v[0] for v in groups.values()]
    buckets=[[] for _ in range(6)];loads=[0]*6
    for c in sorted(canonical,key=lambda c:-sum(len(s['en']) for g in c['groups'] for s in g['sentences'])):
        i=min(range(6),key=lambda i:loads[i]);buckets[i].append(c)
        loads[i]+=sum(len(s['en'])+len(s['zh']) for g in c['groups'] for s in g['sentences'])
    OUT.mkdir(exist_ok=True);PACKS.mkdir(parents=True,exist_ok=True)
    plan={'groups':{},'copies':{v[0]['id']:[c['id'] for c in v[1:]] for v in groups.values() if len(v)>1}}
    for i,bucket in enumerate(buckets,1):
        name=f'组{i:02d}';plan['groups'][name]=[c['id'] for c in bucket]
        parts=[RULE]
        for c in bucket:
            parts += [f'\n# 套号 {c["id"]} · {c["title"]}']
            hints=source_hints(c['id'])
            for g in c['groups']:
                parts += [f'\n## {g["title"]}']
                for s in g['sentences']:
                    parts += [f'[{s["display_sentence"]}] {s["en"]}\n中文：{s["zh"]}']
                for n in g['qs']:
                    q=c['questions'][n-1];parts += [f'\nQ{n}. {q["stem"] or "（题干为录音口述，见本组Question句）"}　【当前答案：{q["answer"]}】']
                    parts += [f'{k}. {v}' for k,v in q['options'].items()]
                    if str(n) in hints:parts += ['原始解析提示（仍须按本组实际原文核对）：'+hints[str(n)]]
        (PACKS/f'{name}.txt').write_text('\n'.join(parts),'utf-8')
    PLAN.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({'groups':plan['groups'],'copies':plan['copies'],'chars':loads},ensure_ascii=False,indent=2))


def check_case(c):
    path=OUT/(c['id']+'.json')
    assert path.exists(),f'{c["id"]}缺详解'
    x=json.loads(path.read_text('utf-8'));assert x['id']==c['id']
    assert not x.get('待核'),f'{c["id"]}待核：{x.get("待核")}'
    assert set(x['题'])=={str(i) for i in range(1,21)},f'{c["id"]}题数不齐'
    sentences={s['display_sentence']:s for g in c['groups'] for s in g['sentences']}
    for q in c['questions']:
        n=q['n'];r=x['题'][str(n)];lab=f'{c["id"]}Q{n}'
        assert r['答案']==q['answer'],lab+'答案不符'
        assert set(r['选项译'])==set(q['options']),lab+'选项译不齐'
        assert set(r['错项'])==set(q['options'])-{q['answer']},lab+'错项不齐'
        assert r['题干译'].strip() and all(v.strip() for v in r['选项译'].values()),lab+'空翻译'
        assert 40<=len(r['讲解'])<=500,lab+'讲解长度不当'
        assert all(6<=len(v)<=220 for v in r['错项'].values()),lab+'错项说明过短或过长'
        assert 1<=len(r['依据'])<=4 and len(r['依据'])==len(set(r['依据'])),lab+'依据数量错误'
        allowed={s['display_sentence'] for g in c['groups'] if n in g['qs'] for s in g['sentences']}
        assert set(r['依据']).issubset(allowed),lab+'依据跨组或不存在'
        assert not any(re.match(r'^Question\s*[:：]',sentences[k]['en'],re.I) for k in r['依据']),lab+'不能只引用题干当依据'
    return x


def duplicate():
    all_cases={c['id']:c for c in cases()};p=json.loads(PLAN.read_text('utf-8'))
    for canonical,others in p['copies'].items():
        x=check_case(all_cases[canonical])
        for sid in others:
            c0,c1=all_cases[canonical],all_cases[sid];assert fingerprint(c0)==fingerprint(c1)
            a=[s for g in c0['groups'] for s in g['sentences']];b=[s for g in c1['groups'] for s in g['sentences']]
            mapping={s0['display_sentence']:s1['display_sentence'] for s0,s1 in zip(a,b)}
            result=copy.deepcopy(x);result['id']=sid;result['精确复用自']=canonical
            for r in result['题'].values():r['依据']=[mapping[k] for k in r['依据']]
            (OUT/(sid+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
            check_case(c1)
    print('完全一致的题目与录音内容已精确复用，并重映射依据编号。')


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='duplicate':duplicate()
    else:
        ids=set(sys.argv[2:]);cc=[c for c in cases() if not ids or c['id'] in ids]
        for c in cc:check_case(c)
        print(f'{len(cc)}套、{20*len(cc)}题详解结构、当前答案及依据引用检查通过')
