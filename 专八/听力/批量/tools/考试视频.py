"""逐年专八考试适配器：复用2025纯白考卷及编码/核验底座，不修改2025源文件。

python 考试视频.py YEAR_DIR layout|stills|audio|video [--sample] [--fast] [--audio FILE] [--out DIR]
python 考试视频.py --自检
python 考试视频.py --convert-2025 TARGET_DIR
所有时间轴事件均为剪头前原音秒；只授权剪掉片头音乐，其余原声保持不变。
"""
import argparse
import copy
import hashlib
import html
import http.server
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
LISTEN = HERE.parents[1]
ROOT = LISTEN.parents[1]
BASE_FILE = LISTEN / 'tools/听力视频.py'
spec = importlib.util.spec_from_file_location('tem8_2025_exam_base', BASE_FILE)
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
ESC = lambda s: html.escape(str(s), quote=False)
BASE_VERIFY = B.verify
PAPER = None
TIMELINE = None
OUT = None
AUDIT = None
DRAFT = False
SOURCE_DIR = None
BASE_CSS = B.CSS
SHEET_PAGES = []
PREVIEW_PAGES = {}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def validate(p, t, allow_draft=False):
    pending = p.get("pending") or p.get("待核") or t.get("pending") or t.get("待核")
    require(allow_draft or not pending, "存在pending/待核，必须核清后才能制作成品")
    require(isinstance(p.get('year'), int) and 2000 <= p['year'] <= 2100, 'year须为年份整数')
    require(p.get('title') and p.get('sections'), '缺少标题或说明')
    secs = {s['id']: s for s in p['sections']}
    require(len(secs) == len(p['sections']), 'section id重复')
    require(all(s.get('title') and isinstance(s.get('lines'), list) for s in secs.values()), 'section缺标题或lines')
    questions = p.get('questions', [])
    qs = {q['n']: q for q in questions}
    require(len(qs) == len(questions), '选择题题号重复')
    for q in questions:
        require(isinstance(q['n'], int) and q['n'] > 0, '选择题题号须为正整数')
        require(len(q.get('options', [])) == 4 and all(q['options']), f'Q{q["n"]}选项须为四项')
        answer = q.get('answer')
        require((allow_draft and answer is None) or (isinstance(answer, str) and len(answer) == 1 and answer in 'ABCD'), f'Q{q["n"]}答案错误')
        require(isinstance(q.get('unscored', False), bool), 'unscored须为布尔值')
        require(not q.get('unscored') or (isinstance(q.get('source_note'),str) and q['source_note'].strip()), f'Q{q["n"]}不计分题必须说明题源问题')
    groups = {g['id']: g for g in p.get('groups', [])}
    require(len(groups) == len(p.get('groups', [])), 'group id重复')
    for g in groups.values():
        require(g.get('title') and g.get('questions'), 'group缺标题或题号')
        require(set(g['questions']) <= set(qs), 'group题号不存在')
        require(len(g['questions']) == len(set(g['questions'])), 'group题号重复')
    grouped = [n for g in groups.values() for n in g['questions']]
    require(sorted(grouped) == sorted(qs), '每道选择题须且仅须属于一个group')
    answers = p.get('gap_answers', [])
    require(isinstance(answers, list) and all(isinstance(a, str) and a.strip() for a in answers), 'gap_answers须为完整字符串列表')
    pages = p.get('sheets', [p.get('sheet', [])])
    gaps = []
    for rows in pages:
        for row in rows:
            require(row[0] in ['title', 'h', 'b', 'e', 'd', 'p', 'col'], '未知sheet行类型')
            if row[0] != 'col':
                require(len(row) == 2 and isinstance(row[1], str), 'sheet行缺文字')
                gaps += [int(x) for x in re.findall(r'\{(\d+)\}', row[1])]
    require(sorted(gaps) == list(range(1, len(answers) + 1)), '答题卡空号须各出现一次并与答案一一对应')
    duration = t.get('source_duration')
    require(isinstance(duration, (int, float)) and math.isfinite(duration) and duration > 0, 'source_duration无效')
    trim = t.get('trim', {'start': 0})
    start = trim.get('start', 0)
    require(isinstance(start, (int, float)) and math.isfinite(start) and 0 <= start < duration, '剪头时刻无效')
    if start:
        require(trim.get('reason') in ['片头音乐', 'intro_music'], '仅授权剪除片头音乐')
        require(re.fullmatch('[0-9a-f]{64}', trim.get('source_sha256', '')), '剪头记录须绑定原音SHA256')
        require(trim.get('evidence'), '剪头记录须写核定依据，避免剪掉正式说明')
    events = t.get('events', [])
    require(events, '缺events')
    last = start
    seen_q = set()
    for e in events:
        x = e.get('t')
        require(isinstance(x, (int, float)) and math.isfinite(x) and start <= x < duration, '事件越界')
        require(x >= last, '事件须按原音时刻递增，不允许静默排序修复')
        last = x
        require(e['kind'] in ['instr', 'sheet', 'plist', 'q', 'end'], '考试事件不得含答案或未知类型')
        if e['kind'] == 'instr':
            require(e.get('sec') in secs, '事件section不存在')
            shown = e.get('lines', secs[e['sec']]['lines'])
            require(shown and all(v in secs[e['sec']]['lines'] for v in shown), '分屏说明必须取自本section原句')
            require(-1 <= e.get('hi', -1) < len(shown), '说明高亮序号不存在')
        elif e['kind'] == 'sheet':
            require(0 <= e.get('page', 0) < len(pages), '答题卡页不存在')
        elif e['kind'] == 'plist':
            require(e.get('group') in groups, '选项一览group不存在')
            nums = e.get('numbers', groups[e['group']]['questions'])
            require(0 < len(nums) <= 5 and len(nums) == len(set(nums)) and set(nums) <= set(groups[e['group']]['questions']), '选项一览每屏1—5题；长group用numbers分页')
        elif e['kind'] == 'q':
            require(e.get('n') in qs, '单题题号不存在')
            seen_q.add(e['n'])
        if 'countdown' in e:
            c = e['countdown']
            require(isinstance(c.get('end'), (float, int)) and x < c['end'] <= duration, '倒计时结束越界或为零')
            require(c.get('label'), '倒计时缺label')
    require(seen_q == set(qs), '时间轴须包含每道选择题的单题画面')
    for i, e in enumerate(events):
        if 'countdown' in e and i + 1 < len(events):
            require(e['countdown']['end'] <= events[i+1]['t'] + 1e-6, '倒计时跨越下一事件')
    return True


