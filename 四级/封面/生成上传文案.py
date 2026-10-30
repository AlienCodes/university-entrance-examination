"""B 站上传文案：合集标题、简介、标签，以及 60 个视频（分P）的标题。标题长度按 B 站上限 80 字检查。"""
import json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
C4 = HERE.parent
d = json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']
d = sorted(d, key=lambda p: p['id'], reverse=True)                    # 2026 → 2021
SENTS = sum(len(para) for p in d for para in p['paras'])
UNIQ = len({w['h'].lower() for p in d for para in p['paras'] for s in para for w in s['w']})

def short(p):            # “2026年6月 第3套” → “2026年6月第3套”
    return p['paper'].replace(' ', '')

def video_title(p):
    t = f"【四级阅读真题】{short(p)} {p['passage']}｜{p['title']}｜逐句精读 中英对照 生词全标注 CET4仔细阅读"
    if len(t) > 80:
        t = f"【四级阅读真题】{short(p)} {p['passage']}｜{p['title']}｜逐句精读 生词全标注"
    assert len(t) <= 80, t
    return t

SERIES = f"【60篇】四级阅读真题逐句精读｜2021-2026 CET4仔细阅读 Passage One+Two｜中英对照 生词全标注 记住四级重点单词｜4K"
assert len(SERIES) <= 80, len(SERIES)
TAGS = ['英语四级', '四级阅读', '四级真题', '大学英语四级', 'CET4', '四级词汇', '仔细阅读', '英语阅读', '逐句精读', '四级备考']
assert len(TAGS) == 10 and all(len(t) <= 20 for t in TAGS)

DESC = f"""60篇大学英语四级（CET-4）仔细阅读真题，逐句精读，配英文朗读、中文翻译和生词注释。2021年6月到2026年6月的四级真题，Passage One 和 Passage Two 各30篇。

【每个视频里有什么】
1. 真题原文一句一屏，男声逐句朗读，适合跟读、听读、磨耳朵
2. 每句都有中文翻译，中英对照，读懂每一句
3. 句子里的生词、词组全部标出，带编号、词性和释义，60篇共 {UNIQ}+ 个词汇，{SENTS} 句
4. 4K 高清，手机上也看得清

【怎么用效果最好】
先只看英文，试着自己理解 → 听朗读跟读 → 看翻译核对 → 把标出的生词记下来。一篇大约 2 到 3 分钟，每天几篇，坚持刷完 60 篇，四级阅读里反复出现的重点单词都会见过很多遍。

【适合谁】
准备大学英语四级（CET4）考试的同学；想提高英语阅读、扩充四级词汇、练习英语听力和朗读的同学。也可以作为六级、专升本、考研英语的基础阅读练习。

篇目按时间从新到旧排列，2026年6月第1、2、3套在最前。

关键词：英语四级 四级阅读 四级真题 四级阅读真题 大学英语四级 CET4 CET-4 仔细阅读 Section C 篇章阅读 阅读理解 Passage One Passage Two 逐句精读 逐句翻译 中英对照 四级单词 四级词汇 背单词 四级备考 英语阅读 英语精读 英语朗读 英语听力 跟读 2026年6月四级 2025年12月四级 2025年6月四级 2024年四级 2023年四级 2022年四级 2021年四级"""
assert len(DESC) <= 2000, len(DESC)

# ---- 合集简介（用户 2026-10-08：60 个视频做成一个合集，要非常详细的简介）----
import subprocess
from collections import Counter, defaultdict
VIDS = sorted((C4 / '最终视频').glob('*.mp4'))
assert len(VIDS) == 60, len(VIDS)
SECS = [float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(v)],
                             capture_output=True, text=True, check=True).stdout) for v in VIDS]
