"""只读已成功43段的持久证据与真实producer；不碰两个待恢复叶、不生成/重试/批准任何媒体。"""
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('tem8_good43_audit',HERE/'精听缓存核齐与组装调度.py')
A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
P=A.pub
ids=sorted(set(A.pin['expected_payload_sha256'])-{'2022-A','2024-A'})
assert len(ids)==43
release=P.release(P.CACHE_TAG);rows=[]
producer={'run_id':A.pin['production_run'],'commit':A.pin['production_commit']}
for ident in ids:
    assert P.gate('intensive',ident)['payload_sha256']==A.pin['expected_payload_sha256'][ident]
    rows.append(A.cache_producer(ident,producer,release))
    record={'status':'in-progress' if len(rows)<43 else 'pass','checked_at':A.now(),'producer':producer,
            'count':len(rows),'target_count':43,'excluded_failed_leaves':['2022-A','2024-A'],'rows':rows,
            'scope':'真实ZIP CRC/每个证据SHA/原producer/输入/当前完整审核/PNG/clock/原音/服务器MP4摘要；只读，不冒称45或整套完成'}
    P.dump(HERE/'精听43已成品严格核验.json',record)
    print('GOOD43_STRICT',len(rows),ident,flush=True)
print('GOOD43_ALL_STRICT_PASS',flush=True)
