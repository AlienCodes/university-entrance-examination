#!/usr/bin/env python3
"""Upload a verified kit as a draft, verify GitHub digests, then publish it."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

def run(*args):
    return subprocess.run(args,check=True,capture_output=True,text=True).stdout.strip()

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for data in iter(lambda:f.read(2**20),b''):h.update(data)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',default='AlienCodes/university-entrance-examination')
    p.add_argument('--branch',required=True)
    p.add_argument('--tag',required=True)
    p.add_argument('--dest',type=Path,required=True)
    p.add_argument('--video-dir',type=Path,required=True)
    p.add_argument('--publish',action='store_true',help='Publish after all attachments verify; otherwise leave a draft.')
    a=p.parse_args();d=a.dest.resolve()
    content=json.loads((d/'CET4-content-check.json').read_text())
    videos=json.loads((d/'CET4-video-check.json').read_text())
    assert content['sets']==35 and content['questions']==875 and content['pages_total']==1103
    assert len(content['layout'])==10 and all(not x['problems'] for x in content['layout'])
    assert videos['videos']==70 and len(videos['files'])==70
    paths=[d/n for n in ['CET4-listening-PDF-complete.zip','CET4-listening-shop-ready.zip','CET4-listening-free-sample.pdf','CET4-shop-preview.jpg','CET4-shop-cover.jpg','CET4-content-check.json','CET4-video-check.json']]
    known={x['file']:x for x in videos['archives']}
    for i in range(1,4):paths.append(a.video_dir/f'cet4-listening-{i}.zip')
    entries=[]
    for path in paths:
        assert path.is_file() and path.stat().st_size>0
        checksum=known[path.name]['sha256'] if path.name in known else digest(path)
        if path.name in known:assert path.stat().st_size==known[path.name]['size']
        entries.append({'name':path.name,'bytes':path.stat().st_size,'sha256':checksum})
    manifest={'product':'四级听力真题35套精讲','source_branch':a.branch,'tag':a.tag,'original_papers':'店主明确将单独增加；不包含在脚本生成的6份讲义PDF包中','files':entries}
    mp=d/'CET4-release-manifest.json';mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    paths.append(mp);entries.append({'name':mp.name,'bytes':mp.stat().st_size,'sha256':digest(mp)})
    hp=d/'CET4-checksums.sha256';hp.write_text(''.join(f'{x["sha256"]}  {x["name"]}\n' for x in entries))
    paths.append(hp);expected={x['name']:x['sha256'] for x in entries};expected[hp.name]=digest(hp)
    notes='''四级听力学习资料与小店上架素材已整理完成。收录 **2018年6月—2026年6月，20次考试、35套、875题**。

**上架小店下载这两个：**
- `CET4-listening-shop-ready.zip`：10张2000×2000商品图、标题、647字简介、一句话卖点、商品参数、FAQ、发货消息、商家上架说明、预览网页及可编辑HTML排版源文件。
- `CET4-listening-PDF-complete.zip`：6份完整PDF讲义，共1103页，附阅读说明、35套资料导航与CSV对应表。

**原卷：** 按店主要求保留“另附历年真题原卷”的卖点。原卷由店主另行增加；本Release的讲义ZIP只包含6份讲义，不把原卷算进1103页。将原卷加入买家交付文件夹或随原有发货流程一并发送，详细步骤见商家说明。

**可以直接看：**
- `CET4-listening-free-sample.pdf`：10页免费试读，内页取自实际交付PDF。
- `CET4-shop-cover.jpg`：商品主图。
- `CET4-shop-preview.jpg`：全部10张商品图总览。

**配套视频完整包：** 35个考试版＋35个原文精读版，均为4K，复用已发布成品、未重新编码。下载3个ZIP并解压到同一位置，会合并为“四级听力”文件夹，视频均为中文名。
- `cet4-listening-1.zip`：26个视频，2026年6月至2023年6月第1套。
- `cet4-listening-2.zip`：26个视频，2023年6月第2套至2020年9月。
- `cet4-listening-3.zip`：18个视频，2020年7月至2018年6月。

**核对结果：** 6份PDF页数、非空页面、目录链接目标范围、书签与表单已检查；5份带目录PDF的已读勾选均已测试保存后重新打开。35套解析结构完整，共875题、960组原文与选项对应。10张图片通过画布与内容溢出检查。3个视频ZIP的SHA256、70个内含视频的CRC与SHA256均与原发布资产一致；逐个核对了音视频流、时长、4K分辨率和编码。没有在本轮重复历史逐句听校或逐帧解码全部视频。详见校验JSON和SHA256清单。

旧版资料与视频来源：
- https://github.com/AlienCodes/university-entrance-examination/releases/tag/cet4-listening-handout
- https://github.com/AlienCodes/university-entrance-examination/releases/tag/cet4-listening

商品内容、售价、发货与售后设置以店主实际上架情况为准；没有新增保过、保证提分、永久答疑或未来更新承诺。
'''
    nf=d/'release-notes.txt';nf.write_text(notes)
    title='四级听力35套｜全套讲义、70个视频与小店上架包'
    found=subprocess.run(['gh','release','view',a.tag,'--repo',a.repo,'--json','isDraft,name,url'],capture_output=True,text=True)
    if found.returncode:
        run('gh','release','create',a.tag,'--repo',a.repo,'--target',a.branch,'--title',title,'--notes-file',str(nf),'--draft','--latest=false')
    else:
        r=json.loads(found.stdout);assert r['name']==title and r['isDraft'],'Refusing to replace an existing published release.'
    # Upload larger archives first; run one at a time to avoid proxy request bursts.
    for path in sorted(paths,key=lambda p:p.stat().st_size,reverse=True):
        print('Uploading',path.name,flush=True)
        run('gh','release','upload',a.tag,str(path),'--repo',a.repo,'--clobber')
    r=json.loads(run('gh','api',f'repos/{a.repo}/releases/tags/{a.tag}'))
    actual={x['name']:x for x in r['assets']}
    assert set(actual)==set(expected),(set(actual),set(expected))
    for name,checksum in expected.items():
        assert actual[name]['state']=='uploaded'
        assert actual[name]['digest']=='sha256:'+checksum,(name,actual[name]['digest'])
    if a.publish:run('gh','release','edit',a.tag,'--repo',a.repo,'--draft=false','--latest=false')
    print(json.dumps({'url':r['html_url'],'published':a.publish,'verified_assets':len(actual)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
