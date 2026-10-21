"""Non-API synthetic tests for Stage 1's frozen-input integrity gate."""
import json
import copy
from unittest.mock import patch
import tempfile
import unittest
from pathlib import Path
from e3_accuracy_replay import file_sha256, verify_frozen_audit

REQUIRED = {
    'e1_cheap': 270, 'e1_strong': 270, 'e1_paired': 270,
    'e1_invalid': 0, 'e1_unexpected_roles': 0,
    'e1_unpaired_cheap': 0, 'e1_unpaired_strong': 0,
    'e2_total': 1620, 'e2_invalid': 0, 'e2_orphan': 0,
    'e2_invalid_identity': 0, 'e2_duplicate_keys': 0,
    'e2_expected_keys': 1620, 'e2_actual_unique_keys': 1620,
    'e2_missing_keys': 0, 'e2_unexpected_keys': 0,
}

class ReplayGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        cls.e1, cls.e2 = root/'e1', root/'e2'
        cls.e1.mkdir(); cls.e2.mkdir()
        cls.report = root/'audit.json'
        inventories = {}
        for name, folder, count in (('e1', cls.e1, 540), ('e2', cls.e2, 1620)):
            hashes = {}
            for index in range(count):
                path = folder/f'{name}_{index:04d}.json'
                path.write_text('{}', encoding='utf-8')
                hashes[path.name] = file_sha256(path)
            inventories[name] = {'count': count, 'sha256': hashes}
        cls.p1 = cls.e1/'e1_0000.json'
        cls.p2 = cls.e2/'e2_0000.json'
        cls.baseline_audit = {
            'status': 'PRELIMINARY_ONLY', 'counts': dict(REQUIRED),
            'files': inventories,
        }

    def setUp(self):
        self.audit = copy.deepcopy(self.baseline_audit)
        self.save()

    def tearDown(self):
        # Restore only the real fixture files changed by the rejection tests.
        self.p1.write_text('{}', encoding='utf-8')
        self.p2.write_text('{}', encoding='utf-8')
        (self.e1/'extra.json').unlink(missing_ok=True)

    def save(self): self.report.write_text(json.dumps(self.audit))

    def test_complete_valid_inventory(self):
        self.assertEqual(len(list(self.e1.glob('*.json'))), 540)
        self.assertEqual(len(list(self.e2.glob('*.json'))), 1620)
        self.assertTrue(verify_frozen_audit(self.e1, self.e2, self.report))

    def test_missing_raw_file(self):
        self.p1.unlink()
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            verify_frozen_audit(self.e1, self.e2, self.report)

    def test_modified_raw_file(self):
        self.p2.write_text('{"changed": true}')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            verify_frozen_audit(self.e1, self.e2, self.report)

    def test_extra_raw_file(self):
        (self.e1/'extra.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            verify_frozen_audit(self.e1, self.e2, self.report)

    def test_incomplete_counts(self):
        self.audit['counts']['e1_cheap'] = 269
        self.save()
        with self.assertRaisesRegex(ValueError, 'prerequisite failed'):
            verify_frozen_audit(self.e1, self.e2, self.report)

    def test_incomplete_inventory(self):
        self.audit['files']['e2']['sha256'] = {}
        self.save()
        with self.assertRaisesRegex(ValueError, 'Incomplete audit SHA inventory'):
            verify_frozen_audit(self.e1, self.e2, self.report)


    def test_internally_consistent_wrong_cardinalities_rejected(self):
        for name, required_size in (('e1', 540), ('e2', 1620)):
            for size in (0, 1, required_size - 1, required_size + 1):
                with self.subTest(population=name, size=size):
                    self.audit = copy.deepcopy(self.baseline_audit)
                    self.audit['files'][name] = {
                        'count': size,
                        'sha256': {f'synthetic_{i}.json': '0' * 64 for i in range(size)},
                    }
                    self.save()
                    with self.assertRaisesRegex(ValueError, f'cardinality mismatch: {name}'):
                        verify_frozen_audit(self.e1, self.e2, self.report)

    def test_declared_count_must_match_inventory(self):
        for name in ('e1', 'e2'):
            with self.subTest(population=name):
                self.audit = copy.deepcopy(self.baseline_audit)
                self.audit['files'][name]['count'] -= 1
                self.save()
                with self.assertRaisesRegex(ValueError, 'Incomplete audit SHA inventory'):
                    verify_frozen_audit(self.e1, self.e2, self.report)

    def test_declared_count_requires_integer(self):
        for name in ('e1', 'e2'):
            for invalid in (True, str(self.baseline_audit['files'][name]['count']),
                            float(self.baseline_audit['files'][name]['count']), None):
                with self.subTest(population=name, count=invalid):
                    self.audit = copy.deepcopy(self.baseline_audit)
                    self.audit['files'][name]['count'] = invalid
                    self.save()
                    with self.assertRaisesRegex(ValueError, 'Incomplete audit SHA inventory'):
                        verify_frozen_audit(self.e1, self.e2, self.report)

    def test_cardinality_failure_prevents_replay_and_report_write(self):
        import e3_accuracy_replay as replay
        self.audit['files']['e1'] = {
            'count': 1, 'sha256': {self.p1.name: file_sha256(self.p1)},
        }
        self.save()
        output = self.report.parent/'not-created'/'result.json'
        arguments = ['replay', '--e1-dir', str(self.e1), '--e2-dir', str(self.e2),
                     '--audit-report', str(self.report), '--report', str(output)]
        with patch('sys.argv', arguments), patch.object(replay, 'build_rows') as build, \
             patch.object(replay, 'summarize') as summarize:
            with self.assertRaisesRegex(ValueError, 'cardinality mismatch'):
                replay.main()
            build.assert_not_called()
            summarize.assert_not_called()
        self.assertFalse(output.parent.exists())

if __name__ == '__main__': unittest.main()
