import copy
import socket
import unittest
from pathlib import Path
from unittest.mock import patch
from extensions.overlap_v1.analysis import stage1_v1 as s
from extensions.overlap_v1.analysis.verify_stage1_v1 import verify
from src import e1_score


class Stage1Tests(unittest.TestCase):
    def setUp(self):
        target=patch.object(socket,'create_connection',side_effect=AssertionError('network forbidden'))
        target.start();self.addCleanup(target.stop)

    def test_historical_set_contract_order_duplicates_and_wrong_sets(self):
        for actual,correct in [(['A','B'],True),(['B','A'],True),(['A','A','B'],True),
                               (['A'],False),(['A','B','C'],False)]:
            self.assertEqual(s.score(dict(success=True,parsed_response={'controls':actual}),['A','B'])['exact_match'],correct)

    def test_failures_and_invalid_distinct(self):
        for rec,status in [(dict(success=False,parsed_response={'controls':[]}), 'execution_failure'),
                           (dict(success=True,parsed_response=None),'invalid_response'),
                           (dict(success=True,parsed_response={'controls':'A'}),'invalid_response')]:
            self.assertEqual(s.score(rec,[])['scoring_status'],status)

    def test_all_joint_cells_and_conditioning_denominators(self):
        rows=[dict(pair_valid=True,case_id='X',weak_correct=w,strong_correct=t)
              for w,t in [(True,True),(True,False),(False,True),(False,False)]]
        a=s.summarize(rows)
        self.assertEqual(set(a['joint_rendering_counts'].values()),{1})
        self.assertEqual(a['strong_error_given_weak_wrong'],dict(numerator=1,denominator=2,value=.5))
        self.assertEqual(a['strong_error_given_weak_correct'],dict(numerator=1,denominator=2,value=.5))

    def test_zero_denominators_and_invalid_pair_exclusion(self):
        self.assertIsNone(s.summarize([])['strong_accuracy']['value'])
        rows=[dict(pair_valid=True,case_id='X',weak_correct=True,strong_correct=True),
              dict(pair_valid=False,case_id='Y',weak_correct=None,strong_correct=None)]
        a=s.summarize(rows)
        self.assertEqual(a['valid_paired_renderings'],1)
        self.assertIsNone(a['strong_error_given_weak_wrong']['value'])

    def test_full_corpus_independent_historical_reproduction(self):
        report=s.build()
        self.assertEqual(verify(report)['status'],'PASS')
        self.assertEqual(report['primary_summary']['case_weighted']['canonical_denominator'],60)

    def test_independent_verifier_rejects_altered_scores(self):
        report=s.build()
        report['solver_scores'][0]['exact_match']=not report['solver_scores'][0]['exact_match']
        with self.assertRaises(ValueError):verify(report)


if __name__=='__main__':unittest.main()
