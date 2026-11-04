"""2026 新课标Ⅰ卷 读后续写讲解稿（2026-11-03 新会话从零写，旧稿作废）→ 稿.json（范文.json 只去掉旧讲法的“块”）。
逐句讲（用户 2026-11-03 第二版：一块一块翻、注意时态、一气呵成）：zh 中文构思 → chunk 逐块翻（≥ 1 块，show = 1..N）
  → join 连成一句（有保底版 base 时拆成 step=base / step=fan 两段，否则只有 fan）→ read 读整句 → pt 得分点（档 + 原文出处 src/mark）→ alt 可替换。
逐块翻、连成一句的配音和画面字段来自 逐块翻译稿.json（续写检查.py ④ 查 hl ⊂ 中文句、marks ⊂ 范文句、base 拼写）。
朗读规则：中文段不写阿拉伯数字；问句不带 呢/吧/啊、后面接 ‖；成句英文前后用中文标点隔开（讲解音频.lang_split 单独按英文合成）。
用法：python3 稿源.py"""
import json
from pathlib import Path

D = Path(__file__).resolve().parent
P3 = 'Standing outside were Daniel and his wife Rachel, who noticed the stranded (被困的) vehicle on their way home and stopped to see if they could help.'
P3B = 'With genuine warmth in her voice, Rachel said they could take Emily to a nearby cafe they knew.'
P3C = 'When Emily rolled down the window, Rachel asked if she was okay and told her it was not safe to stay overnight in the car.'
P4A = 'In the cafe, the couple bought Emily a hot chocolate and listened patiently as she explained her desperate situation'   # 原文第四段这一句太长，出处只放用到的半句
P4 = 'she was about a hundred miles from her destination, her car was completely stuck, and her entire holiday plan could be ruined.'
P1A = ('Emily Sanders, a 25-year-old from Detroit, Michigan, set out on December 23rd with high hopes of reaching Toronto to meet her boyfriend '
       'for Christmas.')
DITCH = 'While Emily was driving on a narrow stretch of road, her car slid into a ditch (沟).'
WHITE = 'The blinding whiteout made driving nearly impossible.'
SEEING = 'Seeing no hope of immediate rescue, Emily decided to spend the night in her car.'
GRATE = 'Grateful and relieved, Emily accepted the offer.'
PANIC = 'As night fell, panic set in.'
G2 = 'Three days later, Emily returned to get her car.'

segs = []


def add(i, screen, text, lang='Chinese', gap=0.6, **kw):
    segs.append(dict(id=i, screen=screen, lang=lang, gap=gap, text=text, **kw))


# ---------- 题目要求、评分标准 ----------
add('t01', 'task', '好，那接下来我们就开始讲一下这篇二零二六年新课标一卷的续写。')
add('t02', 'task', '先看题目要求：根据材料内容和所给的两段开头语，续写两段，词数一百五十个左右。')
add('t03', 'task', '第一段的开头是：丹尼尔和瑞秋建议艾米丽坐火车，继续她的旅程。', hi='o1')
add('t04', 'task', '第二段的开头是：三天后，艾米丽回来取她的车。', hi='o2', gap=0.8)
add('g01', 'rubric', '再看评分标准。最高一档，一共有四条要求。')
add('g02', 'rubric', '第一条，和原文内容融洽，和两段开头语衔接合理。', note='① 与原文融洽，与开头语衔接合理')
add('g03', 'rubric', '第二条，内容丰富。', note='② 内容丰富')
add('g04', 'rubric', '第三条，语法结构和词汇丰富、准确。', note='③ 语法结构和词汇丰富、准确')
add('g05', 'rubric', '第四条，有效使用语句间的连接成分，结构紧凑。‖记住这四条。后面讲每一个得分点，都会告诉你它对应哪一条。', note='④ 有效使用连接成分，结构紧凑', gap=0.8)

