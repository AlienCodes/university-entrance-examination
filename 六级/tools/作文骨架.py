"""一次性：由 作文题截取.py 的输出生成 六级/作文/<年>.json 骨架（body 留空；已存在的篇目保留 body）。
OCR 订正逐条写在 FIX（每条必须恰好匹配一次）；2021-06 两套截不到，按 PDF 原页手录。"""
import json, re, pathlib, subprocess, sys
D = pathlib.Path(__file__).resolve().parents[1]
raw = subprocess.run([sys.executable, str(D / 'tools/作文题截取.py')], capture_output=True, text=True).stdout
FIX = {('2022-06', 1): [('lifestyle.99', 'lifestyle.”')], ('2022-06', 2): [('world."', 'world.”')]}
MANUAL = {
 ('2021-06', 1): "Directions: For this part, you are allowed 30 minutes to write an essay based on the graph below. You should start your essay with a brief description of the graph and comment on China’s achievements in urbanization. You should write at least 150 words but no more than 200 words.\n\nDegree of urbanization in China from 1980 to 2019\n\n【图表】折线图（城镇化率）：1980 年 19.39%，1985 年 23.71%，1990 年 26.41%，1995 年 29.04%，2000 年 36.22%，2005 年 42.99%，2010 年 49.95%，2011 年 51.27%，2013 年 53.73%，2015 年 56.1%，2016 年 57.35%，2018 年 59.58%，2019 年 60.6%（2012、2014、2017 年只画点、未标数值）",
 ('2021-06', 2): "Directions: For this part, you are allowed 30 minutes to write an essay based on the chart below. You should start your essay with a brief description of the chart and comment on China’s achievements in higher education. You should write at least 150 words but no more than 200 words.\n\nGross enrolment ratio in higher education in China (1990-2019)\n\nSource: Ministry of Education\n\n【图表】柱状图 + 折线（高等教育毛入学率）：1990 年 3.4%，1995 年 6.86%，2000 年 11%，2001 年 13.3%，2002 年 15%，2003 年 17%，2004 年 19%，2005 年 21%，2006 年 22%，2007 年 23%，2008 年 23.3%，2009 年 24.2%，2010 年 26.5%，2011 年 26.95%，2012 年 30%，2013 年 34.5%，2014 年 37.5%，2015 年 40.0%，2016 年 42.7%，2017 年 45.7%，2018 年 48.1%，2019 年 51.6%",
}
items = {}
for blk in re.split(r'^=== ', raw, flags=re.M)[1:]:
    head, _, txt = blk.partition('\n')
    m = re.match(r'(\d{4}-\d\d) 第(\d)套', head); k = (m[1], int(m[2]))
    txt = MANUAL.get(k) or txt.strip()
    assert txt != '截取失败', k
    for a, b in FIX.get(k, []):
        assert txt.count(a) == 1, (k, a); txt = txt.replace(a, b)
    assert '"' not in txt and "'" not in txt.replace('’', ''), k
    items[k] = txt
for y in sorted({k[0][:4] for k in items}):
    p = D / '作文' / f'{y}.json'
    old = {e['id']: e for e in json.loads(p.read_text())} if p.exists() else {}
    out = []
    for (ym, n), txt in sorted(items.items(), key=lambda kv: (kv[0][0], kv[0][1]), reverse=True):
        if ym[:4] != y: continue
        i = f'c{ym}-{n}'
        q = re.search(r'begins with the sentence “([^”]+)”', txt)
        typ = '图表作文' if '【图表】' in txt else '短文评论（现象 + 对策）' if 'short passage' in txt else '议论文（给定首句）'
        e = {'id': i, 'paper': f'{ym[:4]}年{int(ym[5:])}月大学英语六级 第{n}套', 'part': 'Part I Writing', 'type': typ,
             'limit': 'at least 150 words but no more than 200 words' + (' (not including the sentence given)' if 'not including' in txt else ''),
             'prompt': txt}
        if q: e['first'] = q[1]
        e['body'] = old.get(i, {}).get('body', [])
        out.append(e)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(y, len(out))
