"""从已提取解析生成听力正文候选，不翻译、不宣布原文已核定。

保留来源页、原始行与清理过程；仅清理参考定位号、下划线和可确认跨行断字。
正文边界不明确或含OCR异常时列待核；题干候选独立，不假定录音确实读出。
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

D=Path(__file__).resolve().parents[1]
OUT=D/'原文候选'
LEX=Path('/workspace/tem8-ocr-tessdata/words_alpha.txt')
YEARS=list(range(2009,2020))+list(range(2021,2025))


def flat(s):return re.sub('[^A-Za-z0-9]','',s).upper()


def group_heading(s):
    t=flat(s)
    m=re.match(r'^(?:PART|INTERVIEW)(ONE|TWO|1|2)(?:OFTHEINTERVIEW)?$',t)
    if m:return 1 if m[1] in ['ONE','1'] else 2
    return None


def clean(lines,lex):
    s='\n'.join(lines)
    s=s.replace('\xad\n','').replace('\xad','')
    # 只有完整拼合词在词典中才复原跨行断字，其他连字符保留并列待核。
    def join(m):return m[1]+m[2] if (m[1]+m[2]).lower() in lex else m[1]+'-'+m[2]
    s=re.sub(r'([A-Za-z]+)-\s*\n\s*([a-z]+)',join,s)
    s=re.sub(r'\[(?:\d{1,2}|[lI])(?:\]|J|\})','',s)
    s=s.replace('_',' ')
    return re.sub(r'\s+',' ',s).strip()


def run(year,lex):
    source=D/'来源'/str(year)/'解析.txt';ls=source.read_text('utf-8').splitlines()
    page=0;rows=[]
    for i,s in enumerate(ls):
        m=re.search(r'=== 原PDF第(\d+)页',s)
        if m:page=int(m[1]);continue
        if not page:continue
        # 书页页脚/标题，不属于讲话内容。
        if re.search(r'20\d{2}',s) and len(s)<50 and len(re.findall('[A-Za-z]',s))<8:continue
        rows.append({'line':i+1,'page':page,'text':s})
    groups=[(i,group_heading(r['text'])) for i,r in enumerate(rows) if group_heading(r['text'])]
    if year==2009 and len(groups)==1:
        # 页图核对：原解析第4页蓝色Part Two被OCR漏掉，首句锚点在原页中唯一。
        hits=[i for i,r in enumerate(rows) if re.search(r'Then.{0,5}how does Toastmasters train people',r['text'],re.I)]
        if len(hits)==1:groups.append((hits[0]-1,2))
    pending=[]
    if len(groups)!=2:pending.append(f'解析正文分组标题识别到{len(groups)}个，应核访谈分段边界。')
    first_group=groups[0][0] if groups else len(rows)
    starts=[i for i,r in enumerate(rows[:first_group]) if re.search(r'Good\s*mo(?:rn|m)ing|Good\s*afternoon|Good\s*evening|Hello,?\s+everyone',r['text'],re.I)]
    if not starts:
        pending.append('未定位讲座开头问候，需核正文边界。');lecture_start=0
    else:lecture_start=starts[0]
    title_candidates=[r['text'].strip() for r in rows[max(0,lecture_start-5):lecture_start]
                      if len(re.findall('[A-Za-z]+',r['text']))>=2 and not re.search('[\u4e00-\u9fff]',r['text']) and 'SECTION' not in r['text'].upper() and 'LISTENING' not in r['text'].upper()]
    title=title_candidates[-1] if title_candidates else f'{year} Mini-Lecture'
    bounds=[('A','Section A',title,lecture_start,first_group)]
    for j,(start,n) in enumerate(groups):
        end=groups[j+1][0] if j+1<len(groups) else len(rows)
        bounds.append((f'B{n}',f'Section B Part {"One" if n==1 else "Two"}',f'Interview {n}',start+1,end))
    units=[];questions=[]
    for uid,section,title,a,b in bounds:
        body=[];paras=[];para=[];pages=set();start_line=None;end_line=None;cut_reason=None
        for local_i,row in enumerate(rows[a:b]):
            s=row['text'].strip();t=flat(s)
            if t in ['SECTIONA','SECTIONB','PARTILISTENINGCOMPREHENSION']:continue
            following=next((r['text'].strip() for r in rows[a+local_i+1:b] if r['text'].strip()),'')
            if re.match(r'^\s*\d{1,2}[.、]\s*\S',s) and (uid!='A' or len(re.findall('[\u4e00-\u9fff]',following))>=3 or '//' in s):
                cut_reason='答案或题干编号开始';break
            if '?' in s and len(re.findall('[\u4e00-\u9fff]',following))>=3:
                cut_reason='题干后紧接中文解析（原编号可能被OCR遗漏）';break
            if len(re.findall('[\u4e00-\u9fff]',s))>=3:cut_reason='中文解析开始';break
            if not s:
                if para:paras.append(clean(para,lex));para=[]
                continue
            if s.startswith('===') or not re.search('[A-Za-z]',s):continue
            if not body and len(re.findall('[A-Za-z]+',s))<3:continue
            # 换说话人另起段；保留原标记，不猜性别或修正I/1等OCR歧义。
            if re.match(r'^(?:[MWIDT]|Interviewer|Interviewee|\([MWIDT1]\))\s*[:：]',s,re.I) and para:
                paras.append(clean(para,lex));para=[]
            para.append(s);body.append(row);pages.add(row['page'])
            if start_line is None:start_line=row['line']
            end_line=row['line']
        if para:paras.append(clean(para,lex))
        en='\n\n'.join(p for p in paras if p)
        qstarts=[(j,r) for j,r in enumerate(rows[a:b]) if uid!='A' and re.match(r'^\s*\d{1,2}[.、]\s*\S',r['text']) and '?' in r['text'] and not re.search('[\u4e00-\u9fff]',r['text'])]
        for j,r in qstarts:
            s=r['text'].strip();m=re.match(r'^(\d{1,2})[.、]\s*(.+)',s)
            if m:questions.append({'n':int(m[1]),'en':clean([m[2]],lex),'page':r['page'],'source_line':r['line'],'status':'解析中的题干候选，须与实际录音核对是否朗读及是否完整。'})
        # 非词典词仅提示，不自动改正专名、词形或OCR错误。
        words=re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?",en)
        unknown=list(dict.fromkeys(w for w in words if len(w)>=4 and w.lower() not in lex and w.lower().rstrip('s') not in lex))
        issues=[]
        if len(words)<60:issues.append('正文候选异常短，应重新核边界，不能据此认为原文完整。')
        if re.search('[\u4e00-\u9fff]',en):issues.append('候选英文含汉字，可能为OCR标点或混入解析，须逐处核页图。')
        if re.search(r'\[[^\]]|\d+\]|[A-Za-z]_[A-Za-z]',en):issues.append('有未闭合定位标记或OCR符号，须核源页。')
        if not cut_reason:issues.append('末尾未检出明确题干/答案边界，须核正文末句。')
        info=json.loads((D/'来源'/str(year)/'来源选择.json').read_text())['analysis']
        units.append({'id':f'{year}-{uid}','section':section,'title':title,'paragraphs':paras,'en':en,
          'source_refs':[{'file':info['file'],'sha256':info['sha256'],'pages':sorted(pages),'extracted_text':str(source.relative_to(D)),'source_lines':[start_line,end_line]}],
          'raw_lines':body,'boundary_stop':cut_reason,'word_count':len(words),'unknown_words_for_check':unknown,
          '待核':issues+['候选尚未逐句对照页图和实际录音，不代表定稿原文。']})
    result={'year':year,'status':'unreviewed_candidate','version_note':'所供新题型优化版；按实际配套录音核定。' if year<=2015 else '所供本年听力解析；录音配套关系由后续核音确认。',
      'normalizations':['剔除可辨的方括号参考定位编号（不剔除正文数字）','清理下划线与软换行','词典可确认的跨行断字复原；不猜改生词或专名'],
      'units':units,'question_stems_candidates':questions,'待核':pending}
    OUT.mkdir(exist_ok=True)
    (OUT/f'{year}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    return {'year':year,'units':[(u['id'],u['word_count'],u['source_refs'][0]['pages']) for u in units],'pending':pending}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dictionary',type=Path,default=LEX,help='英文词表路径；首次可先运行解析提取.py自动下载words_alpha.txt。')
    ap.add_argument('--years',type=int,nargs='+',default=YEARS)
    args=ap.parse_args();LEX=args.dictionary
    lex=set(LEX.read_text('utf-8').splitlines())
    for year in args.years:
        if (D/'来源'/str(year)/'解析.txt').exists():print(json.dumps(run(year,lex),ensure_ascii=False),flush=True)
