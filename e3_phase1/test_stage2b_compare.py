"""Fully offline Stage 2b tests. No files or paid APIs needed."""
import unittest
from e3_stage2b_compare import (estimated_cost, aggregate_baseline, analyze,
                                 EXPECTED_BY_ROLE, ROLES, ROUTES, consistent_winner)
from e3_controlset_review import primary_grid


def synthetic_data():
    slots={}
    report={'status':'ANALYTICAL_SIMULATION_ONLY','source_observations':270,
            'reviewer_profiles':36,'routes':{}}
    for role in ROLES:
        c=EXPECTED_BY_ROLE[role]
        rows=[]
        for label,count,correct,verdict in (
            ('correct_pass',c['correct_pass'],True,'PASS'),
            ('wrong_pass',c['wrong_pass'],False,'PASS'),
            ('wrong_fail',c['wrong_fail'],False,'FAIL'),
            ('correct_fail',c['correct_fail'],True,'FAIL')):
            rows.extend({'weak_correct':correct,'strong_correct':True,'verdict':verdict,
                         'weak_cost':.00035,'strong_cost':.00137,
                         'validator_cost':.00062 if role=='cheap_validator' else .00150} for _ in range(count))
        assert len(rows)==810
        slots[role]=rows
        profiles=[]
        for p in primary_grid():
            dc=p.D*p.C
            profiles.append({'D':p.D,'C':p.C,'F':p.F,
                             'weak_to_human':(708*(1-p.F)+102*dc)/810,
                             'strong_to_human':1-p.F,
                             'weak_validator_to_human_on_fail':(708-c['correct_fail']*p.F+c['wrong_fail']*dc)/810})
        report['routes'][role]={'slots':810,'validator_fail_count':c['FAIL'],
           'observed_weak_accuracy':708/810,'observed_strong_accuracy':1.0,
           'reconstructed_weak_validator_strong_accuracy':(c['correct_pass']+c['FAIL'])/810,
           'human_review_profiles':profiles}
    return report,slots

class Stage2BTests(unittest.TestCase):
    def test_all_72_profiles_and_5_routes(self):
        stage1,slots=synthetic_data()
        r=analyze(stage1,slots,0.1,0.01)
        self.assertEqual(r['status'],'STAGE2B_CONDITIONAL_ONLY')
        for role in ROLES:
            self.assertEqual(len(r['routes'][role]['profiles']),36)
            self.assertEqual(len(r['routes'][role]['automated_baselines']),3)
            self.assertEqual(len(r['routes'][role]['profiles'][0]['comparison']),2)
    def test_stage1_consistency_rejects_changed_accuracy(self):
        stage1,slots=synthetic_data()
        stage1['routes']['cheap_validator']['human_review_profiles'][0]['weak_to_human']+=.001
        with self.assertRaisesRegex(ValueError,'Stage 1 mismatch'):
            analyze(stage1,slots,.1,.01)
    def test_no_free_human_mistake(self):
        s,slots=synthetic_data()
        result=analyze(s,slots,0,0)
        for role in ROLES:
            best=result['routes'][role]['best_automated_at_assumptions']
            self.assertEqual(best,'weak_only')
    def test_weak_cost_smaller_than_strong(self):
        _,slots=synthetic_data()
        b=aggregate_baseline(slots['cheap_validator'],0)
        self.assertLess(b['weak_only']['api_cost_usd_per_slot'],b['strong_only']['api_cost_usd_per_slot'])
    def test_no_negative_cost_or_unpriced_usage(self):
        base={'run_id':'test','usage':{'total_input_tokens':100,'total_output_tokens':10,'total_thought_tokens':0,
                   'total_tokens':110,'total_cached_tokens':0,'total_tool_use_tokens':0}}
        self.assertAlmostEqual(estimated_cost(base,'cheap'),.000055)
        base['usage']['total_cached_tokens']=1
        with self.assertRaisesRegex(ValueError,'not covered'):
            estimated_cost(base,'cheap')
    def test_loss_cost_and_break_even(self):
        s,slots=synthetic_data()
        out=analyze(s,slots,1,.01)
        entry=next(x for x in out['routes']['cheap_validator']['profiles'] if (x['D'],x['C'],x['F'])==(.75,.75,.05))
        self.assertAlmostEqual(entry['comparison']['weak_human_all']['accuracy'],.9012037037037037)
        self.assertAlmostEqual(entry['comparison']['weak_validator_human_on_fail']['review_rate'],83/810)
    def test_near_tie_consistent_winner(self):
        costs={r:1.0 for r in ROUTES}
        costs['weak_human_all'] = 1.0 - 5e-13
        self.assertEqual(consistent_winner(costs,ROUTES),'weak_only')
        costs['weak_human_all'] = 1.0 - 2e-12
        self.assertEqual(consistent_winner(costs,ROUTES),'weak_human_all')

    def test_not_both_validator_costs(self):
        s,slots=synthetic_data()
        out=analyze(s,slots,0,0)
        cheap=out['routes']['cheap_validator']['automated_baselines']['weak_validator_strong_on_fail']['api_cost_usd_per_slot']
        strong=out['routes']['strong_validator']['automated_baselines']['weak_validator_strong_on_fail']['api_cost_usd_per_slot']
        self.assertNotEqual(cheap,strong)

if __name__=='__main__':unittest.main()
