"""核对取回的50套准备材料及其原声、逐词识别哈希；不做语义审校通过登记。"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parents[1]
papers = json.loads((P / '套.json').read_text('utf-8'))
manifest = json.loads((HERE / '来源清单.json').read_text('utf-8'))
assert manifest['套数'] == len(papers) == 50
assert set(manifest['套']) == set(papers)
for sid, paper in papers.items():
    row = manifest['套'][sid]
    d = HERE / sid
    raw = (P / '识别' / paper['识别'] / '原音.sha256').read_text().split()[0]
    report = json.loads((d / '转写差异.json').read_text('utf-8'))
    assert row['卷名'] == paper['名'] == report['套'], sid
    assert row['原音_sha256'] == raw == report['原音_sha256'], sid
    data = (d / '识别.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == row['逐词文件_sha256'], sid
    words = json.loads(data)
    assert len(words) == row['逐词数量'] > 0, sid
    assert all(len(w) == 3 and isinstance(w[0], str) and 0 <= w[1] <= w[2] for w in words), sid
    assert all(words[i][1] <= words[i+1][1] for i in range(len(words)-1)), sid
print('通过：50/50套原声SHA-256、逐词文件SHA-256、卷别、数量和时间顺序；仍须语义审校。')