# ---------- 读原文 ----------
add('a01', 'p1', '先读原文。第一段，交代人物和目标。‖艾米丽，二十五岁，十二月二十三日出发，要赶到多伦多，和男朋友一起过圣诞。‖这就是全文的目标，续写一定要给它一个结果。',
    mark=['Emily Sanders, a 25-year-old from Detroit, Michigan', 'reaching Toronto to meet her boyfriend for Christmas'], note='人物与目标：赶去多伦多，和男朋友过圣诞')
add('a02', 'p1', '冲突从哪里来？‖有两处。第一，她听到了暴风雪预警，却没放在心上。第二，雪越下越大，她被引下高速，开上了一条陌生的路。‖一个大意，一个路不熟，麻烦就这么来了。',
    mark=['she didn’t give it much thought', 'Emily was directed off the highway'], note='冲突起点：轻视暴风雪，被引下高速', gap=0.8)
add('a03', 'p2', '第二段，困境一步一步升级。‖大雪茫茫，几乎没法开车；天黑了，她开始慌；车又滑进了沟里。',
    mark=['The blinding whiteout made driving nearly impossible', 'panic set in', 'her car slid into a ditch'], note='困境升级：大雪封路，车滑进沟里')
add('a04', 'p2', '手机没有信号，她只能裹着毯子，在车里过夜。‖我们把情感线理一理：从满怀希望，到慌乱，再到无助。',
    mark=['found no signal on her phone', 'She wrapped herself in a blanket'], note='情感线：希望 → 慌乱 → 无助', gap=0.8)
add('a05', 'p3', '第三段，是全文的转机。‖丹尼尔和瑞秋夫妇在回家的路上，看到被困的车，停下来帮忙。‖注意这个短语：genuine warmth，真诚的温暖。‖全文的主题就落在这里：陌生人的善意。',
    mark=['Daniel and his wife Rachel', 'With genuine warmth in her voice'], note='转机：陌生夫妇停车相助，真诚温暖')
add('a06', 'p3', '艾米丽又感激，又宽慰，接受了帮助。‖她的情感，从无助转向了温暖。', mark=['Grateful and relieved'], note='情感转折：感激、宽慰', gap=0.8)
add('a07', 'p4', '第四段最关键，艾米丽说出了三个难题。‖第一，离目的地还有一百英里；第二，车完全困住了；第三，整个假期计划可能泡汤。‖续写的任务，就是把这三个难题一个一个解决掉。',
    mark=['she was about a hundred miles from her destination', 'her car was completely stuck', 'her entire holiday plan could be ruined'],
    note='三个难题：离目的地一百英里；车困住了；假期计划可能泡汤')
add('a08', 'p4', '还有一个细节：夫妇俩给她买了热巧克力，耐心听她说完。‖记住这份善意。续写的结尾，要让艾米丽回报它。',
    mark=['the couple bought Emily a hot chocolate and listened patiently'], note='伏笔：热巧克力、耐心倾听——结尾要有回报', gap=0.8)

# ---------- 开头语、提纲、伏笔 ----------
add('o01', 'open', '再看开头语。第一段的开头，夫妇俩建议她坐火车。‖这解决了第一个难题：怎么去多伦多。‖可是，车还在沟里。所以这一段必须把车安排好，给第二段埋下伏笔。',
    hi='o1', note='第一段：解决“怎么去多伦多”，还要安排好那辆车')
add('o02', 'open', '第二段的开头，三天后，她回来取车。‖这说明，第一段一定交代了车的去处。‖这一段要写三件事：车怎么样了，她怎么道谢，最后点明主题。',
    hi='o2', note='第二段：回来取车 → 车的结果、道谢回报、点明主题', gap=0.8)
add('l01', 'outline', '按这个思路，列一个提纲。‖第一段，分四步。第一，讲清方案：附近就有车站。第二，艾米丽担心车，丹尼尔答应拖车、保管。‖第三，夫妇送她到车站，告别时她忍不住落泪。第四，那天晚上，她赶到多伦多，赶上了圣诞。',
    col=1, lines=['① 讲清方案：附近有车站', '② 担心车 → 丹尼尔答应拖车、保管', '③ 送站告别，忍不住落泪', '④ 那晚到多伦多，赶上圣诞'])
