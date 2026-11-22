"""Independently draft a sentence translation with Tencent's offline translation model."""
import json
import os
import re
import urllib.request


def translate_sentence(sentence, previous, term_hints, notes):
    facts = ['%s 对应 %s' % (a,b) for a,b in term_hints if a and b]
    facts += [str(note['check']) for note in notes if isinstance(note,dict) and note.get('check')]
    prompt = ''
    if previous:
        prompt += '原文上文：'+previous+'\n'
    if facts:
        prompt += '本句的术语与语境参考：\n'+'\n'.join(facts) + '\n'
    if prompt:
        prompt += '参考上面的信息，把下面的文本翻译成简体中文，注意不需要翻译上文，也不要额外解释：\n\n'
    else:
        prompt += '将以下文本翻译为简体中文，注意只需要输出翻译后的结果，不要额外解释：\n\n'
    req={'messages':[{'role':'user','content':prompt+sentence}], 'temperature':0.15, 'top_k':20,
         'top_p':0.6,'repeat_penalty':1.05,'seed':6285,'max_tokens':max(160,min(1100,len(sentence)*2))}
    url=urllib.request.Request('http://127.0.0.1:'+os.environ.get('IELTS_MT_PORT','8124')+'/v1/chat/completions',
        data=json.dumps(req,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(url,timeout=600) as response:choice=json.load(response)['choices'][0]
    text=choice['message']['content'].strip()
    if choice.get('finish_reason')=='length' or not re.search(r'[\u3400-\u9fff]',text):
        raise ValueError('Incomplete reference translation')
    return text
