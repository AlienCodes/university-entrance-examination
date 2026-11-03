# 稿.json 由本文件生成（改稿改这里，再在本目录运行 python3 稿源.py，并复制到 高考语法填空/tts/稿_续写_2026_新课标Ⅰ卷.json；续写检查.py ⑥ 核对副本）
import json, sys
fw = json.load(open('范文.json'))
S = [s for p in fw['paragraphs'] for s in p]
own = [s for s in S if not s.get('given')]
segs = []
def Z(id, screen, text, gap=0.6, **kw): segs.append(dict(id=id, lang='Chinese', screen=screen, text=text, gap=gap, **kw))
def E(id, screen, text, gap=0.7, **kw): segs.append(dict(id=id, lang='English', screen=screen, text=text, gap=gap, **kw))
def noq(s): return s.replace('“', '').replace('”', '')

# 一、题目要求
Z('t01', 'task', '同学们好。今天讲二零二六年全国新课标一卷的读后续写。‖这道题二十五分：先读一篇三百多词的故事，再根据给出的两句开头语续写两段，一共一百五十词左右。')
Z('t02', 'task', '要求有三条。‖第一，情节要接着原文往下走，人物和前因后果都不能改。‖第二，两段都给了开头语，写的内容必须紧扣开头语。‖第三，词数一百五十左右，开头语不算在内。我们这篇范文写了一百七十七词。', 0.7)
Z('t03', 'task', '先听一遍两句开头语。第一段：', 0.4, hi='o1')
E('t04', 'task', fw['paragraphs'][0][0]['en'], 0.5, hi='o1')
Z('t05', 'task', '丹尼尔和瑞秋建议艾米丽坐火车，继续她的旅程。‖第二段：', 0.4, hi='o2')
E('t06', 'task', fw['paragraphs'][1][0]['en'], 0.5, hi='o2')
Z('t07', 'task', '三天后，艾米丽回来取她的车。', 0.8, hi='o2')

# 二、读原文
Z('r01', 'p1', '先读原文。‖读的时候盯住四样东西：人物、情节、冲突、情感线。同时把后面能用上的细节记下来。', 0.6,
  note='读原文：人物 · 情节 · 冲突 · 情感线 · 伏笔')
Z('r02', 'p1', '第一段交代人物和目的。‖艾米丽二十五岁，从底特律出发，要赶到多伦多，和男朋友一起过圣诞节。‖这是续写要收的第一条线：她到底能不能赶上圣诞节。', 0.6,
  mark=['Emily Sanders, a 25-year-old from Detroit, Michigan', 'to meet her boyfriend for Christmas'], note='人物与目的：赶去多伦多，和男朋友过圣诞（12 月 23 日出发）')
Z('r03', 'p1', '再看她的性格。‖她听到了暴风雪的警告，却没当回事，原文是：she didn’t give it much thought。‖这是一个伏笔：她有点大意。结局可以呼应它，让她吸取教训。', 0.6,
  mark=['she didn’t give it much thought'], note='伏笔：不把暴风雪预警当回事 → 结局可以吸取教训')
Z('r04', 'p1', '结果雪越下越大，她被引下高速，开上一条陌生的路，往一个加拿大小镇去。‖人生地不熟，危险已经开始了。', 0.7,
  mark=['was directed off the highway', 'an unfamiliar road toward a Canadian town'], note='情节：被引下高速 → 陌生小路，人生地不熟')
Z('r05', 'p2', '第二段，冲突一步步升级。‖大雪白茫茫一片，几乎没法开车；车先是卡住，好不容易挣脱；天黑了，她开始慌；最后车滑进了沟里，手机也没有信号。‖车掉进沟里，是续写里一定要交代的问题。', 0.6,
  mark=['The blinding whiteout', 'Emily’s car got stuck', 'panic set in', 'her car slid into a ditch', 'found no signal on her phone'], note='冲突升级：卡住 → 天黑、慌 → 滑进沟里 → 没信号')
Z('r06', 'p2', '她只能在车里过夜：裹着毯子，时不时发动引擎取暖。‖这里的情绪是孤独、寒冷、害怕。后面写温暖，就可以拿这里的冷来对比。', 0.7,
  mark=['She wrapped herself in a blanket', 'ran her engine for a few minutes every now and then'], note='情绪：孤独、寒冷、害怕 → 后文用“暖”来对比')