add('l02', 'outline', '第二段，也分四步。第一，写环境：雪停了，天晴了，和暴风雪形成对比。第二，车已经拖出来，雪也清好了，丹尼尔兑现了承诺。‖第三，艾米丽送上自己烤的饼干和一张卡片，回报善意。第四，点题：陌生人的善意，让这个圣诞节成了最温暖的一个。',
    col=2, lines=['① 环境对比：雪停天晴', '② 车已拖出、清好雪（兑现承诺）', '③ 回报：自制饼干和感谢卡', '④ 点题：陌生人让圣诞最温暖'], gap=0.8)
add('e01', 'echo', '下面看伏笔和呼应。‖原文说，车完全困住了；续写就让丹尼尔找人，把车从沟里拖出来。', row=['her car was completely stuck', 'have it towed out of the ditch'])
add('e02', 'echo', '原文的目标，是赶到多伦多见男朋友；续写就让她在那天晚上，扑进男朋友的怀里。', row=['reaching Toronto to meet her boyfriend for Christmas', 'fell into her boyfriend’s arms in Toronto'])
add('e03', 'echo', '原文是茫茫大雪；第二段换成了阳光。环境变了，心情也跟着变了。', row=['The blinding whiteout made driving nearly impossible', 'lay quiet in the sunshine'])
add('e04', 'echo', '原文里，艾米丽担心假期计划会泡汤；结尾就用同一个词 ruin 收住：圣诞节差点被毁了，最后却成了最温暖的一个。', row=['her entire holiday plan could be ruined', 'nearly ruined her Christmas'])
add('e05', 'echo', '原文写瑞秋的声音里，透着真诚的温暖；结尾就落在最温暖上。主题从头到尾，是一条线。‖原文读完了，下面我们一句一句来写。', row=['With genuine warmth in her voice', 'the warmest of her life'], gap=0.8)

# ---------- 逐句讲范文 ----------
# 每句：zh（为什么）、得分点 [hl, 档, src, mark, 画面行, 配音, 例]、可替换 [画面行, 配音, 替换]；
# 逐块翻、连成一句的配音和画面在 逐块翻译稿.json（协调会话三方审阅定稿，2026-11-03），这里只读，不改字
S = []
ZK = json.loads((D / '逐块翻译稿.json').read_text('utf-8'))
SPLIT = '范文在这个基础上'      # 有保底版（base）的 join 在这里拆成两段：先出保底版，讲到范文时再出范文句


def sent(why, pts, alt):
    S.append(dict(why=why, pts=pts, alt=alt))


sent(('第一句。先用中文想好：他们解释说，附近就有个火车站，中午有一趟去多伦多的火车。‖为什么要写这句？‖开头语只说了坐火车。方案必须落到实处，读者才会信。',
      ['为什么：开头语只说“坐火车”，先把方案讲实（车站在哪、几点有车）']),
     [('they explained', ['③'], P3B, 'Rachel said they could take Emily to a nearby cafe',
       ['插入语 they explained：不写 They explained that…，句式更灵活', '插入语不算主干，句子主干仍是两个分句'],
       '我们来看得分点。‖得分点一，插入语 they explained。‖不写成 they explained that，句式就更灵活。这一点对应第三条：语法结构丰富。', ['they explained that']),
      ('a train to Toronto would leave at noon', ['①'], P4, 'she was about a hundred miles from her destination',
       ['地点、时间都具体：方案可信', '解决难题一：离目的地还有一百英里'],
       '得分点二：a train to Toronto would leave at noon。‖地点、时间都具体，方案才可信。原文说，离目的地还有一百英里；‖这一句，就把怎么去的问题解决了。对应第一条，与原文融洽。', [])],
     (['The nearest station was just a short drive away.', 'a train would leave for Toronto at noon'],
      '这句话还有别的写法。‖前半句可以写：The nearest station was just a short drive away，最近的车站，开车一会儿就到。‖后半句也可以写：a train would leave for Toronto at noon。'))

