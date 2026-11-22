from pathlib import Path
from zipfile import ZipFile
import hashlib, json, re, sys
from lxml import etree as ET

from argparse import ArgumentParser
parser=ArgumentParser(description='Re-extract the checked Word paragraphs and evidence for Cambridge IELTS 21.')
parser.add_argument('docx',type=Path)
parser.add_argument('output',type=Path)
parser.add_argument('ids',nargs='*')
args=parser.parse_args()
ROOT=args.output
DOCX=args.docx
for folder in ['source','proof','work']:
    (ROOT/folder).mkdir(exist_ok=True,parents=True)
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
DIGEST = hashlib.sha256(DOCX.read_bytes()).hexdigest()
assert DIGEST == '8bcfdef900c65bdb2a3fcda7f48e11b486a48e2063376bfabd20a4892e57e8eb'
INDEX = 'One-based /w:document/w:body/w:p in word/document.xml; includes blank top-level paragraphs, excludes paragraphs nested within tables. The python-docx Document.paragraphs index is this number minus one.'
with ZipFile(DOCX) as archive:
    document = ET.fromstring(archive.read('word/document.xml'))
    plist = document.xpath('w:body/w:p', namespaces=NS)
    assert len(plist) == 676

# title, subtitle, final prose paragraph, section label paragraphs, lexicographic notes
PASSAGES = {
    'C21T1P1': (5,[6],16,[],[18,19,20]), 'C21T1P2': (55,[],71,[56,58,60,62,64,67,70],[]),
    'C21T1P3': (105,[],113,[],[]), 'C21T2P1': (172,[],182,[],[]),
    'C21T2P2': (203,[204],218,[205,207,209,211,213,215,217],[220]),
    'C21T2P3': (248,[],261,[],[]), 'C21T3P1': (320,[],329,[],[]),
    'C21T3P2': (362,[],372,[],[]), 'C21T3P3': (401,[],410,[],[]),
    'C21T4P1': (471,[],482,[],[]), 'C21T4P2': (521,[],531,[],[533]),
    'C21T4P3': (575,[576],584,[],[586,587]),
}

def digest(data):
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def dump(path, value):
    data = json.dumps(value,ensure_ascii=False,indent=1) + '\n'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(data)
    temporary.replace(path)
    return digest(data)

def word_text(element):
    mapping={'tab':'\t','br':'\n','cr':'\n','noBreakHyphen':'‑','softHyphen':'\u00ad'}
    return ''.join(node.text or '' if (name:=ET.QName(node).localname)=='t' else mapping[name]
                   for node in element.iter() if ET.QName(node).localname in {'t',*mapping})

def raw(number):
    return word_text(plist[number-1])

def normal(text):
    return ' '.join(text.split())

ABBREVIATION = re.compile(r'(?:\b(?:Mr|Mrs|Ms|Dr|Prof|Mt|St|Fig|No|vs|etc|Jr|Sr|ca|c)|\be\.g|\bi\.e|\bet al|\b[A-Z])\.$')
TERMINAL = re.compile(r'''[.!?]+[’”"')\]]*(?=\s+|$)''')

def sentences(text):
    result=[]; start=0
    for m in TERMINAL.finditer(text):
        boundary=m.end()
        if boundary==len(text):
            continue
        next_token=text[boundary:].lstrip().lstrip('‘“"\'([')
        if not next_token or not (next_token[0].isupper() or next_token[0].isdigit()):
            continue
        if ABBREVIATION.search(text[:boundary].rstrip('’”"\')]:')):
            continue
        result.append(text[start:boundary].strip())
        start=boundary
    result.append(text[start:].strip())
    assert all(result) and ' '.join(result)==text
    return result

def word_proof(number,role):
    obj=plist[number-1]
    raw_text=raw(number)
    pos=0;spans=[]
    for run in obj.xpath('.//w:r',namespaces=NS):
        value=word_text(run)
        attrs=[]
        for tag in ('i','b','vertAlign'):
            prop=run.find('w:rPr/w:'+tag,NS)
            if prop is not None and prop.get('{'+W+'}val') not in ('false','0','off','baseline'):
                attrs.append(prop.get('{'+W+'}val') if tag=='vertAlign' else {'i':'italic','b':'bold'}[tag])
        if attrs and value:spans.append({'raw_document_range':[pos,pos+len(value)],'format':attrs})
        pos+=len(value)
    assert pos==len(raw_text)
    report={'word_paragraph':number,'python_docx_index':number-1,'role':role,
            'raw_text_sha256':digest(raw_text),'raw_text':raw_text}
    if spans:report['formatted_runs']=spans
    return report