Z('r07', 'p3', '第三段是转折。‖她被轻轻的敲窗声叫醒，车外站着丹尼尔和他的妻子瑞秋。他们是回家路上看到这辆车，停下来帮忙的。‖原文有个短语：on their way home，可以推断他们就住在附近。这一点后面很有用：车留在这里有人照看，她回来也知道去哪儿找。', 0.6,
  mark=['a gentle knock', 'Daniel and his wife Rachel', 'on their way home'], note='转折：好心夫妻 Daniel 和 Rachel，就住在附近')
Z('r08', 'p3', '瑞秋说话的时候，原文用了：genuine warmth，真诚的温暖。‖艾米丽的心情也变了：grateful and relieved，感激又放心。‖情感线就出来了：从害怕，到被温暖，再到感激。', 0.7,
  mark=['With genuine warmth in her voice', 'Grateful and relieved'], note='情感线：害怕 → 被温暖 → 感激')
Z('r09', 'p4', '最后一段在咖啡馆。‖夫妻俩给她买了一杯热巧克力，耐心听她讲。热巧克力是个小道具，续写里可以再用一次。', 0.6,
  mark=['bought Emily a hot chocolate', 'listened patiently'], note='小道具：一杯热巧克力 → 续写可以再用')
Z('r10', 'p4', '原文停在三个难题上。‖离目的地还有一百英里左右；车彻底陷住了；整个假期计划可能泡汤。‖续写的任务很清楚：把这三个难题一个一个解决掉。', 0.8,
  mark=['about a hundred miles from her destination', 'her car was completely stuck', 'her entire holiday plan could be ruined'], note='三个难题：还差 100 英里 · 车陷住 · 假期可能泡汤')

# 三、开头语分析
Z('o01', 'open', '再看两句开头语。‖第一段开头，夫妻俩建议她坐火车走。所以第一段要写：她怎么接受建议，怎么到车站，车怎么安排。', 0.6,
  hi='o1', note='第一段：接受建议 → 怎么到车站 → 车怎么安排')
Z('o02', 'open', '第二段开头，三天后，她回来取车。‖这句话透露了两件事。‖第一，第一段结束的时候，车还留在小镇。‖第二，她平安到了多伦多，过完节才回来。所以第二段要写：车怎么样了，她怎么感谢夫妻俩，最后点题。', 0.6,
  hi='o2', note='第二段：车怎么样了 → 感谢夫妻俩 → 结尾点题')
Z('o03', 'open', '两段怎么衔接？‖第一段结尾留一个钩子：丹尼尔答应帮她把车从沟里拖出来。这样第二段一开头回来取车，就顺理成章。', 0.8,
  note='衔接：第一段埋“答应拖车”，第二段“回来取车”就顺理成章')

# 四、提纲与呼应
Z('u01', 'outline', '根据这些，列一个提纲。‖第一段四步。丹尼尔说明车站不远、火车还在开；艾米丽犹豫，但为了和男朋友过平安夜，下了决心；在夫妻俩家住一晚，天亮被送到车站，瑞秋塞给她一壶热巧克力，丹尼尔答应把车拖出来；火车开动，她含着泪挥手。', 0.6,
  col=1, lines=['① 车站不远，火车还在开', '② 犹豫 → 为了过平安夜，下决心', '③ 住一晚，天亮送站：热巧克力、答应拖车', '④ 火车开动，含泪挥手'])
Z('u02', 'outline', '第二段也是四步。车已经被拖出来、刮干净了；她送上从多伦多带来的巧克力，道谢；瑞秋笑着提醒她，下次要听天气预警；她开车离开，想明白这场风暴带给她的东西。', 0.7,
  col=2, lines=['① 车已拖出、刮干净', '② 送多伦多巧克力，道谢', '③ 瑞秋笑着提醒：听预警', '④ 晴空下离开，点题：陌生人的温暖'])
Z('e01', 'echo', '再检查一遍：原文的伏笔，在提纲里都要有着落。', 0.4)
Z('e02', 'echo', '一杯热巧克力，回来变成一盒巧克力。', 0.4, row=['a hot chocolate', 'a box of chocolates'])
Z('e03', 'echo', '没当回事的预警，变成瑞秋的提醒。', 0.4, row=['didn’t give it much thought', 'listen to the weather warnings'])
Z('e04', 'echo', '车滑进沟里，变成丹尼尔的承诺，第二段兑现。', 0.4, row=['slid into a ditch', 'pulled out of the ditch'])
Z('e05', 'echo', '可能泡汤的假期，变成救回来的圣诞节。', 0.4, row=['holiday plan could be ruined', 'you saved my Christmas'])
Z('e06', 'echo', '寒冷的雪夜，对应结尾的温暖。‖每一条线都收住，结局才完整。', 0.8, row=['the blinding whiteout', 'the warmth of strangers'])

