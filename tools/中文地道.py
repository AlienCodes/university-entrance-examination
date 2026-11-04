"""中文必须地道（用户 2026-11-04：“像 忍泪 这种描述，根本就不符合中国人的说话习惯……一般大家肯定会说他强忍住眼泪……
一定要考虑这个描述，它完完全全符合中国人的说话习惯”）。规则只写在这一处，所有中文讲解稿（配音 + 画面字）都调它。

problems(items)：items 是 [(位置, 中文)]，返回问题列表（每条带建议改法）。
  ① 黑名单 BAD：文言 / 书面缩略的生硬词（忍泪、挥别、驻足、颔首、未曾、彼时……）、翻译腔（进行了分析、被……所……、驶离、挽救了我的……）；
  ② 一个小句（两个标点之间）里堆 4 个以上“的”（翻译腔）。
  黑名单只收“确定不地道”的说法；自然不自然的最终判断交审阅员（带埋雷），审阅员看出、程序能查的补进 BAD。
lesson_items(目录)：读后续写一课的全部中文（稿.json 的配音 text 与画面字、逐块翻译稿、范文中文、高亮 / 伏笔 / 可替换中文）；
  题目.json（原题、评分标准照原卷）不查；说明、复核、旧稿错误等内部记录不查。
用法：python3 tools/中文地道.py 讲解目录      |   双向验证：python3 tools/防复发/验证/中文地道.py"""
import json
import re
import sys
from pathlib import Path

# (正则, 建议)。只收确定生硬的；新加一条先在现有全部讲稿上跑，不许误报。
BAD = [
    (r'忍泪', '强忍着眼泪 / 忍住眼泪'),
    (r'拭泪|拭去(?:了)?泪', '擦眼泪'),
    (r'含泪(?!水)', '含着眼泪 / 眼里含着泪'),
    (r'挥别', '挥手告别 / 挥手道别'),
    (r'驻足', '停下脚步 / 停下来'),
    (r'伫立', '站着 / 静静地站在'),
    (r'颔首', '点头 / 点了点头'),
    (r'未曾', '从没 / 没有'),
    (r'尚未', '还没'),
    (r'彼时', '那时候 / 当时'),
    (r'此番', '这次'),
    (r'旋即', '马上 / 很快'),
    (r'遂(?!愿|心)', '于是 / 就'),
    (r'袭来', '直接说感受：她开始慌了 / 一下子慌了'),
    (r'驶离', '开出 / 开下（高速）'),
    (r'一以贯之', '从头到尾没变 / 始终如一'),
    (r'停车相助|出手相助|(?<![互])相助', '帮忙 / 帮她一把'),
    (r'更显(?!得)', '显得更……'),
    (r'(?:同时|一并)呈现', '一起写出来 / 一句写完'),
    (r'挽救了(?:我|你|她|他|我们|你们|他们)的', '救了……的'),
    (r'获救的希望', '没人能来救 / 一时半会儿没人来救'),
    (r'被引导', '被分流 / 被引着'),
    (r'进行(?:了)?(?:一番|一次|一下)?(?:讨论|分析|解释|翻译|描写|描述|处理|说明|思考|改写)', '直接用动词：分析一下 / 解释说'),
    (r'被[^，。；：、！？\s]{1,8}所(?:[^以有在])', '去掉“所”，或改成主动句'),
    (r'作为一个(?:学生|老师|人)', '直接说：学生要…… / 我们……'),
    (r'(?:做|作)出(?:了)?(?:回应|反应)(?!过来)', '直接用动词：回应 / 回答'),
    (r'对此', '对这件事 / 这一点'),
    (r'予以', '直接用动词'),
    (r'加以(?:说明|解释|分析)', '直接用动词：说明一下'),
]
BAD_RE = [(re.compile(a), b) for a, b in BAD]
DE_MAX = 3          # 一个小句里“的”最多 3 个
CLAUSE = re.compile(r'[^，。；：、！？,.;:!?（）()“”‘’—…\n‖]+')


def problems(items):
    E = []
    for where, s in items:
        for rx, tip in BAD_RE:
            for m in rx.finditer(s):
                E.append(f'中文不地道 {where}：“{m.group(0)}”（上下文：{s[max(0, m.start() - 8):m.end() + 8]}）→ 建议：{tip}')
        for c in CLAUSE.findall(s):
            if c.count('的') > DE_MAX:
                E.append(f'中文不地道 {where}：一个小句堆了 {c.count("的")} 个“的”（{c}）→ 建议：拆成两句或去掉几个“的”')
    return E


SKIP = {'说明', '复核', '旧稿错误', '合成提醒', '题目', '范文', 'en', 'base', 'marks', 'src', 'mark', 'read', 'lang', 'screen', 'id'}
HAN = re.compile('[一-鿿]')


def _walk(o, path, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k not in SKIP:
                _walk(v, f'{path}.{k}' if path else k, out)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _walk(v, f'{path}[{i}]', out)
    elif isinstance(o, str) and HAN.search(o):
        out.append((path, o))


def doc_items(doc, name='稿.json'):
    """稿.json：段以 id 标位置。"""
    out = []
    for s in doc.get('segments', []):
        _walk(s, '', tmp := [])
        out += [(f'{name} {s.get("id")}.{p}', t) for p, t in tmp]
    return out


def lesson_items(d):
    d = Path(d)
    out = doc_items(json.loads((d / '稿.json').read_text('utf-8')))
    for f in ('逐块翻译稿.json', '范文.json', '高亮中文.json', '伏笔中文.json', '可替换中文.json'):
        p = d / f
        if p.exists():
            _walk(json.loads(p.read_text('utf-8')), '', tmp := [])
            out += [(f'{f} {k}', t) for k, t in tmp]
    return out


if __name__ == '__main__':
    E = problems(lesson_items(sys.argv[1]))
    print('\n'.join(E))
    print(f'中文地道检查：{len(E)} 处')
    sys.exit(1 if E else 0)
