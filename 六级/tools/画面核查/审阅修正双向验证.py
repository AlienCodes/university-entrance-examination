"""六级黑板截图盲审（2026-10-17，6 批，每批埋雷全部查出）报出的真问题：每一类都有排版机械检查（layoutcheck.py），这里双向验证：
   ① 审阅前的引擎（专八/tools/make_video_审阅前.py，正文 600 的教室黑板样式 = 审阅员看到的截图；jieba 不加载 分词补充.txt）在审阅员报出问题的句子上，
      对应的检查必须报出（检查真能查出这类毛病）；
   ② 现在的引擎和样式在同样的句子上 0 处（修正到位）；
   ③ 审阅之后又补的修正（左单引号前加 <wbr>）撤掉 → 必须报出，现在 0。
不是真问题、驳回的审阅意见（理由）记在 驳回 里，不验证。
用法：/opt/ttsenv/bin/python 六级/tools/画面核查/审阅修正双向验证.py（约 10 分钟；全部通过退出码 0）"""
import json
import subprocess
import sys
import tempfile
import types
from collections import defaultdict
from pathlib import Path

R = Path(__file__).resolve().parents[3]
TOOLS = R / '专八' / 'tools'
sys.path.insert(0, str(TOOLS))
P = {p['id']: p for p in json.loads((R / '六级/data/vocab.json').read_text('utf-8'))['passages']}

