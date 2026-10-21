"""Offline E3 strong-solver robustness. Hypothetical probabilities, never new observations.

All original inputs are read-only. Uses the historical scorer, Audit 03 gate,
Stage 2b price/join logic, and corrected Stage 2c route-order tolerance.
New JSON and Markdown outputs are exclusive-create. No model SDK or network.
"""
import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from e3_accuracy_replay import build_rows, load, summarize, verify_frozen_audit
from e3_stage2b_compare import analyze as analyze_baseline, read_costed_slots
from e3_stage2c_boundaries import (
    AUTO_ROUTES, HUMAN_ROUTES, ROLES, ROUTES, TIE_ABS_USD, analyze as analyze_grid,
    make_coefficients, route_winner, validate_profiles,
)

UNIFORM_GRID = (0., .001, .005, .01, .02, .05, .1, .2, .5, 1.)
OVERLAP_GRID = (0., .01, .05, .1, .25, .5, 1.)
CONCENTRATION_GRID = (0., 1/270, .005, .01, .02, 1/30, .05, .1, .2, .5, 1.)


def probability(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('probability must be a finite number in [0,1]')
    return float(value)


def source_table(weak, slots):
    """One row per solver pair; validator repetitions are exposures, not new solvers."""
    table = []
    if set(slots) != set(ROLES) or not weak:
        raise ValueError('source/role coverage')
    for source, metadata in sorted(weak.items()):
        entry = dict(source=source, case=metadata['case'], rendering=metadata['rendering'],
                     weak_correct=metadata['correct'], fail_fraction={})
        common = None
        for role in ROLES:
            rows = [s for s in slots[role] if s['source'] == source]
            if len(rows) != 3 or {s['rep'] for s in rows} != {1, 2, 3}:
                raise ValueError('expected exactly three validator repetitions')
            if any(s['weak_correct'] != entry['weak_correct'] or s['strong_correct'] is not True
                   or s['verdict'] not in ('PASS', 'FAIL') for s in rows):
                raise ValueError('source correctness/verdict inconsistent')
            pair = {(s['weak_cost'], s['strong_cost']) for s in rows}
            if len(pair) != 1 or (common is not None and pair != common):
                raise ValueError('inconsistent frozen pair costs')
            common = pair
            entry['fail_fraction'][role] = sum(s['verdict'] == 'FAIL' for s in rows)/3
        table.append(entry)
    for role in ROLES:
        if len(slots[role]) != len(table)*3 or {s['source'] for s in slots[role]} != set(weak):
            raise ValueError('extra/missing validator sources')
    return table


def exposures(table, q):
    if set(q) != {s['source'] for s in table}:
        raise ValueError('hypothetical probabilities must cover exact source population')
    q = {src: probability(v) for src, v in q.items()}
    n = len(table)
    return dict(strong_error=sum(q.values())/n,
                escalation_error={role: sum(s['fail_fraction'][role]*q[s['source']]
                                           for s in table)/n for role in ROLES})


def rank(costs, routes=ROUTES):
    """All margins are relative to the mathematical minimum, not selected route."""
    minimum = min(costs[r] for r in routes)
    eligible = [r for r in routes if costs[r] <= minimum + TIE_ABS_USD]
    ordered = sorted(costs[r] for r in routes)
    return dict(winner=eligible[0], within_tolerance=eligible, minimum_usd_per_slot=minimum,
                excess_usd_by_route={r: costs[r]-minimum for r in routes},
                runner_up_gap_usd=ordered[1]-ordered[0])


def planes(reference, profile, table):
    """J = intercept + wrong_slope*u + correct_slope*v at original L,H."""
    role, p = profile
    item = reference['routes'][role]
    coeff = make_coefficients(item, p)
    loss = reference['assumptions']['error_loss_usd_per_incorrect_result']
    human = reference['assumptions']['human_review_usd_per_routed_case']
    n = len(table)
    wrong = sum(not s['weak_correct'] for s in table)/n
    fw = sum(s['fail_fraction'][role] for s in table if not s['weak_correct'])/n
    fc = sum(s['fail_fraction'][role] for s in table if s['weak_correct'])/n
    result = {}
    for r, v in coeff.items():
        b, c = (loss*wrong, loss*(1-wrong)) if r == 'strong_only' else (
            (loss*fw, loss*fc) if r == 'weak_validator_strong_on_fail' else (0., 0.))
        result[r] = [v['api']+loss*v['errors']+human*v['review_rate'], b, c]
    return result


def evaluate(reference, table, q):
    e = exposures(table, q)
    loss = reference['assumptions']['error_loss_usd_per_incorrect_result']
    human = reference['assumptions']['human_review_usd_per_routed_case']
    out = {'hypothetical_exposure': e, 'roles': {}}
    for role in ROLES:
        item = reference['routes'][role]
        results = []
        for p in item['profiles']:
            coeff = make_coefficients(item, p)
            costs, errors = {}, {}
            for r, v in coeff.items():
                extra = e['strong_error'] if r == 'strong_only' else (
                    e['escalation_error'][role] if r == 'weak_validator_strong_on_fail' else 0.)
                errors[r] = v['errors'] + extra
                costs[r] = v['api'] + loss*errors[r] + human*v['review_rate']
            results.append(dict(D=p['D'], C=p['C'], F=p['F'],
                                expected_error_by_route=errors, ranking=rank(costs),
                                automated_ranking=rank(costs, AUTO_ROUTES)))
        out['roles'][role] = results
    return out


def line_values(lines, x):
    return {r: a+b*x for r, (a, b) in lines.items()}


def envelope_1d(lines, lo=0., hi=1., routes=ROUTES):
    """Partition at equalities AND tolerance offsets; keep only active boundaries.

    Intervals are open at their endpoints. Boundary points get their own ranks.
    Equality events below are restricted to the actual mathematical lower envelope.
    """
    roots = {lo, hi}
    equalities = set()
    for i, r in enumerate(routes):
        for s in routes[i+1:]:
            a, b = lines[r][0]-lines[s][0], lines[r][1]-lines[s][1]
            if b == 0:
                continue
            for offset in (-TIE_ABS_USD, 0., TIE_ABS_USD):
                x = (offset-a)/b
                if lo < x < hi:
                    roots.add(x)
                    if offset == 0:
                        equalities.add(x)
    points = sorted(roots)
    intervals = []
    for left, right in zip(points, points[1:]):
        if right <= left:
            continue
        ranking = rank(line_values(lines, (left+right)/2), routes)
        sig = (ranking['winner'], ranking['within_tolerance'])
        if intervals and (intervals[-1]['winner'], intervals[-1]['within_tolerance']) == sig:
            intervals[-1]['to'] = right
        else:
            intervals.append(dict(start=left, to=right, winner=sig[0], within_tolerance=sig[1]))
    boundaries = []
    for x in sorted(equalities):
        vals = line_values(lines, x)
        minimum = min(vals[r] for r in routes)
        # Only numerical round-off allowance here, not the economic tie tolerance.
        tied = [r for r in routes if abs(vals[r]-minimum) <= 1e-15]
        if len(tied) >= 2:
            boundaries.append(dict(error_rate=x, mathematical_minimizers=tied, ranking=rank(vals, routes)))
    transitions = []
    for a, b in zip(intervals, intervals[1:]):
        if a['winner'] != b['winner']:
            x = b['start']
            transitions.append(dict(error_rate=x, before=a['winner'], after=b['winner'],
                                    ranking_at_boundary=rank(line_values(lines, x), routes)))
    return dict(intervals=intervals, lowest_cost_equalities=boundaries,
                priority_transitions=transitions,
                endpoints=[dict(error_rate=x, ranking=rank(line_values(lines, x), routes)) for x in (lo, hi)])


def clip_polygon(poly, a, b, c):
    """Keep a*x+b*y+c <= 0, with no decision-tolerance shift."""
    if not poly:
        return []
    output = []
    for p, q in zip(poly, poly[1:]+poly[:1]):
        vp, vq = a*p[0]+b*p[1]+c, a*q[0]+b*q[1]+c
        if vp <= 0:
            output.append(p)
        if (vp < 0 < vq) or (vq < 0 < vp):
            t = vp/(vp-vq)
            output.append([p[0]+t*(q[0]-p[0]), p[1]+t*(q[1]-p[1])])
    return output


def lower_regions(affine):
    """Actual mathematical lowest-cost polygons and active equality segments.

    Regions may share exact-tie boundaries. rank() specifies the existing
    tolerance policy; polygons intentionally describe unshifted cost minima.
    """
    cells = {}
    for r, (a, b, c) in affine.items():
        poly = [[0., 0.], [1., 0.], [1., 1.], [0., 1.]]
        for s, (aa, bb, cc) in affine.items():
            if s != r:
                poly = clip_polygon(poly, b-bb, c-cc, a-aa)
        if poly:
            cells[r] = poly
    boundaries = []
    for i, r in enumerate(ROUTES):
        for s in ROUTES[i+1:]:
            a, b, c = (x-y for x, y in zip(affine[r], affine[s]))
            if b == c == 0:
                if a == 0 and r in cells and s in cells:
                    boundaries.append(dict(routes=[r, s], coincident_minimum_region=cells[r]))
                continue
            points = []
            if c != 0:
                for x in (0., 1.):
                    y = -(a+b*x)/c
                    if 0 <= y <= 1: points.append([x, y])
            if b != 0:
                for y in (0., 1.):
                    x = -(a+c*y)/b
                    if 0 <= x <= 1: points.append([x, y])
            points = sorted({tuple(p) for p in points})
            if not points: continue
            p, q = points[0], points[-1]
            tlo, thi = 0., 1.
            for other in ROUTES:
                ar, br, cr = affine[r]
                ao, bo, co = affine[other]
                v = ar-ao+(br-bo)*p[0]+(cr-co)*p[1]
                slope = (br-bo)*(q[0]-p[0])+(cr-co)*(q[1]-p[1])
                if slope == 0:
                    if v > 1e-15: thi = -1.
                elif slope > 0: thi = min(thi, -v/slope)
                else: tlo = max(tlo, -v/slope)
            if tlo <= thi and 0 <= thi and tlo <= 1:
                ends = [[p[0]+t*(q[0]-p[0]), p[1]+t*(q[1]-p[1])]
                        for t in (max(0., tlo), min(1., thi))]
                boundaries.append(dict(routes=[r, s], segment=ends,
                                       equation=dict(constant=a, wrong=b, correct=c)))
    return dict(mathematical_minimum_regions=cells, active_lowest_cost_boundaries=boundaries,
                tolerance_note='Exact lower-envelope geometry; tolerance-based ranks are separate.')


def ordered_groups(table, target_role, unit, direction):
    if unit not in ('source', 'canonical_case') or direction not in ('inside_first', 'outside_first'):
        raise ValueError('unknown concentration specification')
    grouped = defaultdict(list)
    for s in table:
        grouped[s['source'] if unit == 'source' else s['case']].append(s)
    groups = [dict(id=k, sources=[s['source'] for s in values], size=len(values),
                   fail_fraction={r: sum(s['fail_fraction'][r] for s in values)/len(values) for r in ROLES})
              for k, values in grouped.items()]
    sign = -1 if direction == 'inside_first' else 1
    return sorted(groups, key=lambda g: (sign*g['fail_fraction'][target_role], g['id']))


def allocation(table, groups, rate):
    """Fill groups at q=1, then at most one group at a common fractional q."""
    rate = probability(rate)
    q = {s['source']: 0. for s in table}
    remaining = rate*len(table)
    for g in groups:
        fraction = min(1., max(0., remaining/g['size']))
        for source in g['sources']:
            q[source] = fraction
        remaining = max(0., remaining-g['size'])
    return q


def concentration_segments(table, groups):
    n = len(table)
    count = 0
    t = dict.fromkeys(ROLES, 0.)
    segments = []
    for g in groups:
        lo, hi = count/n, (count+g['size'])/n
        if segments and segments[-1]['exposure_slope'] == g['fail_fraction']:
            segments[-1]['to'] = hi
        else:
            segments.append(dict(start=lo, to=hi, exposure_at_start=dict(t),
                                 exposure_slope=g['fail_fraction']))
        for r in ROLES:
            t[r] += g['size']/n*g['fail_fraction'][r]
        count += g['size']
    return segments


def path_envelope(reference, table, role, profile, segments, routes=ROUTES):
    base = planes(reference, (role, profile), table)
    loss = reference['assumptions']['error_loss_usd_per_incorrect_result']
    records = []
    for seg in segments:
        lo = seg['start']
        slope = seg['exposure_slope'][role]
        t0 = seg['exposure_at_start'][role]
        lines = {r: [a, 0.] for r, (a, _, _) in base.items()}
        lines['strong_only'][1] = loss
        lines['weak_validator_strong_on_fail'] = [
            base['weak_validator_strong_on_fail'][0]+loss*(t0-slope*lo), loss*slope]
        records.append(envelope_1d(lines, lo, seg['to'], routes))
    intervals, equalities, transitions = [], [], []
    previous = None
    for record in records:
        for v in record['intervals']:
            if previous is not None and previous['winner'] != v['winner']:
                if previous['to'] == v['start']:
                    transitions.append(dict(error_rate=v['start'], before=previous['winner'], after=v['winner']))
            if intervals and intervals[-1]['winner'] == v['winner'] and intervals[-1]['within_tolerance'] == v['within_tolerance']:
                intervals[-1]['to'] = v['to']
            else: intervals.append(dict(v))
            previous = v
        equalities.extend(record['lowest_cost_equalities'])
    # Junctions are separately evaluated, including crossings exactly at case boundaries.
    junctions = []
    groups_rates = sorted({s['start'] for s in segments} | {1.})
    for rate in groups_rates:
        seg = next((s for s in segments if s['start'] <= rate <= s['to']), segments[-1])
        t = seg['exposure_at_start'][role]+seg['exposure_slope'][role]*(rate-seg['start'])
        costs = {r: v[0] for r, v in base.items()}
        costs['strong_only'] += loss*rate
        costs['weak_validator_strong_on_fail'] += loss*t
        junctions.append(dict(error_rate=rate, ranking=rank(costs, routes)))
    return dict(intervals=intervals, priority_transitions=transitions,
                lowest_cost_equalities=equalities, concentration_junctions=junctions)


def profile_id(p):
    return dict(D=p['D'], C=p['C'], F=p['F'])


def analyze(reference, table):
    if len(table) != 270 or sum(not s['weak_correct'] for s in table) != 34:
        raise ValueError('expected frozen 270 sources / 34 weak errors')
    if Counter(Counter(s['case'] for s in table).values()) != {9: 30}:
        raise ValueError('expected 30 canonical cases with nine sources each')
    for role in ROLES:
        validate_profiles(reference['routes'][role]['profiles'])
    out = dict(uniform={}, overlap={}, concentration=[])
    for role in ROLES:
        un, ov = [], []
        for p in reference['routes'][role]['profiles']:
            affine = planes(reference, (role, p), table)
            lines = {r: [a, b+c] for r, (a, b, c) in affine.items()}
            un.append(dict(**profile_id(p), cost_lines=lines, all_routes=envelope_1d(lines),
                           automated=envelope_1d(lines, routes=AUTO_ROUTES)))
            ov.append(dict(**profile_id(p), cost_planes=affine, **lower_regions(affine)))
        out['uniform'][role] = un
        out['overlap'][role] = ov
    out['uniform']['sampled_rates'] = [
        dict(error_rate=q, result=evaluate(reference, table, dict.fromkeys((s['source'] for s in table), q)))
        for q in UNIFORM_GRID]
    out['overlap']['sampled_rates'] = [
        dict(weak_wrong_error=u, weak_correct_error=v,
             result=evaluate(reference, table, {s['source']: v if s['weak_correct'] else u for s in table}))
        for u in OVERLAP_GRID for v in OVERLAP_GRID]
    for unit in ('source', 'canonical_case'):
        for target in ROLES:
            for direction in ('inside_first', 'outside_first'):
                groups = ordered_groups(table, target, unit, direction)
                segments = concentration_segments(table, groups)
                path = dict(unit=unit, target_role=target, direction=direction,
                            allocation_order=groups, roles={})
                for role in ROLES:
                    path['roles'][role] = [
                        dict(**profile_id(p), all_routes=path_envelope(reference, table, role, p, segments),
                             automated=path_envelope(reference, table, role, p, segments, AUTO_ROUTES))
                        for p in reference['routes'][role]['profiles']]
                rates = sorted(set(CONCENTRATION_GRID) | (
                    {k/30 for k in range(31)} if unit == 'canonical_case' else set()))
                path['samples'] = [
                    dict(error_rate=q,
                         whole_case_binary_allocation=(unit == 'canonical_case' and abs(q*30-round(q*30)) < 1e-12),
                         fractional_probability_group=next((g['id'] for g in groups
                             if sum(h['size'] for h in groups[:groups.index(g)])+1e-10 < q*len(table)
                             < sum(h['size'] for h in groups[:groups.index(g)+1])-1e-10), None),
                         result=evaluate(reference, table, allocation(table, groups, q)))
                    for q in rates]
                out['concentration'].append(path)
    return out


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def markdown(result):
    lines = ['# E3 hypothetical strong-solver robustness 01', '',
             'Status: analytical sensitivity only. No new model or human observations.',
             'L = US$0.10 per wrong result; H = US$0.01 per human review.',
             'Costs are frozen token-derived USD estimates, not invoice-verified charges.', '',
             '## Baseline verification', '',
             'Audit 03 SHA inventory, historical Stage 1 replay, complete Stage 2b JSON and Stage 2c JSON reproduced.',
             'At q=0 all original results remain unchanged.', '',
             '## Uniform strong errors: automated lower-envelope transitions', '']
    for role in ROLES:
        p = result['analyses']['uniform'][role][0]
        lines.append(f"- {role}:")
        for t in p['automated']['priority_transitions']:
            lines.append(f"  - q = {t['error_rate']:.12g}: {t['before']} -> {t['after']}.")
    lines += ['', '## First all-route departure from strong-only under uniform errors', '']
    for role in ROLES:
        groups = defaultdict(list)
        for p in result['analyses']['uniform'][role]:
            trans = p['all_routes']['priority_transitions']
            first = next((t for t in trans if t['before'] == 'strong_only'), None)
            if first: groups[first['after']].append(first['error_rate'])
        for winner, rates in groups.items():
            lines.append(f"- {role}: {winner}, {len(rates)} profiles, q from {min(rates):.12g} to {max(rates):.12g}.")
    lines += ['', '## Concentration: automated first departure from strong-only', '']
    for path in result['analyses']['concentration']:
        p = path['roles'][path['target_role']][0]
        first = next((t for t in p['automated']['priority_transitions'] if t['before'] == 'strong_only'), None)
        text = 'none on [0,1]' if first is None else f"q={first['error_rate']:.12g}, to {first['after']}"
        lines.append(f"- {path['unit']}, {path['target_role']}, {path['direction']}: {text}.")
    lines += ['', '## Interpretation and limits', '',
              'The frozen findings do not change. Hypothetical strong errors can change route rankings; their placement matters.',
              'Whole-case integer allocations are distinct from fractional case-probability paths.',
              'Inside/outside paths optimize exposure for one target role at a time; every allocation is evaluated under BOTH roles.',
              'They are bounds for the stated source or equal-within-case probability constraints, not frequencies or confidence intervals.',
              'Costs, weak correctness and validator verdicts remain fixed. Strong solver and strong validator performance are not equated.',
              'Repeated slots are correlated: 30 canonical cases, 90 renderings, 270 source pairs, 810 slots per role.',
              'Actual lowest-cost regions use unshifted equations; reported ranks apply the unchanged absolute tolerance and route order.',
              'No operational generalization or actual future strong error rate is inferred.',
              'New canonical-case experiments are justified to measure conditional strong errors if decisions depend on these reversal regions;',
              'more repetitions of the existing perfect sample cannot identify failure modes outside that sample.',
              'Human competence, asymmetric losses and costs of genuinely different strong outputs require separate evidence.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in (
        ('e1-dir', 'data/raw/e1'), ('e2-dir', 'data/raw/e2_full'),
        ('audit-report', 'e3_phase1/e3_replay_audit_03.json'),
        ('stage1-report', 'e3_phase1/e3_accuracy_stage1_01.json'),
        ('stage2b-report', 'e3_phase1/e3_stage2b_conditional_01.json'),
        ('stage2c-report', 'e3_phase1/e3_stage2c_boundaries_01.json')):
        parser.add_argument('--'+name, type=Path, default=Path(default))
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    args = parser.parse_args()
    if args.report.resolve() == args.summary.resolve() or args.report.exists() or args.summary.exists():
        parser.error('outputs must be distinct new files; existing evidence is never overwritten')
    # Hash every pre-existing phase-1 JSON report plus imported implementation dependencies.
    protected = list(args.stage2b_report.parent.glob('*.json'))
    protected += list(Path(__file__).resolve().parent.glob('*.py'))
    protected += list(Path('src').glob('e1_*.py'))
    hashes = {str(p): sha(p) for p in protected}
    verify_frozen_audit(args.e1_dir, args.e2_dir, args.audit_report)
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.e1_score import score_run
    weak, strong, verdicts = build_rows(args.e1_dir, args.e2_dir, score_run)
    stage1 = load(args.stage1_report)
    if summarize(weak, strong, verdicts) != stage1:
        raise ValueError('historical Stage 1 does not reproduce exactly')
    slots = read_costed_slots(args.e1_dir, args.e2_dir, weak, strong, verdicts)
    baseline = analyze_baseline(stage1, slots, .1, .01)
    baseline['inputs'] = {'audit_report_sha256': sha(args.audit_report),
                          'stage1_report_sha256': sha(args.stage1_report)}
    reference = load(args.stage2b_report)
    if baseline != reference:
        raise ValueError('complete Stage 2b report does not reproduce exactly')
    grid = analyze_grid(reference)
    grid['inputs'] = {'stage2b_report_sha256': sha(args.stage2b_report)}
    if grid != load(args.stage2c_report):
        raise ValueError('complete Stage 2c report does not reproduce exactly')
    table = source_table(weak, slots)
    result = dict(schema_version='1.0', status='HYPOTHETICAL_STRONG_ERROR_SENSITIVITY_ONLY',
                  currency='USD', provenance={
                      'observed': 'Frozen E1 solver outputs and E2 weak-response validator judgments.',
                      'reconstructed': 'Cascade routes; strong calls are reused E1 observations, not new escalations.',
                      'hypothetical': 'q_i probabilities, their overlap/placement, and D/C/F human expectations.',
                      'cost': 'Frozen E1 normalized input and output+thought USD list-price estimates; not invoices.'},
                  assumptions=reference['assumptions'], pricing_basis=reference['pricing_basis'],
                  denominators=dict(canonical_cases=30, renderings=90, source_pairs=270,
                                    weak_incorrect_sources=34, weak_correct_sources=236,
                                    validator_slots_per_role=810, independent_case_sample=False),
                  tolerance_usd=TIE_ABS_USD, route_order=ROUTES,
                  baseline_verification=dict(audit_sha_inventory=True, stage1_exact=True,
                                             stage2b_complete_json_exact=True, stage2c_complete_json_exact=True),
                  baseline_stage2b=reference, source_exposures=table,
                  equations={
                      'strong_error': 'mean_i(q_i)',
                      'cascade_error': 'observed_false_accept_fraction + mean_i(fail_fraction_iv*q_i)',
                      'expected_cost': 'estimated_api_cost + L*expected_error + H*review_fraction',
                      'q_semantics': 'Marginal hypothetical probability, not a generated or observed wrong answer.',
                      'joint_semantics': 'Same source q under both validator roles and every attached repetition; no independence assumption needed for expectations.',
                      'placement_bounds': 'Greedy fractional allocation by FAIL exposure; whole-case grouping enforces equal q within a canonical case.',
                      'geometry': 'Uniform and concentration paths: exact affine partition including tolerance offsets. Overlap: exact lower-envelope polygons and active equality segments; grid ranks use unchanged tolerance.'},
                  limitations=[
                      'No empirical strong failures; q and strong/weak/routing overlap are unidentified.',
                      'Fixed recorded costs do not estimate tokens for genuinely different strong outputs.',
                      'Validator judgments are on frozen weak answers and are not perturbed.',
                      '30 selected synthetic canonical cases; no independent-270 or independent-810 inference.',
                      'Whole-case continuous paths use fractional marginal probabilities; binary whole-case samples separately identified.',
                      'Placement extremes are optimized per target role, not simultaneously optimal for both roles.',
                      'No new asymmetric loss, delay, human competence measurements or operational validity.'],
                  analyses=analyze(reference, table))
    # No writes until analysis and both historical replay gates have succeeded.
    verify_frozen_audit(args.e1_dir, args.e2_dir, args.audit_report)
    if any(sha(Path(p)) != h for p, h in hashes.items()):
        raise ValueError('protected source/report changed during analysis')
    result['input_sha256'] = hashes
    result['verification'] = dict(protected_files_unchanged=True, protected_file_count=len(hashes),
                                  post_analysis_raw_sha_inventory=True)
    summary = markdown(result)
    encoded = json.dumps(result, indent=2, allow_nan=False)+'\n'
    with args.report.open('x', encoding='utf-8') as stream:
        stream.write(encoded)
    with args.summary.open('x', encoding='utf-8') as stream:
        stream.write(summary)
    print(summary)
    print('JSON:', args.report)
    print('Summary:', args.summary)


if __name__ == '__main__':
    main()
