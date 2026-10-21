"""Regression checks for root Git exclusion and retained payload checks."""
import tempfile,json,hashlib,unittest
from pathlib import Path
from unittest.mock import patch
import scan_release,verify_package
class GitPackageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
  (self.root/'provenance').mkdir()
  (self.root/'data/raw').mkdir(parents=True)
  (self.root/'data/raw/record.json').write_text('{"success":true}')
  (self.root/'provenance/projection_map.json').write_text('{"observation_records":[]}')
  files={p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
  (self.root/'provenance/package_inventory.json').write_text(json.dumps(dict(files_sha256=files)))
  for module in (scan_release,verify_package):
   context=patch.object(module,'ROOT',self.root)
   context.start();self.addCleanup(context.stop)
 def test_normal_git_directory_is_excluded(self):
  (self.root/'.git/objects').mkdir(parents=True)
  (self.root/'.git/objects/binary').write_bytes(bytes([255,0,128]))
  self.assertEqual(verify_package.verify()['status'],'PASS')
  self.assertEqual(scan_release.scan()['files_scanned'],3)
 def test_modified_scientific_payload_rejected(self):
  (self.root/'data/raw/record.json').write_text('{}')
  with self.assertRaises(ValueError):verify_package.verify()
 def test_missing_payload_rejected(self):
  (self.root/'data/raw/record.json').unlink()
  with self.assertRaises(ValueError):verify_package.verify()
 def test_ignored_untracked_payload_rejected(self):
  (self.root/'.env').write_text('example')
  with self.assertRaises(ValueError):verify_package.verify()
  self.assertTrue(scan_release.scan()['findings'])
 def test_nested_git_is_not_exempt(self):
  (self.root/'nested/.git').mkdir(parents=True)
  (self.root/'nested/.git/config').write_text('example')
  with self.assertRaises(ValueError):verify_package.verify()
  self.assertTrue(scan_release.scan()['findings'])
 def test_secret_scan_retained(self):
  (self.root/'example.txt').write_text('AIza'+'x'*35)
  self.assertTrue(any(x['category']=='google_api_key' for x in scan_release.scan()['findings']))
 def test_forbidden_provider_metadata_retained(self):
  (self.root/'data/raw/record.json').write_text('{"provider_interaction_id":"example"}')
  self.assertTrue(any(x['category']=='forbidden_observation_metadata' for x in scan_release.scan()['findings']))
 def test_root_git_file_is_not_directory_exemption(self):
  (self.root/'.git').write_text('example')
  with self.assertRaises(ValueError):verify_package.verify()
  self.assertTrue(scan_release.scan()['findings'])
