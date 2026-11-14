"""真实10秒两阶段短片的发布proof正反例；只读生产代码，不编码新媒体。"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
B = HERE.parents[1]
spec = importlib.util.spec_from_file_location('publisher_for_two_stage_proof_tests', B / 'tools/发布汇集.py')
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
WORK = Path('/workspace/tem8-intensive-two-step/new-adapter')


def fixture():
    proof = P.read(WORK/'two-stage-encoding.json')
    tm = {'file':'native.wav','audio_sha256':proof['prepared_pcm_sha256'],
          'source_sha256':proof['source_sha256'],'duration':10.0,'sample_rate':44100,'channels':2,
          'aac_bitrate':'192k','window':[100,106.3],'kept_intervals':[[100,106.3]],
          'compressed_gaps':[],'protected_source_intervals':[],'sentences':[{'end':7.8}]}
    data = {n:P.read(WORK/n) for n in ['two-stage-encoding.json','meta.json','verification.json','prepared.json','audio-precheck.json']}
    data['audio/timings.json'] = {'cet4_male':{'2022-A':tm}}
    # Independently connect the genuine positive proof to actual PCM/media and ffprobe.
    assert P.sha(WORK/'audio/native.wav') == proof['prepared_pcm_sha256']
    assert P.sha(WORK/data['meta.json']['mp4']) == proof['mp4_sha256']
    info = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(WORK/data['meta.json']['mp4'])]))
    video = next(r for r in info['streams'] if r['codec_type']=='video')
    audio = next(r for r in info['streams'] if r['codec_type']=='audio')
    assert video['width']==3840 and video['height']==2160 and video['r_frame_rate']=='30/1' and int(video['nb_frames'])==300
    assert int(audio['sample_rate'])==44100 and audio['channels']==2 and abs(float(video['duration'])-float(audio['duration']))<.05
    return data, info


def set_value(file, key, value):
    def apply(d): d[file][key] = value
    return apply


def argv_option(file, key, option, value):
    def apply(d):
        cmd = d[file][key]; cmd[cmd.index(option)+1] = value
    return apply


def remove_check(item):
    def apply(d):
        d['verification.json']['checks'] = [c for c in d['verification.json']['checks'] if c['item'] != item]
    return apply


def protected_branch(*changes):
    """合成的保护区间契约分支；不把技术短片窗口冒充真实新增保护登记。"""
    def apply(d):
        d['audio/timings.json']['cet4_male']['2022-A']['protected_source_intervals'] = [[101, 102]]
        d['verification.json']['checks'].append({'item':'2022窗口内低电平信号保护段完整保留','ok':True,'detail':[[101,102]]})
        for change in changes: change(d)
    return apply


def main():
    baseline, probe = fixture(); proof='two-stage-encoding.json'
    cases = [('真实10秒4K原PCM与实际ffprobe相符的完整proof',None,True)]
    for key,value in [('id','2024-A'),('adapter_sha256','0'*64),('original_engine_sha256','0'*64),
                      ('fingerprint','0'*64),('base_fingerprint','0'*64),('prepared_pcm_sha256','0'*64),
                      ('mp4_sha256','0'*64),('source_sha256','0'*64),('frames',301),
                      ('sample_rate',48000),('channels',1),('aac_bitrate','256k')]:
        cases.append((f'篡改proof.{key}',set_value(proof,key,value),False))
    cases += [
        ('篡改meta原音SHA',set_value('meta.json','原音_sha256','0'*64),False),
        ('篡改meta成品SHA',set_value('meta.json','mp4_sha256','0'*64),False),
        ('篡改原严检为未通过',set_value('verification.json','ok',False),False),
        ('篡改prepared为草稿',set_value('prepared.json','draft',True),False),
        ('篡改audio原样登记',set_value('audio-precheck.json','raw_exact_before_encoding',False),False),
        ('篡改tm时长',lambda d:d['audio/timings.json']['cet4_male']['2022-A'].update(duration=10.1),False),
        ('篡改原核验时长',set_value('verification.json','duration',10.1),False),
    ]
    for option,value in [('-vf','fps=30:start_time=0:round=near'),('-c:v','libx265'),('-preset','medium'),
                         ('-crf','20'),('-g','300'),('-x264-params','scenecut=40'),('-frames:v','301'),('-t','11.000000000')]:
        cases.append((f'picture参数{option}改变',argv_option(proof,'picture_argv',option,value),False))
    for option,value in [('-c:v','libx264'),('-c:a','copy'),('-b:a','256k'),('-movie_timescale','1000')]:
        cases.append((f'mux参数{option}改变',argv_option(proof,'mux_argv',option,value),False))
    for extra in [['-af','volume=0.5'],['-ar','48000'],['-ac','1'],['-af','loudnorm'],['-shortest'],['-c:a','aac']]:
        cases.append(('mux追加'+' '.join(extra),lambda d,x=extra:d[proof]['mux_argv'].__setitem__(slice(-1,-1),x),False))
    cases.append(('picture追加第二vf',lambda d:d[proof]['picture_argv'].__setitem__(slice(-1,-1),['-vf','hflip']),False))
    # Regression: all([]) must never turn an empty or incomplete strict report into a pass.
    cases += [
        ('global ok为真但checks为空',set_value('verification.json','checks',[]),False),
        ('checks字段被删除',lambda d:d['verification.json'].pop('checks'),False),
        ('额外未知检查即使ok为真',lambda d:d['verification.json']['checks'].append({'item':'伪造全局通过项','ok':True}),False),
        ('重复原生采样率项目',lambda d:d['verification.json']['checks'].append(copy.deepcopy(d['verification.json']['checks'][4])),False),
        ('长度仍10但重复native替换原声项',lambda d:d['verification.json']['checks'].__setitem__(5,copy.deepcopy(d['verification.json']['checks'][4])),False),
        ('global ok为真但原声项失败',lambda d:d['verification.json']['checks'][5].update(ok=False),False),
        ('原声项数字1不能冒充True',lambda d:d['verification.json']['checks'][5].update(ok=1),False),
    ]
    for check in baseline['verification.json']['checks']:
        cases.append(('删除固定严检项:'+check['item'],remove_check(check['item']),False))
    protected_item = '2022窗口内低电平信号保护段完整保留'
    cases += [
        ('保护区间有交集且11项唯一完整通过',protected_branch(),True),
        ('保护区间有交集但缺保护检查',protected_branch(remove_check(protected_item)),False),
        ('保护区间有交集但global真保护失败',protected_branch(lambda d:d['verification.json']['checks'][-1].update(ok=False)),False),
        ('保护检查重复不能补数量',protected_branch(lambda d:d['verification.json']['checks'].append(copy.deepcopy(d['verification.json']['checks'][-1]))),False),
        ('有保护检查但删native',protected_branch(remove_check('原采样率与声道')),False),
        ('有保护检查但删原声核对',protected_branch(remove_check('原声逐样本核对')),False),
        ('有保护检查但删图片时钟',protected_branch(remove_check('图片时钟全状态首尾及邻帧')),False),
        ('无交集却伪加保护检查',lambda d:d['verification.json']['checks'].append({'item':protected_item,'ok':True}),False),
        ('仅贴窗口左边界不算交集',lambda d:d['audio/timings.json']['cet4_male']['2022-A'].update(protected_source_intervals=[[99,100]]),True),
        ('仅贴窗口右边界不算交集',lambda d:d['audio/timings.json']['cet4_male']['2022-A'].update(protected_source_intervals=[[106.3,110]]),True),
    ]
    rows=[]
    for name,mutate,want in cases:
        data=copy.deepcopy(baseline)
        if mutate: mutate(data)
        try:
            got=P.validate_two_stage_proof('2022-A',lambda n:copy.deepcopy(data[n]))
            accepted=got is not None;reason='accepted'
        except (AssertionError,KeyError,ValueError,TypeError,IndexError) as exc:
            accepted=False;reason=type(exc).__name__+': '+str(exc)
        rows.append({'case':name,'expected':'accept' if want else 'reject','actual':'accept' if accepted else 'reject','passed':accepted==want,'reason':reason})
    # Scope isolation: old successful IDs must not start requiring recovery proof.
    assert P.validate_two_stage_proof('2023-A',lambda n: (_ for _ in ()).throw(AssertionError('must not read')) ) is None
    rows.append({'case':'其余43段不读取新proof','expected':'ignore','actual':'ignore','passed':True})
    report={'status':'PASS' if all(r['passed'] for r in rows) else 'FAIL','publisher_sha256':P.sha(B/'tools/发布汇集.py'),
            'adapter_sha256':P.sha(B/'tools/精听两步编码.py'),'tested_function':'P.validate_two_stage_proof(ident, read_work)',
            'positive_real_proof_sha256':P.sha(WORK/'two-stage-encoding.json'),'positive_real_MP4_sha256':baseline[proof]['mp4_sha256'],
            'positive_real_PCM_sha256':baseline[proof]['prepared_pcm_sha256'],'positive_real_probe':probe,
            'fixture_timing':baseline['audio/timings.json'],'cases':rows,'case_count':len(rows),
            'production_files_modified':False,'media_rendered':False,'scope':'JSON proof cross-binding, exact complete/unique check Counter, protection-intersection branch and strict argv whitelist; genuine positive independently checks actual PCM/MP4 SHA and real ffprobe. The added protected-window branch is a synthetic contract fixture, not a new source or semantic approval. Existing stage/cache byte-level checks remain separate.'}
    P.dump(HERE/'proof校验正反例结果.json',report)
    print(json.dumps({'status':report['status'],'case_count':len(rows),'failed':[r for r in rows if not r['passed']]},ensure_ascii=False))
    assert report['status']=='PASS'


if __name__=='__main__':main()
