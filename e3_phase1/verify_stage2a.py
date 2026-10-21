"""Independent, read-only E3 Stage 2a mathematical and structural verification.

Reads saved Stage 1 and Stage 2a reports. No report writes and no API calls.
It checks the assumed equal-loss economics; it does not validate real human costs.
"""
import argparse
import json
import math
from pathlib import Path

EXPECTED = {
    'cheap_validator': (702, 25, 77, 6),
    'strong_validator': (708, 0, 102, 0),
}
DS = (.25, .5, .75, 1.)
CS = (.5, .75, 1.)
FS = (0., .05, .15)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def numerical(actual, expected, label):
    require(isinstance(actual, (int, float)) and not isinstance(actual, bool)
            and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
            f'{label}: expected {expected}, found {actual}')


def check(stage1, economics):
    require(stage1.get('status') == 'ANALYTICAL_SIMULATION_ONLY', 'Unexpected Stage 1 status')
    require(stage1.get('source_observations') == 270, 'Unexpected source count')
    require(economics.get('status') == 'ECONOMIC_SENSITIVITY_ONLY', 'Unexpected Stage 2a status')
    require(economics.get('unit') == 'dimensionless H/L', 'Unexpected cost units')
    require(set(economics.get('validator_routes', {})) == set(EXPECTED), 'Unexpected Stage 2a routes')
    require(set(stage1.get('routes', {})) == set(EXPECTED), 'Unexpected Stage 1 routes')
    checks = 0
    for role, (cp, wp, wf, cf) in EXPECTED.items():
        entry = economics['validator_routes'][role]
        stage = stage1['routes'][role]
        n = cp + wp + wf + cf
        require(n == 810, f'{role}: unexpected N')
        require(entry.get('source_slots') == n, f'{role}: source slots')
        counts = entry.get('observed_validator_confusion', {})
        for name, count in zip(('correct_pass','wrong_pass','wrong_fail','correct_fail'), (cp, wp, wf, cf)):
            require(counts.get(name) == count, f'{role}: {name}')
        profiles = entry.get('profiles', [])
        source_profiles = stage.get('human_review_profiles', [])
        require(len(profiles) == len(source_profiles) == 36, f'{role}: profile count')
        source_map = {(p['D'],p['C'],p['F']):p for p in source_profiles}
        require(len(source_map) == 36, f'{role}: Stage 1 duplicate profiles')
        index = {(p['D'],p['C'],p['F']):p for p in profiles}
        require(len(index) == 36, f'{role}: Stage 2a duplicate profiles')
        require(set(index) == set(source_map) == {(d,c,f) for d in DS for c in CS for f in FS},
                f'{role}: incomplete profile grid')
        for (d,c,f), row in index.items():
            original = source_map[(d,c,f)]
            cases = (
                ('weak_all_review', cp+cf, wp+wf, 'weak_to_human'),
                ('strong_all_review', n, 0, 'strong_to_human'),
                ('validator_fail_only_review', cf, wf, 'weak_validator_to_human_on_fail'),
            )
            for route, right, wrong, source_field in cases:
                sub = row[route]
                reviewed = right + wrong
                gain = (wrong*d*c-right*f)/n
                threshold = (wrong*d*c-right*f)/reviewed if reviewed else None
                require(sub.get('review_count') == reviewed, f'{role} {d,c,f} {route}: review count')
                numerical(sub.get('review_rate'), reviewed/n, f'{role} {d,c,f} {route}: review rate')
                numerical(sub.get('accuracy_gain'), gain, f'{role} {d,c,f} {route}: accuracy gain')
                if threshold is None:
                    require(sub.get('break_even_review_cost_over_error_loss') is None,
                            f'{role} {d,c,f} {route}: zero-review threshold')
                else:
                    numerical(sub.get('break_even_review_cost_over_error_loss'), threshold,
                              f'{role} {d,c,f} {route}: break-even')
                require(sub.get('profitable_for_positive_review_cost_possible') is (gain > 0),
                        f'{role} {d,c,f} {route}: feasibility')
                numerical(original[source_field], (cp+cf)/n+gain if route != 'strong_all_review' else 1+gain,
                          f'{role} {d,c,f} {route}: Stage 1 agreement')
                checks += 1
    return {'routes_checked':len(EXPECTED), 'human_profiles_checked':72,
            'strategy_profile_calculations_checked':checks,
            'status':'PASS'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage1-report', type=Path, required=True)
    parser.add_argument('--stage2a-report', type=Path, required=True)
    args = parser.parse_args()
    with args.stage1_report.open(encoding='utf-8') as f:
        s1=json.load(f)
    with args.stage2a_report.open(encoding='utf-8') as f:
        s2=json.load(f)
    outcome=check(s1,s2)
    print('E3 Stage 2a independent verification:', outcome['status'])
    print('Reviewer profiles:',outcome['human_profiles_checked'])
    print('Strategy/profile calculations:',outcome['strategy_profile_calculations_checked'])
    print('Limits: verifies algebra and frozen aggregate counts; not real human costs, losses, or deployment fitness.')


if __name__ == '__main__':
    main()
