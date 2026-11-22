"""Render the IELTS pilot with the original CET-6 layout and video checks."""
import argparse
import hashlib
import json
import sys
import tempfile
import re
import unicodedata
from pathlib import Path

from lesson import LESSON, PID, PROJECT, ROOT, TEXT, load, save
sys.path.insert(0, str(ROOT / '六级/tools'))
import make_video as engine

PROJECT_ID = '雅思学术阅读'
SHOTS = PROJECT / '样片' / '截图' / PID
REVIEW = PROJECT / '样片' / 'review.json'
engine.PROJECTS[PROJECT_ID] = {
    **engine.PROJECTS['六级'],
    'dir': '雅思/学术阅读', 'tag': 'IELTS · ACADEMIC READING', 'top': 'IELTS READING',
    'exam':'', 'sub_fit': True, 'max_mb': 1900, 'tmp':'ielts_reading_',
    'name_re': r'剑桥雅思20 Test 1 Passage 1 鸮鹦鹉\.mp4',
}
engine.set_project(PROJECT_ID)

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
    return cet_sentence_slide(p, sentence, k, n, part)

engine.sentence_slide = ielts_sentence_slide

def prepare():
    p = load()
    p['year'] = 2025   # Publication year of Cambridge IELTS 20; required by shared video QA.
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
        for lo, hi, zh, _ in parts:
            selected=visible_words(s,lo,hi)
            glosses=[w['m'] for w in selected]
            glosses=[engine.POS.match(t).group(2) if engine.POS.match(t) else t for t in glosses]
            numbers=[str(i) for i in range(1,len(selected)+1)]
            spans=sorted((a,b) for w in selected for a,b in w['sp'])
            labels=[str(i) for _,i in sorted((word['sp'][-1][0],i) for i,word in enumerate(selected,1))]
            result.append(dict(en=s['en'][lo:hi],zh=zh,glosses=glosses,
                               heads=[w['h'] for w in selected],numbers=numbers,labels=labels,
                               forms=[s['en'][a:b] for a,b in spans]))
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
    save(engine.SAMPLE_REG,{PID+'@3':{'指纹':review_data['fingerprint'],'截图':{s['file']:s['sha256'][:16] for s in review_data['screens']}}})
    sys.argv=['make_video.py',PID,'--project',PROJECT_ID,'--out',str(PROJECT/'最终视频')]
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

    verify_videos.frame = frame_for_checks
    try:
        engine.main()
    finally:
        verify_videos.frame = read_frame

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['stills','video'])
    args=parser.parse_args()
    passage=prepare()
    if args.stage=='stills': review(passage)
    else: encode()