sent(('第二句，中文是：可是我的车怎么办，艾米丽焦急地问。‖这句写的是她的第二个难题：人能走了，车还在沟里。让她自己说出来，比旁白更有力。',
      ['为什么：人能走了，车还在沟里——让她自己说出第二个难题']),
     [('“But what about my car?”', ['①', '④'], P4, 'her car was completely stuck',
       ['直接引语：人物开口，比叙述更生动', '承上：原文的难题“车困住了”；启下：引出拖车的安排'],
       '得分点一：直接引语。‖让人物自己开口，比叙述更生动。它接住了原文的难题：车完全困住了；又引出下一句丹尼尔的安排。承上启下，对应第一条和第四条。', []),
      ('anxiously', ['①'], PANIC, 'panic set in',
       ['anxiously：一个副词写出焦急', '情感线：慌乱 → 焦急，后面再转成感激'],
       '得分点二：anxiously，一个副词，就写出了她的焦急。‖原文写过她的慌乱：panic set in。这里的焦急，接着这条情感线往下走，后面再转成感激。对应第一条，与原文融洽。', [])],
     (['What will happen to my car?', 'Emily asked with a worried frown'],
      '也可以换个说法。‖问句也可以写成：What will happen to my car？‖后面也可以写：Emily asked with a worried frown，皱着眉头问。'))

sent(('第三句，中文是：丹尼尔答应找人把车从沟里拖出来，放在他家车库，等她回来。‖这句有两个作用：一是回答上一句的担心；二是给第二段回来取车，埋下伏笔。',
      ['为什么：回答“车怎么办”；给第二段“回来取车”埋伏笔']),
     [('have it towed', ['③'], DITCH, 'her car slid into a ditch',
       ['have it towed：使役结构，找人拖，不是自己拖——意思准确', '回应原文：车滑进了沟里（ditch）'],
       '得分点一：have it towed，使役结构。‖不是丹尼尔自己去拖，而是找人拖，意思准确。对应第三条。‖它还直接回应了原文：her car slid into a ditch，车滑进了沟里。连 ditch 这个词，都照应上了。', []),
      ('until she returned', ['①', '④'], G2, 'returned to get her car',
       ['伏笔：until she returned', '第二段开头 Emily returned to get her car：同一个动词，衔接严密'],
       '得分点二：until she returned。‖这是给第二段埋的伏笔。第二段开头说：Three days later, Emily returned to get her car。‖两处用的是同一个动词 return，两段衔接严丝合缝。对应第一条和第四条。', [])],
     (['Daniel offered to get the car pulled out', 'look after it until she came back'],
      '换个写法也可以。‖前半句：Daniel offered to get the car pulled out，主动提出找人把车拖出来。‖后半句：look after it until she came back，替她照看到她回来。'))

sent(('第四句，中文是：接着，夫妇俩开车送她到车站，陪她一直等到火车进站。‖方案落实了，夫妇俩的善意也写足了。',
      ['为什么：方案落地（从咖啡馆到车站），把夫妇的善意写足']),
     [('drove her to the station and waited with her', ['③', '④'], P3, 'noticed the stranded (被困的) vehicle on their way home and stopped',
       ['并列谓语：一句两个动作，结构紧凑', '原文写这对夫妇，也是并列谓语：noticed … and stopped'],
       '得分点一：并列谓语。‖一句话写两个动作，结构紧凑。对应第三条和第四条。‖原文写这对夫妇，也是这么写的：注意到被困的车，停下来看能不能帮忙。', []),
      ('waited with her until the train arrived', ['②'], P4A, 'listened patiently',
       ['细节：不是送到就走，而是陪着等车', '和原文 listened patiently 一样，写夫妇的耐心'],
       '得分点二：waited with her until the train arrived。‖不是送到就走，而是陪着等车。这个细节，让善意更具体。对应第二条，内容丰富。‖原文里，他们耐心听她说话；这里，他们耐心陪她等车。写的都是这对夫妇的耐心。', [])],
     (['saw her off at the station', 'stayed by her side until the train pulled in'],
      '可替换的说法有两个。‖一个是 saw her off at the station，送她上车。另一个是 stayed by her side until the train pulled in，一直陪在她身边，等到火车进站。'))

