import random
import unittest
from e3_controlset_review import (ReviewerProfile, primary_grid, exact_set_match,
    review_distribution, expected_accuracy, expected_routed_accuracy, sample_routed_accuracy)
from e3_accuracy_replay import build_rows, summarize


class ControlSetTests(unittest.TestCase):
    def test_grid_and_bounds(self):
        self.assertEqual(len(primary_grid()), 36)
        for invalid in (-0.1, 1.1, float('nan'), True):
            with self.assertRaises(ValueError):
                ReviewerProfile(invalid, .5, 0.)

    def test_exact_set_match(self):
        self.assertTrue(exact_set_match(['A','B'], ['B','A']))
        self.assertFalse(exact_set_match(['A'],['A','B']))
        with self.assertRaises(ValueError):
            exact_set_match(['A','A'], ['A'])

    def test_distributions(self):
        for profile in primary_grid():
            for correct in (True,False):
                d = review_distribution(correct,profile)
                self.assertAlmostEqual(sum(d.values()),1)
                self.assertTrue(all(0 <= v <= 1 for v in d.values()))

    def test_exact_expected_and_monte_carlo(self):
        profile = ReviewerProfile(.75,.8,.05)
        rows = [(True,True)]*70000 + [(False,True)]*30000
        exact = expected_routed_accuracy(rows,profile)
        self.assertAlmostEqual(exact,.7*.95+.3*.75*.8)
        sampled = sample_routed_accuracy(rows,profile,seed=154)
        self.assertLess(abs(sampled-exact),.01)
        self.assertAlmostEqual(expected_accuracy([True]*7+[False]*3,profile),exact)

    def test_unrouted_and_boundaries(self):
        rows=[(True,False),(False,False)]
        self.assertEqual(expected_routed_accuracy(rows,ReviewerProfile(1,1,0)),.5)
        self.assertEqual(expected_routed_accuracy([(False,True)],ReviewerProfile(1,1,0)),1.)
        self.assertEqual(expected_routed_accuracy([(True,True)],ReviewerProfile(1,1,1)),0.)

    def test_replay_synthetic(self):
        import tempfile, json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); a=root/'e1'; b=root/'e2'; a.mkdir(); b.mkdir()
            mapping={}
            for source_good in (True,False):
                case='01' if source_good else '02'
                for role in ('cheap','strong'):
                    rid=f'E1F-C{case}-L1-{role}-R001'
                    obj={'run_id':rid,'model_role':role,'case_id':f'C{case}', 'rendering_id':f'C{case}-L1'}
                    (a/f'{rid}.json').write_text(json.dumps(obj))
                    mapping[rid] = (source_good if role=='cheap' else True)
                source=f'E1F-C{case}-L1-cheap-R001'
                for role in ('cheap_validator','strong_validator'):
                    for rep in (1,2,3):
                        rid=f'E2F-{source}-{role}-R{rep:03d}'
                        verdict='PASS' if source_good else 'FAIL'
                        (b/f'{rid}.json').write_text(json.dumps({'run_id':rid,'source_cheap_run_id':source,'validator_role':role,'success':True,'parsed_response':{'verdict':verdict}}))
            def score(path):
                rid=path.stem
                return {'scoring_status':'scored', 'exact_match':mapping[rid], 'case_id':json.loads(path.read_text())['case_id'], 'rendering_id':json.loads(path.read_text())['rendering_id']}
            weak,strong,verdicts=build_rows(a,b,score)
            summary=summarize(weak,strong,verdicts)
            x=summary['routes']['cheap_validator']
            self.assertEqual(x['slots'],6)
            self.assertEqual(x['validator_fail_count'],3)
            self.assertEqual(x['reconstructed_weak_validator_strong_accuracy'],1)
            self.assertEqual(len(x['human_review_profiles']),36)
            # Corrupt an expected E2 slot: missing rep must fail closed.
            (b/'E2F-E1F-C01-L1-cheap-R001-cheap_validator-R003.json').unlink()
            with self.assertRaisesRegex(ValueError,'coverage mismatch'):
                build_rows(a,b,score)


if __name__=='__main__': unittest.main()