def configure(folder, out, draft=False):
    global PAPER, TIMELINE, OUT, AUDIT, DRAFT, SOURCE_DIR, SHEET_PAGES, PREVIEW_PAGES
    DRAFT = draft
    folder = Path(folder).resolve()
    SOURCE_DIR = folder
    PAPER, TIMELINE = read(folder / '试卷.json'), read(folder / '时间轴.json')
    validate(PAPER, TIMELINE, allow_draft=draft)
    OUT = Path(out).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT = OUT / '核验'
    AUDIT.mkdir(exist_ok=True)
    SHEET_PAGES = paginate_sheet(PAPER)
    PREVIEW_PAGES = {g['id']:preview_pages(g['questions']) for g in PAPER['groups']}
    dump(AUDIT/'大字分页方案.json',{'sheet_pages':SHEET_PAGES,'preview_pages':PREVIEW_PAGES,'policy':{'preview':'30秒按页数均分；绝对倒计时不重置','lecture_seconds_per_page':25,'check_seconds_per_page':30,'interview_seconds_per_page':20},'source_fingerprints':fingerprints()})
    B.D, B.OUT = AUDIT, OUT
    B.Q = {'gap_answers': PAPER.get('gap_answers', [])}
    B.NAME = PAPER.get('filename', f'{PAPER["year"]}年 专八听力 考试.mp4')
    require(Path(B.NAME).name == B.NAME and B.NAME.endswith('.mp4'), 'filename须为单个MP4文件名')
    B.ORIGINAL, B.LIMIT = True, False
    B.CUT_START = TIMELINE.get('trim', {}).get('start', 0)
    B.CUT_CHECK = trim_check
    B.CUT_END, B.INSERTS = None, []
    B.page, B.states, B.verify = page, states, verify
    return PAPER


def fingerprints():
    return {key:sha(path) for key,path in {
        'paper':SOURCE_DIR/'试卷.json',
        'timeline':SOURCE_DIR/'时间轴.json',
        'adapter':Path(__file__),
        'base':BASE_FILE,
    }.items()}


def preview_pages(numbers):
    # 五题按原顺序2+3，避免最后一页只剩一题；其他长度均完整覆盖。
    if len(numbers)==5:return [numbers[:2],numbers[2:]]
    return [numbers[i:i+3] for i in range(0,len(numbers),3)]


def paginate_sheet(p):
    """原题完整逻辑行分为2页，必要时3页；不拆词句、不重复/删除正文。

    用原卷TNR实际字宽估算分栏，浏览器另作40—46px真实度量核验。
    """
    from PIL import ImageFont
    original=[r for rows in p.get('sheets',[p.get('sheet',[])]) for r in rows]
    title=next((r[1] for r in original if r[0]=='title'),p.get('sheet_title','Mini-lecture'))
    rows=[r for r in original if r[0] not in ('col','title')]
    if len(rows)<4:
        cut=max(1,math.ceil(len(rows)/2))
        return [{'rows':[['title',title]]+part+[['col']],'source_row_range':rg,'planned_font_size':46} for part,rg in [(rows[:cut],[0,cut]),(rows[cut:],[cut,len(rows)])]]
    best=None
    for pages in [2,3]:
        for fs in range(46,39,-1):
            fonts={b:ImageFont.truetype(str(B.FL/('TimesNewRomanBold.ttf' if b else 'TimesNewRoman.ttf')),fs) for b in (False,True)}
            costs=[]
            for kind,txt in rows:
                font=fonts[kind=='h'];width=800-{'b':46,'e':80,'d':90}.get(kind,0)
                tokens=re.findall(r'\{\d+\}|\S+',txt);line=0.;lines=1
                for token in tokens:
                    token=re.sub(r'\{(\d+)\}',lambda m:'('+m[1]+') _______',token)
                    w=font.getlength(token,features=['-kern']);space=(font.getlength(' ')+fs*.05) if line else 0
                    if line and line+space+w>width:lines+=1;line=w
                    else:line+=space+w
                costs.append(lines*fs*1.25+(18 if kind=='h' else 0))
            prefix=[0]
            for c in costs:prefix.append(prefix[-1]+c)
            n=len(rows);cols=pages*2;dp={(0,0):(0,[])}
            for k in range(1,cols+1):
                for end in range(k,n+1):
                    options=[]
                    for start in range(k-1,end):
                        if (k-1,start) not in dp or (end<n and rows[end-1][0]=='h'):continue
                        height=prefix[end]-prefix[start]-(18 if rows[start][0]=='h' else 0)
                        prev,cuts=dp[k-1,start];options.append((max(prev,height),cuts+[end]))
                    if options:dp[k,end]=min(options,key=lambda x:x[0])
            if (cols,n) in dp and dp[cols,n][0]<=735:
                best=(pages,fs,dp[cols,n][1]);break
        if best:break
    require(best,'原题在3页40px仍过密，须人工保留原文合理分屏')
    pages,fs,cuts=best;columns=[];a=0
    for z in cuts:columns.append(rows[a:z]);a=z
    result=[]
    for i in range(pages):result.append({'rows':[['title',title]]+columns[2*i]+[['col']]+columns[2*i+1],'source_row_range':[0 if i==0 else cuts[2*i-1],cuts[2*i+1]],'planned_font_size':fs})
    flattened=[r for page in result for r in page['rows'] if r[0] not in ('title','col')]
    require(flattened==rows,'分页正文重复或漏行')
    return result


def paginated_events():
    """只增加画面换页，保留每个原始语音边界和绝对倒计时结束。"""
    source=TIMELINE['events'];result=[];audit=[]
    for i,ev in enumerate(source):
        e=copy.deepcopy(ev);a=e['t'];z=source[i+1]['t'] if i+1<len(source) else TIMELINE['source_duration'];kind=e['kind']
        if kind=='sheet':pages=list(range(len(SHEET_PAGES)))
        elif kind=='plist':
            g=next(g for g in PAPER['groups'] if g['id']==e['group']);pages=preview_pages(e.get('numbers',g['questions']))
        else:result.append(e);continue
        end=min(z,e.get('countdown',{}).get('end',z));span=end-a
        preview=bool('countdown' in e and span<=45)
        step=(span/len(pages) if preview else (30 if 'countdown' in e else 25 if kind=='sheet' else 20))
        starts=[a] if span<=0 or step<=0 else [a+j*step for j in range(max(1,math.ceil(span/step-1e-8))) if a+j*step<end-1e-6]
        for j,x in enumerate(starts):
            pg=j%len(pages);s=copy.deepcopy(e);s['t']=round(x,6);s['display_page']=pg+1;s['display_pages']=len(pages)
            if kind=='sheet':s['page']=pages[pg]
            else:s['numbers']=pages[pg]
            result.append(s)
        audit.append({'kind':kind,'original_start':a,'original_end':z,'pages':len(pages),'page_starts':starts,'absolute_countdown_end':e.get('countdown',{}).get('end'),'preview':preview})
    dump(AUDIT/'自动翻页核验.json',{'segments':audit,'audio_timing_changed':False,'source_fingerprints':fingerprints()})
    return result