sent(('第五句，中文是：隔着结霜的车窗，向他们挥手，艾米丽几乎忍不住泪水。‖告别，是这一段的情感高点，要写出她的感激。',
      ['为什么：告别是情感高点——从无助、焦急到感激']),
     [('Waving to them', ['③', '①'], SEEING, 'Seeing no hope of immediate rescue',
       ['现在分词作状语：动作和情感同时呈现', '原文同样的句式：Seeing no hope of immediate rescue'],
       '得分点一：现在分词作状语，Waving to them。‖原文就有同样的结构：Seeing no hope of immediate rescue。‖续写模仿原文的句式，语言风格就统一了。对应第三条和第一条。', []),
      ('could hardly hold back her tears', ['②', '①'], GRATE, 'Grateful and relieved',
       ['用动作写情感：不说“很感激”，写她忍不住流泪', '情感线：感激、宽慰 → 推到高点'],
       '得分点二：could hardly hold back her tears。‖不直接说她很感激，而是写她忍不住流泪。这叫用动作写情感。‖原文写她 grateful and relieved，又感激又宽慰；这里，把感激推到了最高点。对应第二条和第一条。', [])],
     (['As the train pulled away', 'Emily felt tears of gratitude welling up in her eyes'],
      '这句也可以这样写。‖开头用时间状语从句：As the train pulled away，火车开动的时候。‖后面写：Emily felt tears of gratitude welling up in her eyes，感激的泪水涌上了眼眶。'))

sent(('第六句，中文是：那天晚上，她在多伦多扑进了男朋友的怀里，正好赶上圣诞节。‖这是第一段的收尾，给原文的目标一个结果。',
      ['为什么：第一段收尾——原文的目标（到多伦多和男朋友过圣诞）有了结果']),
     [('fell into her boyfriend’s arms', ['①'], P1A, 'reaching Toronto to meet her boyfriend for Christmas',
       ['目标实现：到多伦多，见到男朋友', '原文开头的 high hopes 有了结果，首尾呼应'],
       '得分点一：fell into her boyfriend’s arms。‖原文一开头就说，她满怀希望，要去多伦多见男朋友，一起过圣诞。这里让目标实现了，首尾呼应。对应第一条。', ['fall into one’s arms']),
      ('That evening', ['④'], G2, 'Three days later',
       ['时间状语放句首：That evening', '与第二段开头 Three days later 连成清楚的时间线'],
       '得分点二：That evening，时间状语放在句首。‖它和第二段开头的 Three days later，连成一条清楚的时间线。对应第四条，连接成分。', [])],
     (['By nightfall, she had reached Toronto', 'in time to spend Christmas with her boyfriend'],
      '这句也可以换个写法。‖前半句：By nightfall, she had reached Toronto，天黑前，她已经到了多伦多。‖后半句：in time to spend Christmas with her boyfriend，赶上和男朋友一起过圣诞。'))

sent(('第二段第一句，中文是：这时天已经放晴，那条曾经困住她的路，静静地躺在阳光里。‖先写环境。环境变了，心情也就变了。',
      ['为什么：先写环境——从暴风雪到晴天，映出心情的变化']),
     [('that had trapped her', ['③'], DITCH, 'a narrow stretch of road',
       ['定语从句 + 过去完成时：时间先后准确', '这条路就是原文那段窄路'],
       '得分点一：that had trapped her，定语从句加过去完成时。‖时间先后，交代准确。对应第三条。‖这条路，就是原文里那段窄路，读者一看就知道是同一个地方。', []),
      ('lay quiet in the sunshine', ['①', '②'], WHITE, 'The blinding whiteout',
       ['环境对比：茫茫大雪 → 阳光、安静', '环境一变，心情也变了'],
       '得分点二：lay quiet in the sunshine。‖原文是茫茫大雪，几乎没法开车；现在是阳光，一片安静。环境一变，心情也变了。对应第一条和第二条。', [])],
     (['The storm had passed', 'the once dangerous road now looked peaceful'],
      '这句也可以这样写。‖前半句：The storm had passed，暴风雪已经过去了。‖后半句：the once dangerous road now looked peaceful，那条曾经危险的路，现在看起来很平静。'))

