import unittest,json,ast
from pathlib import Path
from unittest.mock import patch
from extensions.overlap_v1 import prepare as p,offline_controls as controls
from extensions.overlap_v1.policy_checks import exhaustive_oracle_check,check_rendering
class PublicPackageTests(unittest.TestCase):
    def test_generation_selection_and_renderings_reproduce(self):
        historical=p.load(p.ROOT/'data/e1/canonical_cases.json')
        pool=p.candidate_pool(historical)
        frozen=p.load(p.DEFAULT_FROZEN/'candidate_pool_v1.json')
        self.assertEqual(pool,frozen)
        selected=p.select_cases(pool)
        cases=p.load(p.DEFAULT_FROZEN/'canonical_cases_v1.json')
        self.assertEqual([c['case_id'] for c in selected],[c['case_id'] for c in cases])
        rendered=[p.render(c,level) for c in cases for level in p.LEVELS]
        self.assertEqual(rendered,p.load(p.DEFAULT_FROZEN/'renderings_v1.json'))
        self.assertEqual(p.jobs(cases),p.load(p.DEFAULT_FROZEN/'execution_manifest_v1.json')['jobs'])
    def test_full_independent_oracle_table(self):
        self.assertEqual(exhaustive_oracle_check(),p.load(p.DEFAULT_FROZEN/'oracle_verification_v1.json'))
    def test_failed_records_remain_unknown(self):
        c,pf=controls.preflight()
        failed=[r for r in c['records'].values() if not r['success']]
        self.assertEqual(len(failed),2)
        self.assertTrue(all(r['usage'] is None and r['estimated_cost_usd'] is None for r in failed))
    def test_request_metadata_preflight(self):
        c,pf=controls.preflight()
        self.assertEqual(pf['public_projection_hashes_verified'],720)
        self.assertTrue(all(r['http_execution']['attempt_count'] is None for r in c['records'].values()))
    def test_manifest_identity_mismatch_is_rejected(self):
        original=controls.load
        def altered(path):
            result=original(path)
            if Path(path).name=='execution_manifest_v1.json':
                result['jobs'][0]['case_id']='INVALID'
            return result
        with patch.object(controls,'load',side_effect=altered),self.assertRaises(ValueError):controls.preflight()
    def test_no_execution_sdk_imports(self):
        for folder in ('src','e3_phase1','extensions'):
            for f in (p.ROOT/folder).rglob('*.py'):
                for node in ast.walk(ast.parse(f.read_text())):
                    if isinstance(node,ast.Import):names=[a.name for a in node.names]
                    elif isinstance(node,ast.ImportFrom):names=[node.module or '']
                    else:continue
                    self.assertFalse(any(x.split('.')[0] in ('google','httpx','dotenv','requests') for x in names),str(f.relative_to(p.ROOT)))