def states():
    trim = TIMELINE.get('trim', {}).get('start', 0)
    duration = TIMELINE['source_duration'] - trim
    raw = [(-B.LEAD, {'kind': 'title'})]
    expanded=paginated_events()
    for index,e in enumerate(expanded):
        s = {k: v for k, v in e.items() if k not in ['t', 'countdown']}
        a = e['t'] - trim
        if 'countdown' not in e:
            raw.append((a, s))
            continue
        end = e['countdown']['end'] - trim
        label = e['countdown']['label']
        n = math.ceil(end - a - 1e-6)
        if n > 1 and end - a - (n - 1) < .5:
            n -= 1
        raw.append((a, dict(s, cd=n, cdl=label)))
        stop=(expanded[index+1]['t']-trim) if index+1<len(expanded) else duration
        for k in range(n-1, 0, -1):
            if a+1e-6<end-k<stop-1e-6:raw.append((end-k, dict(s, cd=k, cdl=label)))
    # 同一帧的说明/倒计时边界取最后状态；不同题号碰在同一帧则不允许隐匿。
    by_frame = {}
    merged = []
    for t, s in raw:
        f = round((t + B.LEAD) * B.FPS)
        if f in by_frame:
            old = by_frame[f]
            require(not (old[1]['kind'] == s['kind'] == 'q' and old[1].get('n') != s.get('n')), '两个题目落在同一帧')
            merged.append({'frame': f, 'old': old[1], 'new': s})
        by_frame[f] = (t, s)
    raw = [by_frame[f] for f in sorted(by_frame)]
    # 所有答案自动在原音全部结束后出现，不允许数据事件提前显示答案。
    # 第一答案屏取录音结束后的第一帧，绝不因四舍五入提前半帧。
    at = math.ceil((duration+B.LEAD)*B.FPS-1e-9)/B.FPS-B.LEAD
    first_answer = at
    gaps = list(range(1, len(PAPER.get('gap_answers', [])) + 1))
    choices = [q['n'] for q in PAPER.get('questions', [])]
    gap_pages = PAPER.get('gap_answer_pages') or [gaps[i:i+16] for i in range(0, len(gaps), 16)]
    choice_pages = PAPER.get('choice_answer_pages') or [choices[i:i+10] for i in range(0, len(choices), 10)]
    for kind, pages, seconds in [('ansA', gap_pages, 40), ('ansB', choice_pages, 25)]:
        flat = [n for nums in pages for n in nums]
        want = gaps if kind == 'ansA' else choices
        require(sorted(flat) == sorted(want) and len(flat) == len(set(flat)), '答案分页须覆盖且不重复')
        for i, nums in enumerate(pages):
            if not nums:
                continue
            require(len(nums) <= (16 if kind == 'ansA' else 10), '答案每页数量过多')
            raw.append((at, {'kind': kind, 'numbers': nums, 'page': i+1, 'pages': len(pages)}))
            at += seconds
    if at == duration:
        raw.append((duration, {'kind': 'end'}))
        at += 2
    final_frames = {}
    for x,s in raw:
        f = round((x+B.LEAD)*B.FPS)
        if f in final_frames:
            old = final_frames[f][1]
            require(not (old['kind'] == s['kind'] == 'q' and old.get('n') != s.get('n')), '不同题号碰到同一帧')
            merged.append({'frame':f,'old':old,'new':s})
        final_frames[f] = (x,s)
    raw = [final_frames[f] for f in sorted(final_frames)]
    frames = [round((x + B.LEAD) * B.FPS) for x, _ in raw]
    stop = round((at + B.LEAD) * B.FPS)
    require(all(b > a for a,b in zip(frames, frames[1:] + [stop])), '存在零帧/负帧状态')
    T = {'audioEnd': duration, 'source_duration': TIMELINE['source_duration'], 'trim_start': trim}
    dump(AUDIT / '画面时间轴核验.json', {'source_duration': T['source_duration'], 'trim_start': trim, 'recording_seconds': duration, 'total_seconds': at+B.LEAD, 'frame_count': stop, 'events': len(raw), 'same_frame_boundary_merges': merged, 'answers_start': first_answer+B.LEAD, 'choice_count':len(PAPER['questions']), 'scored_choice_count':sum(not q.get('unscored') for q in PAPER['questions']), 'unscored_questions':[q['n'] for q in PAPER['questions'] if q.get('unscored')]})
    return raw, at, T


def q_by_n():
    return {q['n']: q for q in PAPER['questions']}


