"""Render the IELTS pilot with the original CET-6 layout and video checks."""
import argparse
import base64
import difflib
import hashlib
import inspect
import json
import math
import os
import sys
import tempfile
import re
import unicodedata
from pathlib import Path

from lesson import LESSON, PID, PROJECT, ROOT, TEXT, load, presentation_frames, save
sys.path.insert(0, str(ROOT / '六级/tools'))
sys.path.append(str(ROOT / 'tools/tts'))
import make_video as engine

PROJECT_ID = '雅思学术阅读'
SHOTS = PROJECT / '样片' / '截图' / PID
REVIEW = PROJECT / '样片' / 'review.json'
engine.PROJECTS[PROJECT_ID] = {
    **engine.PROJECTS['六级'],
    'dir': '雅思/学术阅读', 'tag': 'IELTS · ACADEMIC READING', 'top': 'IELTS READING',
    'exam':'', 'sub_fit': True, 'max_mb': 1900, 'tmp':'ielts_reading_',
    'name_re': r'剑桥雅思(?:[1-9]|1[0-9]|2[01]) Test [1-8] Passage [1-3] .+\.mp4',
}
_cet_set_project = engine.set_project

def fit_long_headwords(js):
    # Measure indivisible words after the native layout restores the headword.
    # A multi-word expression still wraps normally. Only its own label scales.
    anchor='const wide = () => {'
    adjustment=r"""
      if (/[\p{Script=Latin}\p{M}]{13}/u.test(b.textContent)) {
        b.style.fontSize = '';
        const cs = getComputedStyle(side), bounds = side.getBoundingClientRect();
        const right = bounds.left + side.clientLeft + side.clientWidth - parseFloat(cs.paddingRight);
        const cell = b.parentElement, left = cell.getBoundingClientRect().left + cell.clientLeft;
        const available = right - left;
        const walker = document.createTreeWalker(b, NodeFilter.SHOW_TEXT);
        const words = [];
        let node, widest = 0;
        while ((node = walker.nextNode())) {
          for (const m of node.data.matchAll(/[\p{Script=Latin}\p{M}]{13,}/gu)) {
            const range = document.createRange();
            range.setStart(node, m.index); range.setEnd(node, m.index + m[0].length);
            words.push(range);
            widest = Math.max(widest, range.getBoundingClientRect().width);
          }
        }
        if (available > 0 && widest > available + 0.5) {
          const original = parseFloat(getComputedStyle(b).fontSize);
          const size = Math.max(34, Math.floor(original * (available - 1) / widest));
          if (size < original) b.style.fontSize = size + 'px';
          // Keep the minimum glyph height for an unusually long single token.
          // Its inline box must also shrink so the following gloss wraps normally.
          for (const range of words.reverse()) {
            const width = range.getBoundingClientRect().width;
            if (width <= available + 0.5) continue;
            const room = Math.max(1, available - parseFloat(getComputedStyle(b).marginRight) - 1);
            const box = document.createElement('span'), ink = document.createElement('span');
            box.style.cssText = 'display:inline-block;font:inherit;color:inherit;width:' + room + 'px';
            ink.style.cssText = 'display:inline-block;font:inherit;color:inherit;white-space:nowrap;transform-origin:left center;transform:scaleX(' + room / width + ')';
            ink.append(range.extractContents()); box.append(ink); range.insertNode(box);
          }
        }
      }
    """
    # The source word, its number and any attached punctuation have to fit as
    # one unit. Resize only its letters, leaving the badge and punctuation alone.
    body_anchor='const phr = () => { const lim = en.clientWidth;'
    body_adjustment=r"""
      for (const word of en.querySelectorAll('[data-ielts-long-word]')) word.style.fontSize = '';
      const walker = document.createTreeWalker(en, NodeFilter.SHOW_TEXT), candidates = [];
      let node;
      while ((node = walker.nextNode())) {
        for (const m of node.data.matchAll(/[\p{Script=Latin}\p{M}]{13,}/gu)) {
          candidates.push([node, m.index, m.index + m[0].length]);
        }
      }
      for (const [text, start, end] of candidates.reverse()) {
        const word = document.createRange();
        word.setStart(text, start); word.setEnd(text, end);
        const unit = word.cloneRange();
        let tail = text, offset = end;
        walker.currentNode = text;
        while (tail) {
          if (tail !== text && tail.parentElement.closest('sup, x-ps')) {
            unit.setEndAfter(tail.parentElement.closest('sup, x-ps'));
          } else {
            const rest = tail.data.slice(offset);
            const punctuation = rest.match(/^[.,:;!?%…’”')\]}/]+/u);
            if (punctuation) unit.setEnd(tail, offset + punctuation[0].length);
            if (rest.length > (punctuation ? punctuation[0].length : 0)) break;
          }
          tail = walker.nextNode(); offset = 0;
        }
        const width = unit.getBoundingClientRect().width;
        if (width <= lim + 0.5) continue;
        const letters = word.getBoundingClientRect().width;
        const original = parseFloat(getComputedStyle(text.parentElement).fontSize);
        let target = text.parentElement;
        if (!target.hasAttribute('data-ielts-long-word')) {
          target = document.createElement('span');
          target.setAttribute('data-ielts-long-word', '');
          target.style.font = 'inherit';
          word.surroundContents(target);
        }
        target.style.fontSize = Math.max(1, Math.floor(original * (letters + lim - width - 1) / letters)) + 'px';
      }
    """
    if js.count(anchor)!=1 or js.count(body_anchor)!=1:
        raise RuntimeError('无法定位六级主题的词头测量步骤')
    return js.replace(anchor,adjustment+anchor).replace(body_anchor,body_anchor+body_adjustment)

