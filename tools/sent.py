import json,re
P=json.load(open('passages.json'))
FIX={
 'f1':[('sand, ire ore','sand, iron ore'),(' utopian ,',' utopian,')],
 'f5':[('on my mind a lot lately A friend','on my mind a lot lately. A friend'),('(交叉 )','(交叉)'),('(营养不良 )people','(营养不良) people'),('(修正 )','(修正)'),('( 量子 )','(量子)'),('( 炒作 )','(炒作)'),('( 幅度 )','(幅度)'),('systems thinking - which,in','systems thinking—which, in')],
 'f6':[('four- fifths','four-fifths')],
 'f7':[('responsible fo human','responsible for human'),('as-sociate','associate'),('ex-periment','experiment'),('be-cause','because'),('th car','the car'),('in he world','in the world'),('a car knowledge','a car, knowledge'),('a state of being :','a state of being:')],
 'f8':[('wellbeing, It is','wellbeing. It is'),('evolved around 300,000 years ago. ”The','evolved around 300,000 years ago. “The'),('cultural evolution,“ said','cultural evolution,” said')],
 'f10':[('form Sweden','from Sweden'),('said : ','said: ')],
 'f11':[('into a new a made-up language','into a new made-up language'),('across fields the arts, sciences, and politics','across fields: the arts, sciences, and politics'),('mood(情绪)','mood (情绪)'),('moderation(适度)','moderation (适度)'),('computer”, says','computer,” says')],
 'f12':[('By around 65 years ago','By around 65 million years ago'),('fossils , these','fossils, these'),('practical way.He','practical way. He')],
 'f15':[('Eric weiner','Eric Weiner'),('undestanding','understanding'),('abour learning','about learning'),('American psyche-we','American psyche — we'),('bad habits,“ says','bad habits,” says')],
 'f16':[('Compared with the developments of Al,','Compared with the developments of AI,'),('artificial life-called ALife','artificial life — called ALife'),('something：perhaps','something: perhaps'),('Earth biosphere','Earth’s biosphere'),('global warming.”Another','global warming.” Another'),('example, but there are others.One','example, but there are others. One')],
 'f18':[('resenting a different perspective','presenting a different perspective'),('curiosity,emotions','curiosity, emotions'),('‘unwilling’’ scenario','“unwilling” scenario'),('‘teasing’ (戏耍的)','“teasing” (戏耍的)')],
 'f19':[],
 'f21':[('installed(安装)has','installed (安装) has'),('pollinators(传粉昆虫)','pollinators (传粉昆虫)'),('Environment(InSPIRE)project','Environment (InSPIRE) project')],
 'f23':[],
 'f25':[('its future now-several decades','its future now — several decades'),('responsible for AI-the technology','responsible for AI — the technology')],
 'f26':[('(雹暴) in','(雹暴) in'),('$2million','$2 million'),('on this issue for years “Basically','on this issue for years. “Basically'),('Stienwan d','Stienwand'),('cousing','causing'),('connect ion','connection'),('We’ re','We’re')],
 'f27':[('（北极的）',' (北极的)'),('（融化）',' (融化) '),('（永冻层）',' (永冻层)'),('（缩小的）',' (缩小的)'),('（e. g. Exercise is good for you, and polluted air isn’t）','(e.g. exercise is good for you, and polluted air isn’t)'),('“disastrous lake loss”','“disastrous lake loss”.')],
 'f32':[('on I January','on 1 January')],
 'f34':[('how may of','how many of'),('poor produced','poorly produced'),('gender(性别)','gender (性别)'),('versus(相对于)','versus (相对于)'),('nurture(培育)','nurture (培育)'),('algorithm(算法)','algorithm (算法)'),('exacerbating(使恶化)','exacerbating (使恶化)'),('worth talking about','worth talking about.')],
 'f35':[('standard- size','standard-size'),('370,000, not higher.','370,000, if not higher.'),('“The innovative techniques presented in the study open the door for further research to better understand the potential risks to human health.” said','“The innovative techniques presented in the study open the door for further research to better understand the potential risks to human health,” said'),('toxic exposures.” said','toxic exposures,” said')],
 'f37':[],
 'f38':[('unnoticed-we','unnoticed — we')],
}
ABBR=r'(?:Mr|Mrs|Ms|Dr|Prof|St|U\.S|e\.g|i\.e|vs|etc|No|Inc|Nov|a\.m|p\.m|Jr)'
def fix_typography(t):
    """排版统一：直引号转弯引号，引号内侧不留空格，标点后补空格，括号前补空格。"""
    t=t.replace('"Big change requires big ideas." he said','"Big change requires big ideas," he said')
    t=t.replace('most important. " She also','most important." She also')
    t=t.replace('in recent years transport studies','in recent years, transport studies')
    t=t.replace('affected seal behavior Professor','affected seal behavior, Professor')
    t=re.sub(r'(^|[\s(\[—])"',r'\1“',t)
    t=t.replace('"','”')
    t=re.sub(r"(?<=[A-Za-z])'(?=[A-Za-z])",'’',t)   # 词内撇号 world's → world’s
    t=re.sub(r'“\s+','“',t)
    t=re.sub(r'(?<=[.,!?])\s+”','”',t)
    t=re.sub(r'(?<=[A-Za-z])([,;:])(?=[A-Za-z“])',r'\1 ',t)
    t=re.sub(r'(?<=[A-Za-z])\((?=[A-Za-z])',' (',t)
    t=re.sub(r'(?<=[a-z])\.(?=[A-Z][a-z])','. ',t)
    return t