sent(('第二段第二句，中文是：停在夫妇俩车库外面的，正是她的车。雪已经清干净，随时可以上路。‖丹尼尔的承诺，兑现了。',
      ['为什么：兑现第一段丹尼尔的承诺——车真的拖出来、保管好了']),
     [('Parked outside the couple’s garage was her car', ['③', '①'], P3, 'Standing outside were Daniel and his wife Rachel',
       ['完全倒装：焦点放在句尾 her car', '原文同样的句式：Standing outside were Daniel and his wife Rachel'],
       '得分点一：完全倒装。‖原文第三段就用了这个句式：Standing outside were Daniel and his wife Rachel。‖续写照着用，句式有变化，又和原文的风格一致。对应第三条和第一条。‖焦点放在句尾：her car。读者等的，就是这辆车。', []),
      ('cleaned of snow and ready to go', ['①'], P4, 'her car was completely stuck',
       ['兑现承诺：车拖出来了，雪也清了', '原文“车完全困住了”到这里彻底解决'],
       '得分点二：cleaned of snow and ready to go。‖原文里，车完全困住了；第一段，丹尼尔答应拖车、保管；到这里，承诺兑现了，伏笔也收住了。对应第一条。', [])],
     (['Her car was waiting outside the garage', 'free of snow'],
      '这句也可以这样写。‖主干写成：Her car was waiting outside the garage，她的车，就停在车库外面等她。‖雪清干净了，也可以说：free of snow。'))

sent(('第二段第三句，中文是：艾米丽递给他们一盒自己烤的饼干，和一张卡片，上面写着：谢谢你们挽救了我的假期。‖他们帮了她，她要回报这份善意。',
      ['为什么：回报善意——原文他们给她买了热巧克力']),
     [('homemade cookies', ['①', '②'], P4A, 'the couple bought Emily a hot chocolate',
       ['回报：原文他们给她买热巧克力，她带着亲手烤的饼干回来', '一来一往，善意有了回应'],
       '得分点一：homemade cookies，亲手烤的饼干。‖原文里，夫妇俩给她买了热巧克力；现在，她带着自己做的饼干回来。一来一往，善意有了回应。对应第一条和第二条。', []),
      ('that read, “Thank you for saving my holiday.”', ['③', '①'], P4, 'her entire holiday plan could be ruined',
       ['read 作“写着”讲：词汇准确', '卡片上的 holiday 回应原文“假期计划可能泡汤”'],
       '得分点二：a card that read。read 在这里的意思是写着。‖卡片上的话是：Thank you for saving my holiday。‖holiday 这个词，正好回应原文：her entire holiday plan could be ruined。对应第三条和第一条。', [])],
     (['a thank-you card', 'as a small token of her gratitude'],
      '这句也可以换个说法。‖卡片可以说 a thank-you card，感谢卡。还可以加一句：as a small token of her gratitude，聊表谢意。'))

sent(('第二段第四句，中文是：我们只是做了任何人都会做的事，瑞秋说着，温暖地拥抱了她。‖瑞秋的回答轻描淡写，反而更显真诚。',
      ['为什么：瑞秋的回答——轻描淡写，更显真诚']),
     [('We just did what anyone would do', ['①'], P3B, 'With genuine warmth in her voice',
       ['人物一致：帮了大忙，却说是“任何人都会做的事”', '和原文声音里透着温暖的瑞秋是同一个人'],
       '得分点一：We just did what anyone would do。‖帮了这么大的忙，却说只是做了任何人都会做的事。谦和，真诚。‖这和原文里声音温暖的瑞秋，是同一个人。对应第一条。', []),
      ('giving her a warm hug', ['③'], P3C, 'Rachel asked if she was okay',
       ['现在分词作伴随：说话和拥抱同时发生', '从原文问她好不好，到这里拥抱她，温暖一以贯之'],
       '得分点二：giving her a warm hug，现在分词作伴随状语。‖说话和拥抱同时发生，一句话写了两个动作。‖从原文里问她好不好，到这里拥抱她，瑞秋的温暖从头到尾都没变。对应第三条。', [])],
     (['It was nothing', 'hugging her tightly'],
      '这句也可以这样写。‖说的话可以是：It was nothing，没什么。‖动作也可以写：hugging her tightly，紧紧抱住她。'))

