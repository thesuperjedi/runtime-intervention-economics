import copy
import itertools
import socket
import unittest
from unittest.mock import patch
from extensions.overlap_v1.analysis import stage2_v1 as s
from extensions.overlap_v1.analysis.verify_stage2_v1 import verify


class Stage2Tests(unittest.TestCase):
    def setUp(self):
        target=patch.object(socket,'create_connection',side_effect=AssertionError('network forbidden'))
        target.start();self.addCleanup(target.stop)

    def row(self,w=True,strong=True,v='PASS',cid='X'):
        return dict(case_id=cid,status='valid',pair_valid=True,weak_correct=w,strong_correct=strong,verdict=v)

    def test_all_eight_solver_verdict_combinations(self):
        rows=[self.row(w,t,v) for w,t,v in itertools.product((False,True),(False,True),('PASS','FAIL'))]
        a=s.summary(rows)
        self.assertEqual(a['confusion'],dict(true_accept=2,false_accept=2,true_reject=2,false_reject=2))
        self.assertEqual((a['corrections'],a['corruptions'],a['failed_repairs']),(1,1,1))
        self.assertEqual(a['cascade_accuracy']['value'],.5)
        self.assertEqual(a['fail_queue']['strong_correctness']['value'],.5)

    def test_failed_malformed_missing_not_verdicts(self):
        self.assertEqual(s.response_status(None),'missing_record')
        self.assertEqual(s.response_status(dict(success=False)),'provider_failure')
        for parsed in (None,{},dict(verdict='MAYBE'),dict(verdict='PASS',extra=1)):
            self.assertEqual(s.response_status(dict(success=True,provider_completed=True,response_valid=True,
                                                   parsed_response=parsed)),'malformed_response')
        a=s.summary([dict(self.row(),status='provider_failure',verdict=None)])
        self.assertEqual(a['valid_judgments'],0)
        self.assertIsNone(a['cascade_accuracy']['value'])
        self.assertIsNone(a['FAR']['value'])

    def test_zero_fail_queue_and_denominators(self):
        a=s.summary([self.row()])
        self.assertIsNone(a['fail_queue']['strong_correctness']['value'])
        self.assertIsNone(a['FAR']['value'])
        self.assertEqual(a['FRR'],dict(numerator=0,denominator=1,value=0))

    def test_case_weighting_not_invocation_weighting(self):
        rows=[self.row(cid='A') for _ in range(3)]+[self.row(w=False,strong=False,cid='B')]
        a=s.summary(rows,True)
        self.assertEqual(a['cascade_accuracy']['value'],.75)
        self.assertEqual(a['case_weighted']['cascade_accuracy']['value'],.5)

    def test_full_raw_reproduction_and_complete_case_exclusion(self):
        report=s.build();self.assertEqual(verify(report)['status'],'PASS')
        cheap=report['roles']['cheap_validator'];strong=report['roles']['strong_validator']
        self.assertEqual(len(cheap['complete_case_ids']),60)
        self.assertEqual(len(strong['complete_case_ids']),58)
        self.assertEqual(strong['excluded_case_ids'],['X013','X032'])
        self.assertEqual(strong['primary_complete_cases']['overall']['valid_judgments'],174)
        self.assertEqual(strong['available_renderings_descriptive']['overall']['valid_judgments'],178)
        self.assertEqual(len(strong['valid_rows_excluded_from_primary']),4)
        for slot in report['unresolved_slots']:
            self.assertIsNone(slot['verdict']);self.assertIsNone(slot['cascade_correct'])
        self.assertEqual(report['evidence']['common_case_denominator'],58)

    def test_independent_verifier_rejects_wrong_confusion_or_imputation(self):
        report=s.build()
        for mode in ('count','imputation'):
            changed=copy.deepcopy(report)
            if mode=='count':
                changed['roles']['cheap_validator']['primary_complete_cases']['overall']['confusion']['false_accept']+=1
            else:
                slot=next(r for r in changed['slots'] if r['status']=='provider_failure')
                slot['verdict']='FAIL';slot['cascade_correct']=True
            with self.subTest(mode=mode),self.assertRaises(ValueError):verify(changed)


if __name__=='__main__':unittest.main()
