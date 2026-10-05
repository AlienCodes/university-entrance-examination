import json,re,sys
from pathlib import Path
SP=Path('/tmp/claude-0/-home-user/8ecea899-aaa9-5a52-878f-ec29bb403c87/scratchpad')
ABBR=r'(?:Mr|Mrs|Ms|Dr|Prof|St|Jr|Sr|vs|etc|e\.g|i\.e|U\.S|U\.K|Ph\.D|a\.m|p\.m|No|Inc|Co|Ltd)'
def split(p):
    q=re.sub(r'\b('+ABBR+r')\.',lambda m:m.group(1).replace('.','<D>')+'<D>',p)
    q=re.sub(r'(?<![A-Za-z])([A-HJ-Z])\.(?=\s+[A-Z])',r'\1<D>',q)
    parts=re.split(r'(?:(?<=[.!?])|(?<=[.!?][”’)]))\s+(?=[“‘(]?[A-Z0-9])',q)
    return [x.replace('<D>','.') for x in parts if x.strip()]
def gen(P,outdir,pages):
    outdir.mkdir(exist_ok=True,parents=True)
    for p in P:
        imgs=[str(SP/'cet4img'/f"{p['img']}_p{i}.png") for i in pages[p['img']]]
        L=[f"# {p['id']} CET-4 (College English Test Band 4) {p['year']}-{p['month']:02d} Set {p['set']} Reading Section C {p['passage']}",
           f"Printed exam page image(s) — the source of truth for transcription: {' , '.join(imgs)}",
           *([f"NOTE: the PDF text layer of this scanned paper was unusable, so this text was re-typed by hand from the page image — transcription mistakes are possible; compare with special care."] if p['year']==2021 else []),
           *([f"Already corrected on purpose (obvious errors in the printed paper; do NOT report these differences from the print): " + ' ; '.join(f"'{e['old']}' → '{e['new']}'" for e in p.get('edits',[]))] if p.get('edits') else []),
           "House style applied on purpose (do NOT report as differences from the print): curly quotes/apostrophes; em dashes without spaces; en dash in number ranges; Chinese footnotes written as 'word (中文)'; spacing fixes.",
           "Each paragraph is ¶n; each sentence is [n.m] (paragraph n, sentence m). Chinese in parentheses after a word is the exam's own footnote gloss.",""]
        for i,para in enumerate(p['paras'],1):
            L.append(f"¶{i}")
            for j,s in enumerate(split(para),1): L.append(f"[{i}.{j}] {s}")
            L.append("")
        (outdir/f"{p['id']}.txt").write_text('\n'.join(L),'utf-8')
if __name__=='__main__':
    P=json.load(open('四级/仔细阅读/passages.json'))
    E=json.load(open('四级/tools/原文订正.json'))
    for p in P: p['img']=p['id']; p['edits']=E.get(f"{p['paper']} {p['passage']}",[])
    pages=json.load(open(SP/'cet4img'/'pages.json'))
    gen(P,SP/sys.argv[1],pages)
