"""精听适配的实际音频/失败注入检查，不需要下载ASR或TTS模型。"""
import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import soundfile as sf

from 精听数据 import compact,compile_input,content_sha,sha,validate,align_words,first_aligned_word,audio_protection,PROTECTION_2022,resolve_manual_splits,bind_manual_pauses,assert_manual_preserved,dump,ROOT


def example(audio):
    d={'id':'2009-test','year':2009,'section':'Section A','title':'接口测试','audio':{'sha256':sha(audio),'window':[0,8]},
       'names':[],'待核':[],'sentences':[
           {'en':'Hello.','zh':'你好。','start':0.05,'end':1.0,'w':[{'t':'core','h':'hello','m':'int. 你好','sp':[[0,5]]}],
            'words':[['Hello',.05,.9]]},
           {'en':'Goodbye.','zh':'再见。','start':6.0,'end':7.0,'w':[{'t':'core','h':'goodbye','m':'int. 再见','sp':[[0,7]]}],
            'words':[['Goodbye',6.,6.9]]}]}
    d['review']={'status':'approved','content_sha256':content_sha(d)}
    return d


class Checks(unittest.TestCase):
    def setUp(self):
        self.sr=16000;t=np.arange(self.sr)/self.sr
        self.x=np.zeros((self.sr*8,2),np.float32)
        self.x[:self.sr,0]=.1*np.sin(2*np.pi*440*t);self.x[:self.sr,1]=.07*np.sin(2*np.pi*650*t)
        self.x[self.sr*6:self.sr*7]=self.x[:self.sr]
        self.sents=[{'start':.05,'end':1.},{'start':6.,'end':7.}]

    def test_only_pure_silence_removed(self):
        body,warp,kept,removed,unshortened=compact(self.x,self.sr,0,8,self.sents)
        self.assertEqual(removed,[(2*self.sr,5*self.sr)])
        self.assertEqual(len(body),5*self.sr)
        self.assertTrue(np.array_equal(body,np.concatenate([self.x[:2*self.sr],self.x[5*self.sr:]])))
        self.assertAlmostEqual(warp(6),4.5)

    def test_breath_or_uncovered_speech_not_removed(self):
        self.x[3*self.sr:3*self.sr+100]=.03
        body,_,_,removed,kept=compact(self.x,self.sr,0,8,self.sents)
        self.assertEqual(removed,[]);self.assertTrue(kept)
        self.assertTrue(np.array_equal(body,self.x))

    def test_front_window_exclusion_is_explicit(self):
        body,_,kept,removed,_=compact(self.x,self.sr,1.2,8,self.sents[1:])
        self.assertTrue(np.array_equal(body,self.x[round(1.2*self.sr):]))

    def test_compile_and_failures(self):
        with tempfile.TemporaryDirectory() as t:
            t=Path(t);source=t/'source.wav';sf.write(source,self.x,self.sr,subtype='FLOAT')
            d=example(source);f=t/'input.json';f.write_text(json.dumps(d,ensure_ascii=False))
            _,p,tm=compile_input(f,source,t/'build')
            got,sr=sf.read(t/'build/audio/原音.wav',dtype='float32',always_2d=True)
            expected=np.concatenate([self.x[:2*self.sr],self.x[5*self.sr:]])
            self.assertTrue(np.array_equal(got[24000:24000+len(expected)],expected))
            self.assertEqual(sr,self.sr);self.assertEqual(got.shape[1],2)
            self.assertEqual(tm['mode'],'原音不动')
            self.assertEqual(p['year'],2009)
            self.assertAlmostEqual(tm['sentences'][1]['start'],4.5)
            changed=copy.deepcopy(d);changed['sentences'][0]['zh']='篡改译文。'
            with self.assertRaises(AssertionError):validate(changed)
            wrong=copy.deepcopy(d);wrong['audio']['sha256']='0'*64;wrong['review']['content_sha256']=content_sha(wrong)
            f.write_text(json.dumps(wrong))
            with self.assertRaises(AssertionError):compile_input(f,source,t/'bad')
            pending=copy.deepcopy(d);pending['待核']=['词时刻未定']
            with self.assertRaises(AssertionError):validate(pending)
            validate(pending,draft=True)

    def test_unproven_word_times_rejected(self):
        s={'en':'She cannot go.','start':0,'end':1,'words':[['She',0,.2],['go',.7,.9]]}
        with self.assertRaises(AssertionError):align_words(s)

    def test_split_cannot_skip_missing_first_word(self):
        en='He paused, then spoke.';cut=en.index('then')
        aa=[{'char':en.index('spoke'),'char_end':en.index('spoke')+5,'start':2.,'end':2.3}]
        with self.assertRaisesRegex(AssertionError,'首词缺少真实对齐'):first_aligned_word(aa,en,cut)
        aa.insert(0,{'char':cut,'char_end':cut+4,'start':1.5,'end':1.8})
        self.assertEqual(first_aligned_word(aa,en,cut)['start'],1.5)

    def test_registered_low_level_periodic_signal_preserved(self):
        # -83dBFS左右的真实形态信号低于旧静音门槛；保护登记必须先于门槛执行。
        t=np.arange(5*self.sr)/self.sr
        signal=(1e-4*np.sin(2*np.pi*440*t)).astype(np.float32)
        self.x[self.sr:6*self.sr,0]=signal
        plain=compact(self.x,self.sr,0,8,self.sents)
        self.assertEqual(plain[3],[(2*self.sr,5*self.sr)])
        protected=compact(self.x,self.sr,0,8,self.sents,[(1.,6.)])
        self.assertEqual(protected[3],[])
        self.assertTrue(np.array_equal(protected[0],self.x))
        self.assertTrue(protected[4][0]['protected'])

    def test_protection_source_sha_is_mandatory(self):
        r=json.loads(PROTECTION_2022.read_text())
        d={'year':2022,'audio':{'sha256':r['canonical']['sha256']}}
        intervals,evidence=audio_protection(d)
        self.assertEqual(intervals,[[54.68,84.85],[586.87,767.6],[804.25,834.32]])
        self.assertEqual(evidence['registration_sha256'],sha(PROTECTION_2022))
        d['audio']['protected_source_intervals']=intervals[:1]
        with self.assertRaisesRegex(AssertionError,'保护段'):audio_protection(d)
        d['audio'].pop('protected_source_intervals')
        d['audio']['sha256']='0'*64
        with self.assertRaisesRegex(AssertionError,'原音SHA'):audio_protection(d)
        d={'year':2009,'audio':{'sha256':'0'*64}}
        self.assertEqual(audio_protection(d),([],None))
        d['audio']['protected_source_intervals']=intervals
        with self.assertRaisesRegex(AssertionError,'非2022'):audio_protection(d)

    def test_exact_fallback_words_and_semantic_reversal(self):
        exact={'en':'Good morning.','start':0.,'end':1.,'words':[['Good',.1,.3],['morning',.4,.9]]}
        self.assertEqual([(w['char'],w['char_end']) for w in align_words(exact)],[(0,4),(5,12)])
        # 同词数但内容不同：不得利用数组长度制造同序时间对应。
        reversed_word={'en':'Good morning.','start':0.,'end':1.,'words':[['Good',.1,.3],['evening',.4,.9]]}
        with self.assertRaises(AssertionError):align_words(reversed_word)
        negation={'en':'She cannot go.','start':0.,'end':1.,'words':[['She',.1,.2],['can',.3,.5],['go',.7,.9]]}
        with self.assertRaises(AssertionError):align_words(negation)
        # 弯/直撇号可正字法等价；we'll与well仍是不同的真实词。
        apostrophe={'en':'We’ll go.','start':0.,'end':1.,'words':[["We'll",.1,.4],['go',.6,.9]]}
        self.assertEqual(len(align_words(apostrophe)),2)
        apostrophe['words'][0][0]='Well'
        with self.assertRaises(AssertionError):align_words(apostrophe)

    def test_real_2024_manual_plans_through_actual_finalizer(self):
        from 精听 import engine,script
        source=ROOT/'专八/听力/批量/精听数据/2024-A.json'
        d=json.loads(source.read_text('utf-8'));plans=resolve_manual_splits(d);pid=d['id']
        self.assertEqual(len(d['manual_splits']),2)
        self.assertEqual(len(plans),2)
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);(out/'tools').mkdir();(out/'audio').mkdir()
            # 分屏定稿只需此结构；不写虚构英语词时刻或音频。
            dump(out/'audio/timings.json',{'cet4_male':{pid:{'sentences':[]}}})
            dump(out/'tools/人名.json',{'names':[]})
            bad={k:{'at':'deliberately wrong automatic cut','zh':['错误自动候选']} for k in plans}
            dump(out/'tools/分屏_水墨.json',{pid:bad});dump(out/'tools/分屏手定_水墨.json',{pid:plans})
            suggestion={'done':[pid],'plan':{pid:bad},'results':{f'{pid}:{k}':{'候选':[{'at':['deliberately wrong automatic cut'],'zh':['错误自动候选'],'对齐（错/对）':[0,1],'无停顿':False}]} for k in plans}}
            dump(out/'suggestion.json',suggestion);m=engine(out)
            with contextlib.redirect_stdout(io.StringIO()):script(ROOT/'专八/tools/分屏定稿.py',[str(out/'suggestion.json'),pid])
            actual=json.loads((out/'tools/分屏_水墨.json').read_text())[pid]
            assert_manual_preserved(plans,actual)
            # 故意移除手定后，再走真实定稿路径：坏自动候选必须被我们的后置守门拒绝。
            (out/'tools/分屏手定_水墨.json').unlink();dump(out/'tools/分屏_水墨.json',{pid:bad})
            with contextlib.redirect_stdout(io.StringIO()):script(ROOT/'专八/tools/分屏定稿.py',[str(out/'suggestion.json'),pid])
            overwritten=json.loads((out/'tools/分屏_水墨.json').read_text())[pid]
            with self.assertRaisesRegex(AssertionError,'覆盖人工'):assert_manual_preserved(plans,overwritten)
        conflict=copy.deepcopy(d);key=next(iter(plans));conflict['splits'][key]['at']='conflicting cut'
        with self.assertRaisesRegex(AssertionError,'冲突'):resolve_manual_splits(conflict)
        missing=copy.deepcopy(d);missing['manual_splits'][0]['en']+=' missing anchor'
        with self.assertRaisesRegex(AssertionError,'英文锚'):resolve_manual_splits(missing)

    def test_manual_pause_flags_only_from_real_aligned_fixture(self):
        # 合成时间/文字夹具，仅测试真实gap vs 无gap分支；不作为年度录音证据。
        en='He paused, then spoke.';cut=en.index('then')
        plan={'1':{'at':'then spoke','zh':['他停了一下，','然后说话。'],'无停顿':'过期旧标记'}}
        sentence=[{'en':en}];it={'word_alignment':[{'char':cut,'char_end':cut+4,'start':1.5,'end':1.7}], 'parts':[[0.,1.],[1.4,2.]]}
        bound,evidence=bind_manual_pauses(plan,sentence,[it])
        self.assertNotIn('无停顿',bound['1']);self.assertEqual(evidence['1'][0]['actual_gap'],[1.,1.4])
        it['parts']=[[0.,2.]];bound,evidence=bind_manual_pauses(plan,sentence,[it])
        self.assertEqual(bound['1']['无停顿'],'句中没有停顿');self.assertEqual(evidence['1'][0]['switch_time'],1.5)
        it['parts']=[[0.,.3],[.5,2.]];bound,_=bind_manual_pauses(plan,sentence,[it])
        self.assertEqual(bound['1']['无停顿'],'停顿处切不开')
        it['word_alignment']=[]
        with self.assertRaisesRegex(AssertionError,'首词缺少真实对齐'):bind_manual_pauses(plan,sentence,[it])


if __name__=='__main__':unittest.main()