def page(s):
    k = s['kind']
    p = PAPER
    top = '<div class="top"><b><em>PART I</em>LISTENING COMPREHENSION</b>'
    if s.get('st'):
        top += f'<span class="st">{ESC(s["st"])}</span>'
    if 'cd' in s:
        top += f'<div class="cd"><i>{ESC(s["cdl"])}</i><span>{s["cd"]//60}:{s["cd"]%60:02d}</span></div>'
    top += '</div>'
    if k == 'title':
        top = ''
        body = f'<div class="ttl blk"><h1>TEST FOR ENGLISH MAJORS ({p["year"]})</h1><h2>-GRADE EIGHT-</h2><div class="pt"><span>PART I</span><span>LISTENING COMPREHENSION</span><span>({p.get("minutes",25)} MIN)</span></div><div class="zh">{ESC(p["title"])}</div><div class="note">原题原音</div><div class="note">请备好纸笔作答，参考答案将在考试结束后给出。</div></div>'
    elif k == 'instr':
        sec = next(x for x in p['sections'] if x['id'] == s['sec'])
        lines = s.get('lines', sec['lines'])
        hi = s.get('hi', -1)
        text = ' '.join(f'<s class="{"on" if i==hi else ""}">{ESC(x)}</s>' for i,x in enumerate(lines))
        body = f'<div class="main"><div class="sec blk">{ESC(sec["title"])}</div><div class="instr blk">{text}</div></div>'
    elif k == 'sheet':
        rows = SHEET_PAGES[s.get('page', 0)]['rows']
        title = next((x[1] for x in rows if x[0] == 'title'), p.get('sheet_title', 'Mini-lecture'))
        title += f'　({s.get("page",0)+1}/{len(SHEET_PAGES)})'
        cols, cur = [], []
        for it in rows:
            if it[0] == 'title':
                continue
            if it[0] == 'col':
                cols.append(cur);cur=[];continue
            cur.append(f'<div class="ln {it[0]}">{B.gaps(it[1])}</div>')
        cols.append(cur)
        body = f'<div class="main"><div class="sheet blk"><div class="t">{ESC(title)}</div><div class="cols">'+''.join('<div class="col">'+''.join(c)+'</div>' for c in cols)+'</div></div></div>'
    elif k == 'plist':
        group = next(g for g in p['groups'] if g['id'] == s['group'])
        label=f'　({s["display_page"]}/{s["display_pages"]})' if s.get('display_pages',1)>1 else ''
        rows = []
        for n in s.get('numbers', group['questions']):
            q = q_by_n()[n];o=q['options']
            rows.append(f'<div class="qg"><div class="r"><span class="n">{n}.</span>'+''.join(f'<span class="opt"><b class="opt-label">{"ABCD"[j]}.</b><span class="option-text">{ESC(o[j])}</span></span>' for j in (0,1))+'</div><div class="r"><span></span>'+''.join(f'<span class="opt"><b class="opt-label">{"ABCD"[j]}.</b><span class="option-text">{ESC(o[j])}</span></span>' for j in (2,3))+'</div></div>')
        # 选项卡保留题组标题；完整正式说明原音/说明页保留，不在每次循环卡上重复整段。
        intro = f'<div class="inst2 blk">{ESC(group["intro"])}</div>' if group.get('intro') and p.get('show_group_instructions',False) else ''
        body = f'<div class="main pl"><div class="sec blk">{ESC(group["title"]+label)}</div>{intro}<div class="blk">'+''.join(rows)+'</div></div>'
    elif k == 'q':
        q = q_by_n()[s['n']]
        stem = q.get('stem') or 'Listen to the question in the recording.'
        body = f'<div class="main"><div class="qn blk">Question {q["n"]}</div><div class="stem blk">{ESC(stem)}</div><div class="ql blk">'+''.join(f'<div class="opt one"><b>{"ABCD"[j]}.</b><span>{ESC(v)}</span></div>' for j,v in enumerate(q['options']))+'</div></div>'
        if q.get('unscored'):
            note = f'<div class="source-note blk">题源表述存疑，本题不计分。{ESC(q["source_note"])}</div>'
            body=body[:-6]+note+'</div>'
    elif k == 'end':
        body = '<div class="main"><div class="end blk"><h1>This is the end of<br>PART I LISTENING COMPREHENSION.</h1><p>听力考试结束，请放下笔。下面是参考答案。</p></div></div>'
    elif k == 'ansA':
        top = top.replace('</b>', '</b><span class="st">参考答案：Mini-lecture</span>', 1)
        rows = []
        for n in s['numbers']:
            a = p['gap_answers'][n-1]
            m = re.match(r'(.*?)(（.*）)?$', a)
            note = f'<span class="zh">{ESC(m[2])}</span>' if m[2] else ''
            rows.append(f'<div class="qg"><span class="n">({n})</span><span class="a">{ESC(m[1])}</span>{note}</div>')
        nr = math.ceil(len(rows)/2)
        body = f'<div class="main"><div class="sec blk">KEY　MINI-LECTURE</div><div class="ans blk" style="grid-template-rows:repeat({nr},auto)">'+''.join(rows)+'</div></div>'
    elif k == 'ansB':
        top = top.replace('</b>', '</b><span class="st">参考答案：Listening</span>', 1)
        nums = s['numbers'];mid=math.ceil(len(nums)/2)
        # 每列自上而下递增，保持2025版左右两栏排列。
        interleaved = [x for pair in zip(nums[:mid], nums[mid:]+[None]*(2*mid-len(nums))) for x in pair if x is not None]
        rows = []
        for n in interleaved:
            q=q_by_n()[n];a=q['answer'];answer=q['options']['ABCD'.index(a)] if a else '答案待核';a=a or '—'
            if q.get('unscored'):
                a='—';answer='题源存疑·不计分。'+q['source_note']
            rows.append(f'<div class="qg"><span class="n">{n}.</span><b>{a}</b><span class="answer-text">{ESC(answer)}</span></div>')
        body = '<div class="main"><div class="sec blk">KEY　LISTENING COMPREHENSION</div><div class="ansb blk">'+''.join(rows)+'</div></div>'
    else:
        raise ValueError('未知画面类型：'+k)
    css = BASE_CSS.replace('FL/', B.FL.as_uri() + '/')
    style = p.get('sheet_style', {})
    if style:
        fs = style.get('font_size', 37); lh = style.get('line_height', 46); gap = style.get('heading_gap', 18)
        require(32 <= fs <= 37 and lh >= fs*1.1 and 4 <= gap <= 18, '答题卡缩放超出可读下限，须分sheets而不能继续缩字')
    preview_style = p.get('preview_style', {})
    if preview_style:
        fs = preview_style.get('font_size', 36)
        lh = preview_style.get('line_height', 48)
        require(30 <= fs <= 40 and lh >= fs*1.15, '选项预览字号超出可读下限，须分预览页')
    # 历史题长度不同：先尝试2025默认；不适配才按浏览器实测从最大字号逐级调整。
    # 只有明确标注的历史长选项允许自然换行，整个画面/边框/块重叠检查仍完整执行。
    css += '.source-note{font-family:"Noto Serif SC";font-size:28px;line-height:40px;margin-top:20px}.answer-text{min-width:0}'
    css += '.ln,.stem,.ql .opt,.pl .r,.inst2,.instr,.ansb .qg,.ans .qg,.ttl{word-spacing:.05em;font-kerning:none}.pl .r{grid-template-columns:92px minmax(0,1fr) minmax(0,1fr);column-gap:44px}.pl .opt{display:flex;column-gap:18px;align-items:flex-start}.pl .opt-label{flex:0 0 1.1em;margin-right:0}.pl .option-text{min-width:0;flex:1}.ql .opt{column-gap:24px}.ql .opt b{margin-right:0}'
    if DRAFT:
        body += '<div style="position:absolute;left:90px;bottom:9px;font:22px Noto Serif SC;color:#666">待核样片 · 非成品</div>'
    css = "@import url('"+(ROOT/'四级/tools/fonts/fonts.css').as_uri()+"');" + css
    return '<!doctype html><html><head><meta charset="utf-8"><style>'+css+'</style></head><body>'+top+body+'</body></html>'


# 保留2025所有越界、重叠、禁断字等检查；仅对已经显式开启多行的长选项更新单行规则。
CHECK_JS = B.CHECK_JS.replace("if (e.getBoundingClientRect().height > lh * 1.6 + 8)", "if (!e.classList.contains('allow-wrap') && e.getBoundingClientRect().height > lh * 1.6 + 8)")
CHECK_JS = CHECK_JS.replace("if (rs.length > 1)", "if (!e.classList.contains('allow-wrap') && rs.length > 1)")