engine.FIT_JS=fit_long_headwords(engine.FIT_JS)

def fit_early_layout(js):
    # Test the ordinary spacing at the certified minimum independently of the
    # shared starting size for a multi-screen sentence. Preserve the native
    # margins for a screen that already fits at that size.
    anchor = 'while (!sideFits() && vs > 16)'
    body_anchor = 'while (box.scrollHeight > main.clientHeight && fs > 30)'
    if js.count(anchor) != 1 or js.count(body_anchor) != 1:
        raise RuntimeError('无法定位六级主题的词栏字号测量')
    measure = """
      const startVs = vs;
      side.classList.remove('ielts-dense-side');
      vs = MINVS;
      r.setProperty('--vs', vs+'px');
      if (!sideFits()) side.classList.add('ielts-dense-side');
      vs = startVs;
      r.setProperty('--vs', vs+'px');
    """
    body_measure = """
      const startFs = fs;
      main.classList.remove('ielts-tight-body', 'ielts-punctuation-room');
      fs = BODY_FLOOR;
      r.setProperty('--fs', fs+'px'); phr();
      if (en.scrollWidth > en.clientWidth + 1) main.classList.add('ielts-punctuation-room');
      phr();
      if (box.scrollHeight > main.clientHeight) main.classList.add('ielts-tight-body');
      fs = startFs;
      r.setProperty('--fs', fs+'px'); phr();
    """
    floor = engine.SIZES[engine.PROJECTS[PROJECT_ID]['look']]['min_fs']
    return js.replace(anchor, measure + anchor).replace(body_anchor, body_measure.replace('BODY_FLOOR', str(floor)) + body_anchor)

if int(PID[1:PID.index('T')]) <= 10:
    engine.FIT_JS = fit_early_layout(engine.FIT_JS)

def select_lesson(name, look=True):
    _cet_set_project(name, look)
    if name == PROJECT_ID and PID != 'C20T1P1':
        meta = json.loads((LESSON/'篇目信息.json').read_text())
        if (LESSON/'分屏.json').is_file():
            engine.SPLIT.update(json.loads((LESSON/'分屏.json').read_text()))
        engine.NAMES = list(dict.fromkeys(engine.NAMES + meta.get('zh_names',[])))

engine.set_project = select_lesson
engine.set_project(PROJECT_ID)

_native_zh_html=engine.zh_html

def ielts_zh_html(text,gloss=False,latin_words=False):
    markup=_native_zh_html(text,gloss,latin_words)
    if not gloss:
        # Chromium 141 otherwise holds ‘大脑’ together with the following
        # indivisible word and leaves room for the entire quotation unused.
        markup=re.sub(r'’(?=(?:<nobr>)?[\u3400-\u9fff])','’<wbr>',markup)
    return markup

