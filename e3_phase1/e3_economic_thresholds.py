"""E3 Stage 2a: offline, correctness-only economic break-even analysis.

Inputs are E3 Stage 1 analytical report and audited E2 confusion counts embedded
as a frozen reference (NOT estimated reviewer performance or financial costs).
Outputs are normalized ratios, not monetary estimates or deployment guidance.
No API calls or source file modifications; output is created exclusively.
"""
import argparse
import json
import math
from pathlib import Path

# Frozen E2 observed-validator replay counts; each role has 810 slots.
# Column meanings: AI correct PASS, AI wrong PASS, AI wrong FAIL, AI correct FAIL.
FROZEN_COUNTS = {
    "cheap_validator": dict(correct_pass=702, wrong_pass=25, wrong_fail=77, correct_fail=6),
    "strong_validator": dict(correct_pass=708, wrong_pass=0, wrong_fail=102, correct_fail=0),
}
N = 810
PROFILES = {(d, c, f) for d in (.25, .5, .75, 1.)
            for c in (.5, .75, 1.) for f in (0., .05, .15)}


def close(actual, expected, label):
    if not isinstance(actual, (int, float)) or isinstance(actual, bool) or not math.isfinite(actual):
        raise ValueError(f"{label}: invalid numeric value {actual!r}")
    if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10):
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def review_analysis(correct_reviewed, wrong_reviewed, n, d, c, f):
    """Normalized per-reviewed-case cost threshold H/L for positive net value.

    L = assumed equal loss of any wrong result; H = added cost of one review.
    Accuracy gain is (wrong_reviewed*D*C - correct_reviewed*F) / n.
    Incremental net expected benefit per original slot divided by L is
       accuracy_gain - review_rate * (H/L).
    Break-even H/L is correction gain per REVIEWED case; it can be negative.
    """
    reviewed = correct_reviewed + wrong_reviewed
    if not (0 <= correct_reviewed <= n and 0 <= wrong_reviewed <= n
            and reviewed <= n and all(0 <= x <= 1 for x in (d, c, f))):
        raise ValueError('invalid counts or probability')
    gain = (wrong_reviewed * d * c - correct_reviewed * f) / n
    return dict(review_count=reviewed, review_rate=reviewed / n,
                accuracy_gain=gain,
                break_even_review_cost_over_error_loss=(gain*n/reviewed if reviewed else None),
                profitable_for_positive_review_cost_possible=(gain > 0))


def analyze(stage1):
    if stage1.get('status') != 'ANALYTICAL_SIMULATION_ONLY' or stage1.get('source_observations') != 270 or stage1.get('reviewer_profiles') != 36 or stage1.get('validator_reps_per_source_role') != 3:
        raise ValueError('Unexpected Stage 1 report header; refuse to analyze')
    if set(stage1.get('routes', {})) != set(FROZEN_COUNTS):
        raise ValueError('Missing or unexpected Stage 1 validator roles')
    result = dict(status='ECONOMIC_SENSITIVITY_ONLY', unit='dimensionless H/L',
                  assumed_error_loss='same for each incorrect final result; L > 0',
                  human_review_cost='H paid once per routed review, independent of result',
                  interpretation='positive net incremental value iff H/L < break_even_review_cost_over_error_loss; equality means break-even',
                  validator_routes={})
    for role, counts in FROZEN_COUNTS.items():
        section = stage1['routes'][role]
        if section.get('slots') != N:
            raise ValueError(f'{role}: unexpected slot count')
        correct_total = counts['correct_pass'] + counts['correct_fail']
        wrong_total = counts['wrong_pass'] + counts['wrong_fail']
        fail = counts['correct_fail'] + counts['wrong_fail']
        close(section.get('observed_weak_accuracy'), correct_total / N, f'{role} weak accuracy')
        close(section.get('observed_strong_accuracy'), 1, f'{role} strong accuracy')
        close(section.get('validator_fail_count'), fail, f'{role} fail count')
        close(section.get('reconstructed_weak_validator_strong_accuracy'),
              (counts['correct_pass'] + fail)/N, f'{role} reconstructed cascade')
        profiles = section.get('human_review_profiles')
        if not isinstance(profiles, list) or len(profiles) != len(PROFILES):
            raise ValueError(f'{role}: incomplete reviewer profile grid')
        seen = set()
        values = []
        for row in profiles:
            d, c, f = (row[k] for k in ('D', 'C', 'F'))
            key = (d, c, f)
            if key not in PROFILES or key in seen:
                raise ValueError(f'{role}: duplicate/unexpected profile {key}')
            seen.add(key)
            all_weak = review_analysis(correct_total, wrong_total, N, d, c, f)
            all_strong = review_analysis(N, 0, N, d, c, f)
            flagged = review_analysis(counts['correct_fail'], counts['wrong_fail'], N, d, c, f)
            close(row.get('weak_to_human'), correct_total/N + all_weak['accuracy_gain'], f'{role} {key} weak human')
            close(row.get('strong_to_human'), 1 + all_strong['accuracy_gain'], f'{role} {key} strong human')
            close(row.get('weak_validator_to_human_on_fail'),
                  correct_total/N + flagged['accuracy_gain'], f'{role} {key} validator human')
            values.append(dict(D=d, C=c, F=f,
                               weak_all_review=all_weak,
                               strong_all_review=all_strong,
                               validator_fail_only_review=flagged))
        result['validator_routes'][role] = dict(observed_validator_confusion=counts,
                                               source_slots=N, profiles=values)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage1-report', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    with a.stage1_report.open(encoding='utf-8') as f:
        stage1 = json.load(f)
    output = analyze(stage1)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    with a.report.open('x', encoding='utf-8') as f:
        json.dump(output, f, indent=2, allow_nan=False)
        f.write('\n')
    print('Status:', output['status'])
    for role, data in output['validator_routes'].items():
        print(role, 'slots=', data['source_slots'], 'profiles=', len(data['profiles']),
              'reviewed-on-FAIL=', data['observed_validator_confusion']['correct_fail'] + data['observed_validator_confusion']['wrong_fail'])
    print('Report:', a.report)


if __name__ == '__main__':
    main()
