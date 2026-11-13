"""将供给材料中的2016—2024听力试卷转为考试适配器数据；不编口述题干。"""
import json,re,hashlib
from pathlib import Path
D=Path(__file__).resolve().parents[1]
YEARS=[2016,2017,2018,2019,2021,2022,2023,2024]

def clean_text(t):
    out=[]
    for l in t.splitlines():
        if re.search(r'^来源：|^SHA256：|^方式：|^原PDF|^以下文字|^以下为|^===|英语专业八级考试真题解析|网站 tem8.net|微信公号|^\s*\d+\s*/\s*\d+\s*$|https://',l):continue
        out.append(l)
    return '\n'.join(out)

def questions(t):
    t=t[t.index('SECTION B INTERVIEW')+len('SECTION B INTERVIEW'):]
    t=re.split('ANSWER SHEET 1',t)[0]
    t=re.sub(r'(?im)^\s*Now,? listen[^\n]*\n','\n',t)
    qs=list(re.finditer(r'(?m)^\s*(\d{1,2})[.．]\s*(?=A[.．])',t));out=[]
    for i,m in enumerate(qs):
        s=t[m.end():qs[i+1].start() if i+1<len(qs) else len(t)]
        opts=list(re.finditer(r'(?<!\w)([ABCD])[.．]\s+',s));row={}
        for k,x in enumerate(opts):
            raw=s[x.end():opts[k+1].start() if k+1<len(opts) else len(s)]
            raw=re.sub(r'\s+',' ',raw).strip()
            row[x[1]]=raw
        assert set(row)==set('ABCD'),(m[1],row,s)
        out.append({'n':int(m[1]),'stem':'','options':[row[l] for l in 'ABCD'],'answer':None,'group':'part1' if int(m[1])<=5 else 'part2'})
    assert [q['n'] for q in out]==list(range(1,11)),[q['n'] for q in out]
    return out

def sheet(rows):
    return [[k,v] if k!='col' else ['col'] for k,v in rows]