if PID!='C20T1P1':
    engine.zh_html=ielts_zh_html

def visible_words(sentence, lo, hi):
    words = []
    for word in sentence['w']:
        spans = [[a, b] for a, b in word['sp'] if lo <= a and b <= hi]
        if spans:
            words.append({**word, 'sp': spans})
    return sorted(words, key=lambda word: word['sp'][0][0])

cet_sentence_slide = engine.sentence_slide

def ielts_sentence_slide(p, sentence, k, n, part=None):
    if part:
        lo, hi = part[:2]
        sentence = {**sentence, 'w': visible_words(sentence, lo, hi)}
    slide = cet_sentence_slide(p, sentence, k, n, part)
    if re.search(r'[⁰⁴-⁹₀-₉]',slide):
        # Full Inter contains these glyphs; the Latin web subsets omit them.
        # A unicode-range face covers both the passage and its vocabulary panel.
        variable=Path(__file__).with_name('fonts')/'inter-notations.woff2'
        data=base64.b64encode(variable.read_bytes()).decode('ascii')
        slide=slide.replace("font-family:'Inter'", "font-family:'IELTS Inter Notation','Inter'")
        face=("@font-face{font-family:'IELTS Inter Notation';font-style:normal;font-weight:100 900;"
              "unicode-range:U+2070,U+2074-2079,U+2080-2089;src:url(data:font/woff2;base64,"+data+") format('woff2')}")
        scope=".en,.en .w,.en .ph,.v b{font-family:'IELTS Inter Notation','Inter','ZH Regular',sans-serif}"
        slide=slide.replace('</head>','<style>'+face+scope+'</style></head>',1)
    # Keep a dash introducing an appositive and its continuation on the same
    # line as the preceding word (e.g. "Rakiura – …").
    return re.sub(r'([\w-]+[ \u00a0]+[–—])(<span class="cont">\u00a0…</span>)',
                  r'<nobr>\1\2</nobr>',slide)

def batch_sentence_slide(p,sentence,k,n,part=None):
    header=p.get('reading_header',{})
    if header:
        p={**p,'passage':p['passage'].split(' · ',1)[0]+' · '+header['english'],'title':header['chinese']}
    return ielts_sentence_slide(p,sentence,k,n,part)

def word_quotes(text):
    # The Word transcription uses straight quotes. These one-character substitutions
    # keep every source span and every recorded switch at its original offset.
    text=re.sub(r"(?<=\w)'(?=\w)|(?<=s)'(?=\s)", '’', text)
    text=re.sub(r'(^|(?<=[\s(—–]))"', '“', text).replace('"', '”')
    return re.sub(r"(^|(?<=[\s(—–“]))'", '‘', text).replace("'", '’')


def word_sentence_slide(p,sentence,k,n,part=None):
    shown={**sentence,'en':word_quotes(sentence['en']),
           'w':[{**word,'h':word_quotes(word['h'])} for word in sentence['w']]}
    return batch_sentence_slide(p,shown,k,n,part)

