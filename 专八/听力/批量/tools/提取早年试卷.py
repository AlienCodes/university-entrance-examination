"""2009—2015供给的新题型优化版试卷：提取选择题，题面与答题卡由所供PDF核对。"""
import json,re,hashlib,subprocess
from pathlib import Path
import fitz
D=Path(__file__).resolve().parents[1]
INPUT=Path('/workspace/tem8-input')
ROWS=json.loads((D/'原始材料清单.json').read_text())['files']

def paper(year):
 return next(r for r in ROWS if r['suffix']=='.pdf' and f'{year}年' in r['file'] and 'B1' in r['file'] and '解析' not in Path(r['file']).name and '补充' not in r['file'] and '打印' not in r['file'])

def questions(year):
 r=paper(year);src=INPUT/r['file'];doc=fitz.open(src)
 txt='\n'.join(p.get_text(sort=True,clip=fitz.Rect(0,0,p.rect.width,p.rect.height*.96)) for p in doc[:2])
 txt=re.split(r'READING COMPREHENSION',txt,flags=re.I)[0]
 txt=re.sub(r'(?m)^.*?2\s*0\s*\d\s*\d\s*[-~]\s*\d+\s*$','',txt)
 txt=re.sub(r'(?m)^.*?~\s*\)?\\.*?20\d\d\s*-\s*\d+\s*$','',txt)
 starts=list(re.finditer(r'(?m)^\s*(\d{1,2})\s*\.+\s*(?=A[.\s])',txt))
 out=[]
 for i,m in enumerate(starts):
  n=int(m[1]);seg=txt[m.end():starts[i+1].start() if i+1<len(starts) else len(txt)]
  seg=re.split(r'Now\s*,?\s*listen\s+to\s+Part\s+Two',seg,flags=re.I)[0]
  opts=list(re.finditer(r'(?<![\w.])([ABCD])\s*[.．]\s*(?=\S)|(?<![\w.])([BD])\s+(?=[A-Z][a-z])',seg))
  if len(opts)!=4 or [m[1] or m[2] for m in opts]!=list('ABCD'):
   raise ValueError((year,n,'选项定位失败',[(o[1] or o[2],o.start()) for o in opts],seg))
  vals=[re.sub(r'\s+',' ',seg[o.end():opts[j+1].start() if j+1<4 else len(seg)]).strip() for j,o in enumerate(opts)]
  # 去掉页面脚注（原题仍保留原文；仅剥离非题面文字）。
  vals[-1]=re.sub(r'\s+PART[-\s]+[IU]+\s*$','',vals[-1]).strip()
  vals[-1]=re.sub(r'\s*[~专][^\n]*?20\d\d\s*-\s*\d+\s*$','',vals[-1]).strip()
  out.append({'n':n,'stem':'','options':vals,'answer':None,'group':'interview1' if n<=5 else 'interview2'})
 assert [q['n'] for q in out]==list(range(1,11)),(year,[q['n'] for q in out])
 return out

if __name__=='__main__':
 for y in range(2009,2016):
  try:
   qs=questions(y)
   print(y)
   for q in qs:print(q['n'],q['options'])
  except Exception as e:print(y,'ERROR',e)
