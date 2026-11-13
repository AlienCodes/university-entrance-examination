"""只提取专八原卷和解析中的听力页，保留页码、来源和OCR不确定性。

python 解析提取.py [--years 2009 2012 ...] [--workers 2] [--tessdata PATH]
原始资料须先按原始材料清单提取到 /workspace/tem8-input（可用 --input 改变）。
需系统pdftotext、tesseract与Python pymupdf；指定tessdata目录含eng与chi_sim模型。
英文词典缺失时从明示的公开来源下载；词典及OCR模型为工具依赖，非原始试卷材料。
不把教材的“新题型优化”视为当年原始试题；录音关联须由后续ASR与人工核对。
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import fitz

D = Path(__file__).resolve().parents[1]
YEARS = list(range(2009, 2020)) + list(range(2021, 2025))
OUT = D / '来源'
TESSDATA = Path('/workspace/tem8-ocr-tessdata')
DICT_PATH=TESSDATA/'words_alpha.txt'
DICT_URL='https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt'


def dictionary_quality(text):
    if not DICT_PATH.exists():
        import urllib.request
        TESSDATA.mkdir(parents=True,exist_ok=True)
        urllib.request.urlretrieve(DICT_URL,DICT_PATH)
    lexicon=set(DICT_PATH.read_text('utf-8').splitlines())
    sample=re.sub(r'(?<=[A-Za-z])[-\xad]\s*\n\s*(?=[a-z])','',text)
    ws=re.findall(r'[a-z]{3,}',sample.lower())
    bad=[w for w in ws if w not in lexicon and w.rstrip('s') not in lexicon]
    return {'checked_words':len(ws),'dictionary_ratio':round(1-len(bad)/max(len(ws),1),5),
            'threshold':0.95,'unknown_examples':list(dict.fromkeys(bad))[:40],
            'dictionary_url':DICT_URL,'dictionary_sha256':sha(DICT_PATH),
            'meaning':'只用于发现坏数字层，词典命中不代表听力原文已经正确或核定。'}


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def norm(s):
    return re.sub(r'\s+', '', s).upper()


READING = re.compile(r'PART(?:II|11|I1|2)[\W_]*READING|READING[\W_]*COMPREHENSION', re.I)


def boundary(text):
    """在空白不稳定的PDF/OCR文字中定位阅读章节，返回原文本下标。"""
    pats = [r'(?m)^\s*PART[ -]+\S{1,4}\s+READING\b',
            r'PART[\s-]*(?:II|11|I1|2|U|H|Ⅱ)\s*READING\b',
            r'PART[\s-]*(?:II|11|I1|2|U|H|Ⅱ)\s*\n\s*READING',
            r'(?m)^\s*READING\s+COMPREHENSION\s*(?=\n|\[|$)']
    hits = [m.start() for p in pats for m in re.finditer(p, text, re.I)]
    return min(hits) if hits else None


def text_page(pdf, pno):
    return subprocess.run(['pdftotext', '-layout', '-f', str(pno), '-l', str(pno), str(pdf), '-'],
                          capture_output=True, text=True, check=True).stdout.replace('\x0c', '')


def ocr_page(pdf, pno, dpi, high=False):
    env = dict(os.environ, OMP_THREAD_LIMIT='1')
    with tempfile.TemporaryDirectory(prefix='tem8ocr-') as td:
        image = Path(td) / 'page.png'
        with fitz.open(pdf) as doc:
            doc[pno-1].get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), colorspace=fitz.csGRAY).save(image)
        cmd = ['tesseract', str(image), 'stdout', '-l', 'eng+chi_sim' if high else 'eng', '--psm', '3']
        if high:
            assert (TESSDATA / 'chi_sim.traineddata').exists(), '需准备chi_sim模型'
            cmd += ['--tessdata-dir', str(TESSDATA)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        return result.stdout


def extract(base, row, cache, include_sheet=False,force_ocr=False,check_quality=False):
    pdf = base / row['file']
    assert sha(pdf) == row['sha256'], row['file']
    cache.mkdir(parents=True, exist_ok=True)
    done = cache / '提取.json'
    txt_path = cache / '听力页.txt'
    if done.exists() and txt_path.exists():
        old = json.loads(done.read_text('utf-8'))
        if old.get('extractor_version')==5 and old['sha256'] == row['sha256'] and (not include_sheet or old.get('include_answer_sheet')) and (not force_ocr or old['mode']=='OCR'):
            return old, txt_path.read_text('utf-8')
    with fitz.open(pdf) as doc:
        total = len(doc)
        lengths = [len(doc[i].get_text()) for i in range(min(2, total))]
    has_layer=sum(lengths)>=400
    quality=dictionary_quality('\n'.join(text_page(pdf,n) for n in range(1,min(2,total)+1))) if has_layer and check_quality else None
    rejected_layer=quality is not None and quality['dictionary_ratio']<quality['threshold']
    mode = '数字层' if has_layer and not force_ocr and not rejected_layer else 'OCR'
    pages, texts = [], []
    end_found = False
    boundary_context = ''
    fallback_reason='数字层英文词典可信率低于0.95，不采信为原文，改用页图OCR。' if rejected_layer else None
    # 有数字层却找不到实际章节，说明文字层可能坏；只对卷首听力页降级OCR。
    modes=['数字层','OCR'] if mode=='数字层' else ['OCR']
    for scan_mode in modes:
        mode=scan_mode;pages=[];low={}
        limit=total if mode=='数字层' else min(total,8)
        for pno in range(1,limit+1):
            lp = cache / f'低清_{pno}.txt'
            if mode == '数字层':
                candidate = text_page(pdf, pno)
            elif lp.exists():
                candidate = lp.read_text('utf-8')
            else:
                candidate = ocr_page(pdf, pno, 110)
                lp.write_text(candidate, 'utf-8')
            low[pno] = candidate
            cut = boundary(candidate)
            pages.append(pno)
            if cut is not None:
                end_found = True
                boundary_context=candidate[max(0,cut-60):cut+160]
                break
        if end_found:break
        if mode=='数字层':fallback_reason='数字层无法可靠定位阅读章节，降级为听力页OCR。'
    assert end_found, f'候选{limit}页未定位阅读起点，停止自动提取：{row["file"]}'
    for pno in pages:
        if mode == '数字层':
            text = low[pno]
        else:
            hp = cache / f'高精_{pno}.txt'
            if hp.exists():
                text = hp.read_text('utf-8')
            else:
                text = ocr_page(pdf, pno, 280, True)
                hp.write_text(text, 'utf-8')
        cut = boundary(text)
        if cut is not None:
            text = text[:cut]
        if text.strip():
            texts.append(f'=== 原PDF第{pno}页 ===\n{text.rstrip()}\n')
    sheet_pages=[]
    if include_sheet and mode=='数字层':
        # 部分原卷把听力填空答题卡放在全卷末尾；只截卷首会漏掉整套15空。
        for pno in range(1,total+1):
            if pno in pages:continue
            candidate=text_page(pdf,pno)
            flat=norm(candidate)
            if ('ANSWERSHEET1' in flat or 'ANSWERSHEETONE' in flat) and ('LISTENING' in flat or 'MINI-LECTURE' in flat):
                sheet_pages.append(pno)
                texts.append(f'=== 原PDF第{pno}页：另附听力答题卡 ===\n{candidate.rstrip()}\n')
        pages+=sheet_pages
    text = '\n'.join(texts)
    if has_layer and mode=='OCR':
        (cache/'数字层对照.txt').write_text('\n'.join(f'=== 原PDF第{p}页数字层对照，非定稿 ===\n{text_page(pdf,p)}' for p in pages),'utf-8')
    meta = {'extractor_version':5,'file': row['file'], 'sha256': row['sha256'], 'bytes': row['bytes'],
            'pdf_pages': total, 'listening_pages': pages, 'mode': mode,
            'reading_boundary_found': end_found, 'chars': len(text),
            'include_answer_sheet':include_sheet,'appended_answer_sheet_pages':sheet_pages,
            'answer_sheet_scan_unchecked':include_sheet and mode=='OCR','reading_boundary_context':boundary_context,
            'fallback_reason':fallback_reason,
            'forced_image_ocr':force_ocr,'digital_layer_comparison':has_layer and mode=='OCR',
            'digital_layer_quality':quality,
            'ocr_dpi': 280 if mode == 'OCR' else None,
            'ocr_languages': 'eng+chi_sim' if mode == 'OCR' else None,
            'status': 'OCR文字必须与页图及录音复核' if mode == 'OCR' else '原有数字层逐页提取，未自动订正'}
    dump(done, meta)
    txt_path.write_text(text, 'utf-8')
    return meta, text


def select(rows, year):
    prefix = f'/{year}年专八真题+音频+解析/'
    b1 = [r for r in rows if prefix in r['file'] and r['suffix'] == '.pdf' and '补充' not in r['file']]
    analyses = [r for r in b1 if '解析.pdf' in r['file']]
    assert len(analyses) == 1, (year, analyses)
    papers = [r for r in b1 if r not in analyses]
    assert len(papers) == 1, (year, papers)
    small = [r for r in rows if r['suffix'] == '.pdf' and '(1)' not in r['file'] and str(year) in r['file'] and not r['file'].startswith('B1')]
    root_papers = [r for r in small if '/' not in r['file']]
    root_answers = [r for r in small if '答案' in Path(r['file']).name]
    # 2016起兼有未经“新题型优化”的数字原卷，以这些为优先题面来源。
    paper = root_papers[0] if year >= 2016 and root_papers else papers[0]
    audio = [r for r in rows if r['suffix'] in ['.mp3','.wma'] and str(year) in r['file'] and '(1)' not in r['file']]
    audio = list({r['sha256']:r for r in audio}.values())
    audio.sort(key=lambda r: 0 if 'mini-lecture' in r['file'] else 1)
    assert len(audio) == (2 if year == 2018 else 1), (year, audio)
    return {'paper':paper, 'b1_paper':papers[0], 'analysis':analyses[0],
            'answer':root_answers[0] if root_answers else None, 'audio':audio}


def run_year(year, base, rows):
    chosen = select(rows, year)
    dest = OUT / str(year);dest.mkdir(parents=True,exist_ok=True)
    meta = {'year':year, 'selection':chosen, 'extractions':{}, 'warnings':[]}
    if year <= 2015:
        meta['warnings'].append('B1教材标示“新题型/新题型优化”，不是无改动的当年原始题面；按所供优化版原音与题面配套，须逐年核对实际录音的题型及题号，不补造其他版本。')
    for key, filename in [('paper','原卷.txt'),('analysis','解析.txt'),('answer','数字版答案解析.txt')]:
        row = chosen[key]
        if row is None:continue
        info, text = extract(base,row,dest/'提取缓存'/key,include_sheet=key=='paper',force_ocr=key=='analysis' and year<=2011,check_quality=key=='analysis')
        meta['extractions'][key] = info
        (dest/filename).write_text(f'来源：{row["file"]}\nSHA256：{row["sha256"]}\n方式：{info["mode"]}\n原PDF页码：{info["listening_pages"]}\n以下文字未经自动订正；OCR不是定稿原文。\n\n'+text,'utf-8')
        if info['mode'] == 'OCR':meta['warnings'].append(f'{filename}为OCR原始结果，不能当作已校对原文。')
        print(year,key,info['mode'],info['listening_pages'],info['chars'],flush=True)
    if chosen['b1_paper']['sha256'] != chosen['paper']['sha256']:
        try:
            info, text = extract(base,chosen['b1_paper'],dest/'提取缓存/b1_paper',include_sheet=True)
            meta['extractions']['b1_paper'] = info
            (dest/'B1教材题面.txt').write_text(f'来源：{chosen["b1_paper"]["file"]}\n\n'+text,'utf-8')
        except AssertionError as e:
            # 辅助教材不是所选正式题面；其坏数字层不能阻塞已确认的原卷及解析。
            meta['warnings'].append('B1辅助题面章节边界未能自动确认，未自动截取；使用本年已定位的数字原卷。'+str(e))
            meta['b1_paper_extraction_pending']=True
    if year == 2018:meta['warnings'].append('原音是mini-lecture和interview两份，制作顺序为讲座→采访；不可把两文件当作不同年份或漏掉任一份。')
    if year == 2022:meta['warnings'].append('所供小体积数字原卷末页误印“2023年补充卷”；该附页仅为改错题，已排除出听力提取。')
    meta['needs_audio_crosscheck'] = True
    dump(dest/'来源.json',meta)
    return meta


def main():
    global TESSDATA,DICT_PATH
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=Path('/workspace/tem8-input'))
    p.add_argument('--years',type=int,nargs='+',default=YEARS)
    p.add_argument('--workers',type=int,default=2)
    p.add_argument('--tessdata',type=Path,default=TESSDATA)
    args=p.parse_args();assert 1<=args.workers<=2
    TESSDATA=args.tessdata;DICT_PATH=TESSDATA/'words_alpha.txt'
    rows=json.loads((D/'原始材料清单.json').read_text('utf-8'))['files']
    OUT.mkdir(exist_ok=True)
    # 先登记来源和所有可直接提取的题面，让后续数据制作不必等扫描解析OCR。
    for year in args.years:
        chosen=select(rows,year);dest=OUT/str(year);dest.mkdir(exist_ok=True)
        dump(dest/'来源选择.json',{'year':year,**chosen})
        for key,name in [('paper','原卷.txt'),('answer','数字版答案解析.txt')]:
            row=chosen[key]
            if row is None:continue
            with fitz.open(args.input/row['file']) as doc:digit=sum(len(doc[i].get_text()) for i in range(min(2,len(doc))))>=400
            if digit:
                info,text=extract(args.input,row,dest/'提取缓存'/key,include_sheet=key=='paper')
                (dest/name).write_text(f'来源：{row["file"]}\nSHA256：{row["sha256"]}\n方式：{info["mode"]}\n以下为原数字层，未自动订正。\n\n'+text,'utf-8')
    print('可直接提取的数字原卷与答案已就绪，开始有限并发OCR。',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures={ex.submit(run_year,y,args.input,rows):y for y in args.years}
        results=[]
        for f in concurrent.futures.as_completed(futures):results.append(f.result())
    dump(OUT/'来源总表.json',{'years':sorted(args.years),'cancelled_years':[2020],
        'cancelled_source':next(r for r in rows if r['suffix']=='.txt' and '2020' in r['file']),
        'count':len(results),'source_only':'本阶段只提取和登记来源；原音、原文、题面的一致性须后续核验，不代表完成精读审校。',
        'cases':sorted(results,key=lambda r:r['year'])})
    print('提取完成',len(results),'年',flush=True)


if __name__=='__main__':main()
