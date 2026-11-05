"""关卡 4 的第一个答案来源：解析 PDF 里每题的官方答案（按左右半栏分开取文字，按阅读顺序抽“答案为 X”这类标记）。
解析是两栏排版，整页取文字会把左右两栏的同一行拼在一起、两题答案顺序颠倒（踩坑记录：202306-1 两栏交错）。做法：
  每页渲染 200 dpi，左半、右半分别 tesseract（chi_sim+eng，psm 6），阅读顺序 = 第 1 页左、第 1 页右、第 2 页左……；
  只取 Listening Comprehension 到 Reading Comprehension 之间；抽 答案为 X / X)【精析】/ 故 X 为正确答案 / 答案是 X 项 / 选项 X 是正确答案 …；
  恰好 25 个才算数，否则记“抽不全”（交第二来源 + 看图）。
材料：老师 Release 的 default.zip 里的解析 PDF（取材料.py，核 sha256）。
用法：python3 解析答案.py <套> … | ALL      输出 四级/听力/<套>/解析答案.json {"答案": "25 个字母" 或 null, "抽到": n, "序列": "…"}
"""
import json, re, subprocess, sys, tempfile, zipfile, hashlib, os
from pathlib import Path
H = Path(__file__).resolve().parents[1]
JX = json.loads((H / '原始材料/解析清单.json').read_text('utf-8'))
ZIP = Path(os.environ.get('CET4_ZIP', '/tmp/cet4-default.zip'))
INNER = '四级听力视频/解析 听力原文对照.zip'
PAT = (r'答案[为是]\s*([A-D])|([A-D])\s*[)）]?\s*【\s*精\s*析|选项\s*([A-D])\s*[)）]?\s*[为是]?正确答案|([A-D])\s*[)）]?\s*项?\s*[为是]正确答案'
       r'|故\s*([A-D])\s*[)）]?\s*项?\s*[为是]?正确|答案是\s*([A-D])|故\s*答案\s*[为是]?\s*([A-D])|因此\s*选\s*([A-D])|故\s*选\s*([A-D])|所以\s*选\s*([A-D])')


def pdf_bytes(sid):
    info = JX[sid]
    with zipfile.ZipFile(ZIP) as z:
        name = next(n for n in z.namelist() if n.endswith('.zip') and '解析' in n)
        import io
        with zipfile.ZipFile(io.BytesIO(z.read(name))) as z2:
            for i in z2.infolist():
                nm = i.filename if i.flag_bits & 0x800 else i.filename.encode('cp437').decode('gbk', 'ignore')
                if nm.endswith(info['原名']) or info['原名'].endswith(nm.split('/', 1)[-1]):
                    b = z2.read(i)
                    if hashlib.sha256(b).hexdigest() == info['sha256']: return b
    raise SystemExit(f'{sid}：zip 里找不到解析 {info["原名"]}（或 sha256 不符）')


def page_text(pdf, p, tmp):
    png = Path(tmp) / f'p{p}'
    subprocess.run(['pdftoppm', '-f', str(p), '-l', str(p), '-r', '200', '-gray', '-png', '-singlefile', pdf, str(png)], check=True, capture_output=True)
    from PIL import Image
    im = Image.open(f'{png}.png'); w, h = im.size
    out = []
    for k, box in enumerate([(0, 0, w // 2 + 8, h), (w // 2 - 8, 0, w, h)]):
        f = Path(tmp) / f'p{p}_{k}.png'; im.crop(box).save(f)
        out.append(subprocess.run(['tesseract', str(f), '-', '-l', 'chi_sim+eng', '--psm', '6'], capture_output=True, text=True).stdout)
    return out


def run(sid):
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / 'jx.pdf'; pdf.write_bytes(pdf_bytes(sid))
        cache = H / sid / '解析半栏.txt'
        if cache.exists():
            txt = cache.read_text('utf-8')
        else:
            parts = []
            for p in range(1, min(JX[sid]['pages'], 9) + 1):
                l, r = page_text(str(pdf), p, tmp)
                parts += [f'=== 第 {p} 页 左', l, f'=== 第 {p} 页 右', r]
            txt = '\n'.join(parts); cache.write_text(txt, 'utf-8')
    t = re.sub(r'(?<=[一-鿿])\s+(?=[一-鿿])', '', txt)
    i = t.find('Listening'); i = i if i >= 0 else t.find('Section A')
    j = re.search(r'Reading\s*Comprehension|Part\s*(III|Ⅲ)\b', t[i + 400:])
    L = t[i: i + 400 + j.start()] if j else t[i:]
    # 按题号就近配：阅读顺序里每个答案标记归给它前面最近的题干（n. What / Why …），每题只取第一个；
    # 另外“n. 答案 X”这种带题号的直接按题号（202012-1 版式）
    ANS = r'答案\s*[为是选:：;；]?\s*([A-D])(?![a-z])|([A-D])\s*[)）]?\s*[【〖\[]{1,2}\s*精\s*析|([A-D])\s*[)）]?\s*项?\s*[为是]正确答案|选项\s*([A-D])\s*[)）]?\s*[为是]?正确'
    QN = r'(?<![\d\[(（])(\d{1,2})\s*[.．]\s*(?=(?:What|Why|How|Who|Which|When|Where|According|In |For |On |答案))'
    toks = sorted([(m.start(), 'q', int(m.group(1))) for m in re.finditer(QN, L) if 1 <= int(m.group(1)) <= 25] +
                  [(m.start(), 'a', next(g for g in m.groups() if g)) for m in re.finditer(ANS, L)])
    by, cur, seen = {}, None, set()
    for _, typ, v in toks:
        if typ == 'q':
            cur = v if v not in seen else cur; seen.add(v)
        elif cur and cur not in by:
            by[cur] = v
    seq = ''.join(by.get(n, '?') for n in range(1, 26))
    res = {'答案': {str(n): by[n] for n in by}, '序列': seq}
    (H / sid / '解析答案.json').write_text(json.dumps(res, ensure_ascii=False), 'utf-8')
    print(sid, seq)


if __name__ == '__main__':
    ids = sys.argv[1:]
    if ids == ['ALL']: ids = sorted(JX)
    for s in ids: run(s)