SHEETS={
2016:[('title','Models for Arguments'),('h','Three models for arguments'),('b','the first model for arguing is called {1}'),('d','arguments are treated as war'),('d','there is much winning and losing'),('d','it is a {2} model for arguing'),('b','the second model for arguing is arguments as proofs:'),('d','warranted {3}'),('d','valid inferences and conclusions'),('d','no {4} in the adversarial sense'),('b','the third model for arguing is {5}'),('d','the audience is {6} in the argument'),('d','arguments must {7} the audience'),('col',''),('h','Traits of the argument as war'),('b','very dominant: it can shape {8}'),('b','strong arguments are needed'),('b','negative effects include:'),('d','{9} are emphasized'),('d','winning is the only purpose'),('d','this type of arguments prevent {10}'),('d','the worst thing is {11}'),('b','implication from arguments as war: {12}'),('d','e.g., one providing reasons and the other raising {13}'),('d','the other one is finally persuaded'),('h','Suggestions on new ways to {14} of arguments'),('b','think of new kinds of arguments'),('b','change roles in arguments'),('b','{15}')],
2017:[('title','The Modes of Language'),('h','Three modes of language'),('b','Speech'),('b','Writing'),('b','{1}'),('h','Speech and writing'),('b','speech is considered {2} because'),('d','all languages are spoken'),('d','children acquire spoken language first'),('d','{3} requires reading and writing'),('b','speech and writing have {4} roles'),('d','legal contracts are written for'),('e','providing permanent records'),('e','{5} disputes over oral contracts'),('b','speech is more appropriate in {6}'),('d','face-to-face casual conversations'),('d','business transactions in stores'),('d','discussion in a classroom'),('col',''),('b','{7} of speech and writing'),('d','immediate clarification in speech'),('d','visible {8} in conversation'),('d','sense of {9} in writing'),('d','use of intonation to express {10}'),('d','writing seen to be more {11}'),('d','lack of {12} in on-line written “chat”'),('b','{13} between speech and writing'),('d','linguistic markers of interactivity vary with {14}'),('d','how language is structured depends more on {15}'),('h','Conclusion'),('p','As two different modes of language, speech and writing have their own characteristics.')],
2018:[('title','Language and humanity'),('p','Language is powerful and it can help us do or get things as we wish.'),('h','Language as a born trait'),('b','Language has evolved only in {1}.'),('b','Comparison between chimpanzees and human beings:'),('d','Chimpanzees'),('e','use of tools: once seen as a sign of {2}'),('e','inability to {3}'),('e','tendency to {4}'),('d','Human beings'),('e','able to improve and build on {5}'),('e','able to {6} ideas'),('h','Language and social learning'),('b','Problem of social learning: {7}'),('d','Cause:'),('e','stealing others’ idea by {8}'),('d','Solution:'),('e','{9} developed to share ideas'),('col',''),('b','Results'),('d','{10} made available to every individual'),('d','language as social technology to enhance {11}'),('h','Language and the modern world'),('b','Existence of many different languages has led to'),('d','separation of cooperative groups'),('d','{12}'),('d','knowledge protection'),('d','slow flow of ideas and tendency toward {13}'),('b','Globalization needs {14}'),('b','{15} hinder cooperation.'),('h','Solution: one world with one language')],
2019:[('title','Body Language and Mind'),('h','I. Introduction'),('p','Body language reveals who we are.'),('h','II. Nonverbal expressions of {1}'),('b','feeling powerful: {2}'),('d','e.g. athletes with arms up in a V sign'),('b','feeling powerless: {3}'),('d','e.g. refusing to bump into the person nearby.'),('b','people’s behavior tends to become {4} in a high- and low-power situation.'),('d','people don’t mirror each other.'),('b','MBA students exhibit the full range of power nonverbals.'),('d','e.g. students with power have strong desire for {5}'),('b','power nonverbals are also related to {6}'),('col',''),('h','III. Relationship between {7}'),('b','the powerful are more {8}'),('b','hormones differ with {9}'),('b','an experiment:'),('d','procedure:'),('e','adopting high- or low-power poses and completing items'),('e','being given {10}'),('e','having saliva tested'),('d','results:'),('e','{11}: much higher with high-power people'),('e','an increase in {12} in low-power people'),('e','hormonal changes: making brain {13}'),('h','IV. Conclusion'),('b','behavior can {14}'),('b','before getting into stressful situations'),('d','get your brain ready to {15}')],
2021:[('title','Current Challenges Confronting U.S. Higher Education'),('h','The first challenge: force of the marketplace'),('b','Current situation:'),('d','Presence of the marketplace as {1} external force'),('d','Government support: {2}'),('d','Public institution asking for less government {3}'),('e','e.g., new legislation to provide {4}'),('b','Results:'),('d','Higher institutional priorities given to {5}'),('e','because of their {6}'),('d','Ways to generate more money for institutions'),('e','creating new programs, e.g., {7}'),('e','adding new units focusing on generating {8}'),('e','building {9}'),('b','Implications'),('d','increasing focus on {10} in academic research'),('d','higher tuition fees for students'),('p','University administrators have to respond to the marketplace.'),('col',''),('h','The second challenge: equality in {11}'),('b','Post War massification of U.S. higher education:'),('d','{12}'),('b','Reasons:'),('d','Low {13} of racial and ethnic minorities'),('d','Inability of low-income individuals to {14}'),('b','Government role:'),('d','Mediating the negative effects of competition in order to {15}')],
2022:[('title','Fields and Branches of Anthropology'),('h','Literal meaning of anthropology'),('b','Bohannan: each science has its definition of human.'),('d','{1}: a human as a choice-making animal'),('d','philosopher: a human as a rationalizing animal'),('d','anthropology: {2} about human behavior'),('b','Image of anthropologists'),('d','in films and TV shows: adventurers and heroes'),('d','their work in reality: {3}'),('h','Fields and branches of anthropology'),('b','Development of anthropology in Western civilization'),('d','early Greek and Roman philosophers’ interest: {4}'),('d','the Age of Exploration leading to the study of {5}'),('b','Two broad fields of anthropology'),('d','{6} anthropology'),('e','related subjects: anatomy, biology, etc.'),('e','focus of study: evolution of human species'),('e','ways of study: {7}'),('col',''),('d','cultural anthropology'),('e','focus of study: {8} in human societies'),('e','Kluckhohn’s book: {9}, one of the best introductions to the field'),('e','subfields: archaeology, {10} and ethnography'),('e','ethnography: description of human societies based on {11}'),('b','Psychological anthropology'),('d','focus of study: human {12}'),('h','Common features in all societies'),('b','Human biology'),('b','Existence of {13}'),('b','Education'),('h','{14} for anthropology'),('b','Helping future planning'),('b','Helping {15}')],
2023:[('title','Metaphors in Speaking'),('h','Definition'),('p','Metaphor: a way of {1} before a way of words'),('h','Examples of metaphors'),('b','All Shook Up by Elvis Presley'),('d','reason for metaphors: to explain {2}'),('d','Aristotle’s definition of metaphor:'),('e','the thing and its name belonging to {3}'),('b','Romeo and Juliet by Shakespeare'),('d','result of using metaphors'),('e','creating {4}'),('e','providing {5}'),('h','Understanding of metaphors'),('b','first step: {6}'),('b','second step: conceptual synesthesia'),('d','meaning: a stimulus in {7} sense(s)'),('d','example: {8}'),('col',''),('b','third step: cognitive dissonance'),('d','hard to ignore {9} of words'),('d','even harder to reject {10}'),('h','Significance of metaphors'),('b','creating expectations'),('d','agent metaphors create {11}'),('b','{12} by activating analogies'),('d','three descriptive analogies'),('d','WWII analogy triggering more {13}'),('d','solving problems by comparing {14} things'),('p','Metaphor is {15} yet hidden.')],
2024:[('title','Why is it harder to learn a second language?'),('h','Introduction'),('b','First language acquisition is a(n) {1} process.'),('b','Second language learning is different.'),('h','Differences'),('b','{2}'),('d','linguistic parameters set when learning a second language'),('d','learning {3} of the second language'),('d','example: {4}'),('b','{5} of language learning'),('d','first language acquisition taking place at a very young age'),('d','in the second language classroom {6} being better learners'),('b','Learners’ traits'),('d','first language acquisition: without {7}'),('d','traits that improve learning in a second language classroom:'),('col',''),('d','{8}'),('d','motivation'),('d','good self-image'),('d','{9}'),('b','{10}'),('d','more complex in second language learning'),('b','Practice'),('d','{11} in second language learning'),('h','Similarities'),('b','{12}'),('b','Exposure to {13}'),('h','Concluding remarks'),('b','Second language learning: {14}'),('b','Translation is not {15} but creative.')]
}

