#!/usr/bin/env python3
"""Package the original approved shop images unchanged, complete PDFs and sample."""
import argparse,csv,hashlib,html,io,json,re,shutil
from pathlib import Path
from urllib.parse import quote
from zipfile import ZipFile,ZIP_STORED
import fitz
from PIL import Image
HERE=Path(__file__).resolve().parent
LISTENING=HERE.parent
BRAND = '朋克英语'
PRODUCT = '四级听力真题35套精讲'
TITLE = '四级听力35套精讲｜同义替换·听写本·真题原卷'
TAGLINE = '875道题讲清答案依据，做题、精听、听写一套串起来。'
DESCRIPTION = '''【四级听力35套真题精讲｜全套PDF学习资料】
听完一遍，对了答案，还是不知道自己错在哪里？
这套资料把“答案从哪句来、选项换了什么说法、其他选项为什么错”放到每道题旁边，方便你做完一套就回头精听、复盘。

收录2018年6月—2026年6月，20次考试、35套听力、875道题。

你会收到：
① 真题35套精讲（785页）：原文逐句英汉对照，黄色标出答案出处；每题附选项翻译、答案依据、解题思路、原文与选项对应、错项排除。
② 同义替换手册（44页）：960组原文与正确选项对应，分5类整理，含原词复现，每组标明出处。
③ 高频词手册（21页）：487个词条，按35套原文中的出现套数排序，回到原文记词。
④ 听写本（178页）＋独立答案（73页）：听录音、补关键词，再核对。
⑤ 35天刷题计划（2页）：每天一套，也可按自己的节奏安排；对应精讲页码。
⑥ 另附历年真题原卷。

6份PDF讲义合计1103页（不含另附原卷）。带目录的5份PDF支持目录跳转、书签和“已读”勾选；35天计划用于打卡。适合手机、平板、电脑阅读，也可自行打印。

建议顺序：先做题→找答案依据→对照原文精听→听写→复听错题。可搭配同系列考试版、原文精读视频使用。

适合：想精听真题、需要中文辅助、希望系统复盘错题的四级备考同学。请先查看试读，确认版式与内容适合自己。

本商品为PDF电子资料（虚拟商品），不邮寄纸质书。数字内容交付后一般不支持退换（法律及平台另有规定的除外）；文件损坏、漏发等问题请联系处理。'''


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def write(path, text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8')

def pack(folder, target):
    with ZipFile(target,'w',ZIP_STORED,allowZip64=True) as z:
        for p in sorted(folder.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(folder.parent).as_posix())
    with ZipFile(target) as z:
        assert z.testzip() is None
        assert all(i.flag_bits & 0x800 for i in z.infolist() if not i.filename.isascii())

def check_inputs(pdf_dir):
    files=[]
    names=['四级听力真题35套精讲','四级听力同义替换手册','四级听力高频词手册','四级听力听写本','四级听力听写本（答案）','四级听力35天刷题计划']
    expected=[785,44,21,178,73,2]
    report=[]
    for name,n in zip(names,expected):
        found=[p for p in pdf_dir.rglob('*.pdf') if re.sub(r'^\d+\s+','',p.stem)==name]
        assert len(found)==1,(name,found)
        p=found[0];d=fitz.open(p)
        assert len(d)==n,(p,len(d),n)
        assert all(len(x.get_text().strip())>30 for x in d)
        links=[l for page in d for l in page.get_links()]
        for l in links:
            if l.get('kind')==fitz.LINK_GOTO:assert 0<=l['page']<len(d)
        toc=d.get_toc(); widgets=sum(len(list(x.widgets())) for x in d)
        if n!=2:assert toc and links and widgets
        files.append(p)
        report.append(dict(file=name+'.pdf',pages=len(d),bookmarks=len(toc),links=len(links),checkboxes=widgets,sha256=sha(p)))
    js=[json.loads(p.read_text()) for p in (LISTENING/'讲义/解析').glob('*.json')]
    assert len(js)==35
    for j in js:
        assert set(j['题'])==set(map(str,range(1,26)))
        for q in j['题'].values():
            assert q['答案'] in 'ABCD' and q['依据'] and q['讲'] and q['替换']
            assert len(q['错项'])==3 and set(q['选项译'])==set('ABCD')
    assert sum(len(q['替换']) for j in js for q in j['题'].values())==960
    assert sum(expected)==1103
    assert len(TITLE)<=30 and len(DESCRIPTION)<=1000
    assert not re.search(r'保过|包过|必买|保证提分|100%',TITLE+DESCRIPTION)
    return files,report,js

def navigation(buyer, pdf, js):
    d=fitz.open(pdf)
    lookup={}
    for _,title,page in d.get_toc():
        m=re.search(r'(20\d{2})年(\d+)月\s*第(\d)套',title)
        if m:
            y,month,n=m.groups();lookup[f'{y}{int(month):02}-{n}']=page
    assert len(lookup)==35
    rows=[];data=io.StringIO();w=csv.writer(data)
    w.writerow(['套次','精讲PDF文件页','精讲印刷页','考试视频文件名','原文视频文件名'])
    for j in sorted(js,key=lambda x:x['套'],reverse=True):
        sid=j['套'];y=int(sid[:4]);m=int(sid[4:6]);n=int(sid[-1]);page=lookup[sid]
        title=f'{y}年{m}月 第{n}套';stem=f'{y}-{m}-{n}'
        exam=stem+'考试.mp4';text=stem+'原文.mp4'
        w.writerow([title,page,page-1,exam,text])
        href=quote('1 四级听力真题35套精讲.pdf')+f'#page={page}'
        rows.append(f'<tr><td>{title}</td><td><a href="{href}">打开精讲 · P{page-1}</a></td><td><a href="../四级听力/{quote(exam)}">考试</a></td><td><a href="../四级听力/{quote(text)}">原文</a></td></tr>')
    write(buyer/'35套资料对应索引.csv','\ufeff'+data.getvalue())
    write(buyer/'35套资料导航.html','''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>35套听力资料导航</title><style>body{font:17px/1.7 system-ui,sans-serif;background:#f7f5ec;color:#123c31;max-width:1000px;margin:35px auto;padding:0 22px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;border-bottom:1px solid #d4dfd3;text-align:left}a{color:#14604a}p{color:#4e6859}h1{line-height:1.3}</style><h1>四级听力 · 35套资料导航</h1><p>点击对应套次打开精讲。精讲链接直接定位文件页，表格里的P页码对应讲义印刷页。请按年份、月份和套次匹配资料。</p><p>若一起使用本Release的视频包，将3个视频ZIP解压到与本讲义文件夹相同的位置，它们会合并到“四级听力”文件夹。此时下方视频链接可直接打开；手机阅读器对本地链接的支持可能不同，也可按CSV里的完整文件名查找。</p><table><thead><tr><th>套次</th><th>精讲</th><th>考试视频</th><th>原文精读</th></tr></thead><tbody>'''+''.join(rows)+'</tbody></table></html>')

def build(args):
    dest=args.dest.resolve();dest.mkdir(parents=True,exist_ok=True)
    kit=dest/'四级听力_小店上架包';kit.mkdir(exist_ok=True)
    pics=kit/'1 商品图（原版原样保留）';pics.mkdir(exist_ok=True)
    buyer=dest/'四级听力_全套PDF讲义';buyer.mkdir(exist_ok=True)
    files,report,js=check_inputs(args.pdf_dir)
    for n,p in enumerate(files,1):
        name=re.sub(r'^\d+\s+','',p.name)
        shutil.copyfile(p,buyer/f'{n} {name}')
    navigation(buyer,files[0],js)
    images=sorted(args.original_images.glob('*.jpg'))
    assert len(images)==9
    records=[]
    for image in images:
        with Image.open(image) as im:assert im.size==(2000,2000)
        target=pics/image.name;shutil.copyfile(image,target)
        assert sha(target)==sha(image)
        records.append({'image':image.name,'width':2000,'height':2000,'sha256':sha(image),'identical_to_original':True,'problems':[]})
    # The original product overview is the sample cover; no replacement art.
    trial=fitz.open();cover=trial.new_page(width=595,height=635)
    cover.insert_image(fitz.Rect(0,0,595,595),filename=str(images[0]))
    cover.insert_text((20,620),'免费试读 · 以下9页为正式讲义节选，非完整商品。',fontname='china-s',fontsize=12,color=(0.07,0.24,0.19))
    for n,indices in {1:[4,5,7,8],2:[2],3:[2],4:[3],5:[3],6:[0]}.items():
        source=fitz.open(files[n-1])
        for i in indices:trial.insert_pdf(source,from_page=i,to_page=i,links=False,annots=False,widgets=False)
    trial.save(dest/'CET4-listening-free-sample.pdf',garbage=4,deflate=True)
    assert len(trial)==10
    write(kit/'2 商品标题.txt',TITLE)
    write(kit/'3 商品描述.txt',DESCRIPTION)
    write(kit/'一句话卖点.txt',TAGLINE)
    write(kit/'商家上架与发货说明.txt','''四级听力｜商家上架说明

商品图按店主最新要求，沿用之前的9张原版，逐字节相同，未换图、未修改配色和布局。图片2000×2000，按01—09顺序上传，01为商品总图。原版图片制作代码保留在仓库“讲义/商品图”及其共用生成器中。

商品标题、简介与一句话卖点为可复制正文。一个完整SKU即可：全套PDF讲义＋历年真题原卷。售价沿用你现有定价；不邮寄纸质书。

已打包6份PDF讲义，共1103页，附阅读说明、35套资料导航和CSV索引。店主明确会另外增加历年真题原卷，所以原版图片及商品简介均保留原卷卖点。请将你准备的原卷放入买家交付文件夹“7 历年真题原卷”，或在原有发货流程中一并发送。原卷页数不计入1103页。请按35套收录清单核对年月、套次和选项顺序。

35套考试视频和35套原文精读视频复用已完成成品，3个ZIP解压后合并为“四级听力”文件夹。将视频和讲义两个文件夹放在同一级，资料导航里的视频链接即可按套次打开；手机阅读器支持情况可能不同，也可按CSV文件名查找。

请把10页免费试读作为买前预览。试读封面沿用原版商品总图，后9页为实际讲义节选；不是完整商品。

商家说明、店铺图片和开发源文件无需发送给买家。数字内容的发货方式、B站视频公开情况、类目、售价和售后，以你实际店铺设置为准。文件损坏或漏发请及时补发；退换依商品说明、平台规则和适用法律处理。未增加保过、保证提分、未来免费更新或永久答疑承诺。
''')
    write(kit/'买家常见问题.txt','''【这是纸质书吗？】这是PDF电子资料，不邮寄纸质书；手机、平板、电脑可阅读，也可自行打印。

【有多少内容？】6份讲义PDF，共1103页；另附历年真题原卷。听力收录2018年6月—2026年6月，共35套、875题，原卷页数另计。

【怎么学？】先用原卷或同系列考试视频做题，再找答案依据、对照原文精听、听写并复听错题。35天计划可以按自己的节奏调整。

【目录和已读勾选怎么用？】带目录的5份PDF支持目录跳转、书签和已读勾选；建议用支持表单的PDF阅读器，勾选后保存。35天计划可打印打卡。

【听写答案在哪？】听写本与答案分成两个PDF，先练习，再按同套、同篇和编号核对。
''')
    write(kit/'发货消息.txt','同学你好，你的四级听力资料已准备好：6份PDF讲义＋历年真题原卷。请通过本订单约定的交付方式查收。建议先看精讲里的使用说明，再按自己的节奏安排学习。文件无法打开或发现漏发，可通过订单联系处理。祝学习顺利！')
    write(kit/'商品参数.json',json.dumps({'商品名称':TITLE,'资料类型':'PDF电子资料','范围':'2018.06—2026.06','套数':35,'题数':875,'讲义份数':6,'讲义页数':1103,'原卷':'由店主另行增加','商品图':'原版9张，逐字节保留','纸质书':False},ensure_ascii=False,indent=2))
    write(buyer/'0 阅读说明.txt','''四级听力全套PDF讲义｜先看这里

6份PDF共1103页，涵盖2018年6月—2026年6月的35套听力、875题。
1 真题35套精讲；2 同义替换手册；3 高频词手册；4 听写本；5 听写本答案；6 35天刷题计划。

建议顺序：先做题 → 找依据 → 对照原文精听 → 听写 → 复听错题。
“35套资料导航.html”和CSV索引可按套次定位精讲、查找视频。将3个视频包解压到与本讲义文件夹同一级，会合并为“四级听力”文件夹。

带目录的5份PDF支持目录、书签与已读勾选，勾选后请保存；35天计划可打印打卡。阅读器的表单、批注与本地链接支持情况可能不同，也可按CSV里的完整文件名查找。
''')
    figures=''.join(f'<figure><a href="1 商品图（原版原样保留）/{im.name}"><img src="1 商品图（原版原样保留）/{im.name}" alt="{im.stem}"></a><figcaption>{im.stem}</figcaption></figure>' for im in images)
    write(kit/'打开查看商品图.html','<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>四级听力原版商品图</title><style>body{font:16px sans-serif;color:#123c31;background:#f7f5ec;margin:28px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:22px}figure{margin:0}img{width:100%}figcaption{padding:10px 0}</style><h1>四级听力 · 原版商品图</h1><p>沿用之前9张商品图，按文件名顺序上传；点击图片可看原尺寸。</p><div class="grid">'+figures+'</div></html>')
    manifest={'product':PRODUCT,'sets':35,'questions':875,'exam_dates':20,'pages_total':1103,'replacement_pairs':960,'vocabulary_entries':487,'pdf_files':report,'original_papers':'由店主另行添加，不包含在脚本生成的6份讲义包中','images_original_unchanged':True,'layout':records,'sample_pages':10}
    write(dest/'CET4-content-check.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    pack(kit,dest/'CET4-listening-shop-ready.zip');pack(buyer,dest/'CET4-listening-PDF-complete.zip')
    print(json.dumps({'pdf_pages':1103,'questions':875,'original_images':9,'images_byte_identical':True,'sample_pages':10,'description_chars':len(DESCRIPTION),'output':str(dest)},ensure_ascii=False))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pdf-dir',type=Path,default=LISTENING/'讲义/成品')
    p.add_argument('--original-images',type=Path,default=LISTENING/'讲义/商品图/成品')
    p.add_argument('--dest',type=Path,required=True)
    build(p.parse_args())

if __name__=='__main__':main()
