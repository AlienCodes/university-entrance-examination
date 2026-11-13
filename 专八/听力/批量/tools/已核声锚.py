"""采用有证据的整词/专名声锚及非言语事件，绝不分摊词内时刻。"""
import copy
import hashlib
import json
from pathlib import Path
import re

FIELDS=('proper_name_audio_anchors','reviewed_word_audio_anchors','reviewed_phrase_audio_anchors','reviewed_interjection_audio_anchors')
NONVERBAL={'ha','hah','haha','emm','mm','mmm','hmm','um','uh','ah','oh','eh','humming','laughter','laughing'}


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def checked_word_anchor(anchor, sentence, base, prep):
    a,z=anchor['char'];assert 0<=a<z<=len(sentence['en'])
    text=sentence['en'][a:z]
    if anchor.get('text'):assert text==anchor['text']
    ref=(base/anchor['asr_ref']).resolve();assert ref.is_relative_to(base.resolve())
    expected=anchor.get('asr_sha256')
    if expected:assert sha(ref)==expected,'已核声锚的引用SHA改变'
    obj=json.loads(ref.read_text('utf-8'));root=obj
    known={prep['canonical']['sha256'],*(x['sha256'] for x in prep['source_entries'])}
    declared=root.get('canonical_sha256',root.get('canonical_source_sha256')) if isinstance(root,dict) else None
    if declared:assert declared==prep['canonical']['sha256'],'已核声锚引用不同canonical'
    if isinstance(root,dict) and root.get('source_sha256'):assert root['source_sha256'] in known,'已核声锚音源不符'
    for key in anchor.get('asr_pointer','').strip('/').split('/'):
        if key:obj=obj[int(key)] if isinstance(obj,list) else obj[key]
    i,j=anchor['asr_range'];words=obj[i:j];assert words
    lo,hi=min(w[1] for w in words),max(w[2] for w in words)
    assert 0<=lo<hi<=prep['canonical']['duration']+.1
    assert abs(anchor['start']-lo)<.015 and abs(anchor['end']-hi)<.015,'声锚时刻必须为真实词表整体边界'
    return {'char':a,'char_end':z,'start':lo,'end':hi,'whole_reviewed_ASR_span':True,
            'evidence_ref':str(ref.relative_to(base)),'evidence_sha256':sha(ref),
            'asr_pointer':anchor.get('asr_pointer',''),'asr_range':[i,j],'asr_words':words,
            'source_text':text,'decision':anchor.get('decision',anchor.get('method','已核整词/专名实际声段')),
            'source_refs':anchor.get('source_refs',[])}


def apply(result, draft, prep, base, nonverbal_files=()):
    base=Path(base);src=result['source'];evidence=[];covered=set();nonverbal_ids=set()
    for row in result['rows']:
        s=row['sentence'];supplied=[]
        for field in FIELDS:
            for anchor in s.get(field,[]):
                proof=checked_word_anchor(anchor,s,base,prep);proof['field']=field
                a,z=proof['char'],proof['char_end']
                ids=[i for i in row['lexemes'] if a<=src[i].char and src[i].char_end<=z]
                assert ids and not any(src[i].char<a<src[i].char_end or src[i].char<z<src[i].char_end for i in row['lexemes'])
                covered.update(ids)
                row['word_alignment']=[w for w in row['word_alignment'] if w['char_end']<=a or z<=w['char']]
                row['word_alignment'].append({k:v for k,v in proof.items() if k not in ('field','source_refs','decision')})
                row['missing']=[i for i in row['missing'] if i not in ids]
                supplied.append(proof);evidence.append({'unit':row['unit'],'sentence':row['n'],**proof})
        if supplied:
            row['word_alignment'].sort(key=lambda w:w['char'])
            assert all(a['start']<=z['start'] for a,z in zip(row['word_alignment'],row['word_alignment'][1:])),('已核声锚与邻词逆序，须复核整句窗口',row['unit'],row['n'])
            row['anchor_window']=[row['word_alignment'][0]['start'],max(w['end'] for w in row['word_alignment'])]
            row['boundary_anchored']=row['lexemes'][0] not in row['missing'] and row['lexemes'][-1] not in row['missing']
            row['reviewed_whole_ASR_evidence']=supplied
    event_evidence=[]
    for filename in nonverbal_files:
        path=Path(filename);path=path if path.is_absolute() else base/path
        if not path.exists():continue
        obj=json.loads(path.read_text('utf-8'));assert obj['year']==draft['year'] and obj['canonical_source_sha256']==prep['canonical']['sha256']
        for event in obj['events']:
            assert event.get('nonverbal') is True and event.get('decision','').strip()
            rows=[r for r in result['rows'] if r['unit']==event['unit'] and r['sentence']['en']==event['en']]
            assert len(rows)==1,'非言语事件须以完整EN唯一匹配，不用旧ordinal'
            row=rows[0];assert all(src[i].text.lower() in NONVERBAL for i in row['lexemes']),'普通实词不能伪装非言语事件免除词锚'
            ref=(base/event['evidence_ref']).resolve();assert ref.is_relative_to(base.resolve())
            assert sha(ref)==event['evidence_sha256'],'非言语声学证据SHA不符'
            lo,hi=event['start'],event['end'];assert 0<=lo<hi<=prep['canonical']['duration']
            pos=result['rows'].index(row)
            if pos and result['rows'][pos-1].get('anchor_window'):assert result['rows'][pos-1]['anchor_window'][1]<=lo+.15
            if pos+1<len(result['rows']) and result['rows'][pos+1].get('anchor_window'):assert hi<=result['rows'][pos+1]['anchor_window'][0]+.15
            row['nonverbal_boundary']=[lo,hi];row['nonverbal_evidence']={**copy.deepcopy(event),'manifest':str(path.relative_to(base)),'manifest_sha256':sha(path)}
            row['missing']=[];row['word_alignment']=[];nonverbal_ids.update(row['lexemes']);event_evidence.append(row['nonverbal_evidence'])
    lexical=set(result['mapping'])|covered
    result['coverage'].update({'source_mapped':len(lexical-nonverbal_ids),'source_lexical_lexemes':len(src)-len(nonverbal_ids),
        'external_reviewed_ASR_lexemes':len(covered),'nonverbal_not_word_lexemes':len(nonverbal_ids),
        'source_ratio':len(lexical-nonverbal_ids)/(len(src)-len(nonverbal_ids)),
        'all_source_mapped':len(lexical|nonverbal_ids)==len(src),
        'all_boundaries_anchored':all(r['boundary_anchored'] or r.get('nonverbal_boundary') for r in result['rows'])})
    if evidence or event_evidence:result['coverage']['literal_complete']=False
    return evidence,event_evidence