# 首选答案取所供B1解析；冲突的数字版仅作对照，冲突另列。
GAPS={
2016:['the dialectical model','common and fixed','premises','opposition / arguing','arguments as performances / the rhetorical model','participatory / participating','be tailored to / cater for','how we argue / our actual conduct','tactics / strategies','negotiation and collaboration','there’s no solution / progress','learning with losing','questions / counter-considerations / objections','achieve positive effects','support oneself / yourself'],
2017:['signing / sign language','primary','literacy / to become literate','different but complementary','avoiding / to avoid','(many) social contexts / interactive contexts','characteristics / features','reaction','distance','emphasis and emotion','deliberate and time-consuming','intimacy and immediacy','continuum','types of discourse','how it’s used / user’s goal'],
2018:['our species / humans / human beings','their intelligence','learn from others','repeat','others’ wisdom','accumulate','an evolutionary dilemma','watching others','systems of communication','knowledge and wisdom','benefits of cooperation','establishment of identities','isolation','communication','different languages'],
2019:['power and dominance','expanding / opening up','closing up','complementary','dominance','gender','bodies and minds','assertive, confident, optimistic','dominance and stress','opportunities to gamble','risk tolerance / dominance hormone','stress hormone','stress-reactive','change outcomes','do the best'],
2021:['the dominant','not enough / insufficient','regulation and supervision','additional autonomy','certain fields / certain disciplines','stronger market value','executive MBA programs','external grants','conference centers','marketable knowledge','admissions decisions','slow and uneven','enrollment rates / admission rates','complete college / finish college','promote public goals'],
2022:['economist','all-inclusive study','repetitive and tedious','the ideal society','non-Western people','physical','examining the fossils','learned behavior','Mirror for Man','linguistics','the firsthand information','personality and feelings','two sexes','Practical applications','solve human problems'],
2023:['thought','abstract things / something abstract','something else','networks of analogies','a vivid understanding','pattern recognition','different','colored hearing','the literal meaning','the metaphorical meaning','higher expectations','influencing decisions','interventionist recommendations / interventions','familiar with unfamiliar','ubiquitous / everywhere'],
2024:['natural','Language mechanism','the specific rules','word order','Age','younger children','conscious teaching','self-confidence','low anxiety','Input','(more) important','Learning speed','(authentic) language','a harder process','mechanical']}
KEYS={2016:list('CADD BACDCB'.replace(' ','')),2017:list('BADBCD BBDA'.replace(' ','')),2018:list('DBDBC DCBDA'.replace(' ','')),2019:list('ACBCCCACDC'),2021:list('DCBADCABCB'),2022:list('DBCACBACBD'),2023:list('DBCD AADBCD'.replace(' ','')),2024:list('ACDBACBDBC')}


