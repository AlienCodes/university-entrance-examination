"""只测拒绝条件/证据逻辑；不制造视频，也不伪造真实成品核验成功。"""
import copy,importlib.util,tempfile,unittest
from pathlib import Path
P=Path(__file__).with_name('迁移考试缓存.py');spec=importlib.util.spec_from_file_location('migration_test_target',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fixture():
 inputs={f'专八/听力/批量/数据/2009/{n}.json':str(i)*64 for i,n in enumerate(['试卷','时间轴'],1)}
 ac={'total':14,'T':{'audioEnd':8,'source_duration':10,'trim_start':2},'nfr':465,'CUT_START':2,'CUT_END':None,'INSERTS':[],'ORIGINAL':True}
 h=[{'frame':0,'state_sha256':'a'*64,'html_sha256':'b'*64,'png_key':'0'*11+'1'},{'frame':45,'state_sha256':'c'*64,'html_sha256':'d'*64,'png_key':'0'*11+'2'}]
 state={'states_sha256':'e'*64,'fr_sha256':m.pub.hash_json([[r['frame'],r['png_key']] for r in h]),'html_by_state':h,'png_keys_multiset':[r['png_key'] for r in h],'png_keys_unique':[r['png_key'] for r in h],'audio_contract_sha256':m.pub.hash_json({**ac,'LEAD':1.5,'FPS':30})}
 row={'year':2009,'safe_to_migrate':True,'all_states_and_PNG_identical':True,'removed':[],'PNG_key_set_removed':[],'new_PNG_keys':[],'audio_contract_equal':True,'old':state,'new':copy.deepcopy(state),'old_states':2,'new_states':2,'source_inputs':inputs,'audio_contract_evidence':ac}
 return {'years':[row]},inputs

def transition():
 inputs=fixture()[1];deps={m.ADAPTER:m.OLD_SHA,m.BASE:'a'*64,'unchanged.py':'b'*64};payload={'kind':'exam','id':'2009','inputs':inputs,'render_sources':deps};old={**copy.deepcopy(payload),'status':'approved','shots':{'shots/'+'c'*12+'.png':'d'*64}};old['payload_sha256']=m.pub.hash_json(payload);new=copy.deepcopy(payload);new['render_sources'][m.ADAPTER]=m.NEW_SHA
 return old,new,{'old_sha256':m.OLD_SHA,'new_sha256':m.NEW_SHA}

class RefusalTests(unittest.TestCase):
 def reject(self,fn,*args):
  with self.assertRaises(m.MigrationError):fn(*args)
 def test_unaffected_logic_fixture_passes(self):
  c,i=fixture();self.assertEqual(m.validate_year_certificate(c,2009,i)['year'],2009)
 def test_five_affected_years_never_migrate(self):
  c,i=fixture()
  for y in m.FORBIDDEN:self.reject(m.validate_year_certificate,c,y,i)
 def test_safe_flag_cannot_override_changed_state(self):
  c,i=fixture();c['years'][0]['new']['states_sha256']='f'*64;self.reject(m.validate_year_certificate,c,2009,i)
 def test_HTML_change_rejected(self):
  c,i=fixture();c['years'][0]['new']['html_by_state'][1]['html_sha256']='f'*64;self.reject(m.validate_year_certificate,c,2009,i)
 def test_frame_change_rejected(self):
  c,i=fixture();c['years'][0]['new']['html_by_state'][1]['frame']=46;self.reject(m.validate_year_certificate,c,2009,i)
 def test_missing_full_HTML_rejected(self):
  c,i=fixture();c['years'][0]['old']['html_by_state']=[];c['years'][0]['new']=copy.deepcopy(c['years'][0]['old']);self.reject(m.validate_year_certificate,c,2009,i)
 def test_audio_contract_change_rejected(self):
  c,i=fixture();c['years'][0]['audio_contract_evidence']['CUT_START']=3;self.reject(m.validate_year_certificate,c,2009,i)
 def test_input_change_rejected(self):
  c,i=fixture();i=copy.deepcopy(i);i[next(iter(i))]='f'*64;self.reject(m.validate_year_certificate,c,2009,i)
 def test_removed_tick_not_safe(self):
  c,i=fixture();c['years'][0]['removed']=[{'frame':42}];self.reject(m.validate_year_certificate,c,2009,i)
 def test_exact_single_adapter_transition(self):
  old,new,c=transition();self.assertEqual(m.payload_transition(old,new,c)[0],old['payload_sha256'])
 def test_additional_dependency_change_rejected(self):
  old,new,c=transition();new['render_sources'][m.BASE]='f'*64;self.reject(m.payload_transition,old,new,c)
 def test_dependency_added_rejected(self):
  old,new,c=transition();new['render_sources']['extra.py']='f'*64;self.reject(m.payload_transition,old,new,c)
 def test_certificate_adapter_not_current_rejected(self):
  old,new,c=transition();new['render_sources'][m.ADAPTER]='f'*64;self.reject(m.payload_transition,old,new,c)
 def test_failed_or_pending_old_approval_rejected(self):
  old,new,c=transition();old['status']='pending';self.reject(m.payload_transition,old,new,c)
 def test_old_payload_tamper_rejected(self):
  old,new,c=transition();old['inputs'][next(iter(old['inputs']))]='f'*64;self.reject(m.payload_transition,old,new,c)
 def test_current_input_even_extra_registration_change_rejected(self):
  old,new,c=transition();new['inputs']['origin.json']='f'*64;self.reject(m.payload_transition,old,new,c)
 def test_frozen_certificate_sha_cannot_be_replaced(self):
  self.reject(m.validate_certificate,m.CERTIFICATE,'f'*64)
 def test_actual_png_digest_detects_changed_bytes(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'evidence/已审截图/shots';p.mkdir(parents=True);f=p/('a'*12+'.png');f.write_bytes(b'byte-hash-test-fixture-only')
   old=m.actual_pngs(td)[0];f.write_bytes(b'corrupted-byte-fixture');self.assertNotEqual(old,m.actual_pngs(td)[0])
 def test_duplicate_png_key_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'evidence/已审截图';(p/'a').mkdir(parents=True);(p/'b').mkdir()
   for sub in ['a','b']:(p/sub/('a'*12+'.png')).write_bytes(b'fixture')
   self.reject(m.actual_pngs,td)

if __name__=='__main__':unittest.main(verbosity=2)