FIT_JS = r'''(kind) => {
 const setcss = css => { let e=document.getElementById('history-fit'); if(!e){e=document.createElement('style');e.id='history-fit';document.head.appendChild(e);}e.textContent=css; };
 const rectok = () => {
   for(const box of document.querySelectorAll('.main,.sheet')) {
     const b=box.getBoundingClientRect(), m=box.classList.contains('sheet')?14:-.5;
     for(const e of box.querySelectorAll('*')) {const r=e.getBoundingClientRect();if(r.width&&r.height&&(r.bottom>b.bottom-m||r.right>b.right-m||r.left<b.left+m))return false;}
   }
   return true;
 };
 const one = () => [...document.querySelectorAll('.opt,.pl .r > span,.ansb .qg')].every(e=>{
   const r=e.getBoundingClientRect(),c=getComputedStyle(e),lh=parseFloat(c.lineHeight)||parseFloat(c.fontSize)*1.3;
   return e.getClientRects().length<=1&&r.height<=lh*1.6+8;
 });
 const mark=sel=>document.querySelectorAll(sel).forEach(e=>e.classList.add('allow-wrap'));
 if(!['q','plist','sheet'].includes(kind)&&rectok()&&one())return {mode:'2025-default'};
 if(kind==='q') {
   mark('.ql .opt');
   for(let fs=80;fs>=56;fs--) {
     const stem=Math.min(84,fs+4),lh=fs*1.32;
     setcss(`.qn{margin-bottom:18px}.stem{font-size:${stem}px;line-height:1.2;margin-bottom:26px}.ql .opt{font-size:${fs}px;line-height:${lh}px;padding:9px 0;align-items:flex-start}.ql .opt>span{flex:1;min-width:0}.ql .opt b{width:76px}.source-note{margin-top:14px}`);
     if(rectok())return {mode:'question-wrap',font_size:fs,line_height:lh,stem_font_size:stem};
   }
 } else if(kind==='plist') {
   mark('.pl .opt,.pl .r > span,.inst2');
   for(let fs=52;fs>=44;fs--) {
     const lh=fs*1.28;
     setcss(`.pl .sec{margin-bottom:24px}.pl .r{font-size:${fs}px;line-height:${lh}px}.pl .r>span{align-self:start;min-width:0}.pl .qg{padding:11px 0 12px}.pl .qg:first-child{padding-top:0}.pl .inst2{font-size:${fs}px;line-height:${lh}px;margin-bottom:20px}`);
     if(rectok())return {mode:'preview-wrap',font_size:fs,line_height:lh};
   }
 } else if(kind==='ansB') {
   mark('.ansb .qg');
   for(let fs=43;fs>=36;fs--) {
     const lh=fs*1.3;
     setcss(`.ansb .qg{font-size:${fs}px;line-height:${lh}px;white-space:normal;min-height:96px;padding:12px 0;display:grid;grid-template-columns:56px 64px minmax(0,1fr);align-items:start}.ansb b{line-height:62px;align-self:start}.ansb .answer-text{font-family:'TNR','Noto Serif SC'}`);
     if(rectok())return {mode:'answer-wrap',font_size:fs,line_height:lh};
   }
 } else if(kind==='sheet') {
   for(let fs=46;fs>=40;fs--)for(const ratio of [1.25,1.2])for(const gap of [18,12]){
     const lh=fs*ratio;
     setcss(`.ln{font-size:${fs}px;line-height:${lh}px}.ln.h{margin-top:${gap}px}.ln.h:first-child{margin-top:0}`);
     if(rectok())return {mode:'sheet-fit',font_size:fs,line_height:lh,heading_gap:gap};
   }
   // 原有换栏若明显不均，只移动完整逻辑行，保持左栏→右栏的逐字阅读顺序。
   const cols=[...document.querySelectorAll('.sheet .col')], rows=cols.flatMap(c=>[...c.children]);
   if(cols.length===2)for(let fs=46;fs>=40;fs--)for(const ratio of [1.25,1.2])for(const gap of [18,12]){
     const lh=fs*ratio;
     setcss(`.ln{font-size:${fs}px;line-height:${lh}px}.ln.h{margin-top:${gap}px}.ln.h:first-child{margin-top:0}`);
     let best=null;
     for(let n=1;n<rows.length;n++){
       if(rows[n-1].classList.contains('h'))continue;
       cols[0].replaceChildren(...rows.slice(0,n));cols[1].replaceChildren(...rows.slice(n));
       const bottom=Math.max(...cols.map(c=>c.getBoundingClientRect().bottom));
       if(rectok()&&(!best||bottom<best.bottom))best={n,bottom};
     }
     if(best){cols[0].replaceChildren(...rows.slice(0,best.n));cols[1].replaceChildren(...rows.slice(best.n));return {mode:'sheet-rebalance',font_size:fs,line_height:lh,heading_gap:gap,break_after_row:best.n};}
   }
 }
 return {mode:'unfitted'};
}'''


def fit_layout(pg, state):
    return pg.evaluate(FIT_JS, state['kind'])


SPACING_JS = r'''() => {
 const errors=[], spaces=[] , labels=[], numbers=[];
 const rr=(node,a,b)=>{const r=document.createRange();r.setStart(node,a);r.setEnd(node,b);return r.getBoundingClientRect();};
 const textrect=e=>{const r=document.createRange();r.selectNodeContents(e);return r.getBoundingClientRect();};
 for(const root of document.querySelectorAll('.ln,.stem,.ql .opt,.pl .option-text,.instr,.ansb .answer-text,.ans .a,.ttl')){
   const walk=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
   for(let node=walk.nextNode();node;node=walk.nextNode()){
     const txt=node.textContent,fs=parseFloat(getComputedStyle(node.parentElement).fontSize);
     for(let i=1;i<txt.length-1;i++){
       if(txt[i]!==' '||!/[a-z0-9]/i.test(txt[i-1])||!/[a-z0-9]/i.test(txt[i+1]))continue;
       const a=rr(node,i-1,i),sp=rr(node,i,i+1),b=rr(node,i+1,i+2);
       if(Math.abs(a.top-b.top)>2)continue;
       const em=sp.width/fs;spaces.push(em);
       if(em<.275)errors.push('英文空格过窄 '+em.toFixed(3)+'em '+txt.slice(Math.max(0,i-12),i+14));
       if(em>.55)errors.push('英文空格过宽 '+em.toFixed(3)+'em');
     }
   }
 }
 for(const opt of document.querySelectorAll('.ql .opt,.pl .opt')){
   const label=opt.querySelector('b'),body=opt.querySelector('.option-text')||opt.querySelector('span');
   if(!label||!body)continue;
   const a=textrect(label),b=textrect(body),fs=parseFloat(getComputedStyle(opt).fontSize),gap=b.left-a.right;
   labels.push(gap);if(gap<Math.max(16,fs*.28))errors.push('选项标签与正文间距不足 '+gap.toFixed(1)+'px '+opt.textContent.slice(0,25));
 }
 for(const row of document.querySelectorAll('.pl .qg>.r:first-child')){
   const n=row.querySelector('.n'),opt=row.querySelector('.opt');if(!n||!opt)continue;
   const gap=textrect(opt.querySelector('b')).left-textrect(n).right;numbers.push(gap);
   if(gap<28)errors.push('题号与选项间距不足 '+gap.toFixed(1)+'px '+row.textContent.slice(0,25));
 }
 return {errors,spaces_checked:spaces.length,min_space_em:spaces.length?Math.min(...spaces):null,max_space_em:spaces.length?Math.max(...spaces):null,min_label_gap_px:labels.length?Math.min(...labels):null,min_question_number_gap_px:numbers.length?Math.min(...numbers):null};
}'''


def original_texts(s):
    """原卷合法出现的词不能因恰与某空答案相同而被误当泄题。"""
    k=s['kind'];items=[s.get('st',''),s.get('cdl','')]
    if k=='instr':
        sec=next(x for x in PAPER['sections'] if x['id']==s['sec'])
        items += [sec['title']]+s.get('lines',sec['lines'])
    elif k=='sheet':
        rows=SHEET_PAGES[s.get('page',0)]['rows']
        items += [r[1] for r in rows if r[0]!='col']
    elif k=='plist':
        g=next(g for g in PAPER['groups'] if g['id']==s['group'])
        items += [g['title'],g.get('intro','')]
        items += [v for n in s.get('numbers',g['questions']) for v in q_by_n()[n]['options']]
    elif k=='q':
        q=q_by_n()[s['n']];items += [q.get('stem',''),q.get('source_note','')]+q['options']
    return [re.sub(r'\s+',' ',x).lower() for x in items]