# 五、逐句讲范文
def sent(k, intro, mean, role, pts, how):
    s = f's{k}'
    Z(f'{s}a', s, intro, 0.4, ph='read')
    E(f'{s}b', s, noq(own[k - 1]['en']), 0.6, ph='read')
    Z(f'{s}c', s, '意思是：' + mean[0], 0.5, ph='mean', ln='意思：' + own[k - 1]['zh'])
    Z(f'{s}d', s, role[0], 0.6, ph='mean', ln='作用：' + role[1])
    for j, (txt, hl, ln) in enumerate(pts, 1):
        Z(f'{s}p{j}', s, txt, 0.5, ph='pt', hl=hl, ln=ln)
    for j, (txt, ln, *alt) in enumerate(how, 1):
        Z(f'{s}h{j}', s, txt, 0.5 if j < len(how) else 0.8, ph='how', ln=ln, **({'替换': alt[0]} if alt else {}))

Z('s0', 's1', '下面逐句讲范文。‖第一段的开头语给的是建议，第一句就让丹尼尔把建议说具体。', 0.4, ph='read')
sent(1, '第一句。',
 ['车站只有十英里远，火车也还照常运行，丹尼尔说。'],
 ['它回答了读者心里的疑问：这么大的雪，火车还能坐吗？‖丹尼尔先把理由摆出来，建议才站得住。', '回答“这么大的雪，火车还能坐吗？”，让建议有理由'],
 [('得分点一，用人物对话推进情节。续写里有一两句对话，画面马上就活了。', 'Daniel said', '① 对话推进情节（直接引语）'),
  ('得分点二，具体细节：only ten miles away，说明车站近。', 'only ten miles away', '② 细节一：only ten miles away（近）'),
  ('得分点三，still running，说明火车还能坐。有了这两个细节，建议就不显得突兀。', 'still running', '③ 细节二：still running（可行）')],
 [('怎么写出来的？‖先想中文：车站不远，火车照常开。再把“不远”说具体，写成：only ten miles away。“照常开”就是：still running。', '车站不远 → only ten miles away；照常开 → still running'),
  ('可替换的说法：a short drive away，开车一会儿就到；还有：the trains haven’t stopped，火车没停。', '可替换：a short drive away / the trains haven’t stopped', ['a short drive away', 'the trains haven’t stopped'])])
sent(2, '第二句。',
 ['艾米丽犹豫了一下，可一想到能和男朋友一起过平安夜，她就下定了决心。'],
 ['这是心理描写：先犹豫，再下决心。犹豫的是车和陌生的小镇，下决心靠的是原文的目的：和男朋友过圣诞。‖她二十三号出发，第二天就是平安夜，时间线也对得上。', '心理变化：犹豫 → 下决心，呼应“和男朋友过圣诞”'],
 [('得分点一，心理描写，先抑后扬：hesitated，but，一转折，人物就有了起伏。', 'Emily hesitated, but', '① 心理描写，先抑后扬：hesitated, but …'),
  ('得分点二，让抽象名词做主语：the thought of spending Christmas Eve，是“这个念头”帮她下了决心。比直接写她决定了，高级得多。', 'the thought of spending Christmas Eve', '② 抽象名词作主语：the thought of doing'),
  ('得分点三，固定搭配：made up her mind，下定决心。', 'made up her mind', '③ 固定搭配：make up one’s mind')],
 [('怎么写出来的？‖中文是：她一想到……就下了决心。很多同学会写成：when she thought of it, she decided to go。意思没错，但很平。‖换个主语，让“念头”来做事，句子马上就有张力。', '“一想到……就决定” → 让 the thought 做主语'),
  ('可替换的说法：the idea of a Christmas with her boyfriend，或者：she soon made her decision。', '可替换：the idea of … / she soon made her decision', ['the idea of a Christmas with her boyfriend', 'she soon made her decision'])])