sent(('最后一句，中文是：开车离开时，艾米丽意识到，暴风雪差点毁了她的圣诞节，而两个陌生人，却让它成了她一生中最温暖的圣诞。‖这是全文的结尾，要点明主题。',
      ['为什么：全文结尾，点明主题——陌生人的善意']),
     [('had nearly ruined her Christmas', ['①'], P4, 'her entire holiday plan could be ruined',
       ['ruin：原文用过的词，结尾收住', '原文的担心（假期泡汤）有了答案'],
       '得分点一：had nearly ruined her Christmas。‖ruin 这个词，原文用过：her entire holiday plan could be ruined。‖结尾用同一个词收住，原文的担心有了答案。对应第一条。', []),
      ('but two strangers had made it the warmest of her life', ['③', '④'], P3B, 'genuine warmth',
       ['but 转折：暴风雪与陌生人，冷与暖对比', '最高级 the warmest 接住原文 genuine warmth，点题'],
       '得分点二：but 转折。‖前面是暴风雪，后面是陌生人，一冷一暖，形成对比。‖the warmest of her life，用最高级，又接住了原文的 genuine warmth，主题水到渠成。对应第三条和第四条。', [])],
     (['As she drove off', 'the kindness of strangers had turned it into an unforgettable one'],
      '这句也可以这样写。‖开头用：As she drove off，她开车离开的时候。‖后半句写成：the kindness of strangers had turned it into an unforgettable one，陌生人的善意，让它成了一个难忘的圣诞。'))

# ---------- 写进 稿 ----------
fw = json.loads((D / '范文.json').read_text('utf-8'))
own = [(pi, si) for pi, p in enumerate(fw['paragraphs']) for si, s in enumerate(p) if not s.get('given')]
assert len(own) == len(S), (len(own), len(S))


def noq(s):
    return s.replace('“', '').replace('”', '')


def para_read(pi):
    p = fw['paragraphs'][pi]
    k = '一二'[pi]
    add(f'r{pi + 1}a', f'para{pi + 1}', f'第{k}段写完了。我们把这一段从头到尾，连起来读一遍。', gap=0.5)
    add(f'r{pi + 1}b', f'para{pi + 1}', ' '.join(noq(s['en']) for s in p), lang='English', gap=1.0)


for k, ((pi, si), x) in enumerate(zip(own, S), 1):
    sen = fw['paragraphs'][pi][si]
    sen.pop('块', None)                      # 旧讲法（谓语 → 主语 → 其余）的块，新讲法不用
    zk = ZK['sentences'][k - 1]
    assert zk['k'] == k, (zk['k'], k)
    sc = f's{k}'
    why_text, why_ln = x['why']
    add(f's{k}z', sc, why_text, ph='zh', ln=why_ln)
    for j, c in enumerate(zk['chunks'], 1):
        add(f's{k}b{j}', sc, c['say'], ph='chunk', show=j, zh=c['zh'], hl=c.get('hl', c['zh']), en=c['en'], note=c['note'], ln=[c['note']], 例=c['例'])
    jn = zk['join']
    kw = dict(marks=jn['marks'], 例=jn['例'], **({'base': jn['base']} if jn.get('base') else {}))
    if jn.get('base'):
        a, b = jn['say'].split(SPLIT)
        assert a and b and len(jn['ln']) == 2, k
        add(f's{k}bj', sc, a, ph='join', step='base', ln=jn['ln'][:1], **kw)
        add(f's{k}bf', sc, SPLIT + b, ph='join', step='fan', ln=jn['ln'][1:], **kw)
    else:
        add(f's{k}bf', sc, jn['say'], ph='join', step='fan', ln=jn['ln'], **kw)
    add(f's{k}e', sc, noq(sen['en']), lang='English', ph='read', gap=0.7)
    for j, (hl, dang, src, mark, ln, text, ex) in enumerate(x['pts'], 1):
        kw = {'例': ex} if ex else {}
        add(f's{k}p{j}', sc, text, ph='pt', hl=hl, dang=dang, src=src, mark=[mark], ln=ln, **kw)
    alt_ln, alt_text = x['alt']
    add(f's{k}h', sc, alt_text, ph='alt', ln=['可替换：' + a for a in alt_ln], 替换=alt_ln, gap=0.9)
    if (pi, si) == own[-1] or own[k][0] != pi:
        para_read(pi)

