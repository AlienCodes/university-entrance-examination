"""把已核定题目、实际静音/词锚和音乐证据登记进考试时间轴。

只处理已明确解决的候选说明：整块展示正式说明，避免以部分ASR做错误
逐句高亮；漏题号必须有年度题干定点复识别。未知候选一律停止。
"""
import argparse,hashlib,json
from pathlib import Path
B=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def run(y):
 p=B/'数据'/str(y)/'时间轴.json';d=read(p);rp=B/'核验'/f'{y}-考试内容审核.json';r=read(rp)
 assert r['year']==y and r['status']=='content-checked' and not r['remaining_paper_pending']
 assert r['asr_sha256']==sha(B/'预处理'/str(y)/'识别.json'), '内容核验未对应当前音源ASR'
 music=read(B/'音乐剪切'/f'{y}.json');assert music['source_sha256']==d['source_sha256'] and not music['pending']
 old=d['pending'];evidence=[]
 for note in old:
  if isinstance(note,dict) and 'section' in note and note.get('issue','').startswith('说明前缀未唯一对应'):
   evidence.append({'original_note':note,'resolution':'已核原卷说明及原音结构；完整说明块静态展示，不用部分识别猜逐句高亮。预览后的Now listen/When it is over在完整答题卡画面播放，口令音频完整保留。'})
  elif isinstance(note,dict) and 'question' in note:
   q=next(q for q in r['questions'] if q['n']==note['question']);assert q['normalized_exact'] and q['short_audio_asr_recheck']
   evidence.append({'original_note':note,'resolution':'定点小片段重新识别已核题号和题干，显示从前题作答实测终点开始，详见年度内容审核。','question_start':q['canonical_question_start']})
  elif isinstance(note,str) and note.startswith('ASR漏了Section A完整词形') and y in [2010,2013]:
   evidence.append({'original_note':note,'resolution':'唯一说明前标题词锚保留；对应年度正式说明局部识别已恢复Section A，整块说明静态展示，不制造漏词时刻。'})
  else:raise ValueError(('未知未解决时间轴候选',y,note))
 d['events']=[ev for ev in d['events'] if not(ev['kind']=='instr' and ev.get('hi',-1)>=0)]
 d['pending']=[];d['待核']=[];d['review']={'status':'timeline-checked','evidence':f'核验/{y}-时间轴说明处理.json；核验/{y}-考试内容审核.json；音乐剪切/{y}.json','instruction_display':'完整原卷说明静态展示，不以部分ASR猜逐句高亮'}
 dump(p,d);dump(B/'核验'/f'{y}-时间轴说明处理.json',{'year':y,'status':'resolved','content_audit_sha256':sha(rp),'music_sha256':sha(B/'音乐剪切'/f'{y}.json'),'timeline_sha256':sha(p),'items':evidence,'audio_changes':'仅按已核音乐剪点去头，正式说明/预览/讲座/作答/检查均保留原音时长'})
 print(y,'reviewed',len(d['events']),'events')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('years',type=int,nargs='+');a=p.parse_args()
 for y in a.years:run(y)
