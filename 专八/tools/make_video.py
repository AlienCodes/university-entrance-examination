"""生成专八阅读逐句精读视频——大字版（用户 2026-10-16：专八的字要放大，“跟中考差不多大”）。
由中考 make_video.py（最新、含踩坑 33—41 全部排版修正）复制，只改专八的路径、标题文字、文件名和样式；
旧版（2026-10-10 起用来生成已发布的 t01—t10）原样保存在 make_video_旧版.py，可随时回退。

    /opt/ttsenv/bin/python 专八/tools/make_video.py t03 [--scale 2] [--style C|1–6]
    样片（7 种画面）一律用 专八/tools/样片.py（先截图、程序全查、审阅登记，再生成视频）。

画面（--style，默认 C）：C = 专八「书卷水墨」（样式.css + fonts/，英文 EB Garamond、译文霞鹜文楷、释义思源宋体）；
1–6 = 共用背景样式库 tools/video/themes/ 的 6 种背景（晴空校园、手账笔记本、教室黑板、活页单词卡、紫黄撞色、柔彩插画），
专八自己的调整在 样式/<同名>.css。版面尺寸与旧版相同。
字号（用户 2026-10-16：专八的字要放大到“跟中考差不多大”）：每种画面的起始字号与下限在 字号.json（字号标定.py 实测生成）：
按实际用的字体量 x 高度（英文、词条）和中文字面大小，使每类文字在视觉上不小于中考的典型屏（英文 Nunito 64px、译文思源黑体 43.5px、
词汇栏 40px），也不小于这种画面原来的设计大小；放不下自动缩小，低于下限就必须在 分屏.json 里拆屏（用户要求：不硬挤），
换屏时刻落在第二屏第一个词之前的词间空隙；分屏的句子各屏统一用其中最小的字号（layout）。
时间轴、编码和成品核查与中考完全相同（片头静音 1.5 秒、句间 0.8 秒、读完后停留 0.5 秒再切换、结尾静音 ≥ 2 秒、
恒定 30 帧逐屏编码后无损拼接），生成后运行高考 verify_videos.check 全部核查，任何一项不通过就删除成品。
排版机械检查（layoutcheck）与“先审截图后生成视频”的登记（screens_fp）和中考共用 中考/tools/画面核查/，加 --project 专八。
输入：专八/data/vocab.json（复核定稿）、专八/audio/timings.json（cet4_male）。输出：专八/最终视频/。

项目（--project，默认 专八；用户 2026-10-16：六级 60 篇全部改成教室黑板大字版）：本程序同时是六级的引擎（一个引擎、两个项目，不再复制一份）。
    /opt/ttsenv/bin/python 六级/tools/make_video.py s01        # 六级（六级/tools/make_video.py 只是入口，等于本程序 --project 六级；默认画面 3 教室黑板）
两个项目只有这些不同（PROJECTS）：数据、音频、定稿登记、输出在 <项目>/；分屏表、人名表、截图审阅登记在 <项目>/tools/；标题文字、文件名规则、默认画面。
样式、字体、字号表（字号.json）两个项目共用本目录同一份：六级的教室黑板与专八的教室黑板完全一样（同样的 Inter / 思源黑体常规体、同样的字号）。
六级生成视频一律先审截图：六级/tools/大字版.py --stills → 审阅 → --approve 登记（指纹 + 每张截图的哈希）→ 本程序核对登记，并逐屏与审过的截图比对，
不一致就不编码；成品文件名与旧版六级相同（2021年12月 第1套 Passage One 题目.mp4），核查结果写 六级/样片/成品核查/。
旧版六级引擎原样保存在 六级/tools/make_video_旧版.py（配 六级/tools/分屏_旧版.json），可随时回退。
"""
import argparse
import html
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent
ROOT = C4.parent
sys.path.insert(1, str(ROOT / '四级' / 'tools'))      # debuzz.py（电磁音检查）与四级共用
QA = ROOT / '中考' / 'tools' / '画面核查'          # 排版机械检查、截图审阅登记与中考共用（--project 专八）
VOICE = 'cet4_male'               # 四六级男声（与旧版专八相同；CLAUDE.md 铁律 8）
W, H = 1920, 1080
sys.path.insert(1, str(ROOT / 'tools' / 'video' / 'themes'))
import themes as TH  # noqa: E402  共用背景样式库 1–6（基础样式、字体、字形 / 出界 / 封面检查），与西班牙语共用
LOOKS = {'C': '书卷水墨', **{k: v['name'] for k, v in TH.THEMES.items()}}      # 画面：C = 专八自己的样式，1–6 = 共用背景
STYLE = 'C'
# 字号（1080p 基准，4K 下翻倍）：每种画面的起始字号、下限、译文与词条相对字号都在 字号.json（字号标定.py 按实际字体实测生成，见文件开头说明）。
# 旧版（已发布的 t01—t10）：起点 64/30，下限 48/22；中考：起点 64/40，40 篇 817 屏英文全部 64px、词汇栏中位数 40px、95% 的屏 ≥ 34px。
SIZES = json.loads((HERE / '字号.json').read_text('utf-8'))['looks']
FS0 = VS0 = MIN_FS = MIN_VS = None          # set_style() 按 字号.json 设置
# 项目（--project）：同一个引擎生成专八和六级，只有下面这些不同（见文件开头说明）。
# look = 默认画面；stills = 生成视频前必须核对的审阅截图目录（{pid} 换成篇目；专八没有，用 screens_fp / 样片.py --stills）；
# reg = 截图审阅登记（<项目>/tools/画面核查/ 下）；name_re = 成品文件名规则（与各项目旧版相同）；tmp = 临时目录前缀
PROJECTS = {
    '专八': {'tag': 'TEM-8 · READING · SECTION A', 'top': 'TEM-8 READING', 'exam': '英语专业八级', 'look': '1', 'stills': '大字版/截图/{pid}', 'work': '大字版',
             'reg': '截图审阅通过.json', 'sample_reg': '样片审阅通过.json', 'name_re': r'20\d\d年 Passage (One|Two|Three) \S.*\.mp4', 'tmp': 'tem8video_',
             # 变体（环境变量 DZB_VARIANT 选，入口 专八/tools/大字版_水墨.py）：用户 2026-10-23——专八大字版改用原来的「书卷水墨」古风主题，
             # 沿用校园版的新字体模式（英文全部加粗）；截图、成品、分屏方案各用各的目录和文件，晴空校园版的进度不动（登记键 <篇目>@C 与 @1 也分开）
             'variants': {'水墨': {'look': 'C', 'stills': '大字版水墨/截图/{pid}', 'work': '大字版水墨', 'videos': '最终视频_水墨',
                                   'split': '分屏_水墨.json', 'css': '样式/C_水墨大字.css', 'font_css': 'fonts/eb-garamond-bold.css',
                                   'zh_scale': 1.1}}},   # 用户 2026-10-23：译文稍微大点（字号标定.py 按它放大 C@水墨 的 zh_k）
    '六级': {'tag': 'CET-6 · READING · SECTION C', 'top': 'CET-6 READING', 'exam': '大学英语六级', 'look': '3', 'stills': '样片/截图/{pid}', 'work': '样片',
             'reg': '截图审阅通过.json', 'name_re': r'20\d\d年(6|12)月 第[123]套 Passage (One|Two) \S.*\.mp4', 'tmp': 'cet6video_'},
    # 考研（用户 2026-10-20：与专八晴空校园版完全相同的主题、字体、颜色）：paper = “2026年考研英语一”，passage = “Text 1”
    '考研': {'tag': 'KAOYAN · READING · PART A', 'top': 'KAOYAN READING', 'exam': '', 'look': '1', 'stills': '大字版/截图/{pid}', 'work': '大字版',
             'reg': '截图审阅通过.json', 'name_re': r'20\d\d年考研英语[一二] (?:Text [1-4]|Part B) \S.*\.mp4', 'tmp': 'kyvideo_',
             'badge': r'考研\A精读'},      # 封面右上角圆形贴纸（样式/1_晴空校园.css 写的是专八的「专八 / 精读」，考研 k02 截图试跑时发现，按项目覆盖）
    # 考研作文（用户 2026-10-22：范文与阅读视频一样逐句翻译、标生词，换成手账笔记本主题；开头展示原题，截图必须高清）：
    # 篇目 w01—w24，paper “2026年考研英语一”，passage “写作 Part B”；片头之后是原题屏（prompt_slide，数据里有 prompt_img 才有），
    # 原题屏静音停留到第一句开口（数据里的 lead，考研作文/tools/extract.py 定，音频按它留静音）
    '考研作文': {'tag': 'KAOYAN · WRITING · PART A', 'top': 'KAOYAN WRITING', 'exam': '', 'look': '2', 'stills': '大字版/截图/{pid}', 'work': '大字版',
             'reg': '截图审阅通过.json', 'name_re': r'20\d\d年考研英语[一二] 写作 Part [AB] \S.*\.mp4', 'tmp': 'kywvideo_',
             'badge': r'考研\A作文', 'videos': '最终视频'},
    # 六级作文（用户 2026-10-26：主题用六级教室黑板，规格与六级阅读视频一样；写作专有的原题屏、lead 与考研作文相同）：
    # 篇目 c01—c31，paper “2026年6月大学英语六级 第1套 写作”，passage “Part I”
    '六级作文': {'tag': 'CET-6 · WRITING · PART I', 'top': 'CET-6 WRITING', 'exam': '', 'look': '3', 'stills': '大字版/截图/{pid}', 'work': '大字版',
             'reg': '截图审阅通过.json', 'name_re': r'20\d\d年(6|12)月大学英语六级 第[123]套 写作 Part I \S.*\.mp4', 'tmp': 'cet6wvideo_',
             'videos': '最终视频'},
    # 四级作文（用户 2026-10-26：“视频当然还是用四级之前那个视频自带的主题”）：四级阅读视频（Release 007，四级/tools/make_video.py 设计 C）的
    # 「杂志编号注释」= 本引擎的基础样式 CSS 本身（米白底、墨绿竖条、EB Garamond + 思源宋体、圆形编号）；画面 C 但不叠专八的 样式.css（书卷水墨）——plain。
    # 篇目 c01—c32，paper “2026年6月大学英语四级 第1套 写作”，passage “Part I”
    '四级作文': {'tag': 'CET-4 · WRITING · PART I', 'top': 'CET-4 WRITING', 'exam': '', 'look': 'C', 'plain': True, 'size': 'C@杂志',
             'stills': '大字版/截图/{pid}', 'work': '大字版', 'reg': '截图审阅通过.json',
             'name_re': r'20\d\d年(6|12)月大学英语四级 第[123]套 写作 Part I \S.*\.mp4', 'tmp': 'cet4wvideo_', 'videos': '最终视频'},
    # 专八听力原文精读（用户 2026-10-25）：2025 专八听力录音原文（讲座、采访、说明、念题）逐句精读，书卷水墨大字（与专八水墨同一套画面、字号）；
    # 声音用听力原音（不是 TTS），句子起止由 专八/听力/原文/tools/原音音轨.py 对齐求出、长等待压到 2 秒。目录不在仓库顶层：dir。
    # 原音（audio='原音'）不适用 TTS 才有的几项：句间固定 0.8 秒停顿、停顿处数字静音、逐句响度偏差 / 短时波动、电磁音（声码器）、读完固定停留 0.5 秒——
    # 改为：换屏在两句之间（cut_check）、整体响度与峰值（loud_check）；其余成品核查照跑
    '专八听力': {'dir': '专八/听力/原文', 'audio': '原音', 'tag': 'TEM-8 · LISTENING · 2025', 'top': 'TEM-8 LISTENING', 'exam': '', 'look': '1',
             'stills': '大字版/截图/{pid}', 'work': '大字版', 'reg': '截图审阅通过.json',
             'name_re': r'2025年专八听力 Section (A|B Part One|B Part Two) \S.*\.mp4', 'tmp': 'tem8lvideo_',
             'variants': {'水墨': {'look': 'C', 'stills': '大字版水墨/截图/{pid}', 'work': '大字版水墨', 'videos': '最终视频_水墨',
                                   'split': '分屏_水墨.json', 'css': '样式/C_水墨大字.css', 'font_css': 'fonts/eb-garamond-bold.css',
                                   'zh_scale': 1.1}}},
}
PROJ = PJ = T = SPLIT = NAMES = SAMPLE_REG = YP_REG = None      # set_project() 设置


def set_project(name, look=True):
    """切换项目：数据、音频、定稿登记、输出在 <项目>/（C4），分屏表、人名表、截图审阅登记在 <项目>/tools/（T）；look=True 时画面切到该项目的默认画面。"""
    global PROJ, PJ, C4, T, SPLIT, NAMES, SAMPLE_REG, YP_REG
    if name not in PROJECTS:
        raise SystemExit(f'--project 只能是 {"、".join(PROJECTS)}：{name}')
    PROJ, PJ, C4 = name, PROJECTS[name], ROOT / PROJECTS[name].get('dir', name)
    var = os.environ.get('DZB_VARIANT')
    if var:                                       # 项目变体（如 专八 水墨）：覆盖画面、目录、分屏方案和追加样式
        if var not in PJ.get('variants', {}):
            raise SystemExit(f'{name} 没有变体 {var}（可选：{"、".join(PJ.get("variants", {})) or "无"}）')
        PJ = {**PJ, **PJ['variants'][var], 'variant': var}
    T = C4 / 'tools'
    SPLIT = {k: v for k, v in json.loads((T / PJ.get('split', '分屏.json')).read_text('utf-8')).items() if not k.startswith('_')}
    NAMES = json.loads((T / '人名.json').read_text('utf-8'))['names']        # 中文音译人名（整名不断行，见 name_spans）
    SAMPLE_REG = T / '画面核查' / PJ['reg']      # 截图审阅登记（专八：样片.py --approve；六级：大字版.py --approve 写入）
    YP_REG = T / '画面核查' / PJ.get('sample_reg', PJ['reg'])     # 样片.py（同一篇、多种画面）的登记；专八的成套生产（大字版.py）用 SAMPLE_REG，两份分开
    if look:
        set_style(PJ['look'])