sent(3, '第三句，第一段信息量最大的一句。',
 ['在夫妻俩家里住了一晚后，艾米丽天一亮就被送到了车站。在那里，瑞秋把一保温壶热巧克力塞到她手里，丹尼尔答应找人把她的车从沟里拖出来。'],
 ['一句话解决了三件事。‖当晚住哪儿，呼应原文的“在车里过夜不安全”；怎么到车站；车怎么办，这是给第二段埋的钩子。', '解决“住哪儿、怎么到车站、车怎么办”，埋下第二段的钩子'],
 [('得分点一，完成式分词作状语：having spent the night，表示住一晚这件事发生在前。', 'Having spent the night', '① 完成式分词作状语：Having spent …（先发生）'),
  ('得分点二，被动语态：was driven，被送去车站。主语始终是艾米丽，视角不乱。', 'was driven', '② 被动语态：was driven（主语始终是 Emily）'),
  ('得分点三，where 引导非限制性定语从句，接着写车站里发生的事。', 'where Rachel pressed', '③ where 引导非限制性定语从句'),
  ('得分点四，动作描写：pressed a thermos of hot chocolate into her hands，塞到她手里。热巧克力呼应原文。', 'pressed a thermos of hot chocolate into her hands', '④ 动作描写：press … into her hands（呼应 hot chocolate）'),
  ('得分点五，使役结构：have her car pulled out，让别人把车拖出来。', 'have her car pulled out of the ditch', '⑤ have sth. done：have her car pulled out')],
 [('怎么写出来的？‖先列中文三件事：住一晚，被送去车站，在车站两个人各做一件事。‖先发生的放进分词，地点用 where 带出来，两个动作用 and 连起来。三个短句就合成了一个长句。', '三件事 → 分词（先发生）+ 主句 + where 从句'),
  ('可替换的说法：after a night at their home；handed her a thermos；get her car towed out。', '可替换：after a night at their home / handed her … / get her car towed out', ['after a night at their home', 'handed her a thermos', 'get her car towed out'])])
sent(4, '第四句，第一段的结尾。',
 ['火车开动时，她隔着结了霜的车窗挥手，眼里涌出感激的泪水。'],
 ['用一个画面收住情绪。人离开了小镇，车留在了这里，第二段回来取车就有了空间。', '用画面收尾：情绪落在“感激”，人走车留，给第二段留空间'],
 [('得分点一，as 引导时间状语从句：as the train pulled away，pull away 是车开走。', 'As the train pulled away', '① As 引导时间状语从句；pull away 驶离'),
  ('得分点二，环境细节：the frosted window，结了霜的车窗，把风雪带进画面。', 'the frosted window', '② 环境细节：frosted window（结霜的车窗）'),
  ('得分点三，独立主格：tears of gratitude welling up in her eyes，名词加现在分词，写出眼泪涌上来的样子。', 'tears of gratitude welling up in her eyes', '③ 独立主格：tears … welling up in her eyes')],
 [('怎么写出来的？‖中文是：眼里涌出感激的泪水。别只写 she cried。把眼泪当主角：tears of gratitude，再接一个正在发生的动作：welling up。', '“眼里涌出感激的泪水” → 名词 + doing 的独立主格'),
  ('可替换的说法：with tears of gratitude in her eyes；或者：her eyes wet with tears。', '可替换：with tears of gratitude in her eyes / her eyes wet with tears', ['with tears of gratitude in her eyes', 'her eyes wet with tears'])])
Z('s5o', 's5', '第二段。开头语说她回来取车，第一句就要回答读者最关心的：车怎么样了。', 0.4, ph='read')
sent(5, '第五句。',
 ['让她惊讶的是，车就停在夫妻俩家门外，已经从沟里拖了出来，车上的雪也刮得干干净净。'],
 ['紧扣开头语，马上回答车怎么样了。也兑现了上一段丹尼尔的承诺，前后呼应。', '紧扣开头语回答“车怎么样了”，兑现上一段的承诺'],
 [('得分点一，to her surprise，用情绪开头。她惊讶的是：车不但拖出来了，还停在他们家门外，刮得干干净净。', 'To her surprise', '① To her surprise：情绪开头'),
  ('得分点二，两个过去分词短语并列：already pulled out of the ditch，and scraped clean of snow，补充说明车的状态。', 'already pulled out of the ditch and scraped clean of snow', '② 过去分词短语并列作补充说明'),
  ('得分点三，pulled out of the ditch，和上一段的承诺用的是同一个短语，前后呼应。', 'pulled out of the ditch', '③ 与上一段 pulled out of the ditch 呼应')],
 [('怎么写出来的？‖中文是：车已经被拖出来，雪也刮干净了。不必再写一个从句，直接接两个过去分词，句子更紧凑。‖scrape 是刮，scrape it clean，是刮干净。', '“已经被拖出来、刮干净了” → 两个过去分词并列'),
  ('可替换的说法：much to her surprise；或者：cleared of snow。', '可替换：much to her surprise / cleared of snow', ['much to her surprise', 'cleared of snow'])])