# ---------- 失分点、方法、全文 ----------
add('f01', 'fail', '讲完范文，再看常见的失分点。‖第一，第一段只写坐火车，忘了安排那辆车。这样，第二段回来取车，就接不上了。', note='① 只写坐火车、不安排车 → 第二段“回来取车”接不上')
add('f02', 'fail', '第二，时态混乱。叙事用一般过去时；更早发生的事，用过去完成时。‖比如：the road that had trapped her。', note='② 时态：叙事用一般过去时，更早的动作用过去完成时')
add('f03', 'fail', '第三，lie 和 lay 分不清。‖路静静地躺着，用的是 lie 的过去式 lay，别写成 laid。', note='③ lie（躺）→ lay；lay（放）→ laid，不要混')
add('f04', 'fail', '第四，结尾空喊大道理，不回到原文。‖主题要从情节里自然得出来：回到 ruin，回到 warmth。', note='④ 结尾空喊口号 → 回到原文的词：ruin、warmth', gap=0.8)
add('m01', 'sum', '最后，总结一下方法，一共五步。‖第一步，读原文：抓人物、目标、冲突、情感线和伏笔。', note='① 读原文：人物、目标、冲突、情感线、伏笔')
add('m02', 'sum', '第二步，读开头语：想清楚这一段要解决什么，怎么接下一段。', note='② 读开头语：这一段解决什么，怎么接下一段')
add('m03', 'sum', '第三步，列提纲：每段三到四步，原文的伏笔都要收住。', note='③ 列提纲：每段三到四步，伏笔都收住')
add('m04', 'sum', ZK['m04']['say'], note=ZK['m04']['note'])
add('m05', 'sum', '第五步，回头查：句式有没有变化，有没有呼应原文，结尾有没有点题。‖下面，我们把完整的范文，从头到尾读一遍。', note='⑤ 回头查：句式变化、呼应原文、结尾点题', gap=0.8)
n = 0
for pi, p in enumerate(fw['paragraphs']):
    for si, s in enumerate(p):
        n += 1
        add(f'u{n:02d}', 'full', noq(s['en']), lang='English', cur=[pi, si], gap=1.0 if si == len(p) - 1 else 0.6)
add('z01', 'full', '这道题的思路和范文，就讲到这里。同学们，我们下次再见。', gap=0.6)

(D / '范文.json').write_text(json.dumps(fw, ensure_ascii=False, indent=1) + '\n', 'utf-8')
doc = {'说明': '2026 新课标Ⅰ卷 读后续写讲解稿（稿源.py 生成，勿手改）。逐句讲：中文构思 → 逐块翻 → 连成一句（保底版 → 范文）→ 读整句 → 得分点（档 + 原文出处）→ 可替换。',
       '题目': '高考续写/讲解/2026_新课标Ⅰ卷/题目.json', '范文': '高考续写/讲解/2026_新课标Ⅰ卷/范文.json', 'segments': segs}
(D / '稿.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', 'utf-8')
print(f'稿：{len(segs)} 段；范文 {len(own)} 句')