CASES = [  # 篇目, 句号, 必须报出的检查（审阅前的引擎）, 审阅意见
    ('s05', 1, '所有格样式', 'corporations’ 的撇号近黑色（样式 3 没有 --ink）'), ('s15', 24, '所有格样式', 'citizens’'), ('s27', 6, '所有格样式', 'consumers’'),
    ('s37', 6, '所有格样式', 'employees’'), ('s38', 13, '所有格样式', 'advertisements’'), ('s39', 1, '所有格样式', 'human beings’'),
    ('s39', 5, '所有格样式', 'species’'), ('s40', 4, '所有格样式', 'giants’'), ('s56', 21, '所有格样式', 'classmates’'),
    ('s56', 23, '所有格样式', 'The Enlightenment’s 细灰'), ('s57', 13, '所有格样式', 'consumers’'),
    ('s02', 7, '行首禁则', '“（音乐、视频等） / ；流式传输”'),
    ('s01', 11, '数字单位', '$13 / billion'), ('s01', 21, '数字单位', '$350 / billion'), ('s05', 10, '数字单位', '$250 / billion'),
    ('s02', 13, '释义单字', '受 / （法律、规定等）保护'), ('s07', 2, '释义单字', '给（某人）出 / （题）'), ('s08', 18, '释义单字', '使 / （某事）以……为中心'),
    ('s21', 4, '释义单字', '……并 / 不像……'), ('s23', 14, '释义单字', '内化；使 / 成为……'), ('s32', 8, '释义单字', '使 / （论文）得以发表'),
    ('s60', 14, '释义单字', 'in the absence of 在 / 没有……'),
    ('s01', 9, '括注分离', '（有组织的） / 工作'), ('s01', 14, '括注分离', '使用 / （的机会）'), ('s01', 17, '括注分离', '争取 / （……的参与或帮助）'),
    ('s02', 12, '括注分离', '（成功的） / 希望'), ('s06', 3, '括注分离', '（网络） / 平台'), ('s06', 8, '括注分离', '受（疾病） / 影响的'),
    ('s06', 14, '括注分离', '预计 / （某时）到来的'), ('s06', 18, '括注分离', '（大规模） / 数据收集'), ('s07', 15, '括注分离', '（使人） / 想到'),
    ('s07', 19, '括注分离', '（判断） / 正确的'), ('s36', 18, '括注分离', '持有 / （观点）'), ('s37', 17, '括注分离', '组织 / （活动）'),
    ('s38', 3, '括注分离', '接触 / （的机会）'), ('s40', 1, '括注分离', '（大范围的） / 疫情'), ('s46', 8, '括注分离', '背负 / （债务）'),
    ('s47', 6, '括注分离', '（经研究） / 发现'),
    ('s02', 4, '西文断开', 'Stable / Diffusion'),
    ('s27', 16, '术语断开', '“能源 / 转型”'), ('s51', 10, '术语断开', '《思考，快与 / 慢》'), ('s57', 10, '术语断开', '“非 / 转基因”'),
    ('s27', 12, '中英断开', '“100% / 可再生”'),
    ('s37', 17, '分句单字', '传达得 / 好'),
    ('s26', 2, '英文短行', 'actually / compares unfavourably to'), ('s54', 4, '英文短行', 'We / don’t have to look further than'),
    ('s55', 20, '英文短行', 'They also / hold employees accountable for'), ('s56', 2, '英文短行', 'book / Amusing Ourselves to Death'),
    ('s49', 4, '英文短行', 'engage in / science communication'),
    ('s39', 17, '高亮丢失', 'over-imitate 成了正文白色'),
    ('s45', 10, '注释分离', 'toddlers / (学步儿童)'),
    ('s57', 10, '西文撇号', 'Hunt’ s在'),
    ('s35', 10, '译文断词', '占 / 比过高'), ('s02', 1, '译文断词', '文生 / 图AI工具'),
    ('s05', 5, '译文短行', '这种转移 / 自20世纪80年代以来从未停歇'), ('s13', 18, '译文短行', '只是说， / 如果20世纪……'),
    ('s02', 1, '译文短行', 'Stability AI、 / DeviantArt'), ('s05', 10, '译文短行', '总额 / 为2500亿美元'),
]
LATER = [  # 审阅之后补的修正：篇目, 句号, (现在的源码片段, 撤掉后), 必须报出的检查
    ('s02', 5, ("        if c == '‘' and i and s[i - 1] not in ZOPEN and not any(a < i < b for a, b in merged):\n            out[i] = '<wbr>' + out[i]\n", ''),
     '译文短行'),
]
驳回 = {  # 审阅意见不是真问题（不改，理由）
    's01 screen28 South / Sudan.（英文地名跨行、末行一个词）': '英文在词间换行是正常排版，专名的几个词之间同样可以断；末行一个词在英文里常见，不是错误（同理 s03 screen24 英文 Kate / Winslet；该屏中文“凯特·温斯莱特”在第 1 行完整，没有拆开）',
    's06 screen24 译文末行“侵害，”': '末行两个字，符合“最后一行至少两个字”的规则（孤字检查只管一个字）',
    's07 screen21、s44 screen22 译文一行以“——”开头': 'GB/T 15834 只禁止点号、右半标号出现在行首；破折号整体不拆开（x-dash）即可，行首可以是破折号。s07 第 2 行空出约 5.5 字是登记人名“埃文·塞林格”整名不断行的结果（规则如此）；译文离页脚约 30 像素，在内容区内',
    's03 screen24 译文离页脚近': '在内容区以内，“留白”“文字重叠”检查都通过',
    's03 screen26 do…feel 释义“确实感到（do / 加动词原形表示强调）”': '括注本身比一行还长，只能在括注里断开；断在中英交界是规定的断点（括注断开规则）',
    's49 screen25 for public consumption 释义“供公众理解 / （或阅读）的”': '这个分句（12 字）一行放不下，只能断开；断在“词 | 括注”交界是规定的退路（note_segment_html），别处断开会留单字',
    's46 screen24、s49 screen08 词条 tens of thousands of / science communication 折成两行': '词条在这一屏的词汇栏字号下一行放不下，折行后释义另起一行（词条折行检查）；为了不折行而缩小整栏字号得不偿失',
}