sent(6, '第六句。',
 ['艾米丽深受感动，把一盒从多伦多带来的巧克力递给他们，说：你们救的不只是我的车，还有我的圣诞节。'],
 ['这是感谢的高潮。巧克力呼应原文那杯热巧克力，一来一回；救了圣诞节，呼应原文的假期可能泡汤。', '感谢的高潮：巧克力一来一回，“救了圣诞节”呼应“假期可能泡汤”'],
 [('得分点一，形容词短语作状语：deeply moved，交代她的心情。', 'Deeply moved', '① 形容词短语作状语：Deeply moved'),
  ('得分点二，现在分词引出直接引语：saying，动作和说话连在一起。', 'saying', '② 现在分词 saying 引出直接引语'),
  ('得分点三，对比的说法：you didn’t just save my car，前后用分号隔开，后半句一下子把情感推上去。', 'You didn’t just save my car; you saved my Christmas', '③ 对比：didn’t just … ; you …')],
 [('怎么写出来的？‖中文是：你们救的不只是我的车，还有我的圣诞节。可以用 not only，but also，不过偏书面。口语里说 didn’t just，更自然。', '“不只是……还有……” → didn’t just … ; …（口语更自然）'),
  ('可替换的说法：touched by their kindness；还有：you saved more than my car。', '可替换：Touched by their kindness / You saved more than my car', ['touched by their kindness', 'you saved more than my car'])])
sent(7, '第七句。',
 ['瑞秋抱了抱她，眨眨眼说：下次可得听天气预警！'],
 ['呼应原文的伏笔：她当初没把预警当回事。用一句玩笑把教训点出来，不说教。', '呼应伏笔“没把预警当回事”，用玩笑点出教训'],
 [('得分点一，动作：hugged her，抱了抱她。', 'hugged her', '① 动作：hugged her'),
  ('得分点二，神态：with a wink，眨眨眼，一下子就有了画面，也说明这是善意的玩笑。', 'with a wink', '② 神态：with a wink（善意的玩笑）'),
  ('得分点三，用对话点题：listen to the weather warnings，和开头的伏笔对上。', 'listen to the weather warnings', '③ 对话点题，呼应 warnings')],
 [('怎么写出来的？‖中文是：眨眨眼说。用 with 加名词，表示怎么说：said with a wink，同样可以说：said with a smile。', '“眨眨眼说” → said with a wink（with + 名词）'),
  ('也可以说：said playfully，开玩笑地说。', '可替换：said with a smile / said playfully', ['said with a smile', 'said playfully'])])
sent(8, '第八句，全文的结尾。',
 ['在晴朗的蓝天下开车离开时，艾米丽意识到，这场暴风雪差点毁了她的假期，却也给她带来了更珍贵的东西：陌生人的温暖。'],
 ['点题升华。环境前后对比：暴风雪变成了晴空；情感从冷到暖，回到原文的 genuine warmth。', '点题：暴风雪 → 晴空，冷 → 暖，回到原文的 genuine warmth'],
 [('得分点一，现在分词作状语：driving away，交代动作的背景。', 'Driving away', '① 现在分词作状语：Driving away'),
  ('得分点二，环境描写：under a clear blue sky，和原文的漫天大雪形成对比。', 'under a clear blue sky', '② 环境对比：clear blue sky ↔ 暴风雪'),
  ('得分点三，过去完成时：had nearly ruined，差点毁了，说的是之前的事。', 'had nearly ruined her holiday', '③ that 宾语从句 + 过去完成时'),
  ('得分点四，yet 转折，再用冒号引出主题：the warmth of strangers。far 修饰比较级，加强语气：far more precious。', 'something far more precious: the warmth of strangers', '④ yet 转折 + 冒号点题；far 修饰比较级 more precious')],
 [('怎么写出来的？‖中文是：差点毁了……却带来了……。先写失去的，再写得到的，中间用 yet 一转。主题词选 warmth，正好和开头的寒冷对上。', '“差点毁了……却带来了……” → nearly ruined …, yet brought …'),
  ('可替换的说法：almost spoiled her holiday；something much more valuable；the kindness of strangers。', '可替换：almost spoiled / much more valuable / the kindness of strangers', ['almost spoiled her holiday', 'something much more valuable', 'the kindness of strangers'])])

