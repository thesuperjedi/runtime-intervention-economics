"""Synthetic, offline robustness checks; no raw writes, SDKs or network."""
import copy
import itertools
import unittest
from collections import Counter

from e3_accuracy_replay import summarize
from e3_stage2b_compare import analyze as baseline_analyze
from e3_stage2c_boundaries import ROLES, ROUTES, AUTO_ROUTES
from e3_strong_robustness import (
    probability, source_table, exposures, evaluate, planes, envelope_1d, rank,
    lower_regions, allocation, ordered_groups, concentration_segments, path_envelope,
)


def fixture():
    weak, strong = {}, {}
    sources = []
    for case in range(1, 31):
        for level in range(1, 4):
            for rep in range(1, 4):
                src = f'E1F-C{case:02d}-L{level}-cheap-R{rep:03d}'
                meta = dict(case=f'C{case:02d}', rendering=f'C{case:02d}-L{level}',
                            correct=len(sources) >= 34, role='cheap')
                weak[src] = meta
                strong[src.replace('-cheap-', '-strong-')] = dict(meta, correct=True, role='strong')
                sources.append(src)
    slots, verdicts = {}, {}
    for role in ROLES:
        rows = []
        wrong_slot = correct_slot = 0
        for src in sources:
            for rep in (1, 2, 3):
                w = weak[src]['correct']
                if role == 'strong_validator':
                    fail = not w
                elif not w:
                    fail = wrong_slot >= 25
                    wrong_slot += 1
                else:
                    fail = correct_slot < 6
                    correct_slot += 1
                verdict = 'FAIL' if fail else 'PASS'
                verdicts[src, role, rep] = verdict
                rows.append(dict(source=src, rep=rep, weak_correct=w, strong_correct=True,
                                 verdict=verdict, weak_cost=.00035, strong_cost=.00137,
                                 validator_cost=.00062 if role == 'cheap_validator' else .00150))
        slots[role] = rows
    stage1 = summarize(weak, strong, verdicts)
    baseline = baseline_analyze(stage1, slots, .1, .01)
    return weak, slots, baseline


class StrongRobustnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.weak, cls.slots, cls.reference = fixture()
        cls.table = source_table(cls.weak, cls.slots)

    def test_zero_error_reproduces_every_route_and_profile(self):
        result = evaluate(self.reference, self.table, dict.fromkeys(self.weak, 0))
        for role in ROLES:
            for original, actual in zip(self.reference['routes'][role]['profiles'], result['roles'][role]):
                for route in ROUTES:
                    row = (self.reference['routes'][role]['automated_baselines'] if route in AUTO_ROUTES
                           else original['comparison'])[route]
                    self.assertEqual(actual['expected_error_by_route'][route], 1-row['accuracy'])
                    reconstructed = actual['ranking']['minimum_usd_per_slot']+actual['ranking']['excess_usd_by_route'][route]
                    self.assertAlmostEqual(reconstructed, row['total_expected_usd_per_slot'], places=15)
                self.assertEqual(actual['ranking']['winner'], original['minimum_expected_cost_route_at_assumptions'])

    def test_extreme_all_strong_answers_wrong(self):
        out = evaluate(self.reference, self.table, dict.fromkeys(self.weak, 1))
        for role, correct_pass in (('cheap_validator', 702), ('strong_validator', 708)):
            errors = out['roles'][role][0]['expected_error_by_route']
            self.assertEqual(errors['strong_only'], 1)
            self.assertAlmostEqual(1-errors['weak_validator_strong_on_fail'], correct_pass/810)

    def test_probabilities_and_coverage_fail_closed(self):
        for value in (-.1, 1.1, True, None, '0.1', float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                probability(value)
        with self.assertRaises(ValueError):
            exposures(self.table, {})
        self.assertEqual(probability(0), 0)
        self.assertEqual(probability(1), 1)

    def test_uniform_exposure_uses_fail_fraction(self):
        out = exposures(self.table, dict.fromkeys(self.weak, .2))
        self.assertAlmostEqual(out['strong_error'], .2)
        self.assertAlmostEqual(out['escalation_error']['cheap_validator'], .2*83/810)
        self.assertAlmostEqual(out['escalation_error']['strong_validator'], .2*102/810)

    def test_weak_error_overlap_equations(self):
        q = {s['source']: .1 if s['weak_correct'] else .7 for s in self.table}
        e = exposures(self.table, q)
        self.assertAlmostEqual(e['strong_error'], (34*.7+236*.1)/270)
        self.assertAlmostEqual(e['escalation_error']['cheap_validator'], (77*.7+6*.1)/810)
        self.assertAlmostEqual(e['escalation_error']['strong_validator'], 102*.7/810)

    def test_shared_source_perturbation_does_not_change_routes_or_humans(self):
        original = copy.deepcopy(self.slots)
        q = dict.fromkeys(self.weak, 0)
        source = next(s['source'] for s in self.table if s['fail_fraction']['cheap_validator'] == 1)
        q[source] = 1
        e = exposures(self.table, q)
        for role in ROLES:
            self.assertAlmostEqual(e['escalation_error'][role], 1/270)
        a = evaluate(self.reference, self.table, q)
        b = evaluate(self.reference, self.table, dict.fromkeys(self.weak, 0))
        for role in ROLES:
            for x, y in zip(a['roles'][role], b['roles'][role]):
                for r in ('weak_only', 'weak_human_all', 'weak_validator_human_on_fail'):
                    self.assertEqual(x['expected_error_by_route'][r], y['expected_error_by_route'][r])
        self.assertEqual(self.slots, original)

    def test_invalid_repetitions_and_pairing_rejected(self):
        bad = copy.deepcopy(self.slots)
        bad['cheap_validator'][0]['rep'] = 2
        with self.assertRaises(ValueError): source_table(self.weak, bad)
        bad = copy.deepcopy(self.slots)
        bad['strong_validator'][0]['strong_cost'] += 1
        with self.assertRaises(ValueError): source_table(self.weak, bad)

    def test_binary_source_placement_extrema_against_enumeration(self):
        table = [dict(source=str(i), case=str(i), weak_correct=True,
                      fail_fraction={r: f for r in ROLES})
                 for i, f in enumerate((0, 0, 1/3, 2/3, 1, 1))]
        for k in range(7):
            values = []
            for combo in itertools.combinations(range(6), k):
                q = {str(i): int(i in combo) for i in range(6)}
                values.append(exposures(table, q)['escalation_error']['cheap_validator'])
            for direction, expected in (('inside_first', max(values)), ('outside_first', min(values))):
                groups = ordered_groups(table, 'cheap_validator', 'source', direction)
                q = allocation(table, groups, k/6)
                self.assertAlmostEqual(exposures(table, q)['escalation_error']['cheap_validator'], expected)

    def test_whole_canonical_cases_and_fractional_case_probability(self):
        groups = ordered_groups(self.table, 'cheap_validator', 'canonical_case', 'inside_first')
        for k in range(31):
            q = allocation(self.table, groups, k/30)
            self.assertAlmostEqual(sum(q.values())/270, k/30)
            self.assertTrue(all(abs(v-round(v)) < 1e-12 for v in q.values()))
            for g in groups:
                self.assertEqual(len({q[s] for s in g['sources']}), 1)
        q = allocation(self.table, groups, 1/60)
        self.assertEqual(len([v for v in q.values() if v == .5]), 9)

    def test_case_exposure_bounds_against_enumerated_subset(self):
        table = []
        for i, f in enumerate((0, .2, .8, 1)):
            for j in range(9):
                table.append(dict(source=f'{i}-{j}', case=str(i), weak_correct=True,
                                  fail_fraction={r: f for r in ROLES}))
        for k in range(5):
            vals = [sum((0,.2,.8,1)[i] for i in combo)/4
                    for combo in itertools.combinations(range(4), k)]
            for direction, expected in (('inside_first', max(vals)), ('outside_first', min(vals))):
                groups = ordered_groups(table, 'cheap_validator', 'canonical_case', direction)
                self.assertAlmostEqual(exposures(table, allocation(table, groups, k/4))['escalation_error']['cheap_validator'], expected)

    def test_affine_overlap_matches_source_evaluation(self):
        for role in ROLES:
            p = self.reference['routes'][role]['profiles'][12]
            affine = planes(self.reference, (role, p), self.table)
            q = {s['source']: .13 if s['weak_correct'] else .41 for s in self.table}
            result = evaluate(self.reference, self.table, q)['roles'][role][12]['ranking']
            for r, (a,b,c) in affine.items():
                self.assertAlmostEqual(a+b*.41+c*.13,
                                       result['minimum_usd_per_slot']+result['excess_usd_by_route'][r])

    def test_global_minimum_chained_ties_and_exact_tie(self):
        vals = dict.fromkeys(ROUTES, .02)
        vals.update(weak_only=.001+1.5e-12, strong_only=.001+.75e-12,
                    weak_validator_strong_on_fail=.001)
        self.assertEqual(rank(vals)['winner'], 'strong_only')
        self.assertEqual(rank(dict.fromkeys(ROUTES, 1))['winner'], 'weak_only')

    def test_actual_1d_envelope_excludes_dominated_pair_crossing(self):
        lines = dict.fromkeys(ROUTES, (9.,0.))
        lines.update(weak_only=(1.,0.), strong_only=(0.,2.),
                     weak_validator_strong_on_fail=(3.,-1.))
        env = envelope_1d(lines)
        self.assertTrue(any(abs(p['error_rate']-.5)<1e-14 for p in env['lowest_cost_equalities']))
        self.assertFalse(any('weak_validator_strong_on_fail' in p['mathematical_minimizers']
                             for p in env['lowest_cost_equalities']))
        self.assertEqual(env['intervals'][0]['winner'], 'strong_only')
        self.assertEqual(env['intervals'][-1]['winner'], 'weak_only')

    def test_2d_regions_and_active_boundaries(self):
        affine = dict.fromkeys(ROUTES, (9.,0.,0.))
        affine.update(weak_only=(1.,0.,0.), strong_only=(2.,-2.,0.),
                      weak_validator_strong_on_fail=(2.,0.,-2.))
        regions = lower_regions(affine)
        self.assertNotIn('weak_human_all', regions['mathematical_minimum_regions'])
        for boundary in regions['active_lowest_cost_boundaries']:
            for u,v in boundary['segment']:
                vals = {r:a+b*u+c*v for r,(a,b,c) in affine.items()}
                minimum = min(vals.values())
                for r in boundary['routes']:
                    self.assertAlmostEqual(vals[r], minimum, places=12)
        for route, poly in regions['mathematical_minimum_regions'].items():
            for u,v in poly:
                vals = {r:a+b*u+c*v for r,(a,b,c) in affine.items()}
                self.assertLessEqual(vals[route], min(vals.values())+1e-12)

    def test_path_intervals_match_direct_probabilities(self):
        groups = ordered_groups(self.table, 'cheap_validator', 'canonical_case', 'inside_first')
        segments = concentration_segments(self.table, groups)
        for role in ROLES:
            p = self.reference['routes'][role]['profiles'][0]
            env = path_envelope(self.reference, self.table, role, p, segments)
            for interval in env['intervals']:
                q = allocation(self.table, groups, (interval['start']+interval['to'])/2)
                direct = evaluate(self.reference, self.table, q)['roles'][role][0]['ranking']
                self.assertEqual(interval['winner'], direct['winner'])


if __name__ == '__main__':
    unittest.main()