def early_sentence_slide(p,sentence,k,n,part=None):
    html=batch_sentence_slide(p,sentence,k,n,part)
    # Printed section names are needed for matching-heading questions.
    # Show them in the existing footer so they do not enter the spoken prose.
    headers = p.get('section_headers', {})
    starts = [int(start) for start in headers if int(start) <= k]
    if starts:
        heading = headers[str(max(starts))]
        if heading:
            html = html.replace('<span>逐句精读</span>', '<span>' + engine.esc(heading) + '</span>', 1)
    compact = ('.main.ielts-punctuation-room{width:1100px}'
               '.ielts-tight-body .en{line-height:1.22}.ielts-tight-body .zh{margin-top:16px;line-height:1.36}'
               '.side.ielts-dense-side{padding:18px 22px}'
               '.ielts-dense-side #list{gap:calc(var(--vs)*.20)}'
               '.ielts-dense-side .v{line-height:1.22;column-gap:9px}')
    html = html.replace('</head>', '<style>' + compact + '</style></head>', 1)
    # Early printings use a spaced hyphen for a parenthesis or an appositive.
    # Keep the printed punctuation, its highlight and its continuation together.
    match=re.search(r'<div class="en">(.*?)</div>',html,re.S)
    body=match[1]
    # Keep a closing quote with the final word even if its opening quote was
    # on the previous screen. The superscript annotates the quoted word.
    if (part and part[0] and part[1] == len(sentence['en'])
            and '‘' in sentence['en'][:part[0]] and re.search(r'’[.!?]?$', sentence['en'])):
        body = re.sub(r'(<sup(?: [^>]*)?>\d+</sup>)(</span>)(</nobr>)?([’])([.!?]?)$',
                      r'<x-ps>\4</x-ps>\1\2\3\5', body)
    before_cont=r'(<span class="(?:w|ph)">(?:(?!</span>).)*</span>|[\w’]+)([ \u00a0]+[-–—])(<span class="cont">\u00a0…</span>)'
    body=re.sub(before_cont,r'<nobr>\1\2\3</nobr>',body)
    # A year followed by a spaced dash must travel with the dash at a line wrap.
    body=re.sub(r'(?<![>\w])(\d{4} [–—])(?= )',r'<nobr>\1</nobr>',body)
    body=re.sub(r'(?<![>\w])([A-Za-z0-9’]{1,16} - [A-Za-z0-9’]{1,16})(?![\w<])',r'<nobr>\1</nobr>',body)
    # A highlighted preceding word ends in HTML rather than a letter.
    # Bind a typographic dash to the preceding highlight. A spaced ASCII
    # dash binds to the next word below so it cannot resemble a cut compound.
    body=re.sub(r'(</span>) ([–—])(?= (?:<nobr>)?<span class="(?:w|ph)">)',
                lambda m:m[1]+'\u00a0'+m[2],body)
    body=re.sub(r' ([-–—]) <nobr>(?=<span class="(?:w|ph)">|[\w])',r' <nobr>\1 ',body)
    body=re.sub(r'(?<=>) ([-–—] (?:<span class="(?:w|ph)">(?:(?!</span>).)*</span>|[A-Za-z0-9’]+))',
                r' <nobr>\1</nobr>',body)
    return html[:match.start(1)]+body+html[match.end(1):]


engine.sentence_slide = ielts_sentence_slide if PID=='C20T1P1' else batch_sentence_slide
if PID.startswith('C21T'):
    engine.sentence_slide = word_sentence_slide
elif int(PID[1:PID.index('T')])<=10:
    engine.sentence_slide = early_sentence_slide

def speech_tokens(text):
    from textnorm import ordinal
    plain = ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))
    plain = re.sub(r'\bh\. (?=naledi\b)', 'homo ',plain)
    # Match a printed ordinal to the same ordinal in the certified narration.
    plain = re.sub(r'\b(\d+)[ \t]*(?:st|nd|rd|th)\b',lambda m:ordinal(int(m[1])),plain)
    return re.findall(r'[a-z0-9]+',plain)

def reviewed_spelling(audio, timing, printed, recognised):
    evidence=json.loads((PROJECT/'审校/分屏词音对照.json').read_text())
    known={row['mp3_sha256'] for row in evidence if row['lesson']==PID and row['sentence']==timing['k']
           and row['printed'].casefold()==printed and row['recognized'].casefold()==recognised}
    if not known:
        return False
    with Path(audio).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest() in known