# 六、常见失分点
Z('f01', 'fail', '常见失分点，说五个。‖第一，和开头语矛盾。第二段说三天后回来取车，第一段却写她开着车走了。', 0.5, note='① 与开头语矛盾（第一段写她开车走了）')
Z('f02', 'fail', '第二，丢了原文的线索。车在沟里、离目的地还很远、圣诞节的约定，这些不交代，结局就是悬着的。', 0.5, note='② 丢线索：车、路程、圣诞约定没交代')
Z('f03', 'fail', '第三，乱加情节。突然冒出小偷、车祸，和原文温暖的基调不符。', 0.5, note='③ 乱加情节：小偷、车祸，与温暖基调不符')
Z('f04', 'fail', '第四，只讲道理，不写画面。结尾一大段大道理，不如一个动作、一句对话、一个环境细节。', 0.5, note='④ 只讲道理：用动作、对话、环境代替说教')
Z('f05', 'fail', '第五，语法硬伤。时态乱跳，句式堆砌，词数超出太多。宁可句子少一点，但每句都对。', 0.8, note='⑤ 语法硬伤：时态乱、句式堆砌、词数超标')

# 七、方法总结
Z('m01', 'sum', '最后总结方法。‖第一步，读原文：找人物、冲突、情感线，把伏笔圈出来。', 0.5, note='① 读原文：人物、冲突、情感线，圈出伏笔')
Z('m02', 'sum', '第二步，读开头语：推出每段写什么，第一段结尾给第二段留钩子。', 0.5, note='② 读开头语：定每段内容，第一段结尾留钩子')
Z('m03', 'sum', '第三步，列提纲：每一个伏笔都要有着落。', 0.5, note='③ 列提纲：每个伏笔都有着落')
Z('m04', 'sum', '第四步，逐句写：动作、心理、对话、环境搭配着用，高级句式用在要紧的地方。', 0.5, note='④ 逐句写：动作、心理、对话、环境，句式用在要紧处')
Z('m05', 'sum', '第五步，结尾呼应主题，用画面点题。', 0.8, note='⑤ 结尾：呼应主题，用画面点题')
Z('w00', 'full', '最后，把完整的范文读一遍。', 0.6)
k = 0
for pi, p in enumerate(fw['paragraphs']):
    for si, s in enumerate(p):
        k += 1
        E(f'w{k:02d}', 'full', noq(s['en']), 0.9 if si == len(p) - 1 else 0.6, cur=[pi, si])
Z('z01', 'full', '这篇读后续写就讲到这里。', 0.6)

doc = {'说明': '读后续写讲解稿（格式与 高考语法填空 的稿相同：配音工具直接用）。text = 送进配音的文字（中文里成句的英文前后用中文标点隔开，单独按英文合成；‖ 标必须停顿的边界）；screen = 画面；'
             'mark = 原文屏高亮的原文短语；note / lines / row = 画面卡片新增的一行；ph = 逐句屏的阶段（read 读句 / mean 意思与作用 / pt 得分点 / how 怎么写与可替换）；hl = 范文句里标出的得分点短语；替换 = 本段说到的可替换英文表达（不在原文、范文里）；cur = 全文通读当前句。',
       '题目': '高考续写/讲解/2026_新课标Ⅰ卷/题目.json', '范文': '高考续写/讲解/2026_新课标Ⅰ卷/范文.json', 'segments': segs}
json.dump(doc, open('稿.json', 'w'), ensure_ascii=False, indent=1)
zh = sum(len([c for c in s['text'] if '一' <= c <= '鿿']) for s in segs if s['lang'] == 'Chinese')
en = sum(len(s['text'].split()) for s in segs if s['lang'] == 'English')
print(len(segs), '段；中文字', zh, '约', round(zh / 5.6), '秒；英文段词数', en, '约', round(en / 2.5), '秒')
EX = {'s2h1': ['when she thought of it, she decided to go'], 's4p1': ['pull away'], 's4h1': ['she cried'], 's5h1': ['scrape it clean'],
      's6h1': ['not only … but also'], 's7h1': ['said with a smile']}
for s in segs:
    if s['id'] in EX: s['例'] = EX[s['id']]
doc['说明'] += '例 = 讲解里举的反例、泛例英文（不出自原文、范文）。'
json.dump(doc, open('稿.json', 'w'), ensure_ascii=False, indent=1)