def section_lines(t,which):
    t=clean_text(t)
    start=t.find('SECTION '+which+' ');part=t[start:]
    end=re.search(r'Now,? listen[^\n]*(?:\n[^\n]*)?',part)
    # 从连续说明正文中取到最后一条正式开始说明，去掉后面的试题；固定句式来自原卷。
    if which=='A':
        m=re.search(r'Now,? listen to the mini-lecture\..*?check your work\.',part,re.S)
        part=part[:m.end()] if m else part
    else:
        m=re.search(r'Now,? listen to (?:Part One|the first interview)[^\n]*',part)
        part=part[:m.start()] if m else part
    part=re.sub(r'^SECTION [AB] [A-Z -]+\n','',part)
    part=re.sub(r'(?<=\w)-\s*\n\s*(?=\w)','-',part)
    part=re.sub(r'\s+',' ',part).strip()
    part=part.replace('gap-fulling','gap-filling').replace('ANWER SHEET','ANSWER SHEET')
    return re.split(r'(?<=[.!?])\s+(?=[A-Z])',part)


def build():
    for y in YEARS:
        source=D/'来源'/str(y);t=clean_text((source/'原卷.txt').read_text('utf-8'))
        q=questions(t)
        for row,ans in zip(q,KEYS[y]):row['answer']=ans
        selection=json.loads((source/'来源选择.json').read_text('utf-8'))
        paper=selection['paper']
        pending=[]
        for i,ans in enumerate(GAPS[y],1):
            if ans is None:pending.append(f'第{i}空解析答案待OCR核对')
        for row in q:
            if row['answer'] is None:pending.append(f'选择第{row["n"]}题答案待解析核对')
        # 口述题干空白是忠实展示原卷，不阻止按录音作答；总协调可后续据ASR补上。
        data={'year':y,'title':f'{y}年 专八听力 考试','filename':f'{y}年 专八听力 考试.mp4','minutes':25,
              'sections':[{'id':'A','title':'SECTION A　MINI-LECTURE','lines':section_lines(t,'A')},{'id':'B','title':'SECTION B　INTERVIEW','lines':section_lines(t,'B')}],
              'sheet':sheet(SHEETS[y]),'gap_answers':GAPS[y],'questions':q,
              'groups':[{'id':'part1','title':'SECTION B　INTERVIEW: '+('INTERVIEW ONE' if y in [2017,2019,2022,2024] else 'PART ONE'),'intro':'','questions':list(range(1,6))},{'id':'part2','title':'SECTION B　INTERVIEW: '+('INTERVIEW TWO' if y in [2017,2019,2022,2024] else 'PART TWO'),'intro':'','questions':list(range(6,11))}],
              '来源':{'原卷':paper,'原卷页码':[1,2,3] if y<2022 else [1,9],'解析':selection['analysis'],'参考数字答案':selection.get('answer'),'原卷题干':'选择题干由录音口述，原卷只列选项；未按选项编造题干。'},
              '展示订正':[{'原文':'gap-fulling','展示':'gap-filling','说明':'说明中的明显拼写错字，按同页后文gap-filling及标准题型名称订正。'},{'原文':'ANWER SHEET TWO','展示':'ANSWER SHEET TWO','说明':'说明中的明显拼写错字。'}] if y<2022 else [],
              '待核':pending}
        if y in [2017,2019]:
            # 两个无关采访；数字卷沿用了ONE interview通用说明，B1题卷明确TWO interviews。
            data['sections'][1]['lines']=[
                'In this section you will hear TWO interviews.',
                'At the end of each interview, five questions will be asked about what was said.',
                'Both the interviews and the questions will be spoken ONCE ONLY.',
                'After each question there will be a ten-second pause.',
                'During the pause, you should read the four choices of A, B, C and D, and mark the best answer to each question on ANSWER SHEET TWO.',
                'You have THIRTY seconds to preview the choices.']
            data['展示订正'].append({'原文':'ONE interview; divided into TWO parts','展示':'TWO interviews','说明':'数字版套用通用说明；按所供B1同年题卷两篇独立采访说明呈现，待总协调绑定实际原音。'})
        repairs={
            2016:[(5,2,'Ultimately calls when Maggie is busy.','Untimely calls when Maggie is busy.')],
            2017:[(7,1,'Being brave and writing to take a risk.','Being brave and willing to take a risk.')],
            2019:[(5,3,'Subject.','Subjective.')],
        }.get(y,[])
        for n,k,before,after in repairs:
            assert data['questions'][n-1]['options'][k]==before
            data['questions'][n-1]['options'][k]=after
            data['展示订正'].append({'题号':n,'选项':'ABCD'[k],'原文':before,'展示':after,'说明':'按所供B1同年题卷的清晰数字层订正根目录数字卷错字；选项含义和次序不变。'})
        if y==2022:
            data['答案来源映射']={'说明':'根目录数字卷与B1题卷部分选项重新排序；答案先核对B1解析内容，再映回当前数字卷的选项内容，不能直接套B1字母。','B1答案':'BDCAC C A B D B'.replace(' ',''),'当前答案':''.join(KEYS[y]),'差异题':{'1':{'B1':'B','当前':'D'},'2':{'B1':'D','当前':'B'},'6':{'B1':'C','当前':'B'},'8':{'B1':'B','当前':'C'},'9':{'B1':'D','当前':'B'},'10':{'B1':'B','当前':'D'}}}
        data['答案核对说明']={
            2016:['数字答案第10空negation为错字，按B1解析及对应原文采用negotiation and collaboration。'],
            2017:['第5/11空按本次数字卷题卡结构采用avoiding / to avoid和deliberate and time-consuming，不机械套B1不同概括形式。'],
            2018:['第4题数字版答案D与B1解析B不一致；本稿采用B1解析及unreasonable语义，交总协调结合原音复核。'],
            2019:['数字版答案Q1=C、Q7=D、Q8=B与B1及原文语义冲突，本稿采用A、A、C。','第11空两源均允许dominance hormone，B1另给risk tolerance；并列保留。'],
        }.get(y,[])
        nums=[int(n) for _,*rest in data['sheet'] for s in rest for n in re.findall(r'\{(\d+)\}',s)]
        assert sorted(nums)==list(range(1,16)),(y,nums)
        out=D/'数据'/str(y);out.mkdir(parents=True,exist_ok=True);(out/'试卷.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
        print(y,len(q),'questions, 15 gaps; pending',len(pending),flush=True)

if __name__=='__main__':build()
