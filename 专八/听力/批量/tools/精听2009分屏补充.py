"""2009版式补充：真实语境词/自然分屏；只写独立候选快照，不覆盖对齐输入。"""
import copy,json,re
from pathlib import Path
from 精听数据 import dump,sha
from 精听草稿构建 import annotated
D=Path(__file__).resolve().parents[1]
ADD={
'A':{
3:'signed up for~sign up for=phr. 报名选修|psychology=n. 心理学|chances are that=phr. 很可能|statistics=n. 统计学',
6:'journals~journal=n. 学术期刊|critically=adv. 批判性地|assumptions~assumption=n. 假定',
7:'experimental reports=n. 实验报告',
10:'dictate=v. 决定；规定',
11:'present=v. 讲述；呈现',
27:'hypothetical=adj. 假想的|unknowledgeable=adj. 缺乏相关知识的',
34:'area of study=n. 研究领域',
37:'unknowledgeable=adj. 缺乏相关知识的',
43:'grasp=n. 理解；掌握',
45:'important=adj. 重要的',
47:'fit into=phr. 融入；适合',
49:'undertaking=n. 开展；从事',
51:'format=n. 格式|reader awareness=n. 读者意识',
},
'B1':{16:'methods~method=n. 方法|communicating~communicate=v. 表达；传达'},
'B2':{
7:'toastmaster=n. 宴会或会议主持人',
9:'evaluator=n. 评估员|grammarian=n. 语言监督员（此演讲会中的角色）|monitor=v. 监督；留意',
18:'give speeches=phr. 发表演讲|fearful=adj. 害怕的|address=v. 向……讲话|self-confidence=n. 自信',
}}
SPLITS={
'A':{
3:(['chances are that','particularly,'],['刚在大学选修一门课，比如心理学时，','你很可能并没有真正预料到将要学习什么，','尤其没有想到课程会强调研究方法和统计学。']),
6:('examining, critically,',['毫无疑问，在课程学习的其他部分，你们会阅读书籍和期刊，','批判性地考察学者和专家提出的模型、理论、假设和假说。']),
7:('because you will',['我今天的任务是帮助你们了解实验报告的一些重要特点，','因为如果课程重视实践，尤其是实验，你们就必须撰写这类报告。']),
10:('than a modern novelist',['写报告时，你更像古代的说书人，要按照公认且历史悠久的惯例来组织故事，','而不像可以自由决定形式与内容的现代小说家。']),
11:('you are expected',['而且，像旧时的说书人一样，尽管听众往往已经很了解你的故事，','你仍然要把它当作一个从未被听过的故事来讲。']),
27:('an idealized, hypothetical',['然而，实际上，评分人是在代另一个人评估报告：','这是一个理想化、假想的读者，虽然聪明，却不了解你的研究及其所属领域。']),
34:('taking little for granted',['简而言之，你应当为不了解研究领域的人写作，','不要想当然地认为读者具备相关知识。']),
37:('as if it would',['如果你觉得这很难做到，一个有用的办法是：写报告时，','想象读者是你认识的某个人，虽聪明，却不了解你的研究课题。']),
43:('together with evidence',['在这个早期阶段，你主要需要表明自己理解报告中做了什么及其意义，','同时证明自己至少基本掌握了报告格式的要求。']),
45:('because, in being',['“为什么这样做”会变得更重要，','因为既然你要对选题和设计负责，就需要能够说明这种选择的合理性。']),
47:('paying particular attention',['因此，你要养成一种习惯：思考实验或研究中正在考虑的想法，在报告中该如何呈现，','尤其要关注它们如何融入“引言”部分。']),
49:('because it is based',['第二，所开展的项目缺乏研究上的正当理由，','因为其依据的假设，与该领域已有的研究发现相矛盾。']),
51:('and some of the',['好，今天我们简要了解了实验报告的格式、各节的内容，','以及读者意识等一些基本问题。']),
},
'B1':{16:('and equally important,',['加入国际演讲会后，你会学到不同的方法来表达自己真正想说的内容；','同样重要的是，你还会了解听众的期待，从而有条理地向他们传达信息。'])},
'B2':{
7:('but also the opportunity',['是的，国际演讲会安排的不同任务，不仅包括准备演讲并在听众面前发表，','还包括担任会议主持人的机会。']),
9:('or serving as a',['其他任务包括为另一位演讲者担任评估员，','或者担任语言监督员，留意“and”“uh”“er”“you know”等填充词或短语的使用。']),
18:(['he progresses from','to the point where'],['随着一个人不断演讲、不断进步，','他会从害怕站到一群同辈面前，','逐步成长为能够带着一定自信向任何一群人讲话的人。']),
}}


def main():
 import argparse
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
 side={'scope':'只补充2009视觉/语境词，不改变EN/原声时刻/译文完整内容；分屏仍须原音停顿核查','units':[]}
 for code in ['A','B1','B2']:
  src=D/f'精听数据/2009-{code}.json';d=json.loads(src.read_text());before=sha(src);changes=[]
  d['title']=re.sub(r'（新题型优化版所供原文）$','',d['title']);d.setdefault('names',[])
  if code=='B1' and '拉尔夫·斯梅德利' not in d['names']:d['names'].append('拉尔夫·斯梅德利')
  for k,terms in ADD[code].items():
   s=d['sentences'][k-1];extra=annotated(s['en'],s['zh'],terms)['w'];occupied=[(a,b) for w in s['w'] for a,b in w['sp']]
   for w in extra:
    assert all(not any(a<y and b>x for x,y in occupied) for a,b in w['sp']),(code,k,w)
   s['w']+=extra;s['w'].sort(key=lambda w:w['sp'][0][0]);changes.append({'k':k,'en':s['en'],'add':extra})
  for s in d['sentences']:
   for w in s['w']:w['t']='phr' if ' ' in w['h'] else 'word'
  d['splits']={}
  for k,(at,zh) in SPLITS[code].items():
   s=d['sentences'][k-1];assert ''.join(zh)==s['zh'],(code,k,'中文未原样拼回')
   for a in ([at] if isinstance(at,str) else at):assert s['en'].count(a)==1
   d['splits'][str(k)]={'at':at,'zh':zh}
  target=args.out/f'2009-{code}.json';dump(target,d)
  side['units'].append({'id':d['id'],'base_sha256':before,'title':d['title'],'names':d['names'],'vocabulary_additions':changes,'splits':d['splits'],'snapshot':str(target)})
 dump(D/'核验/精听2009版式补充.json',side)
 print('2009三份独立补充快照已生成。')


if __name__=='__main__':main()