def ielts_switch_time(audio, timing, english, cut):
    import numpy as np
    samples, recognised = engine.asr_words(audio, timing)
    spoken = [(word, onset) for text,onset in recognised for word in speech_tokens(text)]
    source = speech_tokens(english)
    index = len(speech_tokens(english[:cut]))
    matches = difflib.SequenceMatcher(None, source, [w for w,_ in spoken], autojunk=False)
    operations = matches.get_opcodes()
    for pos, (tag, a, b, x, y) in enumerate(operations):
        if not a <= index < b:
            continue
        if tag == 'equal':
            onset = spoken[x + index - a][1]
            break
        # An independently checked spelling in this exact recording can still
        # have a measured onset. Require two exact words on both sides.
        if tag == 'replace' and index == a and y-x == 1 and 0 < pos < len(operations)-1:
            printed=' '.join(source[a:b])
            heard=spoken[x][0]
            if b-a>1:
                compound='-'.join(source[a:b])
                if not english[cut:].casefold().startswith(compound) or ''.join(source[a:b])!=heard:
                    continue
            left, right = operations[pos-1], operations[pos+1]
            anchored = (left[0] == right[0] == 'equal' and
                        left[2]-left[1] >= 2 and right[2]-right[1] >= 2)
            if anchored and reviewed_spelling(audio, timing, printed, heard):
                onset = spoken[x][1]
                break
    else:
        raise ValueError(f'读音中未定位到下一屏的开头：{english[cut:cut+45]}')

    absolute = timing['start'] + onset
    # Use the middle of a mastered clause pause when it precedes this word.
    for prior, following in zip(timing['parts'], timing['parts'][1:]):
        end, start = prior[1], following[0]
        if end - .03 <= absolute <= start + .15:
            return (end + start) / 2

    # Inside uninterrupted speech, use the CET 60 ms energy measure close to
    # the aligned word, so an earlier syllable cannot trigger the next screen.
    start = max(0, round((onset-.12)*16000))
    stop = min(len(samples), round((onset+.03)*16000))
    half = 480
    left, right = max(0,start-half), min(len(samples),stop+half)
    energy = np.convolve(samples[left:right].astype(np.float64)**2, np.ones(half*2)/(half*2), mode='same')
    lowest = start + int(np.argmin(energy[start-left:stop-left]))
    return timing['start'] + lowest/16000

engine.switch_time = ielts_switch_time

def prepare():
    p = load()
    p['year'] = 2025   # Publication year of Cambridge IELTS 20; required by shared video QA.
    display_code = inspect.getsource(visible_words) + inspect.getsource(ielts_sentence_slide)
    if PID!='C20T1P1':
        meta = json.loads((LESSON/'篇目信息.json').read_text())
        years={1:1996,2:2000,3:2002,4:2005,5:2006,6:2007,7:2009,8:2011,9:2013}
        p['year'] = int(meta.get('year',years.get(int(meta['book']),2005+int(meta['book']))))
        p['reading_header'] = meta.get('header',{})
        if PID.startswith('C21T'):
            p['passage']=word_quotes(p['passage'])
            if p['reading_header']:
                p['reading_header']={**p['reading_header'],'english':word_quotes(p['reading_header']['english'])}
            display_code+=inspect.getsource(word_quotes)+inspect.getsource(word_sentence_slide)
        elif int(meta['book'])<=10:
            if meta.get('section_headers'):
                p['section_headers'] = meta['section_headers']
            display_code+=inspect.getsource(early_sentence_slide)+inspect.getsource(fit_early_layout)
        display_code += inspect.getsource(batch_sentence_slide) + inspect.getsource(ielts_zh_html) + json.dumps(meta.get('zh_names',[]),ensure_ascii=False)
    p['ielts_display_sha256'] = hashlib.sha256(display_code.encode()).hexdigest()
    save(PROJECT / 'data/vocab.json', {'passages':[p]})
    ann = PROJECT / 'ann' / (PID + '.txt')
    ann.parent.mkdir(exist_ok=True)
    ann.write_bytes(TEXT.read_bytes())
    digest = hashlib.sha256(ann.read_bytes()).hexdigest()
    seal = json.loads((LESSON / 'content-review.json').read_text())
    if digest != seal['text_sha256']:
        raise ValueError('The translation or vocabulary differs from the reviewed lesson.')
    save(ann.parent / '复核通过.json',{'指纹':{PID:digest[:16]}})
    engine.check_names(p)
    return p

