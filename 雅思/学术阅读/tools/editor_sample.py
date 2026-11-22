"""Exercise both independent local language models on a known polysemous example."""
import json
from pathlib import Path
from draft_lesson import translate
from translation import translate_sentence

def main():
    base=Path(__file__).resolve().parents[1]
    row=json.loads((base/'备课/C20T2P1.json').read_text())['rows'][2]
    stem=row['en']
    assert 'Dugongs' in stem and 'manatees' in stem
    zh=translate_sentence(stem,'',row['term_hints'].items(),[])
    if not all(x in zh for x in ('儒艮','海牛','前肢')):raise ValueError(zh)
    guide={1:{'candidates':row['candidates'],'term_hints':row['term_hints'],'translation':zh}}
    unit=translate([(1,stem)],'Manatees','Marine mammals',guide)[0]
    assert unit['zh']==zh and len(unit['v'])>=4,unit
    print(json.dumps(unit,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