TOTAL_MIN = round(sum(SECS) / 60)
LO, HI = int(min(SECS) // 60), int(-(-max(SECS) // 60))                 # 每集分钟数范围（向下、向上取整）
MARKS = sum(len(s['w']) for p in d for para in p['paras'] for s in para)  # 标注总处数（含重复）
GENRE = Counter(p['genre'].split(' · ')[0] for p in d)
SETS = defaultdict(list)                                                  # “2026年6月” → [1, 2, 3]
for p in d:
    exam, n = p['paper'].split(' ')
    if int(n[1]) not in SETS[exam]:
        SETS[exam].append(int(n[1]))
assert sum(len(v) for v in SETS.values()) == 30
SET_LINES = '\n'.join(f"{exam}　第{'、'.join(map(str, sorted(v)))}套" for exam, v in SETS.items())
TITLES = {p['title'] for p in d}

# 话题分组：每个例子都核对过确实是某篇的题目（下面的 assert 逐条检查关键字在题目里）
TOPICS = [
    ('心理与个人成长', ['冒名顶替', '坚毅', '意志力', '好奇心', '情商', '无聊', '雄心', '他人的认可', '道德厌恶', '诚实']),
    ('饮食与健康', ['有机食品', '植物肉', '蛋白质', '服药时间', '营养研究', '饮食质量', '健康饮食', '基因检测']),
    ('职场与经济', ['远程办公', '零工经济', '团队建设', '说服', '女工程师', '七十多岁', '多任务', '竞争对手', '以忙碌为荣']),
    ('教育与学习', ['玩耍', '网络课程', '远程教育', '全年制上学', '理财教育', '衰老的大脑']),
    ('科学与科技', ['自动驾驶', '基因编辑', '科研资金', '科学辩论', '社交媒体']),
    ('社会与环境', ['大熊猫', '水产养殖', '种植权', '粮食计划署', '无家可归', '大房子', '养老院']),
    ('文化与生活', ['音乐', '歌剧', '着装规范', '米其林', '赛马', '超市']),
]
for _, ks in TOPICS:
    for k in ks:
        assert sum(k in t for t in TITLES) >= 1, k
TOPIC_SHOW = {'冒名顶替': '冒名顶替现象', '多任务': '多任务处理', '科学辩论': '公开的科学辩论', '雄心': '过度的雄心', '他人的认可': '别让他人的认可左右自我', '说服': '说服的艺术', '七十多岁': '七十多岁仍在工作',
              '以忙碌为荣': '别再以忙碌为荣', '玩耍': '在玩耍中培养21世纪技能', '衰老的大脑': '学习让衰老的大脑受益',
              '粮食计划署': '世界粮食计划署', '赛马': '传奇赛马红朗姆', '无家可归': '洛杉矶无家可归问题', '大房子': '追求大房子的代价',
              '米其林': '纯素餐厅摘米其林三星', '营养研究': '营养研究背后的资助', '饮食质量': '饮食质量与社会阶层',
              '健康饮食': '青少年健康饮食', '服药时间': '服药时间影响药效', '科研资金': '科研资金与研究偏差',
              '道德厌恶': '孩子的道德厌恶', '诚实': '什么让人更诚实', '社交媒体': '社交媒体与员工流失'}
TOPIC_LINES = '\n'.join(f"· {name}：{'、'.join(TOPIC_SHOW.get(k, k) for k in ks)}" for name, ks in TOPICS)

HEJI_NAME = '60篇四级阅读真题逐句精读'
N_P = len(d)
assert N_P == 60
HEJI = f"""60篇大学英语四级（CET-4）阅读真题，一篇一集，逐句精读。收录2021年6月至2026年6月间30套四级试卷的仔细阅读（Section C），每套 Passage One、Passage Two 两篇全都有，共60篇。真题原文一句一屏，每句配英文朗读、中文翻译和生词编号注释，目标只有一个：在真题原文里把四级阅读的重点单词记全、记牢。

【合集数据】
· {N_P}篇真题，30套试卷，{SENTS}句原文，句句有中文翻译
· 生词标注{MARKS}处，去重后{UNIQ}个单词和词组
· 每集{LO}～{HI}分钟，60集全部看完约{TOTAL_MIN // 60}小时{TOTAL_MIN % 60}分钟
· 4K高清（3840×2160），手机上也看得清
· 体裁：议论文{GENRE['议论文']}篇、说明文{GENRE['说明文']}篇、记叙文{GENRE['记叙文']}篇、书评{GENRE['书评']}篇

【收录试卷】（合集按考试时间从新到旧排列）
{SET_LINES}
以上每套都含 Passage One 和 Passage Two 两篇。

【每一集里有什么】
1. 片头：年份、第几套、第几篇和中文题目，一眼找到要看的那篇
2. 一句一屏：真题原文逐句出现，特别长的句子在合适的地方拆成两屏，字大不挤
3. 逐句朗读：AI合成男声，语速适中；标点处自然停顿，句与句之间停0.8秒，正好跟读
4. 中文翻译：每句英文下面都有翻译，中英对照，读懂每一句
5. 生词注释：句中生词、词组高亮并编号，对应编号给出词性和释义，释义贴合这句话里的意思

【话题覆盖】四级阅读常考的话题基本都有：
{TOPIC_LINES}

【推荐学法：一篇四步】
① 先读：只看英文，遮住下面的翻译，试着自己读懂，卡住的地方记下来
② 再听：听朗读逐句跟读，句间停顿正好够跟一遍
③ 对照：看中文翻译，核对自己哪里理解错了
④ 记词：把高亮的生词抄进单词本，第二天先复习再看新的一篇

【打卡计划】
· 30天计划：每天2集，正好是一套试卷的 Passage One + Passage Two，每天约5分钟
· 15天冲刺：每天4集（两套试卷），每天约10分钟
· 刷完一遍后，按生词本回看没记住的那几篇

【适合谁】
· 备考大学英语四级（CET-4）的同学，尤其是阅读丢分多、单词量不够的同学
· 想用真题背单词的同学：在原文语境里记单词，比单纯背单词书记得牢
· 想练英语听力、跟读、朗读的同学
· 六级、专升本、考研英语打基础

【常见问题】
问：有题目和答案解析吗？
答：没有，这个合集专注原文精读和记单词。建议先自己限时做一遍题，再用视频逐句精读。
问：从哪一集开始看？
答：按顺序从最新的2026年6月开始最好；也可以按年份挑着看。

觉得有用就点赞、收藏合集，转发给一起备考的同学，一起把四级阅读拿下！

关键词：英语四级 四级阅读 四级真题 四级阅读真题 大学英语四级 CET4 CET-4 仔细阅读 Section C 阅读理解 Passage One Passage Two 逐句精读 中英对照 四级单词 四级词汇 背单词 四级备考 英语听力 跟读"""
assert len(HEJI) <= 2000, len(HEJI)                                        # B 站视频简介上限 2000 字

HEJI_SHORT = f"""60篇四级阅读真题（2021.6—2026.6，30套试卷的仔细阅读 Passage One + Passage Two），一篇一集逐句精读：一句一屏、英文朗读、中文翻译、生词编号注释。共{SENTS}句、{UNIQ}个生词词组，4K高清。每天2集刷一套卷，30天把四级阅读的重点单词记全。"""

lines = ['# B 站上传文案（四级阅读真题 60 篇）', '',
         f'## 合集名称（{len(HEJI_NAME)} 字）', '', '```', HEJI_NAME, '```', '',
         f'## 合集简介 · 详细版（{len(HEJI)} 字，在 B 站视频简介上限 2000 字以内）', '',
         '合集里的 60 个视频按“收录试卷”的顺序排（从新到旧，与下面的篇目清单 P1—P60 一致）。', '',
         '```', HEJI, '```', '',
         f'## 合集简介 · 短版（{len(HEJI_SHORT)} 字，合集简介框字数不够时用）', '', '```', HEJI_SHORT, '```', '',
         f'## 合集 / 分P 视频的总标题（{len(SERIES)} 字，上限 80）', '', '```', SERIES, '```', '',
         '## 标签（10 个，B 站上限 10 个）', '', '```', ' '.join(TAGS), '```', '',
         f'## 简介（{len(DESC)} 字，上限 2000）', '', '```', DESC, '```', '',
         '## 60 个视频的标题（单独上传时用作视频标题；分P 上传时用作每一P的标题）', '',
         '每个都带年份、月份、第几套、第几篇和中文题目，方便别人按“2026年6月四级第3套”这样搜到。', '']
lines += [f'{i}. `{video_title(p)}`（{len(video_title(p))} 字）' for i, p in enumerate(d, 1)]
lines += ['', '## 篇目清单（可以放在评论区置顶）', '']
lines += [f'P{i} {short(p)} {p["passage"]} {p["title"]}' for i, p in enumerate(d, 1)]
(HERE / 'B站上传文案.md').write_text('\n'.join(lines) + '\n', 'utf-8')
print('series', len(SERIES), 'desc', len(DESC), 'max video title', max(len(video_title(p)) for p in d))
print(video_title(d[0])); print(video_title(d[-1]))
