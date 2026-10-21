"""Verify licence scopes, evidence exclusions and confirmed attribution offline."""
import json,unittest,hashlib
from scan_release import package_files
from scan_release import package_files
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class FinalLicensingTests(unittest.TestCase):
 def test_every_current_file_has_rights_notice(self):
  notices=json.loads((ROOT/'provenance/rights_inventory.json').read_text(encoding='utf-8'))['files']
  actual={p.relative_to(ROOT).as_posix() for p in package_files(ROOT)}
  self.assertTrue(actual<=set(notices),sorted(actual-set(notices)))
 def test_observation_files_have_no_blanket_cc_by_grant(self):
  notices=json.loads((ROOT/'provenance/rights_inventory.json').read_text(encoding='utf-8'))['files']
  rows=[v for k,v in notices.items() if k.startswith(('data/raw/e1/','data/raw/e2_full/','data/raw/extension_overlap_v1/'))]
  self.assertEqual(len(rows),2880)
  for r in rows:
   self.assertEqual(r['disposition'],'MIXED-PROVIDER-EVIDENCE')
   self.assertIsNone(r['provider_content_licence_from_author'])
 def test_all_experimental_evidence_preserved(self):
  for folder,count in [('e1',540),('e2_full',1620),('extension_overlap_v1',720)]:
   self.assertEqual(len(list((ROOT/'data/raw'/folder).glob('*.json'))),count)
  failed=[]
  for p in (ROOT/'data/raw/extension_overlap_v1').glob('*.json'):
   r=json.loads(p.read_text(encoding='utf-8'))
   if not r['success']:failed.append(r)
  self.assertEqual(len(failed),2)
  self.assertTrue(all(r['usage'] is None and r['estimated_cost_usd'] is None for r in failed))
 def test_software_and_documentation_scopes_differ(self):
  files=json.loads((ROOT/'provenance/rights_inventory.json').read_text(encoding='utf-8'))['files']
  self.assertEqual(files['src/e1_score.py']['author_licence'],'MIT')
  self.assertEqual(files['README.md']['author_licence'],'CC-BY-4.0')
 def test_official_licence_file_hashes(self):
  data=json.loads((ROOT/'provenance/licence_sources.json').read_text(encoding='utf-8'))
  for k in ('MIT','CC_BY_4_0'):
   p=ROOT/data[k]['file'];self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),data[k]['sha256'])
  self.assertEqual(data['CC_BY_4_0']['sha256'],'9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411')
 def test_no_ambiguous_cff_dual_licensing(self):
  c=json.loads((ROOT/'CITATION.cff').read_text(encoding='utf-8'))
  self.assertEqual(c['authors'],[{'given-names':'Jaidev'}])
  self.assertEqual(c['version'],'1.2.0-rc.1')
  self.assertNotIn('license',c)
 def test_ai_assistance_and_provider_provenance_disclosed(self):
  t=(ROOT/'ATTRIBUTION.md').read_text(encoding='utf-8')
  self.assertIn('AI assistants',t)
  self.assertIn('Gemini-generated evidence',t)
  self.assertIn('not an institutional affiliation',t)
 def test_report_response_copies_excluded(self):
  f=json.loads((ROOT/'provenance/rights_inventory.json').read_text(encoding='utf-8'))['files']
  r=f['extensions/overlap_v1/analysis/stage1_results_v1.json']
  self.assertIsNone(r['provider_content_licence_from_author'])
  self.assertIn('copied actual_controls',r['excluded_content'])
