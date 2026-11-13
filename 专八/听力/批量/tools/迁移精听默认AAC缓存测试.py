"""迁移边界/指纹反例；不生成媒体、不伪造视频核验成功。"""
import copy,importlib.util,unittest,ast
from pathlib import Path
s=importlib.util.spec_from_file_location('intensive_aac_migration_test',Path(__file__).with_name('迁移精听默认AAC缓存.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def pair():
 a={'kind':'intensive','id':'2009-A','inputs':{'input.json':'a'*64},'render_sources':{**{k:v[0] for k,v in m.CORE.items()},'unchanged.py':'c'*64},'annotation_source':{'file':'mother.json','unit_sha256':'d'*64}};old=copy.deepcopy(a);old.update(status='approved',shots={'shots/screen001.png':'e'*64},payload_sha256=m.pub.hash_json(a));new=copy.deepcopy(a)
 for k,v in m.CORE.items():new['render_sources'][k]=v[1]
 return old,new
class Cases(unittest.TestCase):
 def reject(self,fn,*args):
  with self.assertRaises(m.MigrationError):fn(*args)
 def test_old_five_allowed_without_policy_field(self):
  for uid in m.IDS:m.target(uid,{'id':uid,'audio':{}})
 def test_2015A_never_migrates_even_if_field_removed(self):self.reject(m.target,'2015-A',{'id':'2015-A','audio':{}})
 def test_other_unit_rejected(self):self.reject(m.target,'2024-B2',{'id':'2024-B2','audio':{}})
 def test_explicit256_rejected(self):self.reject(m.target,'2009-A',{'id':'2009-A','audio':{'aac_bitrate':'256k'}})
 def test_explicit192_is_not_unchanged_old_input(self):self.reject(m.target,'2009-A',{'id':'2009-A','audio':{'aac_bitrate':'192k'}})
 def test_two_core_only_transition(self):
  old,new=pair();m.transition(old,new)
 def test_additional_dependency_rejected(self):
  old,new=pair();new['render_sources']['unchanged.py']='f'*64;self.reject(m.transition,old,new)
 def test_added_dependency_rejected(self):
  old,new=pair();new['render_sources']['extra.py']='f'*64;self.reject(m.transition,old,new)
 def test_changed_input_rejected(self):
  old,new=pair();new['inputs']['input.json']='f'*64;self.reject(m.transition,old,new)
 def test_changed_source_semantics_rejected(self):
  old,new=pair();new['annotation_source']['unit_sha256']='f'*64;self.reject(m.transition,old,new)
 def test_wrong_old_core_rejected(self):
  old,new=pair();k=next(iter(m.CORE));old['render_sources'][k]='f'*64;old['payload_sha256']=m.pub.hash_json({k:old[k] for k in ['kind','id','inputs','render_sources','annotation_source']});self.reject(m.transition,old,new)
 def test_pending_old_approval_rejected(self):
  old,new=pair();old['status']='pending';self.reject(m.transition,old,new)
 def test_payload_tamper_rejected(self):
  old,new=pair();old['payload_sha256']='f'*64;self.reject(m.transition,old,new)
 def test_stale_root_proof_rejected(self):self.reject(m.validate_proof,'f'*64)
 def test_newcode_default_normalization_is_exact(self):
  for p in m.CORE:
   before=m.common.old_blob(m.BASELINE,p);after=(m.ROOT/p).read_bytes();n=m.Defaults();self.assertEqual(m.asts(n.visit(ast.parse(after))),m.asts(ast.parse(before)))
 def test_PNG_changed_bytes_rejected(self):self.reject(m.common.require_png_multiset,{'a':'1'*64},{'a':'2'*64},'changed PNG')
 def test_PNG_multiplicity_rejected(self):self.reject(m.common.require_png_multiset,{'a':'1'*64,'b':'1'*64},{'a':'1'*64},'missing PNG')
if __name__=='__main__':unittest.main(verbosity=2)
