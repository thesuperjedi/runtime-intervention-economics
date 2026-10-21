import copy
from fractions import Fraction as F
import socket
import unittest
from unittest.mock import patch
from extensions.overlap_v1.analysis import stage3_v1 as s
from extensions.overlap_v1.analysis.verify_stage3_v1 import verify,verify_economics


class Stage3Tests(unittest.TestCase):
    def setUp(self):
        target=patch.object(socket,'create_connection',side_effect=AssertionError('network forbidden'))
        target.start();self.addCleanup(target.stop)

    def test_normalized_token_pricing_no_invocation_addition(self):
        rec=dict(job={'role':'cheap'},usage=dict(total_input_tokens=100,total_output_tokens=10,
            total_thought_tokens=20,total_tokens=130,total_cached_tokens=0,total_tool_use_tokens=0),
            estimated_cost_usd=.000105,model_invocation_token_counts=dict(raw_prompt_token=999999))
        self.assertEqual(s.cost(rec),F(105,1000000))
        self.assertIsNone(s.cost(dict(usage=None)))
        rec['usage']['total_cached_tokens']=1
        with self.assertRaises(ValueError):s.cost(rec)

    def test_global_winners_ignore_dominated_pairwise_equality(self):
        lines=dict(weak_only=(F(0),F(1)),strong_only=(F(2),F(0)),
                   cheap_validator_cascade=(F(3),F(1,2)))
        e=s.economics(lines,6);verify_economics(e,lines,6)
        pair=next(x for x in e['pairwise_boundaries'] if x['routes']==['weak_only','cheap_validator_cascade'])
        self.assertEqual(pair['error_loss_usd'],6)
        self.assertFalse(pair['on_global_minimum'])
        self.assertEqual(s.winners(lines,F(2)),['weak_only','strong_only'])

    def test_exact_ties_and_parallel_dominance(self):
        lines=dict(weak_only=(F(1),F(0)),strong_only=(F(1),F(0)),
                   cheap_validator_cascade=(F(2),F(0)))
        e=s.economics(lines,3);verify_economics(e,lines,3)
        self.assertEqual(e['winners_at_zero'],['weak_only','strong_only'])
        self.assertEqual(e['pairwise_boundaries'][0]['kind'],'identical_lines')

    def test_three_way_tie_and_signed_losses(self):
        lines=dict(weak_only=(F(0),F(1)),strong_only=(F(2),F(0)),
                   cheap_validator_cascade=(F(1),F(1,2)))
        e=s.economics(lines,3);verify_economics(e,lines,3)
        self.assertEqual(s.winners(lines,F(2)),list(lines))
        self.assertEqual(s.winners(lines,F(3)),['strong_only'])

    def test_full_raw_verifier_and_unknown_research_charges(self):
        report=s.build();result=verify(report)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(len(report['research_expenditure']['unknown_charge_run_ids']),2)
        self.assertIsNone(report['research_expenditure']['actual_provider_charges'])
        primary=report['primary_common58']
        self.assertEqual((primary['canonical_cases'],primary['evaluated_renderings']),(58,174))

    def test_raw_verifier_rejects_extra_solver_charge_and_wrong_boundary(self):
        report=s.build()
        for mode in ('charge','boundary'):
            changed=copy.deepcopy(report)
            if mode=='charge':
                row=next(x for x in changed['primary_common58']['route_rows']['strong_validator_cascade'] if x['verdict']=='PASS')
                row['charged_run_ids'].append('invented-strong-solver-call')
            else:
                row=next(x for x in changed['primary_common58']['economics']['pairwise_boundaries'] if x['kind']=='point_equality')
                row['error_loss_usd']+=.1
            with self.subTest(mode=mode),self.assertRaises(ValueError):verify(changed)


if __name__=='__main__':unittest.main()