def norm(t):
    t=fix_typography(t)
    t=re.sub(r'(?<=[A-Za-z0-9\)])，\s*',', ',t)
    t=re.sub(r'(?<=[A-Za-z])；\s*','; ',t)
    t=re.sub(r'(?<=[A-Za-z])：\s*',': ',t)
    t=t.replace('（',' (').replace('）',') ')
    t=re.sub(r'\(\s+','(',t); t=re.sub(r'\s+\)',')',t)
    t=re.sub(r'\s+([,.;:?!])',r'\1',t)
    t=re.sub(r'\s{2,}',' ',t).strip()
    return t
def split(p):
    # protect abbreviations
    q=re.sub(r'\b('+ABBR+r')\.',lambda m:m.group(1).replace('.','<DOT>')+'<DOT>',p)
    # 人名缩写 G. K. Chesterton / Félix W. Ortiz 不断句（代词 I 除外）
    q=re.sub(r'(?<![A-Za-z])([A-HJ-Z])\.(?=\s+[A-Z])',r'\1<DOT>',q)
    # “in the U.S. Their recovery” 这里 U.S. 正好在句末
    q=q.replace('in the U<DOT>S<DOT> Their','in the U<DOT>S<DOT>\x00 Their')
    parts=re.split(r'(?<=[.!?])(["”’)]*)\s+(?=["“‘(]?[A-Z0-9])',q)
    out=[];buf=''
    for i,x in enumerate(parts):
        if i%2==0: buf+=x
        else: buf+=x; out.append(buf); buf=''
    if buf: out.append(buf)
    out=[y for x in out for y in x.split('\x00')]
    return [s.replace('<DOT>','.').strip() for s in out if s.strip()]