def leak_check(s, htm):
    bad=B.leak_check(s,htm)
    if not bad:return []
    txt=re.sub(r'<[^>]+>',' ',htm.split('</style>',1)[1])
    txt=re.sub(r'\s+',' ',html.unescape(txt)).lower()
    source=original_texts(s);keep=[]
    for error in bad:
        phrase=error.removeprefix('答案泄露：')
        if phrase=='答案标题':
            # 原题例如“key issue”是普通用词，真正答案标题仍不能提前出现。
            expected=sum(len(re.findall(r'\bkey\b',x)) for x in source)
            if '参考答案 ·' not in txt and len(re.findall(r'\bkey\b',txt))<=expected:continue
        elif sum(x.count(phrase) for x in source)>=txt.count(phrase):
            continue
        keep.append(error)
    return keep


def question_gap_check(pg, s):
    # 单题选项“70.”等数字是答案选项内容，不是多题题号；多题画面完整沿用间隔检查。
    if s['kind']=='q':return []
    return pg.evaluate(B.QGAP_JS,B.MIN_GAP)


def trim_check(a, y, k, sr):
    import numpy as np
    bad = []
    if k != round(TIMELINE.get('trim', {}).get('start',0)*sr):
        bad.append('剪头样本与核定记录不符')
    if not np.array_equal(a[k:], y):
        bad.append('剪头以外原音样本发生变化')
    return bad


def prepare_audio(src):
    src = Path(src).resolve()
    digest = sha(src)
    expected = TIMELINE.get('trim', {}).get('source_sha256') or TIMELINE.get('source_sha256')
    require(expected and expected == digest, '原音SHA256与时间轴来源记录不符')
    decoded = B.decoded(src, OUT/'source')
    import soundfile as sf
    info = sf.info(decoded)
    require(abs(info.duration-TIMELINE['source_duration']) < .05, '原音时长与时间轴不符')
    dump(AUDIT/'原音来源核验.json', {'source':str(src),'sha256':digest,'duration':info.duration,'sample_rate':info.samplerate,'channels':info.channels,'trim':TIMELINE.get('trim',{'start':0}),'processing':'原采样率/声道/音量，仅按核定时刻剪片头音乐；片头与答案区垫数字静音。'})
    return decoded


def verify(out, t, total, fr):
    # 底座检验原音sample匹配、画面切点、帧数、前后静音；另检查编码元信息，防止先改声道/采样率再比较。
    BASE_VERIFY(out, t, total, fr)
    info = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(out)]))
    au = next(s for s in info['streams'] if s['codec_type']=='audio')
    report = read(AUDIT/'核查报告.json')
    extra = []
    if int(au['sample_rate']) != B.ORIG_SR:extra.append('成品音轨采样率改变')
    if au['channels'] != B.ORIG_REF.shape[1]:extra.append('成品音轨声道数改变')
    if extra:
        report['问题'].extend(extra);dump(AUDIT/'核查报告.json',report)
        Path(out).unlink(missing_ok=True)
        raise ValueError('；'.join(extra))
    report['原音采样率'] = int(au['sample_rate'])
    report['原音声道'] = au['channels']
    report['原音模式'] = True
    report['剪头秒'] = TIMELINE.get('trim', {}).get('start',0)
    report['基线兼容'] = '2025白纸黑字、4K30fps、考试过程与答案呈现；新音频遵守更晚铁律25，不沿用2025旧整体增益。'
    report['选择题数'] = len(PAPER['questions'])
    report['选择题计分题数'] = sum(not q.get('unscored') for q in PAPER['questions'])
    report['总计分题数'] = len(PAPER['gap_answers'])+report['选择题计分题数']
    report['不计分题源说明'] = [{'n':q['n'],'source_answer':q['answer'],'source_note':q['source_note']} for q in PAPER['questions'] if q.get('unscored')]
    report['source_fingerprints'] = fingerprints()
    report['成品sha256'] = sha(out)
    dump(AUDIT/'核查报告.json',report)



@contextmanager
def serving():
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def end_headers(self):
            if urlparse(self.path).path.endswith('.html'):
                self.send_header('Cache-Control', 'no-store, max-age=0')
                self.send_header('Pragma', 'no-cache')
            super().end_headers()

        def translate_path(self, path):
            path = unquote(urlparse(path).path)
            for prefix, root in [('/project/', ROOT), ('/render/', OUT)]:
                if path.startswith(prefix):
                    target = (root / path[len(prefix):]).resolve()
                    if target.is_relative_to(root.resolve()):
                        return str(target)
            return '/dev/null'
    server = http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()


def render(sample=False, layout_only=False):
    # 与底座stills相同的所有关卡，明确指定实际可用的浏览器路径。
    from playwright.sync_api import sync_playwright
    l, total, t = states()
    todo = {B.key(s):s for _,s in l}
    if sample:
        chosen = {}
        for key,s in todo.items():
            typ = (s['kind'],bool('cd' in s),s.get('sec'),s.get('group'),s.get('page'),s.get('display_page'),s.get('n'))
            if typ not in chosen:
                chosen[typ]=(key,s)
        todo=dict(chosen.values())
    shots = OUT/'shots';shots.mkdir(exist_ok=True)
    errors, fitted = [], []
    with serving() as base, sync_playwright() as pw:
        exe = shutil.which('chromium') or ('/opt/pw-browsers/chromium' if Path('/opt/pw-browsers/chromium').exists() else None)
        br = pw.chromium.launch(executable_path=exe,args=['--no-sandbox'])
        pager = B.Pager(br,viewport={'width':1920,'height':1080},device_scale_factor=2)
        for key,s in todo.items():
            htm=page(s);tmp=OUT/(key+'.html')
            http_html=htm.replace(ROOT.as_uri()+'/',base+'/project/').replace(OUT.as_uri()+'/',base+'/render/').replace('<body>',f'<body data-render-key="{key}">')
            tmp.write_text(http_html,'utf-8')
            pg=pager.load(base+'/render/'+tmp.name)
            require(pg.locator('body').get_attribute('data-render-key')==key,'浏览器展示了过期页面')
            fit=fit_layout(pg,s)
            spacing=pg.evaluate(SPACING_JS)
            fitted.append({'state':s,'fit':fit,'spacing':spacing})
            bad=pg.evaluate(CHECK_JS)+question_gap_check(pg,s)+B.font_check(pg,pager.cdp)+leak_check(s,htm)+spacing['errors']
            if bad:
                errors.append({'state':s,'errors':sorted(set(bad))})
                pg.screenshot(path=str(shots/(key+'.bad.png')))
                continue
            if not layout_only:
                png=shots/(key+'.png');pg.screenshot(path=str(png))
                c=B.color_check(png)
                if c:errors.append({'state':s,'errors':[c]})
        br.close()
    dump(AUDIT/'排版核验.json',{'states_checked':len(todo),'sample':sample,'problems':errors,'fitted_layouts':fitted,'source_fingerprints':fingerprints(),'draft':DRAFT})
    require(not errors, f'排版/字体/答案检查发现{len(errors)}个问题，详见{AUDIT/"排版核验.json"}')
    print('排版检查0处',len(todo),'屏',flush=True)