def screen_text(page):
    return page.evaluate("""() => {
      const textWithout = (sel, omit) => {
        const x = document.querySelector(sel).cloneNode(true);
        x.querySelectorAll(omit).forEach(e=>e.remove());
        return x.textContent;
      };
      return {
        en:textWithout('.en','sup,.cont'), zh:document.querySelector('.zh').textContent,
        glosses:[...document.querySelectorAll('.v .g')].map(e=>e.textContent),
        heads:[...document.querySelectorAll('.v b')].map(e=>e.textContent),
        numbers:[...document.querySelectorAll('.v em')].map(e=>e.textContent),
        labels:[...document.querySelectorAll('.en sup')].map(e=>e.textContent),
        forms:[...document.querySelectorAll('.en .w, .en .ph')].map(e=>{
          const c=e.cloneNode(true); c.querySelectorAll('sup,x-ps').forEach(n=>n.remove()); return c.textContent;
        })
      };
    }""")

def normalized(s):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC',s)).replace('’',"'").replace('‐','-').replace('‑','-').replace('–','-')

def expected_screens(p):
    result=[]
    for number,s in enumerate((s for para in p['paras'] for s in para),1):
        parts=engine.split_parts(PID,number,s)
        if ''.join(s['en'][lo:hi] for lo,hi,_,_ in parts) != s['en'] or ''.join(zh for _,_,zh,_ in parts) != s['zh']:
            raise ValueError(f'第 {number} 句：分屏后的中英文未完整还原定稿')
        for word in s['w']:
            for a,b in word['sp']:
                if not any(lo <= a and b <= hi for lo,hi,_,_ in parts):
                    raise ValueError(f'第 {number} 句：分屏切断词条 {word["h"]}')
        shown=word_quotes(s['en']) if PID.startswith('C21T') else s['en']
        for lo, hi, zh, _ in parts:
            selected=visible_words(s,lo,hi)
            if not selected:
                raise ValueError(f'第 {number} 句的这一屏缺少对应的语境词条：{s["en"][lo:hi].strip()}')
            glosses=[w['m'] for w in selected]
            glosses=[engine.POS.match(t).group(2) if engine.POS.match(t) else t for t in glosses]
            numbers=[str(i) for i in range(1,len(selected)+1)]
            spans=sorted((a,b) for w in selected for a,b in w['sp'])
            labels=[str(i) for _,i in sorted((word['sp'][-1][0],i) for i,word in enumerate(selected,1))]
            heads=[word_quotes(w['h']) if PID.startswith('C21T') else w['h'] for w in selected]
            result.append(dict(en=shown[lo:hi],zh=zh,glosses=glosses,
                               heads=heads,numbers=numbers,labels=labels,forms=[shown[a:b] for a,b in spans]))
    return result

def reference_errors(page, expected, label):
    got=screen_text(page)
    errors=[]
    for k in expected:
        a,b=got[k],expected[k]
        a,b=([normalized(x) for x in z] if isinstance(z,list) else normalized(z) for z in (a,b))
        if a!=b: errors.append(f'{label} {k}: 实测 {a!r}，定稿 {b!r}')
    return errors