def build(path, css=None, own_jieba=False, edit=None):
    src = path.read_text('utf-8')
    if css is not None:
        old = '(HERE / "样式" / TH.THEMES[STYLE]["file"]).read_text("utf-8")'
        assert src.count(old) == 1
        src = src.replace(old, 'Path(' + json.dumps(str(css)) + ').read_text("utf-8")')
    if own_jieba:                       # 审阅前的引擎没有 分词补充.txt：用自己的 jieba 实例（layoutcheck 的 jieba 加载了补充词，不能共用）
        assert src.count('jieba.cut(') == 2
        src = src.replace('jieba.cut(', '_JB0().cut(') + '\n\ndef _JB0():\n    import jieba\n    global _JB0_T\n    if "_JB0_T" not in globals():\n        _JB0_T = jieba.Tokenizer()\n    return _JB0_T\n'
    if edit:
        assert src.count(edit[0]) == 1, edit[0][:80]
        src = src.replace(*edit)
    m = types.ModuleType('mv_variant')
    m.__file__ = str(TOOLS / 'make_video.py')
    exec(compile(src, str(path), 'exec'), m.__dict__)
    m.set_project('六级')
    return m


def run(pg, f, m, pid, ks):
    """篇目 pid 的第 ks 句（分屏的句子各屏一起排，字号统一）全部检查结果：{句号: [问题…]}。"""
    orig = m.screens
    m.screens = lambda p: [x for x in orig(p) if x[3] in ks]
    m._SPLIT_SIZES.clear()
    out = defaultdict(list)
    for i, label, fit, r in m.layout(pg, P[pid], f):
        out[int(label.split()[1])] += m.screen_checks(pg, label, fit, r)
    m.screens = orig
    return out


def main():
    from playwright.sync_api import sync_playwright
    td = Path(tempfile.mkdtemp())
    css600 = td / '3_600.css'          # 正文 600 的教室黑板样式（9503898 加粗之前，审阅员看到的截图）
    css600.write_text(subprocess.run(['git', '-C', str(R), 'show', '9503898^:专八/tools/样式/3_教室黑板.css'],
                                     capture_output=True, text=True, check=True).stdout, 'utf-8')
    old = build(TOOLS / 'make_video_审阅前.py', css=css600, own_jieba=True)
    cur = build(TOOLS / 'make_video.py')
    byp = defaultdict(set)
    for pid, k, *_ in CASES:
        byp[pid].add(k)
    fails = []
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = br.new_page(viewport={'width': cur.W, 'height': cur.H}, device_scale_factor=2)
        f = td / 'x.html'
        for pid in sorted(byp):
            a, b = run(pg, f, old, pid, byp[pid]), run(pg, f, cur, pid, byp[pid])
            for p, k, chk, what in CASES:
                if p != pid:
                    continue
                hit = [x for x in a[k] if f'：{chk}：' in x]
                ok = bool(hit)
                print(f'{"OK " if ok else "BAD"} {pid} 第 {k} 句 {chk}（{what}）：审阅前 {len(hit)} 处', flush=True)
                for x in hit[:1]:
                    print('       ', x[:180])
                ok or fails.append(f'{pid} 第 {k} 句 {chk}')
            n = sum(len(v) for v in b.values())
            print(f'{"OK " if not n else "BAD"} {pid} 现在的引擎：{n} 处', flush=True)
            for v in b.values():
                for x in v[:3]:
                    print('       现在：', x[:180])
            n and fails.append(f'{pid} 现在的引擎 {n} 处')
        for pid, k, edit, chk in LATER:
            a = run(pg, f, build(TOOLS / 'make_video.py', edit=edit), pid, {k})[k]
            b = run(pg, f, cur, pid, {k})[k]
            hit = [x for x in a if f'：{chk}：' in x]
            ok = bool(hit) and not b
            print(f'{"OK " if ok else "BAD"} 撤掉修正 {pid} 第 {k} 句 {chk}：撤掉 {len(hit)} 处，现在 {len(b)} 处', flush=True)
            for x in hit[:1]:
                print('       ', x[:180])
            ok or fails.append(f'撤掉修正 {pid} 第 {k} 句 {chk}')
        br.close()
    print(f'驳回的审阅意见 {len(驳回)} 条（理由见本文件）')
    print('全部双向通过' if not fails else f'没通过：{fails}')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
