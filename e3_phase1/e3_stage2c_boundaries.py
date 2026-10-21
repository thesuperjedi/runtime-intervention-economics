"""E3 Stage 2c: offline economic decision-boundary sensitivity analysis.

Reads a verified Stage 2b report. Does not call models, modify frozen records,
or claim empirical human competence. Output is exclusive-create.
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROLES = ('cheap_validator', 'strong_validator')
AUTO_ROUTES = ('weak_only', 'strong_only', 'weak_validator_strong_on_fail')
HUMAN_ROUTES = ('weak_human_all', 'weak_validator_human_on_fail')
ROUTES = AUTO_ROUTES + HUMAN_ROUTES
TIE_ABS_USD = 1e-12
EXPECTED_PROFILES = frozenset((d, c, f)
                              for d in (.25, .5, .75, 1.0)
                              for c in (.5, .75, 1.0)
                              for f in (0.0, .05, .15))
DEFAULT_LOSSES = (0, .001, .005, .008, .01, .02, .05, .10, .50, 1.0)
DEFAULT_REVIEWS = (0, .0001, .0005, .001, .002, .005, .01, .02)


def nonnegative(x, label):
    if type(x) not in (int, float) or not math.isfinite(x) or x < 0:
        raise ValueError(f'{label} must be finite and nonnegative')
    return float(x)


def validate_profiles(profiles):
    """Require exactly the prescribed 36 numeric D/C/F combinations."""
    if not isinstance(profiles, list) or len(profiles) != len(EXPECTED_PROFILES):
        raise ValueError('expected exactly 36 reviewer profiles')
    seen = set()
    for profile in profiles:
        if not isinstance(profile, dict) or any(k not in profile for k in ('D', 'C', 'F')):
            raise ValueError('profile must contain D, C and F')
        key = tuple(profile[k] for k in ('D', 'C', 'F'))
        for value in key:
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError('profile values must be finite numbers in [0, 1]')
        if key not in EXPECTED_PROFILES:
            raise ValueError('profile outside prescribed D/C/F grid')
        if key in seen:
            raise ValueError('duplicate profile')
        seen.add(key)
    if seen != EXPECTED_PROFILES:
        raise ValueError('incomplete reviewer profile grid')


def route_winner(costs, tolerance=TIE_ABS_USD):
    """Prefer route order among candidates within tolerance of the global minimum."""
    if set(costs) != set(ROUTES):
        raise ValueError('expected exactly five routes')
    minimum = min(costs[route] for route in ROUTES)
    return next(route for route in ROUTES if costs[route] <= minimum + tolerance)


def automated_winner(costs):
    minimum = min(costs[route] for route in AUTO_ROUTES)
    return next(route for route in AUTO_ROUTES
                if costs[route] <= minimum + TIE_ABS_USD)


def make_coefficients(role_report, profile):
    baseline = role_report['automated_baselines']
    human = profile['comparison']
    if set(baseline) != set(AUTO_ROUTES) or set(human) != set(HUMAN_ROUTES):
        raise ValueError('unrecognized route population')
    coeff = {}
    for route in ROUTES:
        datum = baseline[route] if route in baseline else human[route]
        accuracy = nonnegative(datum['accuracy'], 'accuracy')
        review_rate = nonnegative(datum['review_rate'], 'review_rate')
        api = nonnegative(datum['api_cost_usd_per_slot'], 'API cost')
        if accuracy > 1 or review_rate > 1:
            raise ValueError('accuracy or review rate exceeds one')
        if route in AUTO_ROUTES and review_rate != 0:
            raise ValueError('automated route has human reviews')
        if route == 'weak_human_all' and review_rate != 1:
            raise ValueError('all-review route not fully routed')
        coeff[route] = {'api': api, 'errors': 1 - accuracy, 'review_rate': review_rate}
    return coeff


def costs_at(coeff, loss, human_cost):
    return {route: v['api'] + loss * v['errors'] + human_cost * v['review_rate']
            for route, v in coeff.items()}


def verify_original(role_report, profile, coeff, loss, human_cost):
    values = costs_at(coeff, loss, human_cost)
    for route in AUTO_ROUTES:
        expected = role_report['automated_baselines'][route]['total_expected_usd_per_slot']
        if not math.isclose(values[route], expected, abs_tol=1e-11, rel_tol=1e-10):
            raise ValueError(f'{route}: baseline does not reproduce Stage 2b')
    for route in HUMAN_ROUTES:
        expected = profile['comparison'][route]['total_expected_usd_per_slot']
        if not math.isclose(values[route], expected, abs_tol=1e-11, rel_tol=1e-10):
            raise ValueError(f'{route}: human outcome does not reproduce Stage 2b')
    original_best = role_report['best_automated_at_assumptions']
    if original_best != automated_winner(values):
        raise ValueError('automated winner does not reproduce original report')
    saved_winner = profile['minimum_expected_cost_route_at_assumptions']
    if values[saved_winner] > min(values.values()) + TIE_ABS_USD:
        raise ValueError('saved Stage 2b minimum not mathematically minimal')
    for route in HUMAN_ROUTES:
        datum = profile['comparison'][route]
        threshold = (values[original_best] - (coeff[route]['api'] + loss * coeff[route]['errors'])) / coeff[route]['review_rate']
        if not math.isclose(threshold, datum['break_even_review_usd_vs_best_automated'], abs_tol=1e-11, rel_tol=1e-10):
            raise ValueError('break-even threshold mismatch')


def pairwise_lines(coeff):
    """For each pair: (b_i-b_j)*L + (r_i-r_j)*H = a_j-a_i."""
    lines = []
    for i, left in enumerate(ROUTES):
        for right in ROUTES[i+1:]:
            a, b = coeff[left], coeff[right]
            lines.append({'left': left, 'right': right,
                          'loss_coefficient': a['errors']-b['errors'],
                          'review_cost_coefficient': a['review_rate']-b['review_rate'],
                          'right_hand_side_usd': b['api']-a['api']})
    return lines


def analyze(stage2b, losses=DEFAULT_LOSSES, reviews=DEFAULT_REVIEWS):
    if stage2b.get('status') != 'STAGE2B_CONDITIONAL_ONLY' or set(stage2b.get('routes',{})) != set(ROLES):
        raise ValueError('unexpected Stage 2b input structure')
    losses = [nonnegative(x, 'loss grid') for x in losses]
    reviews = [nonnegative(x, 'review-cost grid') for x in reviews]
    if not losses or not reviews or len(set(losses)) != len(losses) or len(set(reviews)) != len(reviews):
        raise ValueError('grid must contain distinct values')
    if len(losses)*len(reviews) > 10000:
        raise ValueError('grid too large')
    original_l = nonnegative(stage2b['assumptions']['error_loss_usd_per_incorrect_result'], 'original L')
    original_h = nonnegative(stage2b['assumptions']['human_review_usd_per_routed_case'], 'original H')
    output = {'status':'STAGE2C_CONDITIONAL_SENSITIVITY_ONLY', 'currency':'USD',
              'grid':{'error_loss_usd':losses,'human_review_cost_usd':reviews,
                      'tolerance_usd_per_slot':TIE_ABS_USD,
                      'tie_policy':'Treat differences <= absolute tolerance as ties; prefer automated routes and fixed route order.'},
              'reference':{'stage2b_error_loss_usd':original_l,'stage2b_human_review_cost_usd':original_h},
              'routes':{}, 'limits':[
                'All results conditional on hypothetical L, H and reviewer D/C/F; no human observations.',
                'Uses saved Stage 2b mean API cost and accuracy; does not reprocess E1/E2 records.',
                'Frozen sample strong-model accuracy was 100%, not a deployment guarantee.',
                '810 slots per validator role contain correlated repeated E1 solver outputs from 30 canonical cases.',
                'Cost estimates use frozen USD token-price convention, not invoice-verified per-call charges.',
                'Only five enumerated routes; no unequal error harms, delays or governance approvals.',
                'Pairwise equality lines are candidate boundaries, not necessarily globally winning frontiers.',
                'Grid illustrates choices at sampled assumptions, not continuous-domain exhaustive dominance.',
                'Stage 2b trust and preflight prerequisites apply; its input report is not self-authenticating.'
              ]}
    for role in ROLES:
        item = stage2b['routes'][role]
        if item.get('source_slots') != 810:
            raise ValueError('unexpected Stage 2b coverage')
        validate_profiles(item.get('profiles'))
        outprofiles=[]; global_counts=Counter()
        for p in item['profiles']:
            d,c,f = p['D'],p['C'],p['F']
            coeff=make_coefficients(item,p)
            verify_original(item,p,coeff,original_l,original_h)
            wins=Counter(); winners=[]; human_win_cells=[]
            for loss in losses:
                line=[]
                for human_cost in reviews:
                    values=costs_at(coeff,loss,human_cost)
                    chosen=route_winner(values)
                    wins[chosen]+=1; global_counts[chosen]+=1
                    line.append(chosen)
                    if chosen in HUMAN_ROUTES: human_win_cells.append([loss,human_cost,chosen])
                winners.append(line)
            outprofiles.append({'D':d,'C':c,'F':f,'route_coefficients':coeff,
                                'winner_counts_on_grid':dict(wins),
                                'any_human_win_on_grid':bool(human_win_cells),
                                'human_win_cells':human_win_cells,
                                'winner_grid':winners,
                                'pairwise_indifference_lines':pairwise_lines(coeff)})
        output['routes'][role]={'profiles':outprofiles, 'winner_counts_all_profile_grid_cells':dict(global_counts)}
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage2b-report', type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    a=parser.parse_args()
    content=a.stage2b_report.read_bytes()
    result=analyze(json.loads(content))
    result['inputs']={'stage2b_report_sha256':hashlib.sha256(content).hexdigest()}
    a.report.parent.mkdir(parents=True,exist_ok=True)
    with a.report.open('x',encoding='utf-8') as out:
        json.dump(result,out,indent=2,allow_nan=False)
        out.write('\n')
    print('Status:',result['status'])
    print('Grid:',len(result['grid']['error_loss_usd']),'loss values x',len(result['grid']['human_review_cost_usd']),'review costs')
    for role, x in result['routes'].items():
        print(role,'profiles=',len(x['profiles']), 'winning grid cells=',x['winner_counts_all_profile_grid_cells'])
    print('Report:',a.report)

if __name__=='__main__':
    main()
