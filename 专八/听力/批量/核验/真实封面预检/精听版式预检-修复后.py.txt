"""无虚构时间的4K水墨版式/分屏候选检查。候选仍须真实原音停顿和语义复核。

python 精听版式预检.py --out /workspace/tem8-layout --ids 2009-A 2009-B1 2009-B2 --screens --workers 2
默认读取所有年度译注草稿；已有精听数据时优先使用该版真实文本，快照在各单元目录。
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor,as_completed

from 精听 import engine,load_module,fingerprint
from 精听数据 import ROOT,HERE,TOKEN,dump,sha
BATCH=HERE.parent
KNOWN_NAMES=['拉尔夫·斯梅德利','詹姆斯·约翰逊','爱德华·霍尔','斯蒂芬·克拉申','南希·安德烈亚森','文森特·梵高','约翰·塞巴斯蒂安·巴赫','莱昂纳多·达·芬奇','汉斯·塞利','特雷莎·梅','约翰·梅杰','玛吉·肖茨','玛丽·约翰逊','詹姆斯·多宾斯','阿卜杜拉·阿卜杜拉','阿什拉夫·加尼','莫琳·麦克莱恩','海伦·文德勒','威廉·科贝特','贾妮丝·奈特','苏珊·豪','保罗·博汉南','芭芭拉·米勒','玛格丽特·米德','克莱德·克拉克洪','哈丽雅特·桑福德','苏珊·康罗伊','埃尔维斯·普雷斯利','拉尔夫·沃尔多·爱默生','弗朗西斯·培根','吉姆·约翰逊','本杰明·约翰逊']


def passage(d):
    flat=[{k:copy.deepcopy(s[k]) for k in ['en','zh','w']} for s in d['sentences']]
    return {'id':d['id'],'year':d['year'],'month':0,'set':1,'part':'L',
            'paper':f"{d['year']}年专八听力",'passage':d['section'],'title':d['title'],
            'genre':d.get('genre','听力原文'),'summary':d.get('summary',''),'done':True,
            'words':sum(len(TOKEN.findall(s['en'])) for s in flat),'nv':sum(len(s['w']) for s in flat),'paras':[flat]}


def probe_unit(snapshot,out,browser,screens=False):
    from playwright.sync_api import sync_playwright
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    d=json.loads(Path(snapshot).read_text());p=passage(d);pid=p['id'];flat=p['paras'][0];n=len(flat)
    source_title=p['title']
    assert p['title']==d['title'],'版式预检不得替换/缩短来源题名'
    texts='\n'.join([s['zh']+' '+' '.join(w['m'] for w in s['w']) for s in flat])
    proposed_names=list(dict.fromkeys(d.get('names',[])+[name for name in KNOWN_NAMES if name in texts]))
    for folder in ['tools/画面核查','data','阅读','shots']:(out/folder).mkdir(exist_ok=True,parents=True)
    dump(out/'tools/分屏_水墨.json',{pid:d.get('splits',{})});dump(out/'tools/人名.json',{'names':proposed_names})
    dump(out/'data/vocab.json',{'passages':[p]})
    helper=load_module('tem8_layout_http',ROOT/'高考听力/精读/tools/本机预览.py')
    helper.enable([ROOT,out,Path(tempfile.gettempdir())],browser)
    m=engine(out);sug=load_module('tem8_layout_suggest',ROOT/'专八/tools/分屏建议.py')
    m.P_CUR=p;m.check_names(p);page=out/'page.html';frozen=fingerprint(m,p,{})
    plans=copy.deepcopy(d.get('splits',{}));findings={};original_bad=[];font_min=[m.MIN_FS,m.MIN_VS]
    with sync_playwright() as pw:
        br=pw.chromium.launch(executable_path=browser,args=['--no-sandbox'])
        pg=br.new_page(viewport={'width':1920,'height':1080},device_scale_factor=2)
        # 排版即生产所用layout；这一遍定位所有实际放不下的句子。
        bad=set()
        for i,label,fit,r in m.layout(pg,p,page):
            problems=m.screen_checks(pg,label,fit,r)
            if problems:
                original_bad.append({'screen':i+1,'label':label,'problems':problems})
                k=re.match(r'第 (\d+) 句',label)
                if k and fit and (not r[2] or r[0]<m.MIN_FS or r[1]<m.MIN_VS):bad.add(int(k.group(1)))
        for k in sorted(bad):
            s=flat[k-1];en=s['en'];zh=s['zh']
            cs=set(sug.en_cuts(en,s))
            cs.update(x.end() for x in re.finditer(r'[.!?][”\"]?\s+(?=[A-Z“])',en))
            cs={c for c in cs if 12<c<len(en)-12 and not any(a<c<b for w in s['w'] for a,b in w['sp'])}
            def search(pool,dependency=False):
                for count in [1,2,3]:
                    combos=[]
                    # 先按英译锚点、长度挑选，最多实测16个候选；不通过即报告，绝不缩小字号。
                    for cuts in itertools.combinations(sorted(pool),count):
                        b=[0,*cuts,len(en)]
                        if min(y-x for x,y in zip(b,b[1:]))<12:continue
                        if any(len(TOKEN.findall(en[x:y]))<4 for x,y in zip(b,b[1:])):continue
                        missing=sum(not any(x<=w['sp'][0][0]<y for w in s['w']) for x,y in zip(b,b[1:]))
                        z=sug.best_zh(s,list(cuts))
                        if z is None:continue
                        key=(z[0][0],missing,max(y-x for x,y in zip(b,b[1:])),z[0][2])
                        combos.append((key,cuts,z))
                    for key,cuts,z in sorted(combos,key=lambda x:x[0])[:16]:
                        b=[0,*cuts,len(en)];zb=[0,*z[1],len(zh)]
                        parts=[(b[j],b[j+1],zh[zb[j]:zb[j+1]],f' · PART {j+1}/{len(b)-1}') for j in range(len(b)-1)]
                        sizes,ok=sug.fit_parts(pg,page,p,k,s,n,parts)
                        if ok:
                            at=[sug.at_of(en,c) for c in cuts]
                            plan={'at':at if len(at)>1 else at[0],'zh':[a[2] for a in parts]}
                            assert ''.join(plan['zh'])==zh
                            return plan,{'sizes':sizes,'anchor_wrong_right':[z[0][0],-z[0][1]],
                                         'dependency_boundary':dependency,'cuts':list(cuts),'missing_vocab_parts':[j+1 for j,(a,b) in enumerate(zip([0,*cuts],[*cuts,len(en)])) if not any(a<=w['sp'][0][0]<b for w in s['w'])]}
                return None,None
            plan,info=search(cs)
            if plan is None:
                try:wc=sug.word_cuts(en,s)
                except (ImportError,OSError) as ex:wc={};findings[str(k)]={'dependency_unavailable':str(ex)}
                # 无音频时只记录句法候选，不伪称句中没有停顿，也不填时间。
                plan,info=search(set(cs)|set(wc),True)
            if plan is not None:
                plans[str(k)]=plan;m.SPLIT[pid]=plans
                findings[str(k)]={'candidate':plan,**info,'audio_switch_status':'未核；无时间值，须在真实词时刻/停顿上检查'}
            else:
                findings.setdefault(str(k),{}).update({'unresolved':True,'reason':'自然/句法边界的1—3刀仍无合法方案，或某屏无词条；须人工语义分屏/补足真实学习词。','en':en,'zh':zh})
        m.SPLIT[pid]=plans;dump(out/'tools/分屏_水墨.json',{pid:plans})
        final=[];rows=[]
        for i,label,fit,r in m.layout(pg,p,page):
            problems=m.screen_checks(pg,label,fit,r)
            if fit:
                k=int(re.match(r'第 (\d+) 句',label).group(1))
                parts=m.split_parts(pid,k,flat[k-1]);match=re.search(r'第 (\d+) 屏$',label);current=[parts[int(match.group(1))-1]] if match else parts
                empty=[part for part in current if not any(part[0]<=w['sp'][0][0]<part[1] for w in flat[k-1]['w'])]
                if empty:problems.append(label+'：分屏缺少词汇栏内容')
            row={'screen':i+1,'label':label,'sizes':r,'problems':problems}
            if screens or problems:
                target=out/'shots'/f'screen{i+1:03d}.png';pg.screenshot(path=str(target));row.update(file=target.name,sha256=sha(target))
            rows.append(row)
            final.extend(problems)
        br.close()
    dump(out/'分屏候选.json',{pid:plans})
    result={'id':pid,'layout_only':True,'not_audio_approved':True,'input_sha256':sha(snapshot),'precheck_script_sha256':sha(__file__),
            'fingerprint_before':frozen,'fingerprint_after':fingerprint(m,p,{}),'font_min_css_px':font_min,
            'dimensions':[3840,2160],'layout_source_origin':d.get('layout_source_origin'),'manual_rebase_notes':d.get('layout_manual_rebase_notes',[]),'source_title':source_title,'proposed_display_title':p['title'],'proposed_names':proposed_names,'original_problems':original_bad,'split_findings':findings,
            'final_problems':final,'shots':rows,'ok':not final,
            'chinese_integrity':'split_parts逐字核对每屏译文；拼接与整句完全相同',
            'next_gate':'候选必须再通过原声停顿、英文/中文分屏语义及真实换屏时刻核验，才可生产编码'}
    dump(out/'版式预检.json',result);print(pid,'screens',len(rows),'problems',len(final),'split',len(plans),flush=True)
    return {'id':pid,'ok':not final,'screens':len(rows),'problems':len(final),'split':len(plans),'report':str(out/'版式预检.json')}


def manual_overlays(unit):
    """只给几何候选合已审手工EN锚；不修改母稿，也不声称换屏已核音频。"""
    d=copy.deepcopy(unit);records=[];notes=[]
    f=BATCH/'核验/2024人工分屏补充.json'
    if f.exists():
        records += [{'id':r['id'],'en':r['en'],'plan':{'at':r['at'],'zh':r['zh']}} for r in json.loads(f.read_text()).get('split_records',[])]
    f=BATCH/'核验/2018长句分屏译文调整.json'
    if f.exists():
        r=json.loads(f.read_text());records.append({'id':r['unit'],'en':r['en_anchor'],'plan':r['candidate']})
    f=BATCH/'核验/正文局部音证/2018-裁决.json'
    if f.exists():
        records += [{'id':r['unit'],'en':r['en'],'plan':r['candidate']} for r in json.loads(f.read_text()).get('manual_splits',[])]
    f=BATCH/'核验/正文异文复核/2023-B1-人工分屏候选.json'
    if f.exists():
        r=json.loads(f.read_text());records.append({'id':r['id'],'en':r['en'],'plan':r['candidate']})
    for r in records:
        if r['id']!=d['id']:continue
        matches=[(k,s) for k,s in enumerate(d['sentences'],1) if s['en']==r['en']]
        if len(matches)!=1:notes.append('手工EN锚未唯一匹配，未应用：'+r['en']);continue
        k,s=matches[0];zs=r['plan']['zh']
        if ''.join(zs)!=s['zh']:notes.append('手工中文不再与母稿逐字相同，未应用：'+r['en']);continue
        d.setdefault('splits',{})[str(k)]=r['plan']
        notes.append('仅几何预检按EN整句锚合人工候选：'+r['en'])
    d['layout_manual_rebase_notes']=notes
    return d


def worker(args):
    snapshot,out,browser,screens=args
    try:return probe_unit(snapshot,out,browser,screens)
    except BaseException as ex:
        result={'id':json.loads(Path(snapshot).read_text())['id'],'ok':False,'error':type(ex).__name__+': '+str(ex)}
        dump(Path(out)/'版式预检.json',result);print(result,flush=True);return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--ids',nargs='*');ap.add_argument('--workers',type=int,default=2)
    ap.add_argument('--prefer-drafts',action='store_true');ap.add_argument('--resume',action='store_true');ap.add_argument('--screens',action='store_true');ap.add_argument('--browser',default=shutil.which('chromium') or '/usr/bin/chromium')
    args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);units={}
    for f in sorted((BATCH/'译注草稿').glob('*.json')):
        obj=json.loads(f.read_text())
        for u in obj.get('units',[]):units[u['id']]={'year':obj['year'],**u,'layout_source_origin':{'file':str(f.relative_to(BATCH)),'sha256':sha(f)}}
    for f in sorted((BATCH/'精听数据').glob('*.json')):
        u=json.loads(f.read_text())
        if not args.prefer_drafts or u['id'] not in units:units[u['id']]={**u,'layout_source_origin':{'file':str(f.relative_to(BATCH)),'sha256':sha(f)}}
    jobs=[]
    for pid,u in sorted(units.items()):
        if args.ids and pid not in args.ids:continue
        u=manual_overlays(u)
        sub=out/pid;sub.mkdir(exist_ok=True);snap=sub/'source.json';dump(snap,u)
        old=sub/'版式预检.json'
        if args.resume and old.exists() and json.loads(old.read_text()).get('input_sha256')==sha(snap):continue
        jobs.append((snap,sub,args.browser,args.screens))
    results=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(worker,j) for j in jobs]
        for f in as_completed(futures):
            results.append(f.result());dump(out/'汇总.json',{'layout_only':True,'expected':len(jobs),'completed':len(results),'results':results})
    print('完成',len(results),'成功',sum(r['ok'] for r in results),flush=True)


if __name__=='__main__':main()