set_project(os.environ.get('DZB_PROJECT') or '专八', look=False)      # 默认项目专八（画面在下面 set_style('C')）；DZB_PROJECT 指定别的项目（分屏、检查工具 import 本模块时用，如 专八听力）

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden;background:#fbf9f4;color:#1c2421;font-family:'Noto Serif SC',serif}
.band{position:absolute;left:0;top:0;bottom:0;width:22px;background:#1f5c4a}
.top{position:absolute;left:110px;right:90px;top:52px;display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid #1c2421;padding-bottom:16px}
.top b{font-family:'Inter';font-weight:800;font-size:24px;letter-spacing:.14em}
.top span{color:#6b746f;font-size:24px}
.main{position:absolute;left:110px;top:140px;bottom:96px;width:1070px;display:flex;align-items:center}
#box{width:100%}
.en{font-family:'EB Garamond','Noto Serif SC',serif;font-size:var(--fs);line-height:1.5}
.w{font-weight:600;color:#1f5c4a}.ph{font-weight:600;color:#a14a2a}
sup{font-family:'Inter';font-size:calc(var(--fs)*.36);font-weight:700;color:#fff;background:#1f5c4a;border-radius:1em;padding:.05em .45em;margin-left:.12em;vertical-align:.95em;line-height:1}
.ph sup{background:#a14a2a}
.zh{font-size:calc(var(--fs)*.68);line-height:1.65;color:#3c4642;margin-top:calc(var(--fs)*.5);padding-left:24px;border-left:4px solid #d7d2c3}
.side{position:absolute;right:90px;top:140px;bottom:96px;width:600px;background:#eef2ec;border-radius:6px;padding:30px 36px;display:flex;flex-direction:column;justify-content:center}
#list{display:flex;flex-direction:column;gap:calc(var(--vs)*.42)}
.side h3{font-family:'Inter';font-size:20px;letter-spacing:.2em;color:#1f5c4a;margin-bottom:14px}
.v{display:grid;grid-template-columns:calc(var(--vs)*1.3) 1fr;column-gap:12px;font-size:var(--vs);line-height:1.32}
.v em{font-style:normal;font-family:'Inter';font-weight:700;font-size:calc(var(--vs)*.7);color:#fff;background:#1f5c4a;border-radius:50%;width:calc(var(--vs)*1.2);height:calc(var(--vs)*1.2);display:flex;align-items:center;justify-content:center;margin-top:.1em}
.v.ph em{background:#a14a2a}
.v b{font-family:'EB Garamond';font-weight:600;font-size:calc(var(--vs)*1.3)}
.v.ph b{color:#a14a2a}
.v i{font-style:italic;font-family:'EB Garamond';color:#6b746f;margin-right:10px}
.v b{margin-right:10px}
.v span{color:#3c4642}
.zh,.v .g{text-spacing-trim:space-all}
x-i{position:relative;margin:0 .03em}x-i::before,x-i::after{content:'';position:absolute;left:50%;width:.2em;margin-left:-.1em;height:.08em;background:currentColor;border-radius:.03em}
x-i::before{top:.295em}x-i::after{top:.945em}
.en .w x-i::before,.en .ph x-i::before,.en .w x-i::after,.en .ph x-i::after,.v b x-i::before,.v b x-i::after{width:.25em;margin-left:-.125em;height:.135em}
.en .w x-i::before,.en .ph x-i::before,.v b x-i::before{top:.29em}.en .w x-i::after,.en .ph x-i::after,.v b x-i::after{top:.89em}
sup.sd{margin-right:calc(var(--fs)*.084)}   /* 编号后紧跟破折号时留空：专八编号是英文字号的 0.36 倍（中考 0.42），按英文字号定，等于中考的 0.2 × 0.42（t08 “¹¹—”原来只隔 3.7 像素） */
.pr{margin-right:-.5em}.pl{margin-left:-.5em}.pq{margin-left:-.3em}
x-n>.pr:last-child{display:inline-block;width:.5em;margin-right:0;white-space:nowrap}   /* 释义分句末尾的标点（“（内容）广泛的；”）：负外边距让行内块的自身宽度少算半个字，块内放不下、自己折成两行，FIT 只好改成行内拆开（考研 k09 第 10 句 括注分离）；改成半字宽的行内块，宽度算法与排版一致 */
.en .ph{white-space:nowrap}   /* 高亮短语整体不断行（t03 第二轮审阅：rough / treatment、at the / expense of），比一行还长的由 FIT 放开（phr） */
x-n{display:inline-block}     /* 释义里的长括注：放得下一行就整体换到下一行（t03 第二轮审阅：（同 / gunwale）），放不下由 FIT 改成行内、只在指定处断开（notes） */
.cont{color:#9aa39e;font-weight:400}
.en x-ps{font-weight:400;color:var(--ink,#1c2421)}   /* 只是排版前的初值：FIT 一开始把所有格的颜色、粗细、字体设成英文正文实测的样式（六级黑板审阅：--ink 只有样式 1、2 定义，黑板上所有格成了近黑色、几乎看不见） */
x-ap{font-family:'Inter'}     /* 中文里英文词中间的撇号（Hunt’s）：思源黑体的“’”是全角（1 字宽，六级 s57 第 10 句 “Hunt’ s在”），改用英文字体画（zh_html 包 x-ap；画面 C 不包） */
.bot{position:absolute;left:110px;right:90px;bottom:40px;display:flex;justify-content:space-between;align-items:center;font-family:'Inter';font-size:22px;color:#6b746f;letter-spacing:.1em}
.bar{flex:1;height:3px;background:#dcd8cc;margin:0 30px}.bar i{display:block;height:100%;background:#1f5c4a}
.ttl{position:absolute;left:150px;right:150px;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center}
.ttl .tag{font-family:'Inter';font-weight:800;letter-spacing:.3em;font-size:28px;color:#1f5c4a}
.ttl h1{font-size:96px;font-weight:700;margin:30px 0 26px;line-height:1.25}
.ttl .sub{font-size:44px;color:#3c4642}
.ttl .sub i{font-family:'EB Garamond';font-style:italic}
.ttl .meta{margin-top:50px;padding-top:26px;border-top:2px solid #1c2421;font-size:30px;color:#6b746f;display:flex;justify-content:space-between}
.legend{position:absolute;right:120px;bottom:60px;display:flex;gap:30px;font-size:24px;color:#3c4642}
.legend em{display:inline-block;width:22px;height:22px;border-radius:50%;margin-right:8px;vertical-align:-3px}
.legend .lw{background:#1f5c4a}.legend .lp{background:#a14a2a}
"""
# 专八专用样式「书卷水墨」（用户 2026-10-10 选定）：样式.css 追加在上面的通用样式之后覆盖它，只改颜色、字体、装饰和封面，不改版面尺寸。
THEME = HERE / '样式.css'
THEME_FONTS = HERE / 'fonts' / 'fonts.css'
ZH_BOLD = HERE / 'fonts' / 'zh-bold.css'          # 中文粗体黑体（思源黑体 Bold 起名 'ZH Bold'，代替用户要的微软雅黑；哪种画面用它由 样式/*.css 决定）
INTER = HERE / 'fonts' / 'inter' / 'inter.css'      # 英文 Inter（用户要 Aptos，官方下载被网络拦住，用非常相似的 Inter 代替；哪种画面用它由 样式/*.css 决定）
ZH_REGULAR = HERE / 'fonts' / 'zh-regular.css'    # 中文常规体黑体（'ZH Regular'，代替微软雅黑；教室黑板用：英文加粗、中文不加粗）
CRF = {'*': 18}                                      # 整片压缩的 crf（按画面可另给；实测见交接文档）
POS = re.compile(r'^((?:n|v|adj|adv|prep|conj|pron|num|det|int|abbr|pref|suf)\.)\s*(.*)$')


def esc(s):
    return html.escape(s, quote=True)


def cap_i(h):
    """英文大写 I 加上下衬线（z06 画面核查：圆体 Nunito 的大写 I 与小写 l 一模一样，人名 Ieoh 读成 leoh；字体没有带衬线的替换字形，
    用 x-i 的 ::before/::after 画两道短横，位置按 Nunito 实测：常规体竖笔宽 0.085 字、顶 0.30 字、底 1.02 字，粗体竖笔宽 0.155 字、顶 0.295、底 1.015；
    短横比竖笔每边宽约 0.05 字、底横盖住竖笔圆头，I 左右各留 0.03 字，不碰相邻字母和徽章。
    用自定义元素 x-i 而不用 span：词汇栏的 .v span 样式（中文字体、灰色）会套到 span 上，第 1 批第三次画面核查发现词条里的 I 变成灰色细体、像“‡”）。
    h 是已转义的 HTML，标签里的字不动。
    专八：画面 C 不加（英文和词条用 EB Garamond，大写 I 本身带衬线，与小写 l 分得清，再画短横就成了双衬线）；
    共用背景 1–6 的英文是圆体 Nunito（1、2、5、6）或 Baloo 2（3、4，I 只比 l 矮 5%，同样分不清），照中考加（t03 截图检查：layoutcheck“大写I”）；
    Baloo 2 的短横位置在 样式/3_教室黑板.css、4_活页单词卡.css 里按 Baloo 2 实测另给。"""
    if STYLE == 'C':
        return h
    return wh(re.sub(r'(<[^>]*>)|I', lambda m: m.group(1) or '<x-i>I</x-i>', h))


def wh(h):
    """大写 W 后紧跟 h（When、Who、Why、Whoa）：圆体 Nunito 给 W+h 这对字母设了正的字距（+0.05 字），加上 h 左侧留白，
    W 与 h 之间的空隙约是普通字母间距的两倍，像“W hen”（专八校园版第 2 批截图盲审：t04、t06、t07）。W 包在 x-w 里，
    Nunito 的几种画面在样式里给 x-w 收紧字距（-0.07 字，放大对比与 Tho、Wo 的间距一致）；其他画面没有这条样式，不受影响。
    用自定义元素而不用 span（踩坑 34：.v span 有样式）。h 是已转义的 HTML，标签里的字不动。"""
    return re.sub(r'(<[^>]*>)|W(?=[hi])', lambda m: m.group(1) or '<x-w>W</x-w>', h)      # 考研截图盲审：With、Without 的 W+i 同样偏大（“W ith”）


def nobr(h):
    """带连字符的英文词整体不断行（画面核查发现词条 southward-/moving、高亮词 wind-/driven 被拆到两行）。h 是已转义的 HTML，标签里的字不动。"""
    return re.sub(r'(<[^>]*>)|(?<![\w’])([A-Za-z0-9’]+(?:-[A-Za-z0-9’]+)+)', lambda m: m.group(1) or f'<nobr>{m.group(2)}</nobr>', h)


def dash(h):
    """破折号与前一个词不断开（第 2 批截图核查：z19 “comes in¹ / —giving”一行以破折号开头）。h 是已转义的 HTML，标签里的字不动。
    专八校园版（t10 第 20、22 句，杰克·伦敦原文“king,—king”“large,—he”“pounds,—for”）：词与破折号之间还隔着逗号等标点时同样不断开；
    前面的词是高亮词（标签隔开）时，至少把“标点 + 破折号”绑在一起（逗号前本来就不能断行）。"""
    return re.sub(r'(<[^>]*>)|(?<![\w’-])([A-Za-z0-9’]+[,;:.!?’”)]*[—–])|([,;:.!?’”)]+[—–])',
                  lambda m: m.group(1) or f'<nobr>{m.group(2) or m.group(3)}</nobr>', h)


UNITS = (r'kg|g|mg|km|m|cm|mm|ml|mph|°C|°F|percent|kilo(?:gram|metre|meter)s?|(?:centi|milli)?(?:metre|meter)s?|grams?|tonnes?|tons?'
         r'|miles?|feet|foot|inch(?:es)?|degrees?|hours?|minutes?|seconds?|days?|weeks?|months?|years?'
         r'|(?:m|b|tr)illions?|thousands?|hundreds?')      # 数目单位（六级黑板审阅：s01 “$13 / billion”、s05 “$250 / billion”金额被拆到两行）


def esc_en(s):
    """英文里试卷的中文注释（如 architecture (建筑).）整体不断行：中文字之间默认可以断行，画面核查发现“(建 / 筑).”被拆到两行。
    数字与后面的单位之间用不换行空格（z25 截图审阅：“only about 6 / kg”“1,800 / kg”数字与单位被拆到两行）。"""
    s = re.sub(rf'(\d)\s+(?=(?:{UNITS})(?![A-Za-z]))', '\\1\u00a0', s)
    # 称谓与后面的人名不断开（专八校园版第 2 批盲审：t06 “Mr.” 落在行末、“Albert Griggs” 在下一行）
    s = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof|St)\. (?=[A-Z]|$)', '\\1.\u00a0', s)      # 段尾的称谓也算：后面的人名是高亮词条时在另一段（t06 Mr. Albert Griggs）
    # 试卷的中文注释与它注释的前一个词不断开（六级黑板审阅：s45 “toddlers / (学步儿童)”注释单独落到下一行行首）
    s = re.sub(r'\s+(?=\([^()]*[\u4e00-\u9fff][^()]*\))', '\u00a0', s)
    # 专名（连续 2—4 个首字母大写的词：Brett Kavanaugh、West Virginia、Apple TV.）和“18 or 21”整体不断行（考研截图盲审 17 处；规则在 zh_bind.en_spans，layoutcheck 同一份）
    for a, b in ZB().en_spans(s):
        s = s[:a] + s[a:b].replace(' ', '\u00a0') + s[b:]
    h = dash(nobr(re.sub(r'\([^()]*[\u4e00-\u9fff][^()]*\)[.,;:!?”’]*', lambda m: f'<span style="white-space:nowrap">{m.group(0)}</span>', esc(s))))
    # 悬空连字符与后面的 or/and 整体不断行（六级 s20 “right- / or left-brained”，行末是连字符；不换行空格不管用：浏览器允许在连字符后、不换行空格前断行）
    return re.sub(r'(?<![\w’-])([A-Za-z]+-) ((?:or|and|nor|to)\b)', r'<nobr>\1 \2</nobr>', h)


# 译文里整体不断行的术语：短引号术语、书名（六级黑板审阅），短括注、引号术语连同后面紧跟的短括注（专八校园版第 2 批盲审：t04 “（指 / 天鹅）”“papa” / （爸爸））。
# layoutcheck.TERM 与这里相同（“术语断开”）
ZH_TERM = r"“[^“”，。；：！？、]{1,12}”（(?:[^（）]{1,6}|[A-Za-z0-9 ’'.,-]{1,20})）|“[^“”，。；：！？、]{1,6}”|《[^《》]{1,8}》|（[^（），。；：]{1,6}）"      # 考研：“该表演了”（Time to Act）英文括注最多 20 个字符
ZH_NUM = set('一二两三四五六七八九十百千万几半')       # 单独成词时与后面的量词、名词不断开（zh_html；layoutcheck 的“数词断开”）
GLOSS_CHUNK = 9      # 词汇栏一行最多约 9.6 个字（字号最大 40px 时）：9 个字以内的释义块整体不断行（原定 10，z20 “下面就是……的方法；”溢出 16 像素）
ZCLOSE, ZOPEN = set('，。、：；！？）”’】」》］〕'), set('（“‘【「《［〔')   # 思源黑体实测：前一组字形在左半（右半空白），后一组在右半（左半空白）；［］〔〕 考研 k09 实测同（ ）
ZPROP = set('“”‘’')      # 专八译文字体霞鹜文楷的弯引号是半宽字形（宽 0.44/0.33 字），不按全角挤压


def words(s, out):
    """超过 GLOSS_CHUNK 个字的释义块（如“（代替前面提到的复数名词）”）一行放不下，只允许在词与词之间断行：用 jieba 分词，每个多字词整体不断行
    （依赖：/opt/ttsenv/bin/pip install jieba）。"""
    toks, names, pos = [], name_spans(s), 0
    zb = ZB().zh_spans(s, jb())                      # 考研截图盲审：释义“后置 / 定语”“20世纪90 / 年代中期”
    cuts = sorted({x for ab in names for x in ab})
    raw, q = [], 0                                   # 专八校园版 t04 第 8 句：jieba 把“凯洛格和温思罗普”切成“格和温”，跨过两个名字的边界，
    for w in jb().cut(s):                            # 两个名字连同“和”并成一整块不断行、伸出词汇栏 16 像素——先在登记人名的边界处把分词切开
        e = q + len(w)
        for c in [x for x in cuts if q < x < e]:
            raw.append(s[q:c]); q = c
        raw.append(s[q:e]); q = e
    for w in raw:                           # 专八：人名间隔号与前后的词合成一块（t04 “温思罗普· / 凯洛格”在间隔号处断行）
        inside = any(a < pos < b for a, b in names) or any(a < pos < b for a, b in zb)  # 登记的整名（人名.json）、复合词（zh_bind）不在中间断开：并到前一块
        if toks and (w.startswith('·') or toks[-1].endswith('·') or inside):
            toks[-1] += w
        else:
            toks.append(w)
        pos += len(w)
    ell = lambda w: bool(w) and set(w) <= set('…')
    k = 0                                            # jieba 把“……”切成两个“…”：先并成一个
    while k < len(toks) - 1:
        if ell(toks[k]) and ell(toks[k + 1]):
            toks[k:k + 2] = [toks[k] + toks[k + 1]]
        else:
            k += 1
    k = 0                                            # 省略号与后面的词不断开（专八校园版第 2 批盲审：t07 释义“没有走到…… / 的地步”，“的地步”落到下一行行首）
    while k < len(toks) - 1:
        if ell(toks[k]) and toks[k + 1][:1] in ('的', '地', '得', '之'):       # 只管省略号后面紧跟虚词的（“……的”不能落到行首）；“……还是”照旧可断（t02 “无论是……还是……；……或……”连成一块会放不下）
            toks[k:k + 2] = [toks[k] + toks[k + 1]]
            if len(toks[k].strip('…')) == 1 and k + 1 < len(toks) and '一' <= toks[k + 1][0] <= '鿿':       # 后面只跟一个字（“……的”）：再连上后面的词（“……的地步”）
                toks[k:k + 2] = [toks[k] + toks[k + 1]]
            k += 1
        else:
            k += 1
    toks = head_tokens(toks)
    t = len(toks)                                    # 末尾至少两个字（不算标点）整体不断行，免得最后一行只剩一个字（z35 截图审阅）
    while t > 0 and sum(c.isalnum() for c in ''.join(toks[t:])) < 2:
        t -= 1
    res, i = [], 0
    for w in toks[:t]:
        piece = ''.join(out[i:i + len(w)])
        res.append(f'<nobr>{piece}</nobr>' if len(w) > 1 else piece)
        i += len(w)
    return ''.join(res) + (f'<nobr>{"".join(out[i:])}</nobr>' if i < len(s) else '')


def wordch(c):
    """释义里算“字”的字符：汉字、字母数字、省略号（括注紧挨着它们时与括注是一体的，见 note_segment_html）。"""
    return '\u4e00' <= c <= '\u9fff' or c.isalnum() or c == '…'


def head_tokens(toks):
    """长词串（超过 GLOSS_CHUNK 个字，words 在词间断开）开头至少两个字（不算标点）合成一块：不在行末单独留一个字
    （六级黑板审阅：“内化；使 / 成为自身观念的一部分”“in the absence of 在 / 没有……的情况下”“……并 / 不像……那么简单”）。"""
    out = list(toks)
    while len(out) > 1 and sum(c.isalnum() for c in out[0]) < 2:
        out[0:2] = [out[0] + out[1]]
    return out


def gloss_chunks(s):
    """释义切块：右半空白的标点之后、左半空白的标点之前切开。只有一个字（不算标点）的块（第一块除外）不能单独成块（z35 截图审阅：“注意（做）；用心（做）”的
    “（做）”、“节日；（文化）节”的“节”单独落到一行，程序检查在 40 篇里查出 15 处）：并到前一块（“用心（做）”，意思上它属于前面）；并完超过 GLOSS_CHUNK 个字
    （就得在前一块中间断行，如“（表示过去的 / 习惯）会；”）而后面还有块时，改为和后一块绑在一起（“（表示过去的习惯） / 会；总是会”）；
    第一块是单字时，并完不超过 GLOSS_CHUNK 个字就和后一块绑在一起（“教 / （某人）做……”→“教（某人）做……”）。layoutcheck.ok_break 用同样的切法。"""
    cuts = [0] + [i for i in range(1, len(s)) if (s[i - 1] in ZCLOSE and s[i] not in ZCLOSE) or (s[i] in ZOPEN and s[i - 1] not in ZOPEN)] + [len(s)]
    ch = [[a, b] for a, b in zip(cuts, cuts[1:]) if b > a]
    solo = lambda k: sum(c.isalnum() for c in s[ch[k][0]:ch[k][1]]) <= 1
    while True:
        k = next((k for k in range(len(ch)) if solo(k) and (k or len(ch) > 1 and ch[1][1] - ch[0][0] <= GLOSS_CHUNK)), None)
        if k is None:
            return ch
        if k == 0 or ch[k][1] - ch[k - 1][0] > GLOSS_CHUNK and k + 1 < len(ch) and ch[k + 1][1] - ch[k][0] <= GLOSS_CHUNK:
            ch[k:k + 2] = [[ch[k][0], ch[k + 1][1]]]
        else:
            ch[k - 1:k + 1] = [[ch[k - 1][0], ch[k][1]]]


def jb():
    """jieba，先加载 分词补充.txt（与 layoutcheck 共用：中考/tools/画面核查/分词补充.txt；jieba 词典里没有、会切错的词，如“占比”）。"""
    import logging
    import jieba
    if not getattr(jieba, '_zb_dict', False):
        jieba.setLogLevel(logging.WARNING)
        for w in (QA / '分词补充.txt').read_text('utf-8').splitlines():
            if w.strip() and not w.startswith('#'):
                jieba.add_word(w.strip())
        jieba._zb_dict = True
    return jieba


def ZB():
    """中考/tools/画面核查/zh_bind.py：引擎与 layoutcheck 共用的“不许拆开”的片段（中文复合词、英文专名）。"""
    if not hasattr(ZB, 'm'):
        import importlib.util
        sp = importlib.util.spec_from_file_location('zh_bind', QA / 'zh_bind.py')
        ZB.m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(ZB.m)
    return ZB.m


def jieba_words(s):
    """jieba 分词的位置 [(起, 止)]（覆盖整个 s）。译文按词绑定、layoutcheck 的“译文断词”都对整段文字分词，结果一致。
    在登记人名的边界处切开（专八校园版第 2 批盲审：t04 “两位科学家（卢埃拉·凯洛格和温思罗普·凯洛格）”，jieba 切出“格和温”跨过两个名字，
    整段括注连成一块不断行，上一行空出一半；释义的 words 早已这样切）。"""
    cuts = sorted({x for ab in name_spans(s) for x in ab})
    out, pos = [], 0
    for w in jb().cut(s):
        e = pos + len(w)
        for c in [x for x in cuts if pos < x < e]:
            out.append((pos, c))
            pos = c
        out.append((pos, e))
        pos = e
    return out


def notes(s):
    """释义里最外层的括注（（…）或 (…)，可以套括号）的位置 [(起, 止)]。"""
    out, st = [], []
    for i, c in enumerate(s):
        if c in '（(':
            st.append(i)
        elif c in '）)' and st:
            a = st.pop()
            if not st:
                out.append((a, i + 1))
    return out


def long_notes(s):
    """长括注：超过 GLOSS_CHUNK 个字、或里面还有会切块的标点（括号、逗号等）的括注（t03 第二轮审阅：（同 / gunwale）、（with 复合 / 结构）、
    （so… / (that) 结构，此处省略 / that）、（down the length of 顺着…… / 一路）都是旧切块把括注拆开）。短括注照旧是一个不断行的块。"""
    return [(a, b) for a, b in notes(s) if b - a > GLOSS_CHUNK or any(c in ZCLOSE or c in ZOPEN for c in s[a + 1:b - 1])]


def lead_word(t, i):
    """括注开头紧跟左括号的一个短英文词（不超过 6 个字母）之后的空格不断开：“（that / 从句中动词用原形）”行末只剩“（that”（专八书卷水墨截图盲审 t02 第 67 屏）。
    layoutcheck.note_ok 用同一条规则独立判断。"""
    j = i - 1
    while j > 0 and t[j].isspace():
        j -= 1
    k = j
    while k > 0 and t[k].isascii() and t[k].isalpha():
        k -= 1
    return t[k] in '（(' and k == 0 and 0 < j - k <= 6 and '一' <= t[i] <= '鿿'      # 后面是中文时（“（Member of Parliament 的缩写）”这类长英文另有规则）


def note_breaks(t):
    """长括注 t（含两头括号）里可以换行的位置 i（在 t[i] 之前断开）：中英文交界、括注里的逗号顿号分号冒号之后、两个中文片段之间的空格；
    除此以外不断开：中文片段整体不断行（比 GLOSS_CHUNK 还长的由 words 在词间断开），英文片段（down the length of）整体不断行
    （比一行还长的由 FIT 放开，note_html 标 class="lr"；t03 截图对照：画面 C 第 54 句“（down the / length of / 顺着……一路）”）。
    标点归属：右括号、省略号等跟前一个字，左括号跟后一个字。"""
    # 公式里的“+”算英文（与 layoutcheck 的英文片段一致）：“（形容词 + as 引导让步倒装）”“（too + 形容词 + a + 名词）”原来把“+”并到前面的中文，
    # 在“+ / as”“+ / a +”之间断开（水墨 t16 第 54 句、t21 第 21 句，layoutcheck 括注断开）
    kind = ['S' if c.isspace() else 'H' if '一' <= c <= '鿿' else 'L' if c.isascii() and c.isalnum() or c == '+' else '' for c in t]
    for i in range(len(t)):                          # 标点归属：左括号看后面，其余看前面；找不到就看另一边
        if not kind[i]:
            fwd = t[i] in ZOPEN or t[i] == '('
            for j in (list(range(i + 1, len(t))) + list(range(i - 1, -1, -1))) if fwd else (list(range(i - 1, -1, -1)) + list(range(i + 1, len(t)))):
                if kind[j] in ('H', 'L'):
                    kind[i] = kind[j]
                    break
    out = set()
    for i in range(1, len(t)):
        if kind[i] == 'S':
            continue
        if kind[i - 1] == 'S':                       # 空格之后：两边最近的字一边中文一边英文、或两边都是中文，才可以断开
            p = next((kind[j] for j in range(i - 1, -1, -1) if kind[j] != 'S'), kind[i])
            if (p != kind[i] or p == 'H') and not lead_word(t, i):
                out.add(i)
        elif kind[i] != kind[i - 1] or (t[i - 1] in '，；：、' and t[i] not in ZCLOSE):
            out.add(i)
        elif (t[i] == '《' or t[i - 1] == '》') and 0 < i < len(t) - 1:      # 书名号整体不断行、前后可以断（六级 s29：“（宫城先生是电影《龙威小子》中的空手道师父）”）
            out.add(i)
    m = re.match(r'[（(][A-Za-z]{1,6} +(?=[一-鿿])', t)         # 开头短英文词后面不断（lead_word）：给紧跟的中文片段在词间加断点（两头各至少 2 个字），
    if m:                                            # 整段括注一行放不下时不至于只能任意断开（水墨 t02 “（that 从句中动词用原 / 形）”）
        a = b = m.end()
        while b < len(t) and '一' <= t[b] <= '鿿':
            b += 1
        pos = a
        for w in jb().cut(t[a:b]):
            pos += len(w)
            if a + 2 <= pos <= b - 2:
                out.add(pos)
    return sorted(out)


def note_html(t, out):
    """长括注的 HTML（包在行内块 x-n 里）：只在 note_breaks 的位置可以换行（空格照旧，没有空格的地方加 <wbr>），每段整体不断行；
    比 GLOSS_CHUNK 还长的中文段在词间断开（words）。放得下一行时 x-n 是行内块，整体换到下一行；放不下时 FIT 改成行内，在这些位置断开。"""
    zb = ZB().zh_spans(t, jb())                      # 复合词、数字 + 量词不在中间断开（专八 t10 回归：长括注“1896／年在此发现金”）
    cuts = [0] + [c for c in note_breaks(t) if not any(x < c < y for x, y in zb)] + [len(t)]
    res = []
    for a, b in zip(cuts, cuts[1:]):
        e = b
        while e > a and t[e - 1].isspace():
            e -= 1
        body = ''.join(out[a:e])
        han = sum('一' <= c <= '鿿' for c in t[a:e])
        lr = ' class="lr"' if ' ' in t[a:e] else ''      # 含空格的英文片段：比一行还长时 FIT 放开（notes）
        res.append((words(t[a:e], out[a:e]) if han > GLOSS_CHUNK else f'<nobr{lr}>{body}</nobr>') + ''.join(out[e:b]))
        if b < len(t) and e == b:
            res.append('<wbr>')
    return ''.join(res)


def zh_html(s, gloss=False):
    """中文标点挤压（第 1 批画面核查：“说：  “我们”“看法）  ；”“母亲养育” 。”中间空出半个到一个字，段首“记忆…”比下一行缩进半个字；
    字体的 halt 对冒号、引号不生效，所以关掉浏览器自带的挤压（text-spacing-trim: space-all），由这里统一决定）：
    右半空白的标点后面紧跟标点 → 去掉它的右半空白（.pr）；左半空白的标点在开头或紧跟在左半空白的标点后 → 去掉左半空白（.pl）；
    其余左半空白的标点标 .po，排版后落在行首的由 FIT 去掉左半空白。
    断行（同一次画面核查：释义“可/能”“泳/衣”被拆开，译文最后一行只剩“念。”一个字）：
    gloss=True（词汇栏释义）按标点切块（右半空白的标点之后、左半空白的标点之前），GLOSS_CHUNK（9）个字以内的块整体不断行，更长的块只在词与词之间断行（words）；
    gloss=False（译文）最后两个字连同后面的标点绑在一起，最后一行至少两个字。
    专八（t03 第二轮审阅）：释义里的长括注单独排（long_notes / note_html：放得下一行就整体换行，放不下只在空格、中英交界、逗号等处断开）；
    译文的多字词（jieba）整体不断行（“蹦/跳”“相/同”“霎时/间”）。layoutcheck 的“括注拆开 / 括注断开 / 译文断词”逐屏核对。
    专八：译文用霞鹜文楷，它的弯引号“”‘’是半宽字形（实测宽 0.44/0.33 字，没有半字空白可去），不挤压、不去半字（ZPROP）；
    释义用思源宋体，引号是全角，照常处理。人名间隔号“·”前后不断行（旧版画面核查：理查德·帕克 在 · 处断行）。"""
    # 只有画面 C 的译文是霞鹜文楷（弯引号半宽）；1–6 的译文是思源黑体 / Noto Sans SC，弯引号是全角（各画面实测宽 1.00 字），照常挤压
    # （六级 s01 第 10 句：教室黑板的译文「”。」之间空出 1.00 字，layoutcheck 标点挤压查出）
    # 四级杂志（画面 C、plain）的译文是思源宋体，弯引号全角，与 1–6 一样照常处理
    wenkai = STYLE == 'C' and not (PJ and PJ.get('plain'))
    fc, fo = (ZCLOSE, ZOPEN) if gloss or not wenkai else (ZCLOSE - ZPROP, ZOPEN - ZPROP)
    out = []
    for i, c in enumerate(s):
        nxt, prv = s[i + 1:i + 2], s[i - 1:i]
        if c in '’\'' and not wenkai and re.match(r'[A-Za-z]', prv) and re.match(r'[A-Za-z]', nxt):
            out.append(f'<x-ap>{esc(c)}</x-ap>')        # 英文词中间的撇号（Hunt’s）用英文字体画（六级黑板审阅：思源黑体的“’”是全角）
        elif c in fc and nxt and (nxt in ZCLOSE or nxt in ZOPEN):
            out.append(f'<span class="pr">{esc(c)}</span>')
        elif c in fo and fo is not ZOPEN and prv in '”’':
            # 画面 C 译文：霞鹜文楷的右引号是半宽字形，后面全宽左括号的左半空白显得空出一个字（水墨截图盲审 t04 “mama”（妈妈））：往左挪 0.3 字（.pq）。
            # 不用 .pl 的 −0.5 字：右引号只有 0.44 字宽，左括号会挪到引号起点的左边，layoutcheck 按字的位置分行时误判成另起一行
            out.append(f'<span class="pq">{esc(c)}</span>')
        elif c in fo and (not prv or prv in ZOPEN):
            out.append(f'<span class="pl">{esc(c)}</span>')
        elif c in fo:
            out.append(f'<span class="po">{esc(c)}</span>')
        else:
            out.append(esc(c))
    for m in re.finditer('—+', s):                  # 中文破折号整段包成 x-dash（样式 2、3 画成全角居中粗横；其余画面不加样式，与原来一样）
        out[m.start()] = f'<x-dash>{"".join(out[m.start():m.end()])}</x-dash>'
        for k in range(m.start() + 1, m.end()):
            out[k] = ''
    if gloss:
        # 以省略号、破折号开头的块前面加 <wbr>：浏览器不许在“…”“—”前面断行（UAX 14），“……没有什么不对；……无可厚非”两块粘成一整块，
        # 一行放不下就伸出词汇栏（六级 s04 第 17 句、s05 第 9 句，横向溢出 16 像素）
        chunks = lambda lo, hi: ''.join(('<wbr>' if a and s[lo + a] in '…—' else '') +
                                        (f'<nobr>{"".join(out[lo + a:lo + b])}</nobr>' if b - a <= GLOSS_CHUNK else words(s[lo + a:lo + b], out[lo + a:lo + b]))
                                        for a, b in gloss_chunks(s[lo:hi]))
        def stretch(lo, hi):                         # 没有“括注 + 紧挨着的词”的一段：照旧（长括注单独排 note_html，其余按标点切块）
            res, pos = [], lo
            for a, b in long_notes(s):
                if lo <= a and b <= hi:
                    res += [chunks(pos, a) if a > pos else '', f'<x-n>{note_html(s[a:b], out[a:b])}</x-n>']
                    pos = b
            return ''.join(res) + (chunks(pos, hi) if pos < hi else '')
        res, pos = [], 0
        for a, b in gloss_segments(s):               # 六级黑板审阅：括注与紧挨着的词所在的分句整体放进 x-n（note_segment_html）
            h = note_segment_html(s, out, a, b)
            if h:
                res += [stretch(pos, a) if a > pos else '', h]
                pos = b
        return ''.join(res) + (stretch(pos, len(s)) if pos < len(s) else '')
    ish = lambda c: '\u4e00' <= c <= '\u9fff'
    # 第 2 批截图核查：z14 “所说的Z / 世代。”——英文字母、数字与后面紧挨的汉字绑在一起（“Z世代”“20世纪”“2500亿”）。
    # 六级黑板审阅：一段英文（含空格、撇号、百分号：Stable Diffusion、Hunt’s、100%）整体不断行（“Stable / Diffusion”“100% / 可再生”被拆开）；
    # 只绑后面的汉字、不再绑前面的（“自20世”“和Midjourney提”与前后的词连成一长串，一行放不下整串换行，上一行空出 1/3：s05 第 5 句、s13 第 18 句、s02 第 1 句）
    groups = [(m.start(), m.end() + (m.end() < len(s) and ish(s[m.end()]))) for m in re.finditer(LATIN_RUN, s)]
    groups += [(i - 1, i + 2) for i, c in enumerate(s) if c == '·' and 0 < i < len(s) - 1]      # 人名间隔号与前后各一个字不断开
    groups += name_spans(s)                                         # 登记的整名不断开（t03 审阅：“理查 / 德·帕克”）
    groups += [(a, b) for a, b in jieba_words(s) if b - a > 1 and all(ish(c) for c in s[a:b])]   # 词不拆开（t03 第二轮审阅：“蹦/跳”“相/同”“霎时/间”）
    jw = jieba_words(s)                                             # 专八校园版第 2 批盲审（t06 “后部放着一 / 板条箱活鸡”）：单独成词的数词与后面的词不断开
    groups += [(x[0], y[1]) for x, y in zip(jw, jw[1:]) if x[1] - x[0] == 1 and s[x[0]] in ZH_NUM and ish(s[y[0]])]
    groups += [m.span() for m in re.finditer(ZH_TERM, s)]     # 短的引号术语、书名整体不断行（六级黑板审阅：“能源 / 转型”“非 / 转基因”《思考，快与 / 慢》）
    groups += ZB().zh_spans(s, jb())                                # 复合词、前缀 / 后缀、单字介词、数字 + 量词不拆开（考研截图盲审约 20 处：服务 / 人员、这一 / 威胁、可 / 持续发展）
    groups += clause_edges(s)                                       # 分句开头、结尾不单独留一个字（六级黑板审阅：s37 “传达得 / 好，或许……”）
    # 破折号与前一个字不断开，不落在行首（水墨截图盲审 t09、t10）；前一个字是虚词（的了地得着过）时连同再前一个字（复审：“亲手做 / 的——”）
    groups += [(m.start() - (2 if m.start() > 1 and s[m.start() - 1] in DASH_PART else 1), m.end()) for m in re.finditer('—+', s) if m.start() and s[m.start() - 1].strip()]
    han = [i for i, c in enumerate(s) if ish(c)]
    if len(han) >= 3:
        k = han[-2]
        while k > 0 and re.match(r'[A-Za-z0-9]', s[k - 1]):
            k -= 1
        groups.append((k, len(s)))
    merged = []
    for a, b in sorted(g for g in groups if g[1] - g[0] > 1):
        if merged and a < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    # 左单引号前面可以断行：浏览器（Chromium）不在汉字与“‘”之间断行（“”之前可以），s02 第 5 句“还会让‘艺术家’……”整串推到下一行、上一行空出 4.5 字
    # （layoutcheck 的“译文短行”查出）；中文排版里左引号只是不能落在行末，前面照常可以断
    # 专八校园版 t09 第 8 句：“收尾，说道：“她总是……”——Chromium 不在“：”与“““之间断行（引号两边按规则不断），“说道：“她”连成一串推到下一行、
    # 上一行空出 3 个字（layoutcheck 的“译文短行”查出）；左双引号紧跟在标点后面时，在引号前面加断行点（引号照旧不落在行末）
    for i, c in enumerate(s):
        if (c == '‘' and i and s[i - 1] not in ZOPEN or c == '“' and i and s[i - 1] in '：，。！？；、') and not any(a < i < b for a, b in merged):
            out[i] = '<wbr>' + out[i]
    res, pos = [], 0
    for a, b in merged:
        res += out[pos:a] + [f'<nobr>{"".join(out[a:b])}</nobr>']
        pos = b
    return ''.join(res + out[pos:])


DASH_PART = '的了地得着过'           # 破折号前的虚词：连同再前一个字一起与破折号绑定（layoutcheck.zh_breaks 同一组字）
LATIN_RUN = r"[A-Za-z0-9][A-Za-z0-9’'.&%％-]*(?: [A-Za-z0-9][A-Za-z0-9’'.&%％-]*)*"      # 译文里的一段英文 / 数字（可含空格）


def clause_edges(s):
    """译文每个分句（，。、；：！？之间的一段）开头、结尾单独一个字（汉字）时，与相邻的那一个字单位（一个汉字或一段英文 / 数字）绑在一起：
    一行的末尾不留分句的第一个字，下一行的开头不留分句的最后一个字（“传达得 / 好，”）。返回要整体不断行的 [(起, 止)]。"""
    out = []
    for m in re.finditer(r'[^，。、；：！？]+', s):
        a, b = m.span()
        units, i = [], a                             # 字单位：一个汉字或一段英文 / 数字（引号、括号、破折号等标点不算）
        while i < b:
            r = re.compile(LATIN_RUN).match(s, i, b)
            j = r.end() if r and r.end() > i else i + 1
            if r and r.end() > i or '\u4e00' <= s[i] <= '\u9fff':
                units.append((i, j))
            i = j
        if len(units) < 2:
            continue
        if units[0][1] - units[0][0] == 1:           # 分句开头单独一个字：从这个字绑到第二个字单位（不从分句开头绑：开头的“””是上一句的右引号，
            out.append((units[0][0], units[1][1]))  # 绑进来就不能在它后面断行，s29 第 21 句“影响。”拉维夫”整串推到下一行、上一行空出 3.9 字，layoutcheck 的“译文短行”查出）
        if units[-1][1] - units[-1][0] == 1:         # 分句结尾单独一个字：从倒数第二个字单位绑到分句结尾
            out.append((units[-2][0], b))
    return out


def nb(parts):
    """几个字整体不断行（一个字不用包）。"""
    h = ''.join(parts)
    return f'<nobr>{h}</nobr>' if len(parts) > 1 else h


def gloss_segments(s):
    """释义的分句：在最外层（不在括号里）的 ，。、；：！？ 之后切开，标点（连同紧跟的右半空白标点）归前一个分句。返回 [(起, 止)]。"""
    out, a, depth, i = [], 0, 0, 0
    while i < len(s):
        c = s[i]
        if c in '（(':
            depth += 1
        elif c in '）)':
            depth = max(0, depth - 1)
        elif not depth and c in '，。、；：！？':
            j = i + 1
            while j < len(s) and s[j] in ZCLOSE:
                j += 1
            out.append((a, j))
            a = i = j
            continue
        i += 1
    if a < len(s):
        out.append((a, len(s)))
    return out


def note_segment_html(s, out, a, b):
    """六级黑板审阅：释义里括注与它紧挨着的词（中间没有标点）被拆到两行——“前景；（成功的） / 希望”“获取；使用 / （的机会）”“受（疾病） / 影响的”
    “be covered by 受 / （法律、规定等）保护”“使 / （某事）以……为中心”，“以流媒体方式播放（音乐、视频等） / ；流式传输”分号落到行首。
    含括注、括注外又有字的分句 s[a:b] 整体放进 x-n：放得下一行就整体不断行（FIT：x-n 是行内块，整块换到下一行）；放不下才在“词 | 括注”交界（<wbr>）、
    括注里规定的地方（note_html）、长的词串的词间（words）断开。只有一个字的词串并进相邻的括注（不许单独留一个字：“受 / （法律……”）。
    句末的标点放在 x-n 里面（不落到行首）。不是这种分句返回 None（照旧排）。layoutcheck 的“括注分离”“释义单字”逐屏核对。"""
    ns = [(x + a, y + a) for x, y in notes(s[a:b])]
    e = b
    while e > a and s[e - 1] in ZCLOSE and not any(x <= e - 1 < y for x, y in ns):
        e -= 1
    parts, pos = [], a
    for x, y in ns:
        if x > pos:
            parts.append(['run', pos, x])
        parts.append(['note', x, y])
        pos = y
    if pos < e:
        parts.append(['run', pos, e])
    if not ns or not any(p[0] == 'run' and any(wordch(c) for c in s[p[1]:p[2]]) for p in parts):
        return None
    k = 0
    while k < len(parts):                            # 只有一个字的词串并进相邻的括注（前面有括注并到前面，否则并到后面）
        p = parts[k]
        if p[0] == 'run' and sum(c.isalnum() for c in s[p[1]:p[2]]) <= 1 and len(parts) > 1:
            if k:
                parts[k - 1][2] = p[2]
            else:
                parts[1][1] = p[1]
            del parts[k]
            continue
        k += 1
    k = 0
    while k < len(parts):                            # 括注里只有一个字（“（个）”“（口）”）：并进相邻的词串，不单独换行（专八校园版 t09 第 8 句“一两 / （个）”、
        p = parts[k]                                 # 第 29 句“（口） / 就等着……吧”，layoutcheck 的“释义单字”“孤字”查出）：后面有词串并到后面，否则并到前面
        if p[0] == 'note' and sum(c.isalnum() for c in s[p[1]:p[2]]) <= 1 and len(parts) > 1:
            if k + 1 < len(parts) and parts[k + 1][0] == 'run' and k == 0:
                parts[k + 1][1] = p[1]
                del parts[k]
                continue
            if k and parts[k - 1][0] == 'run':
                parts[k - 1][2] = p[2]
                del parts[k]
                continue
        k += 1
    longs = long_notes(s)
    html = []
    for kind, x, y in parts:
        t = s[x:y]
        if kind == 'note':
            # 长括注自己再包一层 x-n：分句放不下一行时，括注本身放得下一行就整体换行（不在括注里断开；FIT 先定里层、再定外层）
            ln = next(((p, q) for p, q in longs if x <= p and q <= y), None)
            if ln:
                h = f'<x-n>{note_html(s[ln[0]:ln[1]], out[ln[0]:ln[1]])}</x-n>'
                if (x, y) != ln:                     # 并进来的单字：字连同括注再包一层 x-n——放得下一行就整体不断行（“受（法律、规定等）”），
                    h = f'<x-n>{nb(out[x:ln[0]])}{h}{nb(out[ln[1]:y])}</x-n>'      # 放不下时括注整体换行、不拆开（s39 第 4 句“……的 / （代替前面提到的名词）”，原来并成一块排，括注被拆开）
                html.append(h)
            else:
                html.append(nb(out[x:y]))
        else:
            html.append(nb(out[x:y]) if y - x <= GLOSS_CHUNK else words(t, out[x:y]))
    return f'<x-n>{"<wbr>".join(html)}{"".join(out[e:b])}</x-n>'


def look_files(look=None):
    """决定这种画面样子的样式文件（指纹用）：C = 样式.css + 专八字体；1–6 = 共用基础样式 + 专八调整 + 共用字体。"""
    look = look or STYLE
    if look == 'C' and PJ and PJ.get('plain'):      # 四级杂志：基础样式（在本文件 CSS 里，程序指纹已含）+ 四级字体
        return sorted(p for p in (ROOT / '四级' / 'tools' / 'fonts').rglob('*') if p.is_file() and p.suffix == '.css')
    if look == 'C':
        var = [HERE / PJ['css']] if PJ and PJ.get('css') else []          # 变体追加的样式（水墨大字：英文加粗）
        return [THEME, *sorted(p for p in (HERE / 'fonts').rglob('*') if p.is_file() and p.suffix == '.css'), *var]
    return [*TH.files(look), HERE / '样式' / TH.THEMES[look]['file'], ZH_BOLD, ZH_REGULAR, INTER, *sorted((HERE / 'fonts' / 'inter' / 'files').glob('*'))]


def size_css(look=None):
    """字号.json 里这种画面的译文、词条相对字号（追加在所有样式之后；字号标定.py 量字体时先去掉这一段 #sizes）。"""
    z = SIZES[size_key(look or STYLE)]
    return f'<style id="sizes">.zh{{font-size:calc(var(--fs)*{z["zh_k"]})}}.v b{{font-size:calc(var(--vs)*{z["hw_k"]})}}</style>'


# 共用背景的 .v span{margin-left:8px/10px}（样式 4、6）也会套到释义里标点挤压用的 span 上，行首左括号的去半字（.pl）被顶掉，
# 释义行首“（航海用语）”比上下行多缩进（layoutcheck 行首缩进）：释义里套着的 span 外边距归零，.pl 恢复去左半字
GLOSS_PUNCT = '.v div>span span{margin-left:0}.v div>span .pl{margin-left:-.5em}'


def page(body):
    """英文里试卷的中文注释（如 “(防水布)”）用样式自己的中文字体画（C：.en 字体表里的思源宋体；1–6：各样式 .en 的中文字体，4 由 样式/4_活页单词卡.css 补上）：
    t03 审阅发现 “(防水布)(用压条固定)(船舷边缘)(反复猛击)” 落到了系统黑体（WenQuanYi Zen Hei），layoutcheck 的“字体回退”逐屏查。"""
    fonts = (ROOT / '四级' / 'tools' / 'fonts' / 'fonts.css').as_uri()      # 字体与四级共用（EB Garamond、Inter、思源宋体）
    if STYLE == 'C' and PJ and PJ.get('plain'):      # 四级杂志：不叠书卷水墨（样式.css），也不加专八字体（霞鹜文楷）
        # 页脚“逐句精读”等 Inter 元素里的中文：Inter 没有中文字形，原四级 CSS 落到系统字体（预检拦下）；中文改用本画面的思源宋体，英文字形不变
        extra, theme = '', ("<style>.bot,.top b,.ttl .tag,.side h3{font-family:'Inter','Noto Serif SC'}"
                         # 原题屏标签：手账的黄纸胶带 + 思源黑体（ZH Bold，本画面没加载）换成杂志的墨绿标签 + 思源宋体
                         "#pq .lab{font-family:'Noto Serif SC';font-weight:700;color:#fff;background:#1f5c4a;clip-path:none;transform:translateX(-50%);border-radius:6px}</style>")
    elif STYLE == 'C':
        extra = f'<link rel="stylesheet" href="{THEME_FONTS.as_uri()}">'
        theme = f'<style>{THEME.read_text("utf-8")}</style>'
        if PJ and PJ.get('css'):              # 变体（水墨大字）：加粗字重的字体 + 追加样式（在原样式之后覆盖）
            extra += f'<link rel="stylesheet" href="{(HERE / PJ["font_css"]).as_uri()}">'
            theme += f'<style>{(HERE / PJ["css"]).read_text("utf-8")}</style>'
    else:                       # 共用背景：共用字体 + 共用基础样式 + 共用版式骨架（词条间距）+ 专八调整（追加在后面覆盖）
        extra = f'<link rel="stylesheet" href="{TH.FONTS_CSS.as_uri()}"><link rel="stylesheet" href="{ZH_BOLD.as_uri()}"><link rel="stylesheet" href="{INTER.as_uri()}"><link rel="stylesheet" href="{ZH_REGULAR.as_uri()}">'
        theme = f'<style>{TH.css(STYLE)}\n{TH.vocab_gaps(".v div>span")}{GLOSS_PUNCT}\n{(HERE / "样式" / TH.THEMES[STYLE]["file"]).read_text("utf-8")}</style>'
        if PJ and PJ.get('badge'):            # 项目自己的封面贴纸文字（考研：「考研 / 精读」），追加在专八调整之后覆盖
            theme += f"<style>.ttl::after{{content:'{PJ['badge']}'}}</style>"
    return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{fonts}">{extra}<style>{CSS}</style>{theme}{size_css()}</head>'
            f'<body><div class="band"></div>{flat_nobr(body)}</body></html>')


def flat_nobr(h):
    """去掉套在 <nobr> 里面的 <nobr>（外层已经不断行）：HTML 解析器遇到嵌套的 nobr 会先关掉外层、把元素拆开重排（“收养代理”算法），
    六级 s39 第 17 句 <nobr><span class="w"><nobr>over-imitate</nobr>…</span>—</nobr> 被拆成空的高亮 span 加上一段没高亮的 over-imitate，
    画面上这个生词成了正文白色（审阅员发现；layoutcheck 的“高亮丢失”逐屏查）。"""
    out, d, pos = [], 0, 0
    for m in re.finditer(r'<(/?)nobr\b[^>]*>', h):
        out.append(h[pos:m.start()])
        pos = m.end()
        d += -1 if m.group(1) else 1
        if (d == 0 and m.group(1)) or (d == 1 and not m.group(1)):
            out.append(m.group(0))
    return ''.join(out) + h[pos:]


def size_key(look):
    """字号.json 里的键：项目变体在自己的画面上用自己的实测（水墨大字：英文加粗后 x 高度变大，同样看上去的大小字号更小），键 <画面>@<变体>；
    变体的键还没标定时退回原画面的设置——字号标定.py --check（截图前调用）会报“与实测不一致”，不会悄悄用错。"""
    if PJ and PJ.get('variant') and look == PJ['look'] and f"{look}@{PJ['variant']}" in SIZES:
        return f"{look}@{PJ['variant']}"
    if PJ and PJ.get('size') and look == PJ['look'] and PJ['size'] in SIZES:      # 四级杂志：C@杂志（没有水墨的字体，同样看上去的大小字号不同）
        return PJ['size']
    return look


def set_style(look):
    """切换画面（C、1–6）：起始字号、下限、FIT 都按 字号.json 里这种画面的设置。"""
    global STYLE, FS0, VS0, MIN_FS, MIN_VS, FIT
    if look not in LOOKS:
        raise SystemExit(f'--style 只能是 {"、".join(LOOKS)}：{look}')
    STYLE = look
    z = SIZES[size_key(look)]
    FS0, VS0, MIN_FS, MIN_VS = z['fs0'], z['vs0'], z['min_fs'], z['min_vs']
    FIT = FIT_JS.replace('FS0', str(FS0)).replace('MINVS', str(MIN_VS)).replace('VS0', str(VS0))


def name_spans(s):
    """中文音译人名（人名.json）在 s 里的位置：整名不断行（t03 审阅：“理查 / 德·帕克”在名字中间断行，旧检查只管间隔号两边）。"""
    out = []
    for n in NAMES:
        out += [(m.start(), m.end()) for m in re.finditer(re.escape(n), s)]
    return out


def check_names(p):
    """中文里每个人名间隔号“·”都必须属于 人名.json 里登记的整名（新篇目出现新人名就报错，登记后才生成：不静默漏掉）。"""
    bad = []
    for k, s in enumerate((s for pa in p['paras'] for s in pa), 1):
        for txt in [s['zh']] + [w['m'] for w in s['w']]:
            cov = name_spans(txt)
            for m in re.finditer(r'(?<=[\u4e00-\u9fff])·(?=[\u4e00-\u9fff])', txt):
                if not any(a <= m.start() < b for a, b in cov):
                    bad.append(f'第 {k} 句「{txt[max(0, m.start() - 5):m.start() + 6]}」')
    if bad:
        raise SystemExit(f'{p["id"]} 有没登记的中文人名（{PROJ}/tools/人名.json 登记整名后再生成）：' + '；'.join(bad))


def ordered(s):
    """词条按在句中第一次出现的位置编号。"""
    return sorted(s['w'], key=lambda w: w['sp'][0][0])


def sentence_html(s, lo=0, hi=None):
    """只排 en[lo:hi]（分屏时每屏一段）；编号按整句统一，第二屏接着第一屏编号。"""
    hi = len(s['en']) if hi is None else hi
    en = s['en']                       # 专名跨在普通文字和高亮词之间（the Mariana / 高亮 Trench、the California / 高亮 Attorney General）：整句先把专名里的空格换成不换行空格（一个字换一个字，位置不变）
    for a, b in ZB().en_spans(en, [x for w in s['w'] for x in w['sp']]):
        en = en[:a] + en[a:b].replace(' ', '\u00a0') + en[b:]
    ws = ordered(s)
    num = {id(w): i + 1 for i, w in enumerate(ws)}
    spans = sorted((a, b, w, j) for w in s['w'] for j, (a, b) in enumerate(w['sp']) if lo <= a and b <= hi)
    last = {}
    for a, b, w, j in spans:
        last[id(w)] = j
    out, pos = '', lo
    for a, b, w, j in spans:
        if a < pos:
            continue
        cls = 'ph' if w['t'] == 'phr' else 'w'
        sup = f'<sup>{num[id(w)]}</sup>' if j == last[id(w)] else ''     # 分开的短语，编号标在本屏最后一段
        # 所有格紧跟在高亮词后面时，编号标在所有格之后（旧版专八画面核查：drivers⑫’ 编号把词和撇号隔开）；所有格本身不高亮（x-ps 正文颜色）。
        # ’s 一律算；单独的 ’ 只在 -s 词后、且本句前面没有左单引号 ‘ 时算（否则可能是引语的右引号）
        m = re.match(r'’s(?![A-Za-z])|’(?=[\s,;:.!?—]|$)', en[b:hi]) if sup else None
        if m and m.group(0) == '’' and (not en[a:b].endswith('s') or '‘' in en[:a]):
            m = None
        ps = f'<x-ps>{esc(m.group(0))}</x-ps>' if m else ''
        out += esc_en(en[pos:a]) + f'<span class="{cls}">{nobr(esc(en[a:b]))}{ps}{sup}</span>'
        pos = b + (len(m.group(0)) if m else 0)
    out += esc_en(en[pos:hi])
    # 连字符复合词跨在普通文字和高亮词之间（z21 “a 600-” + 高亮 kilometer），两段合起来不断行
    hl = r'<span class="(?:w|ph)">(?:(?!</span>).)*</span>'
    out = re.sub(rf'(?<![\w’])([A-Za-z0-9’]+-)({hl})', r'<nobr>\1\2</nobr>', out)
    out = re.sub(rf'({hl})(-[A-Za-z0-9’]+)', r'<nobr>\1\2</nobr>', out)
    out = re.sub(rf'(<span class="(?:w|ph)">(?:(?!</span>).)*-(?:<sup>\d+</sup>)?</span>)([A-Za-z0-9’]+)', r'<nobr>\1\2</nobr>', out)
    out = re.sub(r'<sup>(\d+</sup></span>(?:</nobr>)?[—–])', r'<sup class="sd">\1', out)
    # 单位本身是高亮词时（六级 s11 第 16 句 “77 percent”，percent 是生词），esc_en 看不到后面的单位，数字后的空格要在这里换成不换行空格
    out = re.sub(rf'(\d) (<span class="(?:w|ph)">(?:<nobr>)?(?:{UNITS})(?![A-Za-z]))', '\\1\u00a0\\2', out)
    out = re.sub(rf'({hl}|<nobr>(?:(?!</nobr>).)*</nobr>)([—–])', r'<nobr>\1\2</nobr>', out)      # 高亮词（及其所在的不断行块）与后面的破折号不断开
    if STYLE == '2':      # 手账笔记本：两位数编号用按比例画的宽椭圆手绘圈（样式 sup.d2；考研作文 w02 审阅：原来的圆圈横向拉伸，线条变粗、数字挤在一起）
        out = re.sub(r'<sup( class="sd")?>(\d{2,})</sup>', lambda m: f'<sup class="{"sd " if m.group(1) else ""}d2">{m.group(2)}</sup>', out)
    return cap_i(out)      # 大写 I 最后统一加，免得上面按 </span> 配对的规则配错     # 编号徽章后紧跟破折号时留空（z06 “idea²—let”徽章贴着破折号）


def vocab_html(s, lo=0, hi=None):
    """释义标 lang="zh-CN"：释义以“……”开头时（……的关键），前面紧挨着英文词条，浏览器会按拉丁文排成底线六点，标了中文才是居中的省略号（画面核查发现，2026-10-10）。"""
    hi = len(s['en']) if hi is None else hi
    out = []
    for i, w in enumerate(ordered(s), 1):
        if not any(lo <= a and b <= hi for a, b in w['sp']):
            continue
        m = POS.match(w['m'])
        pos, mean = (m.group(1), m.group(2)) if m else ('', w['m'])
        # 词条的直撇号改弯撇号（与句子一致，踩坑 18）；<wbr>：词性、释义前一定能换行（z09 “Bluetooth-connected adj.”整体不断行，伸进了词汇栏右边留白）
        # 分开的短语词条里的三个点（pull...through）显示成省略号“…”（t03 审阅；只改显示，数据不动）
        d2 = ' class="d2"' if STYLE == '2' and i >= 10 else ''      # 手账笔记本的两位数编号（样式 .v em.d2）
        # 词条以 f 结尾（a lot of、a set of）：<b class="f">——书卷水墨大字的 EB Garamond 粗体 f 弯钩伸出字身，紧贴后面的释义（水墨截图盲审：“of一套”只空 6 像素，
        # 别的词条约 15 像素）；只有 样式/C_水墨大字.css 给 b.f 加右边距，其他画面没有这条样式、渲染不变
        fb = ' class="f"' if w['h'].rstrip(' .…').endswith('f') else ''
        out.append(f'<div class="v {"ph" if w["t"] == "phr" else ""}"><em{d2}>{i}</em><div><b{fb}>{cap_i(nobr(esc(w["h"].replace(chr(39), "’").replace("...", "…"))))}</b>'
                   f'{f"<wbr><i>{pos}</i>" if pos else ""}<wbr><span class="g" lang="zh-CN">{zh_html(mean, gloss=True)}</span></div></div>')
    return ''.join(out)


def head(p):
    return f'{esc(p["paper"])} · {esc(p["passage"])}'


def title_slide(p):
    """--n = 标题字数：专八样式据此把标题排成一行（字号 64—100px），避免在词中间断行（如“使用语|言”“调查|者”）。"""
    tag = PJ["tag"].replace('PART A', 'PART B') if p.get('part') == 'B' else PJ["tag"]       # 考研 2026 年新题型（Part B）两篇
    ans = f'<span class="ans"><b style="margin-right:.5em;color:var(--blue,inherit)">答案</b>{esc(p["answer"])}</span>' if p.get('answer') else ''      # 新题型的答案（三方核对过）显示在片头图例那一行
    return page(f'''<div class="ttl"><div class="tag">{tag}</div><h1 style="--n:{max(len(p.get("title") or ""), 1)}">{esc(p.get("title") or "")}</h1>
      <div class="sub">{PJ["exam"]} {esc(p["paper"])} · <i>{esc(p["passage"])}</i></div>
      <div class="meta"><span>{esc(p.get("genre") or "")}</span><span>全文 {p["words"]} 词 · 逐句精读</span></div></div>
      <div class="legend"><span><em class="lw"></em>单词</span><span><em class="lp"></em>短语</span>{ans}</div>''')


TITLE_SEC = 1.5      # 片头（静音）秒数：有原题屏时，原题屏从这里开始，到第一句开口（p['lead']）为止


def intro(p):
    """句子之前的屏数：片头，加上原题屏（考研作文）。"""
    return 2 if p.get('prompt_img') else 1


def prompt_slide(p):
    """原题屏（考研作文，用户 2026-10-22：视频开头展示原题，截图必须高清）：原卷 PDF 按 600 dpi 渲染、裁出本题（<项目>/原题/<篇目>.png，
    考研作文/tools/原题截图.py），放在白色卡片里按原比例放到最大（只缩小、不放大，PROMPT_JS 实测核对）；卡片上沿贴一条写着“原题”的纸胶带。
    样式只写在这一屏的 <style> 里，别的屏和别的项目不受影响。"""
    img = (C4 / '原题' / p['prompt_img']).as_uri()
    return page(f'''<style>
.pq{{position:absolute;left:100px;right:90px;top:150px;bottom:30px;background:var(--card,#fff);border-radius:10px;
  box-shadow:0 0 0 1px #ebe6da,0 3px 0 #ece7dc,0 10px 26px rgba(60,70,95,.10);display:flex;align-items:center;justify-content:center;padding:46px 30px 24px}}
.pq img{{display:block;max-width:100%;max-height:100%;object-fit:contain}}
.pq .lab{{position:absolute;top:-27px;left:50%;transform:translateX(-50%) rotate(-1.5deg);padding:4px 46px 6px;white-space:nowrap;
  font-family:'ZH Bold';font-weight:700;font-size:34px;line-height:44px;letter-spacing:.32em;text-indent:.32em;color:var(--ink,#1c2421);
  background:repeating-linear-gradient(135deg,rgba(255,228,107,.92) 0 12px,rgba(255,240,170,.92) 12px 24px);
  clip-path:polygon(0 6%,3% 0,6% 8%,9% 0,12% 7%,15% 0,100% 0,100% 94%,97% 100%,94% 92%,91% 100%,88% 93%,85% 100%,0 100%)}}
</style>
<div class="top"><b>{PJ["top"]}</b><span>{head(p)}　{esc(p.get("title") or "")}</span></div>
<div class="pq" id="pq"><span class="lab">原题</span><img src="{img}" alt=""></div>''')


# 原题屏检查：截图加载成功；画面上实际显示的像素（4K 下 CSS 尺寸 × devicePixelRatio）不超过原图像素（只缩小、不放大 = 高清）；
# 比例不变；在卡片内边距以内；“原题”纸胶带不压住截图；卡片不压页眉；截图按卡片放到最大（宽或高顶满内边距）
PROMPT_JS = """() => { const bad = [], q = s => document.querySelector(s), img = q('.pq img'), card = q('.pq'), lab = q('.pq .lab'), top = q('.top');
  if (!img || !card) return ['没有原题卡片或截图'];
  if (!(img.complete && img.naturalWidth)) return ['原题截图没有加载'];
  const r = img.getBoundingClientRect(), c = card.getBoundingClientRect(), cs = getComputedStyle(card), d = devicePixelRatio;
  const L = c.left + parseFloat(cs.paddingLeft), R = c.right - parseFloat(cs.paddingRight), T = c.top + parseFloat(cs.paddingTop), B = c.bottom - parseFloat(cs.paddingBottom);
  if (img.naturalWidth + 0.5 < r.width * d || img.naturalHeight + 0.5 < r.height * d)
    bad.push(`原题截图不够高清：原图 ${img.naturalWidth}×${img.naturalHeight}，画面上要 ${Math.round(r.width * d)}×${Math.round(r.height * d)}（会被放大）`);
  if (Math.abs(r.width / r.height - img.naturalWidth / img.naturalHeight) > 0.003) bad.push('原题截图比例变了');
  if (r.left < L - 0.5 || r.right > R + 0.5 || r.top < T - 0.5 || r.bottom > B + 0.5) bad.push('原题截图超出卡片内边距');
  if (Math.min(R - L - r.width, B - T - r.height) > 1) bad.push(`原题截图没有放到最大（宽还差 ${Math.round(R - L - r.width)}px，高还差 ${Math.round(B - T - r.height)}px）`);
  const a = lab.getBoundingClientRect();
  if (a.bottom > r.top - 2 && a.left < r.right && r.left < a.right) bad.push('“原题”纸胶带压住了截图');
  if (c.top < top.getBoundingClientRect().bottom + 30) bad.push('原题卡片离页眉太近');
  if (c.bottom > innerHeight || c.right > innerWidth || a.top < top.getBoundingClientRect().bottom + 2) bad.push('原题卡片或纸胶带出界、压住页眉');
  return bad; }"""


def empty_split_parts(p):
    """分屏后每一屏至少有一个词条：铁律 1“每句至少标一个词”推广到每一屏（专八书卷水墨截图盲审：t04 第 19 句第 2 屏、t07 第 39 句第 1 屏、
    t08 第 7、15 句第 1 屏的词汇栏只有标题、空着，像没做完）。词条的高亮从哪一屏开始就算哪一屏的。返回问题列表。"""
    out = []
    S = [s for pa in p['paras'] for s in pa]
    for k, s in enumerate(S, 1):
        parts = split_parts(p['id'], k, s)
        if len(parts) > 1:
            out += [f'第 {k} 句 第 {j} 屏：分屏后这一屏没有词条（词汇栏空着），换分屏点' for j, (lo, hi, *_) in enumerate(parts, 1)
                    if not any(lo <= w['sp'][0][0] < hi for w in s['w'])]
    return out


def split_parts(pid, k, s):
    """分屏：返回 [(lo, hi, 中文, 标签), …]；不分屏返回一屏。专八长句多，可拆成多屏：at 写一个分屏点或按顺序的多个分屏点，
    zh 是各屏中文（比分屏点多一段），必须是定稿译文的原样片段（逐个分句核对），合起来不多不少。
    六级大字版：中文语序与英文对不上、在句中标点处切不出与各屏英文对应的几段时（如英文“部署……至关重要，以取代……”，译文是“要用……取代……，部署……至关重要”），
    zh 写 "整句"：各屏都放整句译文（不切，免得某一屏的中文对应的是另一屏的英文）；
    相邻几屏的英文合起来才对应译文的一个分句时（如英文一个长分句拆成两屏，译文是一个分句、切不开），这几屏写同一段中文（连着重复），
    去掉相邻重复后仍须正好拼成定稿译文。
    "无停顿": 原因（句中没有停顿 / 停顿处切不开）：换屏点不在朗读的停顿处（分屏建议.py 只在停顿处切不开时才这样选），截图检查据此放行并逐条列出。"""
    c = SPLIT.get(pid, {}).get(str(k))
    if not c:
        return [(0, len(s['en']), s['zh'], '')]
    en, zh = s['en'], s['zh']
    ats = c['at'] if isinstance(c['at'], list) else [c['at']]
    full = c['zh'] == '整句'
    zs = [s['zh']] * (len(ats) + 1) if full else c['zh']
    ded = [z for i, z in enumerate(zs) if i == 0 or z != zs[i - 1]]        # 相邻几屏可以放同一段中文
    if not full and len(c['zh']) != len(ats) + 1:
        raise SystemExit(f'分屏.json：{pid} 第 {k} 句有 {len(ats)} 个分屏点，中文应分 {len(ats) + 1} 段')
    cuts = []
    for at in ats:
        if en.count(at) != 1:
            raise SystemExit(f'分屏.json：{pid} 第 {k} 句找不到或不唯一：{at}')
        cut = en.index(at)
        if not re.search(r'[ —]$', en[:cut]):
            raise SystemExit(f'分屏.json：{pid} 第 {k} 句的分屏点不在词边界：{at}')
        if any(a < cut < b for w in s['w'] for a, b in w['sp']):
            raise SystemExit(f'分屏.json：{pid} 第 {k} 句的分屏点切断了一个生词')
        cuts.append(cut)
    if cuts != sorted(cuts):
        raise SystemExit(f'分屏.json：{pid} 第 {k} 句的分屏点没有按顺序排列')
    if not full and (sorted(''.join(ded)) != sorted(zh) or ''.join(ded) != zh or any(x not in zh for z in ded for x in re.split(r'(?<=[，；：、])', z) if x)):
        raise SystemExit(f'分屏.json：{pid} 第 {k} 句的中文不是定稿译文的原样片段')
    b = [0] + cuts + [len(en)]
    n = len(b) - 1
    return [(b[x], b[x + 1], zs[x], f' · PART {x + 1}/{n}') for x in range(n)]


def sentence_slide(p, s, k, n, part=None):
    lo, hi, zh, tag = part or (0, len(s['en']), s['zh'], '')
    en = sentence_html(s, lo, hi).rstrip()
    if lo > 0:
        en = '<span class="cont">… </span>' + en
    if hi < len(s['en']):
        en += '<span class="cont"> …</span>'      # 不换行空格：续接号不落到行首（旧版画面核查：续接号 … 换到行首）
    return page(f'''<div class="top"><b>{PJ["top"]}</b><span>{head(p)}　{esc(p.get("title") or "")}</span></div>
      <div class="main"><div id="box"><div class="en">{en}</div><div class="zh" lang="zh-CN">{zh_html(zh)}</div></div></div>
      <div class="side" id="side"><h3>VOCABULARY</h3><div id="list">{vocab_html(s, lo, hi)}</div></div>
      <div class="bot"><span>SENTENCE {k} / {n}{tag}</span><div class="bar"><i style="width:{k / n * 100:.2f}%"></i></div><span>逐句精读</span></div>''')


# 编号徽章与前一个字母至少留 0.03 字的空隙（字号 64px 时约 1.9 像素）：按该字母的字形实测（f、t、r 等笔画伸出字身，第 2 批截图核查 z16 cricket¹ 等徽章贴字）；
# 左侧句子区与右侧词汇栏分别缩放字号，直到都放得下；词汇栏的内容必须在卡片内边距以内（第 1 批画面核查：内容挤进底部留白，离边框只剩 7 像素）；
# 之后把落在行首的左半空白标点（zh_html 标的 .po）去掉左半空白，与上下行的字对齐，并在它前面固定换行
# （样片 z10 画面核查：去掉半字后括号变窄，整块被挤回上一行行末，成了行中的“花（时间）”过度挤压）；
# 词条一行放不下时（z03 “with the development of”被拆成“…development / of 随着……”），在最均衡的词间断开，释义另起一行（hw，每次量词汇栏前重排）
FIT_JS = """(st) => { const r=document.documentElement.style, main=document.querySelector('.main'), box=document.getElementById('box'),
  side=document.getElementById('side'), list=document.getElementById('list');
  const hw = () => { for (const x of document.querySelectorAll('br.hw')) x.remove();
    for (const b of document.querySelectorAll('.v b')) { if (b.dataset.h === undefined) b.dataset.h = b.innerHTML; else b.innerHTML = b.dataset.h;
      const wide = () => { const sc = getComputedStyle(side), R = side.getBoundingClientRect().left + side.clientLeft + side.clientWidth - parseFloat(sc.paddingRight);
        // 比一整行还宽的连字符长词（六级 s10 you-and-me-against-the-world）只好在连字符处断开；按词汇栏内边距量（网格列会被不断行的词撑宽，量列宽量不出来）
        for (const n of b.querySelectorAll('nobr')) if (n.getBoundingClientRect().right > R + 0.5) n.style.whiteSpace = 'normal'; };
      wide();
      if (b.getClientRects().length < 2) continue;
      const ps = b.dataset.h.split(/ (?![^<>]*>)/); let best = null;
      for (let k = 1; k < ps.length; k++) { b.innerHTML = ps.slice(0, k).join(' ') + '<br>' + ps.slice(k).join(' ');
        const rs = b.getClientRects(); if (rs.length !== 2) continue; const w = Math.max(rs[0].width, rs[1].width); if (!best || w < best[0]) best = [w, b.innerHTML]; }
      b.innerHTML = best ? best[1] : b.dataset.h; wide(); const br = document.createElement('br'); br.className = 'hw'; b.after(br); } };
  const notes = () => { const sc = getComputedStyle(side), R = side.getBoundingClientRect().left + side.clientLeft + side.clientWidth - parseFloat(sc.paddingRight);
    for (const e of document.querySelectorAll('x-n nobr.lr')) { e.style.whiteSpace = '';      // 按词汇栏内边距量：网格列会被不断行的片段撑宽（六级 s39 “three- and four-year-olds”伸出 20 像素）
      // 量片段宽度能不能放进一整行（到词汇栏内边距为止），不看它现在落在哪：原来比“现在的右边界 > R”，片段排在行中（“议员（Member of Parliament”）时
      // 明明换到下一行放得下，也被放开成任意断行，“（Member / of Parliament 的缩写）”（水墨 t07 第 10 句，layoutcheck 括注断开）
      const dv = e.closest('.v > div'), L = dv.getBoundingClientRect().left + dv.clientLeft;
      if (e.getBoundingClientRect().width > Math.min(dv.clientWidth, R - L) + 0.5) e.style.whiteSpace = 'normal'; }
    for (const x of [...document.querySelectorAll('x-n')].reverse()) { x.style.display = '';      // 先里层后外层（释义分句的 x-n 里套着长括注的 x-n）
      if (x.getBoundingClientRect().height > parseFloat(getComputedStyle(x).lineHeight) * 1.5) x.style.display = 'inline'; } };
  const sideFits = () => { hw(); notes(); const s=side.getBoundingClientRect(), c=getComputedStyle(side), l=list.getBoundingClientRect(), top=s.top+side.clientTop;
    // 词条里的连字符词一行放不下（hw 只好在连字符处断开）时，先缩小词汇栏字号；缩到下限还放不下（六级 s10 you-and-me-against-the-world）才允许断开（考研 k24 consumer-／generated）
    if (vs > MINVS && [...document.querySelectorAll('.v b nobr')].some(n => n.style.whiteSpace === 'normal')) return false;
    return l.top >= top + parseFloat(c.paddingTop) - 0.5 && l.bottom <= top + side.clientHeight - parseFloat(c.paddingBottom) + 0.5; };
  const en = document.querySelector('.en');
  const phr = () => { const lim = en.clientWidth; for (const e of en.querySelectorAll('.ph')) { e.style.whiteSpace = '';
      if (e.getBoundingClientRect().width > lim + 0.5) e.style.whiteSpace = 'normal'; }
    // 分屏第一屏末尾的续接号“ …”与前面的字不断开；最后一个高亮短语连着续接号一行放不下时（六级 s26 第 19 句 “make a better life for themselves, …”
    // 伸出 71 像素），只好让这个短语在词间断开（layoutcheck 的“短语断开”按短语连同后面粘着的续接号的总宽判断）
    const c = en.lastElementChild, R = en.getBoundingClientRect().left + en.clientLeft + en.clientWidth, ps = en.querySelectorAll('.ph');
    if (c && c.classList.contains('cont') && ps.length && c.getBoundingClientRect().right > R + 0.5) ps[ps.length - 1].style.whiteSpace = 'normal';
    // 整体换到下一行的高亮短语让上一行空出一半以上时（六级黑板审阅：s54 “We / don't have to look further than”、s26 “actually / compares unfavourably to”
    // 一行只剩一两个词），这个短语改为可以在词间断开，先把上一行填满；上一行已过半的照旧整体不断行（layoutcheck 的“英文短行”“短语断开”按同一条线判断）
    // 上一行的长度按短语前面最后一个非空白字的右边界量（整体换行时和断开后，这个字的位置都不变；layoutcheck 用同一个量）
    const L0 = en.getBoundingClientRect().left + en.clientLeft;
    // 紧贴在短语前面、中间没有空格的字（左引号、左括号：s33 第 11 句 summarized as / “survival of the fittest”）与短语一起换行：
    // 从这些字的第一个量是否在行首，上一行的长度按它们前面最后一个非空白字量（layoutcheck 的“短语断开”例外同样跳过这些字）
    const before = e => { const w = document.createTreeWalker(en, NodeFilter.SHOW_TEXT), cs = []; let n;
      while ((n = w.nextNode()) && !e.contains(n) && (e.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_PRECEDING))
        for (let i = 0; i < n.data.length; i++) cs.push([n, i]);
      const sp = k => /[ \\t\\n]/.test(cs[k][0].data[cs[k][1]]);      // 不换行空格不算（“Mr. ”用不换行空格连着人名短语：t06 Mr. Albert Griggs，称谓算短语的一部分）
      let j = cs.length; while (j > 0 && !sp(j - 1)) j--;
      const head = j < cs.length ? cs[j] : null; while (j > 0 && sp(j - 1)) j--;
      const box = c => { if (!c) return null; const g = document.createRange(); g.setStart(c[0], c[1]); g.setEnd(c[0], c[1] + 1); const q = g.getClientRects(); return q[q.length - 1]; };
      return [box(j > 0 ? cs[j - 1] : null), box(head)]; };
    for (const e of ps) { if (e.style.whiteSpace === 'normal') continue;
      const rs = [...e.getClientRects()].filter(q => q.width > 0); if (!rs.length) continue;
      // 短语是否在行首：量短语第一个字本身（手账笔记本的荧光笔衬底有 0.08 字的内边距和负外边距，短语框比字靠左约 5 像素，
      // 按框量永远“不在行首”，这条规则从不生效——考研作文 w05 “to show how they / breathe new life into”、w17 被 layoutcheck 的“英文短行”查出）
      const tw = document.createTreeWalker(e, NodeFilter.SHOW_TEXT); let tn = tw.nextNode(); while (tn && !/\S/.test(tn.data)) tn = tw.nextNode();
      let r0 = rs[0]; if (tn) { const g0 = document.createRange(), k0 = tn.data.search(/\S/); g0.setStart(tn, k0); g0.setEnd(tn, k0 + 1); r0 = g0.getClientRects()[0] || r0; }
      const [p, h] = before(e), first = h || r0; if (Math.abs(first.left - L0) > 1) continue;
      // 上一行：按两个字的竖直中心比（相差超过半个字号就是不同行）。原来比“上一行字框底 ≤ 短语字框顶”，晴空校园的 Nunito 字框高 1.364 字、行高只有 1.3，
      // 上下两行的字框互相重叠，判断失效（专八 t03 第 4 句 “in a manner that / made my heart sink” 上一行只占 45%，layoutcheck 的“英文短行”查出）
      const fsz = parseFloat(getComputedStyle(en).fontSize);
      if (p && (first.top + first.bottom) / 2 - (p.top + p.bottom) / 2 > 0.5 * fsz && p.right - L0 < 0.5 * lim) e.style.whiteSpace = 'normal'; } };
  // 所有格（x-ps，不高亮）用英文正文实测的颜色、粗细、字体（六级黑板审阅：样式 3 没有 --ink，所有格成了近黑色；正文 600 而所有格写死 400）
  { const c = getComputedStyle(document.querySelector('.en'));
    for (const x of document.querySelectorAll('.en x-ps')) { x.style.color = c.color; x.style.fontWeight = c.fontWeight; x.style.fontFamily = c.fontFamily; } }
  let fs=st ? st[0] : FS0, vs=st ? st[1] : VS0; r.setProperty('--fs', fs+'px'); r.setProperty('--vs', vs+'px'); phr();
  const cv = document.createElement('canvas').getContext('2d');
  for (const s of document.querySelectorAll('.en sup')) { let n = s.previousSibling; while (n && n.nodeType === 1) n = n.lastChild || n.previousSibling;
    if (!n || !n.data) continue; const c = n.data.trim().slice(-1); if (!c) continue; const cs = getComputedStyle(n.parentElement);
    cv.font = `${cs.fontWeight} 100px ${cs.fontFamily}`; const m = cv.measureText(c), rsb = (m.width - m.actualBoundingBoxRight) / 100;
    const ls = (parseFloat(cs.letterSpacing) || 0) / parseFloat(cs.fontSize);      // 英文有 -0.012 字的字间距，会把空隙吃掉一部分
    // 专八：编号字号与原有间距按样式实测（专八编号 0.36 倍字号、间距 0.12 字，中考写死的是 0.42 与 0.04），只在空隙不够时加大，不缩小原样式的间距
    const ss = getComputedStyle(s), sr = parseFloat(ss.fontSize) / parseFloat(cs.fontSize);
    if (s.dataset.ml0 === undefined) s.dataset.ml0 = parseFloat(ss.marginLeft) / parseFloat(ss.fontSize);
    const ml = Math.max(+s.dataset.ml0, (0.03 - rsb - ls) / sr); s.style.marginLeft = ml.toFixed(3) + 'em'; }
  while (box.scrollHeight > main.clientHeight && fs > 30) { fs -= 2; r.setProperty('--fs', fs+'px'); phr(); }
  while (!sideFits() && vs > 16) { vs -= 1; r.setProperty('--vs', vs+'px'); }
  for (const e of document.querySelectorAll('.po')) { const k=e.closest('.zh, .v > div'), b=k.getBoundingClientRect();
    if (Math.abs(e.getClientRects()[0].left - (b.left + k.clientLeft + parseFloat(getComputedStyle(k).paddingLeft))) < 1) { e.className = 'pl';
      const x = e.closest('x-n'), g = x && document.createRange(); if (g) { g.setStart(x, 0); g.setEndBefore(e); }
      (x && g.toString() === '' ? x : e).before(document.createElement('br')); } }   // 括注开头的左括号：换行放在括注外面（括注是行内块，放在里面会空出一行）
  return [fs, vs, box.scrollHeight <= main.clientHeight && sideFits()]; }"""      # st = [英文, 词汇栏] 起始字号（分屏的句子统一字号用，见 layout）；不给就从 FS0/VS0 开始
FIT = None          # set_style() 按画面填入起始字号
# 片头标题一行放不下时（六级 s06 “儿童使用社交媒体：不应禁止，但数字媒体巨头须受监管” 25 个字，教室黑板的标题一行只放得下约 21 个字，伸出卡片 200 像素），
# 在第一个冒号后面换行（br.tb），分成意思完整的两行；放得下就什么都不做（专八的标题都放得下，画面不变）。layoutcheck 的“标题”检查认 br.tb：只许在这里分成两行
TITLE_JS = """() => { const h = document.querySelector('.ttl h1'), card = document.querySelector('.ttl'); if (!h || !card) return 0;
  const g = document.createRange(); g.selectNodeContents(h); const a = g.getBoundingClientRect(), c = card.getBoundingClientRect(), cs = getComputedStyle(card);
  const R = c.left + card.clientLeft + card.clientWidth - parseFloat(cs.paddingRight);
  if (a.right <= R + 1 && new Set([...g.getClientRects()].filter(r => r.width).map(r => Math.round(r.top))).size <= 1) return 0;
  const w = document.createTreeWalker(h, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) { const i = n.data.indexOf('：'); if (i >= 0 && i < n.data.length - 1) {
    const br = document.createElement('br'); br.className = 'tb'; n.splitText(i + 1).before(br); return 1; } }
  return -1; }"""
set_style('C')      # 默认画面 C（书卷水墨）


def screens(p):
    """全部屏：[(标签, HTML, 是否句子屏, 句号 k 或 0)]（片头 k = 0）。"""
    sents = [s for pa in p['paras'] for s in pa]
    out = [('片头', title_slide(p), False, 0)]
    if p.get('prompt_img'):                       # 考研作文：片头之后是原题屏
        out.append(('原题', prompt_slide(p), False, 0))
    for k, s in enumerate(sents, 1):
        parts = split_parts(p['id'], k, s)
        for n, part in enumerate(parts, 1):
            out.append((f'第 {k} 句' + (f' 第 {n} 屏' if len(parts) > 1 else ''), sentence_slide(p, s, k, len(sents), part), True, k))
    return out


def layout(pg, p, f):
    """逐屏排版（生成视频、截图、排版检查都用这一个函数，保证三者完全相同）：依次 yield (屏号, 标签, 是否句子屏, (英文, 词汇栏, 放得下))，
    yield 时页面已排好、可以检查和截图。分屏的句子（t03 审阅：s20 第一屏词汇 40px、第二屏 35px，字号忽大忽小）各屏统一用其中最小的
    英文字号和词汇栏字号：先各自适配，取最小值，再全部从这个字号开始重排，直到各屏一致。f = 临时 HTML 文件。"""
    scr = screens(p)

    def load(h, st=None):
        f.write_text(h, 'utf-8')
        pg.goto(f.as_uri())
        pg.evaluate('document.fonts.ready')
        pg.wait_for_timeout(150)
        return tuple(pg.evaluate(FIT, st))

    start = {}
    for k in sorted({x[3] for x in scr if x[3] and sum(y[3] == x[3] for y in scr) > 1}):
        idx = [i for i, x in enumerate(scr) if x[3] == k]
        st = None
        for _ in range(4):
            got = [load(scr[i][1], st) for i in idx]
            want = [min(g[0] for g in got), min(g[1] for g in got)]
            if all(g[:2] == tuple(want) for g in got):
                break
            st = want
        else:
            raise SystemExit(f'{p["id"]} 第 {k} 句各屏的字号统一不了：{got}')
        for i in idx:
            start[i] = list(got[0][:2])
    for i, (label, h, fit, k) in enumerate(scr):
        if not fit:
            f.write_text(h, 'utf-8')
            pg.goto(f.as_uri())
            pg.evaluate('document.fonts.ready')
            pg.wait_for_timeout(150)
            pg.evaluate(TITLE_JS)
            yield i, label, False, None
            continue
        r = load(h, start.get(i))
        if i in start and list(r[:2]) != start[i]:
            raise SystemExit(f'{p["id"]} {label} 字号 {r[:2]} 与同一句其他屏 {start[i]} 不一致')
        yield i, label, True, r


_ASR, _A16, _WORDS = [], {}, {}      # 语音识别模型、16 kHz 音频、每句的识别结果只算一次（六级分屏建议、截图检查一次要测上百个换屏点；结果与每次重算完全相同）


def asr_words(audio, it):
    """一句的音频（16 kHz）和语音识别出的 [[词, 开口时间（句内秒）], …]。"""
    import glob
    import numpy as np
    import sherpa_onnx
    import soundfile as sf
    import soxr
    key = (str(audio), it['start'], it['end'])
    if key in _WORDS:
        return _WORDS[key]
    if str(audio) not in _A16:
        a, sr = sf.read(str(audio), dtype='float32')
        _A16[str(audio)] = soxr.resample(a, sr, 16000).astype(np.float32)
    a16 = _A16[str(audio)]
    seg = a16[int(it['start'] * 16000): int(it['end'] * 16000)]
    if not _ASR:
        d = Path(glob.glob(str(ROOT / 'tools' / 'tts' / 'models' / 'sherpa-onnx-nemo-parakeet*'))[0])
        _ASR.append(sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(d / 'encoder.int8.onnx'), decoder=str(d / 'decoder.int8.onnx'), joiner=str(d / 'joiner.int8.onnx'),
            tokens=str(d / 'tokens.txt'), model_type='nemo_transducer', num_threads=4))
    asr = _ASR[0]
    st = asr.create_stream()
    st.accept_waveform(16000, seg)
    asr.decode_stream(st)
    words = []                                       # (词, 开口时间)
    for tok, t in zip(st.result.tokens, st.result.timestamps):
        if tok.startswith(' ') or not words:
            words.append([tok.strip(), t])
        else:
            words[-1][0] += tok
    _WORDS[key] = (seg, words)
    return _WORDS[key]


def switch_time(audio, it, en, cut):
    """分屏换屏时刻：语音识别得到第二屏第一个词的开口时间，再在它之前 0.45 秒内找能量最低的 60 毫秒（词间空隙）的中点。"""
    import numpy as np
    s0 = it['start']
    seg, words = asr_words(audio, it)
    first = re.sub(r'[^a-z]', '', en[cut:].split()[0].lower())
    expect = (it['end'] - s0) * cut / len(en)
    cand = [t for w, t in words if re.sub(r'[^a-z]', '', w.lower()) == first]
    if not cand:                                     # 识别结果与原文拼法不同（英式 practising，识别成美式 practicing）：按相似度找，同首字母、相似度至少 0.8
        import difflib
        norm = lambda w: re.sub(r'[^a-z]', '', w.lower())
        cand = [t for w, t in words if norm(w)[:1] == first[:1] and difflib.SequenceMatcher(None, norm(w), first).ratio() >= 0.8]
    if not cand:
        raise SystemExit(f'分屏：语音识别里找不到第二屏第一个词 “{first}”')
    wt = min(cand, key=lambda t: abs(t - expect))
    if abs(wt - expect) > 3:
        raise SystemExit(f'分屏：“{first}” 的识别位置 {wt:.2f}s 与估计位置 {expect:.2f}s 相差太远')
    e = np.convolve(seg.astype(np.float64) ** 2, np.ones(960) / 960, mode='same')      # 60 毫秒滑动能量
    lo, hi = int(max(0, wt - 0.45) * 16000), int(min(len(seg) / 16000, wt + 0.05) * 16000)
    return s0 + (lo + int(np.argmin(e[lo:hi]))) / 16000


def switch_check(mp4, times, sw):
    """换屏核查（四级版）：高考的同名检查假定一句一屏；有分屏时改用这一项。
    每句读完后 0.45 秒仍是本句最后一屏、0.55 秒已是下一句第一屏；分屏的句子在换屏时刻前 0.1 秒是第一屏、后 0.1 秒是第二屏，且两屏确实不同。"""
    import numpy as np
    from verify_videos import frame
    same = lambda a, b: np.abs(a - b).mean() <= 1
    bad = []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i, it in enumerate(times):
            first = frame(mp4, it['start'] + 0.2, td)
            last = first
            for x, ts in enumerate(sw.get(i, []), 2):          # 专八：一句可分多屏，逐个换屏核对
                nxt = frame(mp4, ts + 0.2, td)
                if not (same(frame(mp4, ts - 0.1, td), last) and same(frame(mp4, ts + 0.1, td), nxt) and not same(last, nxt)):
                    bad.append(f'第 {i + 1} 句第 {x} 屏')
                last = nxt
            if i + 1 < len(times):
                if not (same(frame(mp4, it['end'] + 0.45, td), last)
                        and same(frame(mp4, it['end'] + 0.55, td), frame(mp4, times[i + 1]['start'] + 0.2, td))):
                    bad.append(f'第 {i + 1} 句')
    return ('读完停留 0.5 秒再切屏，0.3 秒后开读（含分屏）', not bad,
            f'不符合：{bad}' if bad else f'{len(times) - 1} 处切换全部正确' + (f'，另有 {sum(len(v) for v in sw.values())} 处分屏换屏正确' if sw else ''))


def buzz_check(mp4, times):
    """铁律第 10 条：视频音轨不得有电磁音（独立解码测量声码器的 9 个固定频点）。"""
    import numpy as np
    import debuzz as D
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-vn', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    f0, r, e = D.check(np.frombuffer(raw, np.float32), 48000, times)
    return ('无电磁音', not e, f'最强 {f0} Hz {r:+.1f} dB（上限 {D.MAX_DB:+.1f}）')


def video_name(p, look=None):
    """成品文件名；look（样片）在末尾加「（画面名称）」，如 2025年 Passage Three 与虎同舟熬过海上风暴（晴空校园）.mp4。"""
    title = (p.get('title') or '').translate(str.maketrans('/\\:*?"<>|', '／＼：＊？＂＜＞｜'))
    tag = f'（{LOOKS[look]}）' if look else ''
    return f"{p['paper']} {p['passage']} {title}{tag}.mp4"     # 用户指定：年份月份 第几套 第几篇 题目，前面不加“四级”


def fingerprint(pid, look):
    """截图审阅的指纹（专八样片、六级）：生成程序、排版检查程序、这种画面的样式与字体、字号表、本项目人名表、该篇分屏方案与定稿数据；任何一样改了，截图就要重审。"""
    import hashlib
    h = hashlib.sha256()
    for x in [Path(__file__).resolve(), QA / 'layoutcheck.py', QA / '分词补充.txt', QA / 'zh_bind.py', HERE / '字号.json', T / '人名.json',      # zh_bind：引擎和排版检查共用的断行规则（防复发审计：原来漏了，改了它截图登记不作废）
              ROOT / '四级' / 'tools' / 'fonts' / 'fonts.css', *look_files(look)]:
        h.update(str(Path(x).relative_to(ROOT)).encode())
        h.update(Path(x).read_bytes())
    P = {p['id']: p for p in json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
    h.update(json.dumps([look, P[pid], SPLIT.get(pid, {})], ensure_ascii=False, sort_keys=True).encode())
    if P[pid].get('prompt_img'):                  # 原题截图换过（重新裁图）也要重审
        h.update((C4 / '原题' / P[pid]['prompt_img']).read_bytes())
    return h.hexdigest()[:16]


def still_files(d):
    """审阅截图目录里的逐屏截图（screenNN.png；六级是无损 WebP screenNN.webp，像素与 PNG 完全相同、体积约 0.63 倍：
    教室黑板的粉笔颗粒每张 PNG 约 2.1 MB，六级 60 篇 1783 屏要 3.8 GB，磁盘放不下）。"""
    return sorted([*Path(d).glob('screen*.png'), *Path(d).glob('screen*.webp')])


def still_file(d, i):
    """第 i 屏（从 0 数）的审阅截图。"""
    got = [p for p in (Path(d) / f'screen{i + 1:02d}.png', Path(d) / f'screen{i + 1:02d}.webp') if p.exists()]
    if len(got) != 1:
        raise SystemExit(f'{d} 第 {i + 1} 屏的截图{"不存在" if not got else "同时有 PNG 和 WebP"}')
    return got[0]


def file_hash(f):
    import hashlib
    return hashlib.sha256(Path(f).read_bytes()).hexdigest()[:16]


def small(png):
    """4K 截图缩成 1920×1080（2×2 平均）：样片审阅用的截图和生成视频时的比对用同一种缩法。"""
    from PIL import Image
    im = Image.open(png).convert('RGB')
    return im.resize((W, H), Image.BOX) if im.size != (W, H) else im


def same_still(a, b):
    """两张 1920×1080 截图是否同一画面：浏览器光栅化有随机抖动（同一页面重复截图，个别像素差 6—9 级，西班牙语 es01 实测），
    所以允许最多 64 个像素、每个最多差 24 级；换行、换字、字号变化都远超这个范围。返回 (是否相同, 差异像素数, 最大差)。"""
    import numpy as np
    x, y = np.asarray(a, np.int16), np.asarray(b, np.int16)
    if x.shape != y.shape:
        return False, -1, -1
    d = np.abs(x - y).max(axis=2)
    n, m = int((d > 0).sum()), int(d.max())
    return n <= 64 and m <= 24, n, m


_SPLIT_SIZES = {}      # 分屏的句子：第 1 屏的实测字号（screen_checks 用）


def screen_checks(pg, label, fit, r):
    """一屏排好之后的全部程序检查（生成视频和 样片.py 截图用同一套）：字号下限与放得下、分屏各屏实测字号相同、排版机械检查（含整名、字体回退、徽章撇号、词条间距、
    文字重叠、括注拆开 / 断开、短语断开、译文断词）、
    字体加载失败、字形（每个字都由样式字体画出）、句子屏横向不出界、封面各块不出界不重叠。返回问题列表。"""
    out = []
    if fit:
        fs, vs, fits = r
        if not fits or fs < MIN_FS or vs < MIN_VS:     # 放不下或字太小：必须分屏，不硬挤
            out.append(f'一屏放不下或字太小（英文 {fs}px、词汇 {vs}px，下限 {MIN_FS}/{MIN_VS}px）：在 {PROJ}/tools/分屏.json 里拆屏')
        # 分屏字号（实测，不看 FIT 自己的返回值；t03 第二轮审阅：只有 layout 自己的断言把关，样式改动让某一屏字号变了不会报）：
        # 同一句的各屏，英文、译文、词汇栏、词条、释义的实际字号必须完全相同。按屏的顺序调用，第 1 屏记下、后面各屏比对
        m = re.fullmatch(r'(第 \d+ 句) 第 (\d+) 屏', label)
        if m:
            got = LC.sizes(pg)
            if m.group(2) == '1':
                _SPLIT_SIZES[m.group(1)] = got
            elif _SPLIT_SIZES.get(m.group(1)) is None:
                out.append('分屏字号：没有先检查同一句的第 1 屏，无法比对')
            else:
                out += LC.size_diff(_SPLIT_SIZES[m.group(1)], got)
    out += LC.problems(pg, MIN_FS, MIN_VS, poss=True, names=NAMES, fonts=True, gaps=True, breaks=True)
    out += [f'字体加载失败：{x}' for x in pg.evaluate("() => [...document.fonts].filter(f => f.status === 'error').map(f => f.family)")]
    out += [f'字形：{x} 不在样式字体里' for x in pg.evaluate(TH.GLYPH)]
    if fit:
        out += [f'横向出界：{x}' for x in pg.evaluate(HBOX)]
    elif label == '原题':
        out += [f'原题屏：{x}' for x in pg.evaluate(PROMPT_JS)]
        out += [f'原题屏：{x}' for x in deco_project(pg)]
    else:
        out += [f'封面：{x}' for x in pg.evaluate(TH.COVER, False)[2]]
        out += [f'封面：{x}' for x in deco_project(pg)]
    return [f'{label}：{x}' for x in out]


# 各项目封面装饰文字（::before / ::after 的 content，如右上角贴纸）里允许出现的考试名：别的项目的名字出现就报错
# （考研 k02 截图试跑：共用的 样式/1_晴空校园.css 把贴纸写死成「专八 / 精读」，考研封面也成了“专八精读”）
EXAM_WORDS = {'专八': ['专八', 'TEM-8', 'TEM8'], '专八听力': ['专八', 'TEM-8', 'TEM8'], '六级': ['六级', 'CET-6', 'CET6'], '考研': ['考研', 'KAOYAN'], '考研作文': ['考研', 'KAOYAN'], '六级作文': ['六级', 'CET-6', 'CET6'], '四级作文': ['四级', 'CET-4', 'CET4'],
              '四级': ['四级', 'CET-4', 'CET4'], '中考': ['中考'], '高考': ['高考']}
DECO_JS = """() => { const out = [];
  for (const el of document.querySelectorAll('*')) for (const p of ['::before', '::after']) {
    const c = getComputedStyle(el, p).content;
    if (c && c !== 'none' && c !== 'normal' && c !== '""') out.push(c); }
  return out; }"""


def deco_project(pg):
    other = [w for k, ws in EXAM_WORDS.items() if k != PROJ for w in ws if not any(w in x or x in w for x in EXAM_WORDS.get(PROJ, []))]
    return [f'装饰文字 {c} 是别的考试（{w}），应为{PROJ}' for c in pg.evaluate(DECO_JS) for w in other if w in c]


def load_lc():
    import importlib.util                         # 排版机械检查与中考共用同一个程序
    spec = importlib.util.spec_from_file_location('layoutcheck', QA / 'layoutcheck.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


LC = load_lc()
# 横向出界（共用 themes.HBOX）：右半空白的标点（zh_html 标 .pr，margin-right:-.5em，如“；（”里的“；”）落在行末时，字身的右半空白伸出内边距，
# 墨迹其实在界内（六级 s38 第 8 句、s54 第 21 句报“横向出界：；”）：只对 .pr 把右边界加上它的负外边距再比。themes.py 不动（西班牙语等共用，改了指纹全变）
HBOX = TH.HBOX.replace("if (q.width && (q.left < L || q.right > R))",
                       "if (q.width && (q.left < L || q.right + (n.parentElement.classList.contains('pr') ? parseFloat(getComputedStyle(n.parentElement).marginRight) : 0) > R))")
assert HBOX != TH.HBOX, 'themes.HBOX 改过，横向出界检查的 .pr 修正没套上'


# 原音（专八听力）不做的成品核查：都是 TTS 配音才有的性质——句间固定 0.8 秒且数字静音、逐句响度偏差与 3 秒短时波动（录音里本来就有说话人、
# 播音员的音量差别，只做整体增益 + 前瞻限幅）、读完固定停留 0.5 秒（录音的停顿有长有短）。电磁音（声码器细音）也不做（buzz_check 不调用）。
RAW_SKIP = ('句间停顿', '响度一致', '读完停留')


def cut_check(cuts, owner, times, n0):
    """原音：每次换到下一句的时刻都在两句之间（不早于上一句读完、不晚于下一句开口）。"""
    bad = []
    for c, (i, j, _) in zip(cuts[n0:], owner):
        if j == 0 and i and not (times[i - 1]['end'] - 1e-6 <= c <= times[i]['start'] + 1e-6):
            bad.append(i + 1)
    return ('换屏在两句之间（原音）', bool(not bad), f'不符合：第 {bad} 句' if bad else '全部在句间停顿里')


def loud_check(mp4):
    """原音：成品音轨整体响度 −16 ± 0.7 LUFS、峰值 ≤ −1 dBFS（ITU-R BS.1770，pyloudnorm 独立测量）。"""
    import numpy as np
    import pyloudnorm as pyln
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-vn', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    y = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    lufs = pyln.Meter(48000).integrated_loudness(y)
    peak = 20 * np.log10(np.abs(y).max() + 1e-12)
    return ('整体响度与峰值（原音）', bool(abs(lufs + 16) <= 0.7 and peak <= -1.0), f'{lufs:.2f} LUFS，峰值 {peak:.2f} dBFS')


def frame_check(mp4, frames, pngs):
    """成品逐屏画面核查：每屏中间取一帧（4K），与这一屏的 4K 截图比较（编码有轻微损失，按平均差和 99.9% 分位差判断），确认每屏放的是对的画面。"""
    import numpy as np
    from PIL import Image
    bad, worst = [], (0.0, 0)
    with tempfile.TemporaryDirectory() as td:
        for i, png in enumerate(pngs):
            t = (frames[i] + frames[i + 1]) / 2 / 30
            out = Path(td) / 'f.png'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', str(mp4), '-frames:v', '1', str(out)], check=True)
            a = np.asarray(Image.open(out).convert('L'), np.int16)
            b = np.asarray(Image.open(png).convert('L'), np.int16)
            if a.shape != b.shape:
                bad.append(f'第 {i + 1} 屏尺寸 {a.shape}≠{b.shape}')
                continue
            d = np.abs(a - b)
            mean, p999 = float(d.mean()), int(np.percentile(d, 99.9))
            worst = max(worst, (mean, p999))
            if mean > 3.0 or p999 > 24:      # 实测（t03 第 32 句，C、2、3 三种画面，4K 编码后取帧）：平均差 0.2—1.2（yuv420 色彩换算的整体偏差），99.9% 分位差 4
                bad.append(f'第 {i + 1} 屏（平均差 {mean:.2f}、99.9% 分位差 {p999}）')
    return ('逐屏画面与截图一致（每屏中间一帧）', not bad, f'不一致：{bad}' if bad else f'{len(pngs)} 屏全部一致（最大平均差 {worst[0]:.2f}，99.9% 分位差 {worst[1]}）')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pid')
    ap.add_argument('--project', default=PROJ, choices=list(PROJECTS), help=f'项目（本次默认 {PROJ}；六级/tools/make_video.py 默认 六级）')
    ap.add_argument('--scale', type=int, default=2, help='2 = 3840×2160（4K）')
    ap.add_argument('--out', help='输出目录（默认 <项目>/最终视频）')
    ap.add_argument('--audio-root', help='音频目录（含 timings.json；默认 <项目>/audio），试听样片用')
    ap.add_argument('--style', choices=list(LOOKS), help='画面（默认：专八 C，六级 3）：' + '，'.join(f'{k} {v}' for k, v in LOOKS.items()))
    ap.add_argument('--stills', help='样片：审阅通过的截图目录（专八/样片/截图/<画面>/）。代替 screens_fp 登记：核对审阅登记和截图文件，'
                                     '生成时逐屏与截图比对，不一致就不编码；成品旁写 <文件名>_核查.json。'
                                     '六级不用写：一律核对 六级/样片/截图/<篇目>/（大字版.py --approve 登记），成品文件名不带画面名称')
    a = ap.parse_args()
    set_project(a.project, look=False)
    a.style = a.style or PJ['look']
    a.out = a.out or str(C4 / '最终视频')
    a.audio_root = a.audio_root or str(C4 / 'audio')
    set_style(a.style)

    data = json.loads((C4 / 'data' / 'vocab.json').read_text('utf-8'))
    p = next(x for x in data['passages'] if x['id'] == a.pid)
    import hashlib                                # 踩坑 14：复核通过前不生成视频（专八按篇登记标注文件指纹：ann/复核通过.json）
    seal = json.loads((C4 / 'ann' / '复核通过.json').read_text('utf-8'))['指纹']
    if seal.get(a.pid) != hashlib.sha256((C4 / 'ann' / f'{a.pid}.txt').read_bytes()).hexdigest()[:16]:
        raise SystemExit(f'{a.pid} 的翻译与标注与复核定稿不一致（build_vocab.py --reseal），不生成视频')
    check_names(p)
    # 踩坑 36：先审截图，后生成视频——程序或数据改过、截图还没审阅通过，就不生成视频
    sample = bool(a.stills)                       # 专八样片：成品文件名带画面名称、核查结果写在成品旁边
    # 截图目录：样片.py 传 --stills；成套生产（大字版.py：六级教室黑板、专八晴空校园 2026-10-17 起）用项目的截图目录；专八旧版画面 C 仍走 screens_fp
    # 项目变体（专八 水墨：画面 C 走成套生产）同样用项目的截图目录和 大字版 登记，不走旧版的 screens_fp
    stills = Path(a.stills) if a.stills else (C4 / PJ['stills'].format(pid=a.pid) if PJ['stills'] and (a.style != 'C' or PJ.get('variant') or PJ.get('plain')) else None)
    tool = '专八/tools/样片.py' if sample else f"{PROJ}/tools/大字版{'_' + PJ['variant'] if PJ.get('variant') else ''}.py"
    regf = YP_REG if sample else SAMPLE_REG
    if stills:                                    # 样片.py / 大字版.py --approve 登记的指纹与截图文件
        key = f'{a.pid}@{a.style}'
        reg = json.loads(regf.read_text('utf-8')).get(key) if regf.exists() else None
        if not reg or reg['指纹'] != fingerprint(a.pid, a.style):
            raise SystemExit(f'{key} 的样片截图还没有审阅通过，或审阅之后程序、样式、数据改过（{tool} --stills → 审阅 → {tool} --approve）')
        got = {x.name: file_hash(x) for x in still_files(stills)}
        if got != reg['截图']:
            raise SystemExit(f'{stills} 里的截图不是审阅登记的那一份（重新截过图）：先审阅再 {tool} --approve')
    elif a.style != 'C':
        raise SystemExit('共用背景（--style 1–6）目前只做样片：用 专八/tools/样片.py')
    else:
        subprocess.run([sys.executable, str(QA / 'screens_fp.py'), '--project', PROJ, 'check', a.pid], check=True)
    tm = json.loads((Path(a.audio_root) / 'timings.json').read_text('utf-8'))[VOICE][a.pid]
    sents = [s for para in p['paras'] for s in para]
    times = tm['sentences']
    assert len(sents) == len(times), '音频句数与文章句数不一致，请重新生成音频'
    empty = [i + 1 for i, s in enumerate(sents) if not s['w']]
    if empty:                                   # 铁律：每一句至少标出一个单词
        raise SystemExit(f'第 {empty} 句没有标注单词，不生成视频')
    audio = Path(a.audio_root) / tm['file']

    from playwright.sync_api import sync_playwright
    # 踩坑 29：临时目录（每个视频约 35 MB 的截图和分段）以前从不删除，积累到磁盘写满，浏览器截图崩溃（Page crashed）
    import atexit
    import shutil
    free = shutil.disk_usage(C4).free / 2**30
    if free < 3:
        raise SystemExit(f'磁盘剩余只有 {free:.1f} GB（至少需要 3 GB），先清理临时文件再生成视频')
    tmp = Path(tempfile.mkdtemp(prefix=PJ['tmp']))
    atexit.register(shutil.rmtree, tmp, True)          # 无论成功、核查失败还是出错，退出时都删除
    scr = screens(p)
    owner = [None] * intro(p) + [(k - 1, n, part) for k in range(1, len(sents) + 1)
                                 for n, part in enumerate(split_parts(p['id'], k, sents[k - 1]))]     # owner：每屏属于第几句、第几屏（片头、原题屏为 None）
    assert len(owner) == len(scr)
    sizes, probs, diff = [], [], []
    with sync_playwright() as pw:
        exe = '/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={'width': W, 'height': H}, device_scale_factor=a.scale)
        for i, label, fit, r in layout(pg, p, tmp / 'x.html'):
            probs += screen_checks(pg, label, fit, r)
            if fit:
                sizes.append(r[:2])
            pg.screenshot(path=str(tmp / f'{i:03d}.png'))
            if stills:
                ok, n, m = same_still(small(tmp / f'{i:03d}.png'), small(still_file(stills, i)))
                if not ok:
                    diff.append(f'第 {i + 1} 屏（{label}）与审阅过的截图不同：{n} 个像素不同，最大差 {m}')
        br.close()
    if probs:
        raise SystemExit(f'{p["id"]} 排版或画面检查不合格（不生成视频）：\n  ' + '\n  '.join(probs))
    if stills and (diff or len(still_files(stills)) != len(scr)):
        raise SystemExit('画面与审阅过的截图不一致（不生成视频）：\n  ' + '\n  '.join(diff or [f'屏数 {len(scr)} ≠ 截图 {len(still_files(stills))}']))

    starts = [x['start'] for x in times]
    ends = [x['end'] for x in times]
    TAIL = 2.0
    total = max(tm['duration'], ends[-1] + TAIL)
    HOLD, GAP = 0.5, 0.8
    RAW = PJ.get('audio') == '原音'                 # 原音（专八听力）：句间是录音里本来的停顿，不是固定 0.8 秒
    bad = [] if RAW else [i + 2 for i in range(len(times) - 1) if abs(starts[i + 1] - ends[i] - GAP) > 0.01]
    if bad:
        raise SystemExit(f'第 {bad} 句之前的停顿不是 {GAP} 秒，请用最新设置重新生成音频')
    cuts, sw = [0.0], {}
    if p.get('prompt_img'):                       # 原题屏：片头 1.5 秒之后出现，静音停留到第一句开口（音频按 p['lead'] 留的静音）
        if abs(starts[0] - p['lead']) > 0.01 or p['lead'] - TITLE_SEC < 1:
            raise SystemExit(f'第一句从 {starts[0]:.2f}s 开口，数据要求 {p["lead"]}s（片头 {TITLE_SEC}s + 原题屏 ≥ 1s）：请重新生成音频')
        cuts.append(TITLE_SEC)
    for i, j, part in owner[intro(p):]:
        if j == 0:
            if i and RAW:                             # 原音：停顿 ≥ 0.8 秒照常读完停 0.5 秒再切；更短的停顿按同一比例（0.5/0.8）切在停顿中间
                g = starts[i] - ends[i - 1]
                cuts.append(ends[i - 1] + (HOLD if g >= GAP else g * HOLD / GAP))
            else:
                cuts.append(starts[0] if i == 0 else ends[i - 1] + HOLD)
        else:                                       # 分屏的第二屏：在第二屏第一个词开口之前切换
            t = switch_time(audio, times[i], sents[i]['en'], part[0])
            if not starts[i] + 0.3 < t < ends[i] - 0.3:
                raise SystemExit(f'第 {i + 1} 句分屏时刻 {t:.2f}s 不在句子朗读范围内')
            print(f'  第 {i + 1} 句第 {j + 1} 屏，{t - starts[i]:.2f}s 处换屏（第二屏从 “{sents[i]["en"][part[0]:part[0] + 24]}…” 开始）')
            cuts.append(t)
            sw.setdefault(i, []).append(t)
    cuts.append(total)
    assert len(cuts) == len(scr) + 1
    FPS = 30
    frames = [round(c * FPS) for c in cuts[:-1]] + [math.ceil(cuts[-1] * FPS)]
    lst = []
    for i in range(len(scr)):
        n = frames[i + 1] - frames[i]
        segf = tmp / f'seg{i:03d}.mp4'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-framerate', str(FPS),
                        '-i', str(tmp / f'{i:03d}.png'), '-frames:v', str(n), '-vf', 'format=yuv420p',
                        '-c:v', 'libx264', '-preset', 'ultrafast', '-qp', '0', '-pix_fmt', 'yuv420p', str(segf)], check=True)   # 每屏先无损（快），整片最后统一压缩
        lst.append(f"file '{segf}'")
    (tmp / 'list.txt').write_text('\n'.join(lst))
    total = frames[-1] / FPS

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = video_name(p, a.style if sample else None)
    silent = tmp / 'video.mp4'
    # 整片一次压缩（用户 2026-10-16：“尽可能把每一个视频压缩一下，不用这么大”）：原来每屏单独编码（crf 12），每屏开头一张完整画面，
    # 教室黑板的粉笔颗粒每张 4.4 MB，78 屏 431 MB；现在每屏先无损、拼好后整片压一次，换屏时背景沿用前一帧，只存变了的字。
    # 完整画面（关键帧）占体积的八成（黑板静止 20 秒实测：2 张 6.9 MB，其余 598 帧 1.6 MB），所以每 30 秒才放一张（-g 900，不按画面变化另插 scenecut=0）；
    # 用户 2026-10-16：“质量效果不能变、必须 4K，只把体积压下去”——画面（含粉笔颗粒）一点不改，只靠编码：crf 18（公认的“看不出损失”档，
    # 黑板实测与无损比 PSNR 51.5 dB），省下的体积全部来自少放完整画面（同一 crf 下每一帧的画质不变）
    # crf 见 CRF（字的边缘在 4K 下看不出差别；逐屏画面与截图一致、成品体积 ≤ 95 MB 都在下面核查）
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(tmp / 'list.txt'),
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', str(CRF.get(STYLE, CRF['*'])), '-tune', 'stillimage',
                    '-pix_fmt', 'yuv420p', '-g', str(FPS * 30), '-x264-params', 'scenecut=0', str(silent)], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(silent), '-i', str(audio),
                    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', f'apad=whole_dur={total:.3f}',
                    '-t', f'{total:.3f}', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
                    str(out / name)], check=True)
    durs = [float(x) for x in subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=duration', '-of', 'csv=p=0',
                                str(out / name)], capture_output=True, text=True).stdout.split()]
    dur = min(durs)
    # 成品核查：复用高考 verify_videos.check（分辨率、流畅度、声画等长、朗读与画面逐句一致、静音、停顿、响度……）
    sys.path[:0] = [str(ROOT / 'tools' / 'video'), str(ROOT / 'tools' / 'tts')]
    from verify_videos import check
    res = [r for r in check(out / name, p, tm) if not r[0].startswith('文件名') and not (sw and r[0].startswith('读完停留'))
           and not (RAW and r[0].startswith(RAW_SKIP))]
    if sw and not RAW:                            # 原音：分屏换屏时刻由 switch_time 按识别定，句间换屏由 cut_check 查、每屏画面由 frame_check 查；固定停留 0.5 秒不适用
        res.append(switch_check(out / name, times, sw))
    if RAW:
        res += [cut_check(cuts, owner[intro(p):], times, intro(p)), loud_check(out / name)]
    else:
        res.append(buzz_check(out / name, times))
    res.append(('结尾静音 ≥ 2 秒', dur - ends[-1] >= TAIL - 0.05, f'{dur - ends[-1]:.2f} 秒'))
    res.append(frame_check(out / name, frames, [tmp / f'{i:03d}.png' for i in range(len(scr))]))
    size = (out / name).stat().st_size          # GitHub 单个文件上限 100 MB（教室黑板旧版 431 MB 推不上去，也超过发送上限）
    res.append(('成品体积 ≤ 95 MB', size <= 95 * 2**20, f'{size / 2**20:.1f} MB'))
    ok_name = re.fullmatch(PJ['name_re'], name) and name == video_name(p, a.style if sample else None)
    res.append(('文件名', bool(ok_name), name))
    for n_, c, d in res:
        print(f"  {'通过' if c else '不通过'} {n_}：{d}")
    fails = [f'{n_}：{d}' for n_, c, d in res if not c]
    if stills:                                    # 核查结果（样片.py / 大字版.py 据此判断这一篇、这种画面已经做好、可以跳过）：样片写在成品旁边，六级写 六级/样片/成品核查/
        rep_dir = out if sample else C4 / PJ['work'] / '成品核查'
        rep_dir.mkdir(parents=True, exist_ok=True)
        (rep_dir / (Path(name).stem + '_核查.json')).write_text(json.dumps(
            {'video': name, 'style': a.style, '指纹': fingerprint(a.pid, a.style), 'ok': not fails, 'duration': round(dur, 3),
             'size': (out / name).stat().st_size, 'checks': [{'item': n_, 'ok': c, 'detail': d} for n_, c, d in res]},
            ensure_ascii=False, indent=1), 'utf-8')
    if fails:
        (out / name).unlink()
        raise SystemExit('核查未通过，已删除成品：\n  ' + '\n  '.join(fails))
    print(f'  英文字号 {min(x[0] for x in sizes)}–{max(x[0] for x in sizes)}px，词汇栏字号 {min(x[1] for x in sizes)}–{max(x[1] for x in sizes)}px')
    print(f'已生成并核查通过 {out / name}（时长 {dur:.2f} 秒，读完后静音 {dur - ends[-1]:.2f} 秒）')


if __name__ == '__main__':
    sys.exit(main())