def convert_2025(target):
    p=read(LISTEN/'2025/题目.json');t=read(LISTEN/'2025/时间轴.json')
    paper={'year':2025,'title':'2025年 专八听力 考试','minutes':25,'sections':[{'id':'A','title':'SECTION A　MINI-LECTURE','lines':p['instrA'][:6]},{'id':'B','title':'SECTION B　INTERVIEW','lines':p['instrB']}],'sheet':p['sheet'],'gap_answers':p['gap_answers'],'questions':[{'n':i+1,'stem':q[0],'options':q[1],'answer':q[2],'group':'part1' if i<5 else 'part2'} for i,q in enumerate(p['questions'])],'groups':[{'id':'part1','title':'SECTION B　INTERVIEW: PART ONE','intro':'Now, listen to Part One of the interview. Questions 1 to 5 are based on Part One of the interview.','questions':list(range(1,6))},{'id':'part2','title':'SECTION B　INTERVIEW: PART TWO','intro':'Now, listen to Part Two of the interview. Questions 6 to 10 are based on Part Two of the interview.','questions':list(range(6,11))}]}
    # 直接转换已核时间轴，不重新识别或推导2025。
    events=[]
    for sec in ['A','B']:
        events.append({'t':t['sec'+sec],'kind':'instr','sec':sec,'hi':-1})
        for i,x in enumerate(t['instr'+sec]):
            if sec=='B' and i==6:continue
            events.append({'t':x,'kind':'instr','sec':sec,'hi':i})
    events += [{'t':t['previewA'][0],'kind':'sheet','st':'预览答题卡','countdown':{'end':t['previewA'][1],'label':'预览'}},{'t':t['nowA'],'kind':'sheet','st':'Mini-lecture 即将开始，只放一遍'},{'t':t['lecture'],'kind':'sheet','st':'Mini-lecture 播放中，只放一遍'},{'t':t['checkSay'],'kind':'sheet','st':'Mini-lecture 结束，检查时间三分钟'},{'t':t['check'][0],'kind':'sheet','st':'检查答案','countdown':{'end':t['check'][1],'label':'检查'}},{'t':t['check'][1],'kind':'sheet','st':'Section A 结束'}]
    events += [{'t':t['instrB'][6],'kind':'plist','group':'part1','st':'预览 Part One 选项'},{'t':t['previewB'][0],'kind':'plist','group':'part1','st':'预览 Part One 选项','countdown':{'end':t['previewB'][1],'label':'预览'}}]
    for part in [1,2]:
        events += [{'t':t['part'+str(part)],'kind':'plist','group':'part'+str(part),'st':'采访即将开始'},{'t':t['int'+str(part)],'kind':'plist','group':'part'+str(part),'st':'采访播放中'},{'t':t['part'+str(part)+'End'],'kind':'plist','group':'part'+str(part),'st':'采访结束，即将念题'}]
    starts=[t['q1']]+[v[1] for v in t['pauses'][:4]]+[t['q6']]+[v[1] for v in t['pauses'][5:9]]
    for i,((a,b),x) in enumerate(zip(t['pauses'],starts),1):
        events += [{'t':x,'kind':'q','n':i,'st':'念题'},{'t':a,'kind':'q','n':i,'st':'请在答题纸上作答','countdown':{'end':b,'label':'作答'}}]
    events.append({'t':t['endB'],'kind':'end'})
    timeline={'source_duration':t['audioEnd'],'source_sha256':'e7973102a3bba6358bc97e4a32af7efb20e1a871cbc8921fb8b325444bb7e1c7','trim':{'start':0},'events':sorted(events,key=lambda e:e['t'])}
    validate(paper,timeline)
    target=Path(target);dump(target/'试卷.json',paper);dump(target/'时间轴.json',timeline)
    print('2025已核数据转换完成',target,flush=True)


def selftest():
    with tempfile.TemporaryDirectory(prefix='tem8-exam-schema-') as td:
        convert_2025(td);p=read(Path(td)/'试卷.json');t=read(Path(td)/'时间轴.json')
        configure(td,Path(td)/'out');l,total,meta=states()
        require(len(p['gap_answers'])==15 and len(p['questions'])==10,'2025转换数量不符')
        require(l[-2][1]['kind']=='ansA' and l[-1][1]['kind']=='ansB','答案屏转换错误')
        require(0 <= total-(t['source_duration']+65) <= 1/B.FPS,'2025答案时长不符')
        require(l[-2][0] >= meta['audioEnd'],'答案不得早于录音结束')
        require(len(SHEET_PAGES) in (2,3),'大字卡片未完整分2/3页')
        require(all([n for sub in PREVIEW_PAGES[g['id']] for n in sub]==g['questions'] for g in PAPER['groups']),'预览翻页漏题/错序')
        preview=[e for e in paginated_events() if e['kind']=='sheet' and e.get('st')=='预览答题卡']
        require(sorted(e['page'] for e in preview)==list(range(len(SHEET_PAGES))),'30秒预览未覆盖卡片全部页')
        require(len({e['countdown']['end'] for e in preview})==1,'翻页重置了绝对倒计时')
        tests=[]
        x=copy.deepcopy(t);x['events'][0]['kind']='ansA';tests.append((p,x,'提前答案'))
        x=copy.deepcopy(t);x['events'][2]['t']=-1;tests.append((p,x,'时间倒序/越界'))
        x=copy.deepcopy(t);x['trim']={'start':20,'reason':'删除正式说明'};tests.append((p,x,'未授权剪说明'))
        x=copy.deepcopy(p);x['gap_answers']=x['gap_answers'][:-1];tests.append((x,t,'空号与答案不符'))
        x=copy.deepcopy(p);x['questions'][0]['answer']='E';tests.append((x,t,'答案字母越界'))
        x=copy.deepcopy(p);x['pending']=['源卷与原音待核'];tests.append((x,t,'未核数据制作门禁'))
        x=copy.deepcopy(p);x['questions'][0]['unscored']=True;tests.append((x,t,'不计分题缺题源说明'))
        for pp,tt,name in tests:
            try:validate(pp,tt)
            except (ValueError,KeyError,TypeError):print('已拦截',name)
            else:raise AssertionError('未拦截：'+name)
        marked=copy.deepcopy(p);marked['questions'][1].update(unscored=True,source_note='源题地名与正文冲突。')
        dump(Path(td)/'试卷.json',marked);configure(td,Path(td)/'marked');states()
        require('题源表述存疑，本题不计分' in page({'kind':'q','n':2}),'单题缺不计分标记')
        require('题源存疑·不计分' in page({'kind':'ansB','numbers':list(range(1,11))}),'答案页缺不计分标记')
        require(read(AUDIT/'画面时间轴核验.json')['scored_choice_count']==9,'计分题数未排除题源问题')
        # 真实旧题型数量可变：以10空/20选择的结构样本验证，文字明确是schema测试而非历史定稿。
        oldp=copy.deepcopy(p);oldp['year']=2010;oldp['sheet']=[['title','Schema test'],['b',' '.join('{'+str(i)+'}' for i in range(1,6))],['col'],['b',' '.join('{'+str(i)+'}' for i in range(6,11))]];oldp['gap_answers']=['test answer']*10
        oldp['questions']=[copy.deepcopy(q) for q in p['questions']]+[dict(copy.deepcopy(q),n=q['n']+10) for q in p['questions']]
        oldp['groups']=[{'id':'g'+str(j),'title':'SCHEMA TEST','questions':list(range(j*5+1,j*5+6))} for j in range(4)]
        oldt=copy.deepcopy(t);oldt['events']=[{'t':i,'kind':'q','n':i} for i in range(1,21)]
        validate(oldp,oldt)
        dump(Path(td)/'试卷.json',oldp);dump(Path(td)/'时间轴.json',oldt);configure(td,Path(td)/'old');l,_,_=states()
        require(sum(s['kind']=='ansB' for _,s in l)==2,'20题答案分页错误')
        print('自检通过：2025转换、大字分页无漏/无倒计时重置、动态题数、答案分页、不计分题源标记、7项错误注入。')


