"""Offline Stage 2c sensitivity tests using synthetic Stage 2b records."""
import copy
import unittest
from e3_stage2c_boundaries import analyze, route_winner, costs_at, ROUTES, automated_winner, validate_profiles, EXPECTED_PROFILES
from e3_stage2b_compare import analyze as stage2b_analyze, consistent_winner
from test_stage2b_compare import synthetic_data

class Stage2CTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stage1, slots=synthetic_data()
        cls.stage2b=stage2b_analyze(stage1,slots,.1,.01)

    def test_grid_dimensions_and_profiles(self):
        out=analyze(self.stage2b, [0,.01,.1],[0,.01])
        for role in out['routes']:
            self.assertEqual(len(out['routes'][role]['profiles']),36)
            self.assertEqual(sum(out['routes'][role]['winner_counts_all_profile_grid_cells'].values()),36*3*2)

    def test_stage2b_reference_reproduced(self):
        out=analyze(self.stage2b,[.1],[.01])
        for role in out['routes']:
            for result,original in zip(out['routes'][role]['profiles'],self.stage2b['routes'][role]['profiles']):
                self.assertEqual(result['winner_grid'][0][0], original['minimum_expected_cost_route_at_assumptions'])

    def test_zero_loss_and_review_prefers_weak(self):
        out=analyze(self.stage2b,[0],[0])
        for role in out['routes']:
            for result in out['routes'][role]['profiles']:
                self.assertEqual(result['winner_grid'][0][0], 'weak_only')

    def test_winner_consistent_under_tolerance(self):
        vals={'weak_only':.001,'strong_only':.001+2e-12,
              'weak_validator_strong_on_fail':.02,'weak_human_all':.001-5e-13,
              'weak_validator_human_on_fail':.03}
        self.assertEqual(route_winner(vals), 'weak_only')
        self.assertEqual(consistent_winner(vals, ROUTES), 'weak_only')
        vals['weak_human_all']=.001-2e-12
        self.assertEqual(route_winner(vals),'weak_human_all')
        self.assertEqual(consistent_winner(vals,ROUTES),'weak_human_all')

    def test_reject_tampered_baseline_cost(self):
        bad=copy.deepcopy(self.stage2b)
        bad['routes']['cheap_validator']['automated_baselines']['weak_only']['total_expected_usd_per_slot']+=.001
        with self.assertRaisesRegex(ValueError,'baseline does not reproduce'):
            analyze(bad,[.1],[.01])

    def test_reject_tampered_threshold(self):
        bad=copy.deepcopy(self.stage2b)
        bad['routes']['strong_validator']['profiles'][0]['comparison']['weak_human_all']['break_even_review_usd_vs_best_automated']+=.01
        with self.assertRaisesRegex(ValueError,'threshold mismatch'):
            analyze(bad,[.1],[.01])

    def test_api_human_and_loss_terms(self):
        c={r:{'api':.001, 'errors':.1, 'review_rate':0} for r in ROUTES}
        c['weak_human_all']['review_rate']=1
        self.assertAlmostEqual(costs_at(c,.1,.01)['weak_human_all'],.021)
        self.assertAlmostEqual(costs_at(c,.1,.01)['weak_only'],.011)

    def test_negative_and_duplicate_grid_rejected(self):
        with self.assertRaises(ValueError): analyze(self.stage2b,[-1],[0])
        with self.assertRaises(ValueError): analyze(self.stage2b,[0,0],[0])

    def test_chained_near_ties_use_global_minimum(self):
        vals = dict.fromkeys(ROUTES, .02)
        vals.update(weak_only=.001 + 1.5e-12,
                    strong_only=.001 + .75e-12,
                    weak_validator_strong_on_fail=.001)
        self.assertEqual(route_winner(vals), 'strong_only')
        self.assertEqual(automated_winner(vals), 'strong_only')
        vals['weak_human_all'] = 0
        self.assertEqual(route_winner(vals), 'weak_human_all')
        self.assertEqual(automated_winner(vals), 'strong_only')

    def test_previously_identified_three_route_near_tie(self):
        vals = dict.fromkeys(ROUTES, .02)
        vals.update(weak_only=.0013697166674166668,
                    strong_only=.0013697166666666667,
                    weak_human_all=.0013697166659166666)
        # Weak is outside the minimum's tolerance; strong and human are within it.
        self.assertEqual(route_winner(vals), 'strong_only')
        self.assertEqual(automated_winner(vals), 'weak_only')

    def test_exact_ties_follow_existing_route_priority(self):
        for index, preferred in enumerate(ROUTES):
            vals = {route: (0 if i >= index else .02)
                    for i, route in enumerate(ROUTES)}
            with self.subTest(preferred=preferred):
                self.assertEqual(route_winner(vals), preferred)
        for index, preferred in enumerate(ROUTES[:3]):
            vals = {route: (0 if i >= index else .02)
                    for i, route in enumerate(ROUTES)}
            self.assertEqual(automated_winner(vals), preferred)

    def test_tolerance_boundary_includes_preferred_route(self):
        vals = dict.fromkeys(ROUTES, .02)
        vals.update(weak_only=1e-12, strong_only=0)
        self.assertEqual(route_winner(vals), 'weak_only')
        self.assertEqual(automated_winner(vals), 'weak_only')

    def test_exact_profile_grid_and_numeric_endpoints(self):
        profiles = [dict(zip(('D', 'C', 'F'), key)) for key in EXPECTED_PROFILES]
        validate_profiles(profiles)
        for p in profiles:
            for k in ('D', 'C', 'F'):
                if p[k] in (0, 1):
                    p[k] = int(p[k])
        validate_profiles(list(reversed(profiles)))

    def test_reject_invalid_profile_values_before_replay(self):
        for role in self.stage2b['routes']:
            for field in ('D', 'C', 'F'):
                for value in (-.1, 1.1, float('nan'), float('inf'), True, False, '0.5', None, .123):
                    with self.subTest(role=role, field=field, value=value):
                        bad = copy.deepcopy(self.stage2b)
                        bad['routes'][role]['profiles'][0][field] = value
                        # Invalid grid must fail before analytical coefficient access.
                        bad['routes'][role]['profiles'][0].pop('comparison')
                        with self.assertRaisesRegex(ValueError, 'profile'):
                            analyze(bad, [0], [0])

    def test_reject_missing_extra_duplicate_and_malformed_profiles(self):
        original = self.stage2b['routes']['cheap_validator']['profiles']
        variants = [None, {}, original[:-1], original + [original[0]]]
        duplicate = copy.deepcopy(original)
        duplicate[-1] = copy.deepcopy(duplicate[0])
        variants.append(duplicate)
        for replacement in (None, {}, {'D': .25, 'C': .5}):
            malformed = copy.deepcopy(original)
            malformed[0] = replacement
            variants.append(malformed)
        for profiles in variants:
            with self.subTest(profiles_type=type(profiles).__name__):
                with self.assertRaises(ValueError):
                    validate_profiles(profiles)

if __name__=='__main__': unittest.main()
