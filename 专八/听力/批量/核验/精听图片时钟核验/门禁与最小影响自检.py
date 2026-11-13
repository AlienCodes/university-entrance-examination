"""真实2009-A诊断结果上的过期绑定负例；仅结构核准，绝不伪造成品核验通过。"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

HERE=Path(__file__).resolve().parent;B=HERE.parents[1];ROOT=B.parents[2]
BASELINE='2e8034474b664a3c511897fd0fcf3077a75f18e8'
sys.path.insert(0,str(B/'tools'))
import 图片时钟核验 as C
spec=importlib.util.spec_from_file_location('intensive_clock_gate_test',B/'tools/精听.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',type=Path,required=True);ap.add_argument('--diagnostic',type=Path,required=True)
    args=ap.parse_args();stage=args.stage.resolve();diag=args.diagnostic.resolve()
    shots=stage/'evidence/已审截图/shots';fr=json.loads((diag/'实际帧表.json').read_text())
    report=json.loads((diag/'new-explicit30-fpsfilter-report.json').read_text())
    total=report['total_frames'];video=diag/'new-explicit30-fpsfilter.mp4';sources=report['source_fingerprints']
    tests=[]
    def accepted(name,fn):
        fn();tests.append({'case':name,'expected':'pass','passed':True})
    def rejected(name,fn):
        try:fn()
        except (ValueError,FileNotFoundError,AssertionError) as exc:
            tests.append({'case':name,'expected':'reject','passed':True,'reason':str(exc)[:240]});return
        raise AssertionError('负例竟通过：'+name)
    accepted('真实全328探针通过且当前绑定相同',lambda:C.require_pass(video,fr,shots,total,diag/'new-explicit30-fpsfilter-report.json',sources))
    rejected('输入或程序fingerprint改变',lambda:C.require_pass(video,fr,shots,total,diag/'new-explicit30-fpsfilter-report.json',{**sources,'different':'changed'}))
    moved=copy.deepcopy(fr);moved[1][0]+=1
    rejected('真实状态边界移动一帧',lambda:C.require_pass(video,moved,shots,total,diag/'new-explicit30-fpsfilter-report.json',sources))
    rejected('总帧数改变',lambda:C.require_pass(video,fr,shots,total+1,diag/'new-explicit30-fpsfilter-report.json',sources))
    rejected('旧25时钟拒绝报告不可复用',lambda:C.require_pass(diag/'old-default25.mp4',fr,shots,total,diag/'old-default25-report.json',sources))
    rejected('故意错页拒绝报告不可复用',lambda:C.require_pass(diag/'wrong-first-page.mp4',fr,shots,total,diag/'wrong-first-page-report.json',sources))
    with tempfile.TemporaryDirectory(prefix='tem8-clock-negative-') as tmp:
        tmp=Path(tmp)
        changed_video=tmp/'changed.mp4';shutil.copyfile(video,changed_video)
        with changed_video.open('ab') as f:f.write(b'changed-clock-file')
        rejected('真实快片SHA改变',lambda:C.require_pass(changed_video,fr,shots,total,diag/'new-explicit30-fpsfilter-report.json',sources))
        changed_shots=tmp/'shots';changed_shots.mkdir()
        for p in shots.glob('*.png'):(changed_shots/p.name).symlink_to(p)
        first=changed_shots/(fr[0][1]+'.png');first.unlink();shutil.copyfile(shots/first.name,first)
        with first.open('ab') as f:f.write(b'changed-png-bytes')
        rejected('任一实际已审PNG字节改变',lambda:C.require_pass(video,fr,changed_shots,total,diag/'new-explicit30-fpsfilter-report.json',sources))
        for name,mutation in [
            ('checker程序SHA过期',lambda r:r.update(checker_sha256='0'*64)),
            ('缺失一个边界探针',lambda r:r['all_probes'].pop()),
            ('试图提高阈值',lambda r:r.update(threshold_unchanged=4)),
            ('报告仍带失败',lambda r:r.update(failures=[{'error':'bad frame'}])),
        ]:
            r=copy.deepcopy(report);mutation(r);path=tmp/'record.json';C.dump(path,r)
            rejected(name,lambda:C.require_pass(video,fr,shots,total,path,sources))
        rejected('报告缺失',lambda:C.require_pass(video,fr,shots,total,tmp/'missing.json',sources))
        # 在真实production encode入口只隔离已有源审批；fast gate报错后必须没有任何4K子进程。
        # 此例不宣称媒体成功：故意让fast_clock失败，完整编码/核验不可达。
        unit=tmp/'unit.json';C.dump(unit,{});C.dump(tmp/'prepared.json',{'draft':False});C.dump(tmp/'states.json',fr)
        calls=[]
        def fail_fast(*a,**kw):raise ValueError('deliberate boundary rejection')
        with patch.object(M,'validate'),patch.object(M,'cached_check'),patch.object(M,'fast_clock',side_effect=fail_fast),patch.object(M.subprocess,'run',side_effect=lambda *a,**kw:calls.append(a)):
            rejected('production encode快片拒绝先于任何4K命令',lambda:M.encode(None,{'id':'test'}, {'duration':total/30},tmp,unit,True))
        assert not calls
        listing=M.concat_listing(fr,total,tmp).read_text().splitlines()
        files=[i for i,x in enumerate(listing) if x.startswith('file ')]
        assert len(files)==len(fr)+2 and all(listing[i+1]=='option framerate 30' for i in files)
        accepted('production concat全82+2输入逐一显式30fps',lambda:None)
    # 固定AAC阶段core作为本次before；只允许图像时钟/其独立门禁改变。
    # 固定此次开工前已提交的AAC阶段core，未来仍可重跑本次最小改动证据。
    baseline=subprocess.check_output(['git','show',BASELINE+':专八/听力/批量/tools/精听.py'],cwd=ROOT,text=True)
    current=(B/'tools/精听.py').read_text()
    before=ast.parse(baseline);after=ast.parse(current)
    def functions(tree):return {x.name:ast.dump(x,include_attributes=False) for x in tree.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}
    oldf,newf=functions(before),functions(after)
    changed=sorted(k for k in oldf if oldf[k]!=newf[k]);added=sorted(set(newf)-set(oldf))
    assert changed==['encode','fingerprint','verify'],changed
    assert added==['clock_sources','concat_listing','fast_clock'],added
    assert all(oldf[k]==newf[k] for k in ['engine','read_prepared','compare_audio','audio_check','states','stills','cached_check','approve','main'])
    assert hashlib.sha256((B/'tools/精听数据.py').read_bytes()).hexdigest()=='11b4ef9c00ef2bae834dcb54026d6905202e3e3c57ace801033b25b080d1bb3e'
    # full生产命令只有标准fps滤镜新增；原有尺寸、音轨/码率和所有其余编码参数逐项相同。
    def full_command(tree):
        fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='encode')
        return next(x.args[0] for x in ast.walk(fn) if isinstance(x,ast.Call) and ast.unparse(x.func)=='subprocess.run')
    oldcmd=full_command(before);newcmd=copy.deepcopy(full_command(after))
    elts=newcmd.elts;at=next(i for i,x in enumerate(elts) if isinstance(x,ast.Constant) and x.value=='-vf')
    assert ast.literal_eval(elts[at+1])=='fps=30:start_time=0:round=near'
    del elts[at:at+2]
    assert ast.dump(oldcmd,include_attributes=False)==ast.dump(newcmd,include_attributes=False)
    original_shared_sha=C.sha(ROOT/'专八/tools/make_video.py')
    assert subprocess.check_output(['git','show',BASELINE+':专八/tools/make_video.py'],cwd=ROOT)==(ROOT/'专八/tools/make_video.py').read_bytes()
    result={'status':'pass','tests':tests,'actual_media_scope':'真实旧2009-A已审PNG的silent480p；不宣称4K成品或重新原音核验已完成',
            'baseline_commit':BASELINE,
            'baseline_core_sha256':hashlib.sha256(baseline.encode()).hexdigest(),
            'current_core_sha256':C.sha(B/'tools/精听.py'),'checker_sha256':C.sha(B/'tools/图片时钟核验.py'),
            'only_changed_existing_functions':changed,'only_added_functions':added,
            'visual_engine_AST_unchanged':True,'compiled_data_file_unchanged':True,'audio_check_AST_unchanged':True,
            'full_encoding_argv_only_adds_standard_fps_filter':True,'shared_visual_engine_sha256':original_shared_sha,
            'full_4K_audio_and_quality_verification_retained':True,
            'policy':'2015-A显式256k，其他44默认192k；原音/采样率/声道/增益/阈值不变。旧5缓存停止迁移，全部45新编码。'}
    C.dump(HERE/'门禁与最小影响自检结果.json',result)
    print(json.dumps({'status':'pass','tests':len(tests),'changed':changed,'added':added},ensure_ascii=False))


if __name__=='__main__':main()