def review(p):
    from PIL import Image, ImageDraw
    from playwright.sync_api import sync_playwright
    SHOTS.mkdir(parents=True, exist_ok=True)
    problems = engine.empty_split_parts(p)
    report = []
    expected=expected_screens(p)
    with tempfile.TemporaryDirectory() as td, sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        page = br.new_page(viewport=dict(width=engine.W,height=engine.H),device_scale_factor=2)
        temp = Path(td)
        for index,label,fit,sizes in engine.layout(page,p,temp / 'x.html'):
            problems.extend(engine.screen_checks(page,label,fit,sizes))
            if fit: problems.extend(reference_errors(page,expected[index-1],label))
            png = temp / 'screen.png'
            page.screenshot(path=str(png))
            path = SHOTS / f'screen{index+1:02}.webp'
            engine.small(png).save(path, 'WEBP', lossless=True, method=0)
            entry=dict(label=label,sizes=sizes,file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            if fit:
                entry.update({k:expected[index-1][k] for k in ('en','zh','heads')})
            report.append(entry)
        br.close()
    for start in range(0,len(report),12):
        chunk = report[start:start+12]
        sheet = Image.new('RGB',(3*480,((len(chunk)+2)//3)*294),'#e7ede9')
        draw = ImageDraw.Draw(sheet)
        for j,row in enumerate(chunk):
            with Image.open(SHOTS / row['file']) as image:
                image.thumbnail((480,270))
                x,y=(j%3)*480,(j//3)*294
                sheet.paste(image,(x,y));draw.text((x+8,y+271),f"{start+j+1:02}",fill='black')
        sheet.save(SHOTS.parent / f'contact-{start//12+1}.jpg', quality=93)
    save(REVIEW,dict(lesson=PID,fingerprint=engine.fingerprint(PID,'3'),screens=report,problems=problems))
    if problems:
        raise SystemExit('\n'.join(problems))

def encode():
    review_data=json.loads(REVIEW.read_text())
    approval=json.loads((LESSON/'visual-review.json').read_text())
    if approval['review_sha256'] != hashlib.sha256(REVIEW.read_bytes()).hexdigest() or review_data['problems']:
        raise ValueError('Unreviewed layout or unresolved layout problems.')
    if review_data['fingerprint'] != engine.fingerprint(PID,'3'):
        raise ValueError('Layout has changed since review.')
    audio_dir = PROJECT/'audio'
    timings = json.loads((audio_dir/'timings.json').read_text())[engine.VOICE][PID]
    split_review = json.loads((LESSON/'分屏核对.json').read_text())
    if timings['certificate']['mp3_sha256'] != split_review['mp3_sha256']:
        raise ValueError('分屏核对所用音轨与成片音轨不同')
    reviewed = {(x['sentence'],x['part']):x for x in split_review['cuts']}
    for n,(s,timing) in enumerate(zip((s for para in load()['paras'] for s in para),timings['sentences']),1):
        for part,(lo,hi,zh,_) in enumerate(engine.split_parts(PID,n,s)[1:],2):
            row = reviewed.pop((n,part))
            measured = engine.switch_time(audio_dir/timings['file'],timing,s['en'],lo)
            if (s['en'][lo:hi].strip(),zh) != (row['en'],row['zh']) or abs(measured-row['screen_time']) > .08:
                raise ValueError(f'第 {n} 句第 {part} 屏与已审校的中英分段或实际朗读切点不一致')
    if reviewed:
        raise ValueError('成片漏掉了已审校的分屏')
    save(engine.SAMPLE_REG,{PID+'@3':{'指纹':review_data['fingerprint'],'截图':{s['file']:s['sha256'][:16] for s in review_data['screens']}}})
    # Keep the certified MP3 timing intact. Snap the closing hold to the video clock.
    total = presentation_frames(timings) / 30
    presentation = {**timings,'source_duration':timings['duration'],'duration':math.nextafter(total,0)}
    # The two native timing checks request many of the same frames. Both inspect the
    # same immutable MP4. Decode each distinct millisecond once, using the CET reader.
    sys.path.insert(0, str(ROOT / 'tools' / 'video'))
    import verify_videos
    read_frame = verify_videos.frame
    frames = {}

    def frame_for_checks(mp4, seconds, temp_dir):
        key = (mp4, f'{seconds:.3f}')
        if key not in frames:
            frames[key] = read_frame(mp4, seconds, temp_dir)
        return frames[key]

    with tempfile.TemporaryDirectory() as temp:
        timeline = Path(temp)
        (timeline/engine.VOICE).symlink_to(audio_dir/engine.VOICE,target_is_directory=True)
        save(timeline/'timings.json',{engine.VOICE:{PID:presentation}})
        sys.argv=['make_video.py',PID,'--project',PROJECT_ID,'--out',str(PROJECT/'最终视频'),'--audio-root',str(timeline)]
        previous = os.environ.get('IELTS_END_KEYFRAMES')
        os.environ['IELTS_END_KEYFRAMES'] = f'{total-4},{total-2}'
        verify_videos.frame = frame_for_checks
        try:
            engine.main()
        finally:
            verify_videos.frame = read_frame
            if previous is None:
                os.environ.pop('IELTS_END_KEYFRAMES',None)
            else:
                os.environ['IELTS_END_KEYFRAMES'] = previous

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['stills','video'])
    args=parser.parse_args()
    passage=prepare()
    if args.stage=='stills': review(passage)
    else: encode()