def one(pid):
    title,subs,last,section_idx,notes=PASSAGES[pid]
    test,passage=map(int,re.fullmatch(r'C21T(\d)P(\d)',pid).groups())
    body=[i for i in range(title+1,last+1) if i not in section_idx]
    normalized={i:normal(raw(i)) for i in [title,*body,*section_idx,*notes]}
    paras=[sentences(normalized[i]) for i in body]
    labels={i+1:normalized[i] for i in section_idx}
    notes_list=[normalized[i] for i in notes]
    edits=[]
    if pid=='C21T1P1':
        duplicate='by Renoir, including his well-known painting La Parisienne'
        idx=notes.index(20)
        assert notes_list[idx].endswith(' '+duplicate) and normalized[11].endswith(duplicate+'.')
        notes_list[idx]=notes_list[idx].removesuffix(' '+duplicate)
        edits.append({'kind':'duplicate body text appended to third vocabulary note','word_paragraph':20,'python_docx_index':19,
                      'source_note':normalized[20],'edited_note':notes_list[idx],'duplicate_from_word_paragraph':11,
                      'duplicate_from_python_docx_index':10,'body_ending':paras[body.index(11)][-1],
                      'evidence':'Exact contiguous repeated phrase. In paragraph 11 it completes the count of paintings in the sisters’ collection. In footnote 20 the definition of the term is already complete at “the late 1800s”. The museum collection record independently identifies the artist, painting and purchase by Gwendoline Davies. Some online transcriptions repeat the same tail; the provenance of the duplication is undetermined.',
                      'references':[{'publication':'Amgueddfa Cymru — Museum Wales, La Parisienne, collection record','url':'https://museum.wales/collections/online/object/201d93ef-22a7-3af9-b244-0a54d11625fa/The-blue-lady/'},{'publication':'Test transcription with definition ending at 1800s','url':'https://www.scribd.com/document/1046487609/Reading-Cam-21-Passage-1-Test-1'}]})
    provenance={'file':DOCX.name,'kind':'docx','part':'word/document.xml','indexing':INDEX,
                'title_paragraph':title,'subtitle_paragraphs':subs,'section_label_paragraphs':section_idx,
                'footnote_paragraphs':notes}
    out={'id':pid,'book':21,'test':test,'passage':passage,'title':normalized[title],'paragraphs':paras,
         'paragraph_labels':[labels.get(i) for i in body],'subtitle':' '.join(normalized[i] for i in subs),
         'subtitle_paragraphs':[body.index(i) for i in subs],'footnotes':notes_list,'docx_paragraphs':body,
         'source_sha256':DIGEST,'passage_provenance':provenance}
    all_rows=sorted([title,*body,*section_idx,*notes])
    word_rows=[]
    for i in all_rows:
        role='title' if i==title else 'standfirst' if i in subs else 'section_label' if i in section_idx else 'footnote' if i in notes else 'body'
        item=word_proof(i,role)
        if i in body:
            j=body.index(i);item['output_paragraph_index']=j;item['sentence_count']=len(paras[j])
            offset=0;spans=[]
            for sentence in paras[j]:
                begin=normalized[i].index(sentence,offset);end=begin+len(sentence)
                spans.append([begin,end]);offset=end
            item['normalized_sentence_ranges']=spans
        word_rows.append(item)
    proof={'id':pid,'source_file':DOCX.name,'source_sha256':DIGEST,'indexing':INDEX,'passage_provenance':provenance,'word_paragraphs':word_rows,
           'normalization':'Collapse whitespace, nonbreaking spaces, and manual Word line breaks to one text space. Preserve original letter case, apostrophes, quotation marks, footnote symbols and substantive punctuation; content-specific corrections are listed individually.',
           'excluded':{'section_prompt_word_paragraphs':[title-2,title-1],
                       'divider_word_paragraphs':[i for i in range(last+1,max(notes+[last])+1) if i not in notes],
                       'next_exercise_word_paragraph':max(notes+[last])+1,'next_exercise_heading':normal(raw(max(notes+[last])+1))},
           'edits':edits,'sentence_counts_after':list(map(len,paras)),'final_english_sha256':dump(ROOT/'source'/f'{pid}.json',out)}
    assert proof['excluded']['next_exercise_heading'].startswith('Questions')
    if pid=='C21T2P2':
        proof['preserved_source_readings']=[{'word_paragraph':204,'reading':'the kingdom of Mapungubwe, flourished','action':'The uploaded Word has a comma between subject and verb. Kept as supplied; no page image of the printed book supplied.'}]
    dump(ROOT/'proof'/f'{pid}.json',proof)
    lines=[];n=0
    for i,para in zip(body,paras):
        lines.append(f'\nWord {i}')
        for sentence in para:
            n+=1;lines.append(f'{n} {sentence}')
    (ROOT/'work'/f'{pid}-en.txt').write_text('\n'.join(lines)+'\n')
    print(pid,len(paras),n,'notes',len(notes),'word',title,last)

for key in args.ids or PASSAGES:
    one(key)