# 第三轮严格英文复核后的原文订正（语法、用词、逻辑、事实），在排版规范化之后按篇应用，每条必须恰好匹配一次
POST={
 'p58':[('if you do that.”','if you did that.”')],
 'p62':[('the amount of smell-carrying','the number of smell-carrying')],
 'p63':[('do we have “Influencer”','do we have the “Influencer”'),
        ('But that purpose is lost over time.','But that purpose has been lost over time.'),
        ('When faced with such a fence, Chesterton thinks the fact','Chesterton thinks that when we are faced with such a fence, the fact')],
 'p64':[('But while earning my Ph.D. at MIT and then as a post-doctor doing','But while I was earning my Ph.D. at MIT and then working as a postdoc doing'),
        ('on my behalf and all womankind','on my own behalf and on behalf of all womankind'),
        ('students worry how they will','students worry about how they will')],
 'p65':[('This is not just the case with YouTube but with every','This is the case not just with YouTube but with every')],
 'p66':[('math problems, require more energy','math problems, required more energy'),
        ('mental effort is habituated.','mental effort becomes habitual.'),
        ('won’t just feel easier, it will actually be easier','won’t just feel easier; it will actually be easier')],
 'p67':[('1/20000th of an inch','1/25,000th of an inch'),
        ('can see, count and analyze the chemical structure of nanoparticles in bottled water.','can see and count nanoparticles in bottled water and analyze their chemical structure.'),
        ('Instead of 300 per liter,','Instead of the roughly 300 per liter reported in a 2018 study,'),
        ('Healthy Babies, Bright Futures','Healthy Babies Bright Futures'),
        ('chemicals, who was not involved','chemicals — who was not involved')],
 'p68':[('is not a new invention,','is not new,'),
        ('On one hand, they need rubber','On one hand, it needs rubber'),
        ('a synthetic bio-polymer','a synthetic biopolymer'),
        ('which can be grown on existing farmland','which comes from crops grown on existing farmland'),
        ('a zero-sum game','a lose-lose choice')],
 'p69':[('The reviews were written by real people','The fake reviews were written by real people')],
 'p70':[('Scientists at Salk Institute','Scientists at the Salk Institute'),
        ('an AI software that tracks','AI software that tracks'),
        ('as well as whether multiple','as well as find out whether multiple')],
 'p49':[('who had moved her family to Manhattan in the early 1950s','who lived in Manhattan in the 1950s'),
        ('the majority of the western cities','the majority of western cities'),
        ('among the highest rate of car ownership','among the highest rates of car ownership')],
 'p50':[('containing 300 milligrams of calcium carbonate led','containing 300 milligrams of calcium carbonate per liter led'),
        ('less than 60 milligrams of calcium carbonate, boiling','less than 60 milligrams of calcium carbonate per liter, boiling'),
        ('10 to 1,000 times','10 to 100 times'),
        ('an environmental engineer of the University','an environmental engineer at the University')],
 'p51':[('Detrinidad sent out','Detrinidad has sent out'),
        ('in a few ways but the biggest','in a few ways, but the biggest'),
        ('among the groups of people who','among the people who'),
        ('lawyers practice law and you should','lawyers practice law, and you should')],
 'p52':[('For two weeks in March','For three weeks in March'),
        ('the Food Waste Alliance','the Food Waste Reduction Alliance')],
 'p53':[('What I wish I taught','What I wish I had taught')],
 'p54':[('change our minds for better.','change our minds for the better.'),
        ('are built in with our memories','are integrated with our memories'),
        ('Contrary to popular doubt','Contrary to popular belief'),
        ('the author of our own destiny','the author of your own destiny')],
 'p55':[('All animals take in','All mammals take in'),
        ('Sure enough: the higher','Sure enough, the higher'),
        ('But when holding our breath during diving','But when we hold our breath during diving'),
        ('Because every time we surface','This is because every time we surface')],
 'p59':[('their feelings while completing','their feelings while they were completing')],
}
res=[]
used=set()
for n,o in enumerate(P,1):
    ps=[]
    for para in o['paras']:
        t=para
        for a,b in FIX.get(o['file'],[]):
            if a in t: used.add((o['file'],a))
            t=t.replace(a,b)
        if o['file']=='f2': t=re.sub(r'\.(?=[A-Z])','. ',t.replace('，',', ').replace('；','; ').replace('：',': '))
        t=norm(t)
        for a,b in POST.get('p%02d'%n,[]):
            if a in t:
                assert t.count(a)==1, f'原文订正不唯一：p%02d {a}'%n
                used.add(('p%02d'%n,a))
            t=t.replace(a,b)
        ps.append(split(t))
    o['id']='p%02d'%n; o['sents']=ps
    res.append(o)
# 踩坑：原文修正匹配不到时会静默失效，必须报错
miss=[(f,a) for f,l in list(FIX.items())+list(POST.items()) for a,b in l if (f,a) not in used]
assert not miss, f'原文修正没有匹配到：{miss}'
json.dump(res,open('sents.json','w'),ensure_ascii=False,indent=1)
import sys
for o in res:
    with open(f"sents/{o['id']}.txt",'w') as f:
        f.write(f"## {o['id']} {o['year']} {o['paper']} 阅读{o['part']} ({o['words']}词)\n")
        k=0
        for pi,para in enumerate(o['paras'] and o['sents']):
            for s in para:
                k+=1; f.write(f"{k} {s}\n")
            f.write("\n")
print(sum(len(s) for o in res for s in o['sents']))