def layout_selftest():
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory(prefix='tem8-exam-layout-test-') as td:
        convert_2025(td)
        configure(td,Path(td)/'out')
        good={'kind':'q','n':7,'st':'作答','cd':7,'cdl':'作答'}
        sheet={'kind':'sheet','st':'检查答案','cd':125,'cdl':'检查'}
        plist={'kind':'plist','group':'part2','numbers':[6,7,8],'display_page':2,'display_pages':2,'st':'选项预览'}
        with serving() as base,sync_playwright() as pw:
            br=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
            pager=B.Pager(br,viewport={'width':1920,'height':1080},device_scale_factor=1)
            attempt = [0]
            def check(htm,state):
                attempt[0] += 1
                htm=htm.replace(ROOT.as_uri()+'/',base+'/project/').replace(OUT.as_uri()+'/',base+'/render/')
                (OUT/'page.html').write_text(htm,'utf-8')
                pg=pager.load(base+'/render/page.html?attempt='+str(attempt[0]))
                fit_layout(pg,state)
                return pg.evaluate(CHECK_JS)+question_gap_check(pg,state)+B.font_check(pg,pager.cdp)+leak_check(state,htm)+pg.evaluate(SPACING_JS)['errors']
            for state in [good,sheet,plist,{'kind':'ansA','numbers':list(range(1,16))}]:
                bad=check(page(state),state)
                require(not bad,'正常画面被错误拦截：'+str(bad[:3]))
            PAPER['questions'][0].update(unscored=True,source_note='源题地名与正文冲突，本题不计分。')
            for state in [{'kind':'q','n':1},{'kind':'ansB','numbers':list(range(1,11))}]:
                require(not check(page(state),state),'不计分标注屏排版失败')
            PAPER['questions'][0].pop('unscored');PAPER['questions'][0].pop('source_note')
            negatives=[
                ('超长选项',page(good).replace('Mountain climbing.','Mountain climbing. '*35),good,None),
                ('答题卡泄露答案',page(sheet).replace('<div class="sheet blk">','<div class="sheet blk"><div>long-term memory</div>'),sheet,'答案泄露'),
                ('题间距/细线缺失',page(plist).replace('class="qg"','class="missing-group"'),plist,None),
                ('未知字体字形',page(good).replace('Question 7','Question 7 𝄞 ꙮ'),good,'字体回退'),
                ('英文词间距压缩',page(good).replace('</style>','.ql .opt{word-spacing:-.2em!important}</style>'),good,'英文空格过窄'),
                ('标签正文贴合',page(good).replace('</style>','.ql .opt b{width:auto!important}.ql .opt{column-gap:0!important}</style>'),good,'选项标签与正文间距不足'),
                ('预览题号贴合',page(plist).replace('</style>','.pl .r{grid-template-columns:25px minmax(0,1fr) minmax(0,1fr);column-gap:0}</style>'),plist,'题号与选项间距不足'),
            ]
            for name,htm,state,match in negatives:
                bad=check(htm,state)
                require(bool(bad) and (not match or any(match in x for x in bad)),'排版负例未拦截：'+name)
                print('已拦截',name,bad[:1],flush=True)
            htm=page(good).replace('</body>','<div style="position:absolute;left:5px;top:5px;width:30px;height:30px;background:#c00"></div></body>')
            check(htm,good)
            png=OUT/'red.png';pager.pg.screenshot(path=str(png))
            require(bool(B.color_check(png)),'彩色像素负例未拦截')
            print('已拦截彩色像素',flush=True)
            # 原卷原本出现别空答案短语允许保留，再多插入一次仍须报泄题。
            PAPER['sheet'][1][1]+=' long-term memory'
            require(not check(page(sheet),sheet),'原卷合法同词被误报泄题')
            extra=page(sheet).replace('<div class="sheet blk">','<div class="sheet blk"><div>long-term memory</div>')
            require(any('答案泄露' in x for x in check(extra,sheet)),'原卷合法同词导致额外泄题漏检')
            print('已拦截原卷合法同词后的额外答案泄露',flush=True)
            br.close()
        print('浏览器自检通过：含不计分/原卷合法同词的7个正常屏和9项错误注入。',flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('folder',nargs='?');ap.add_argument('command',nargs='?',choices=['layout','stills','audio','video','verify','schema'])
    ap.add_argument('--自检-排版',dest='layout_selftest',action='store_true');ap.add_argument('--draft',action='store_true');ap.add_argument('--out');ap.add_argument('--audio');ap.add_argument('--sample',action='store_true');ap.add_argument('--fast',action='store_true');ap.add_argument('--自检',action='store_true');ap.add_argument('--convert-2025')
    a=ap.parse_args()
    if a.layout_selftest:return layout_selftest()
    if a.自检:return selftest()
    if a.convert_2025:return convert_2025(a.convert_2025)
    require(a.folder and a.command,'需要年度文件夹和命令')
    require(not a.draft or a.command=='schema' or (a.command in ['layout','stills'] and a.sample), '--draft仅允许结构检查或带水印样片；不能制作音轨/视频/全套截图')
    configure(a.folder,a.out or str(Path(a.folder)/'输出'),draft=a.draft)
    states()
    if a.command=='schema':print('schema/时间轴检查通过');return
    if a.command in ['layout','stills']:return render(sample=a.sample,layout_only=a.command=='layout')
    src=a.audio or TIMELINE.get('audio')
    require(src,'audio/video命令需要--audio原音路径')
    wav=prepare_audio(src)
    if a.command=='audio':return B.audio_check(wav)
    # 正式视频必须有完整排版通过记录，以及对应源码生成的全部截图。
    record=read(AUDIT/'排版核验.json')
    require(not record['sample'] and not record['problems'] and not record.get('draft'),'正式编码前须完整stills检查通过')
    require(record.get('source_fingerprints')==fingerprints(),'试卷/时间轴/程序已变，须重新stills核验')
    if a.command=='verify':
        l,total,t,nfr,sr=B.audio_track(wav)
        frames=[(round((x+B.LEAD)*B.FPS),B.key(s)) for x,s in l]
        return verify(OUT/B.NAME,t,total,frames)
    return B.video(wav,fast=a.fast)


if __name__=='__main__':
    main()
