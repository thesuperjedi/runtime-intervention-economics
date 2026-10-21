"""Offline E3 Stage 1: expected exact-set correctness for supported replay routes.

Uses the EXISTING src.e1_score scorer / frozen procurement oracle, never an
LLM. Routing uses observed validator verdicts only; scorer truth does not route.
Produces an exclusive-create JSON report. No E1/E2 input writes or API calls.

Run from e3_phase1 with project-root parent and intact src.e1_score.
"""
import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from e3_controlset_review import primary_grid, expected_routed_accuracy

E2_ID = re.compile(r'E2F-(E1F-C\d+-L\d+-cheap-R\d+)-(cheap_validator|strong_validator)-R00([123])')


def load(path):
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def file_sha256(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def verify_frozen_audit(e1_dir, e2_dir, audit_report):
    """Bind replay to an independently produced audit-03 raw-input SHA inventory.

    This guards against missing, modified, or extra files. It does not by
    itself validate all internal E2 metadata: runner preflight remains needed.
    """
    audit = load(audit_report)
    counts = audit.get('counts', {})
    required = {
        'e1_cheap': 270, 'e1_strong': 270, 'e1_paired': 270,
        'e1_invalid': 0, 'e1_unexpected_roles': 0,
        'e1_unpaired_cheap': 0, 'e1_unpaired_strong': 0,
        'e2_total': 1620, 'e2_invalid': 0, 'e2_orphan': 0,
        'e2_invalid_identity': 0, 'e2_duplicate_keys': 0,
        'e2_expected_keys': 1620, 'e2_actual_unique_keys': 1620,
        'e2_missing_keys': 0, 'e2_unexpected_keys': 0,
    }
    for field, expected in required.items():
        if type(counts.get(field)) is not int or counts[field] != expected:
            raise ValueError(f'Audit prerequisite failed: {field} != {expected}')
    if audit.get('status') != 'PRELIMINARY_ONLY':
        raise ValueError('Unexpected audit status')
    populations = [('e1', e1_dir, counts['e1_cheap'] + counts['e1_strong']),
                   ('e2', e2_dir, counts['e2_total'])]
    for name, folder, population_count in populations:
        inventory = audit.get('files', {}).get(name, {})
        expected = inventory.get('sha256')
        if (not isinstance(expected, dict)
                or type(inventory.get('count')) is not int
                or len(expected) != inventory['count']):
            raise ValueError(f'Incomplete audit SHA inventory: {name}')
        if len(expected) != population_count:
            raise ValueError(f'Audit SHA inventory cardinality mismatch: {name}; '
                             f'expected {population_count}, got {len(expected)}')
        actual_paths = {p.name: p for p in folder.glob('*.json')}
        if set(actual_paths) != set(expected):
            raise ValueError(f'Frozen {name} file inventory changed: '
                             f'missing={len(set(expected)-set(actual_paths))}, '
                             f'extra={len(set(actual_paths)-set(expected))}')
        for filename, path in actual_paths.items():
            if file_sha256(path) != expected[filename]:
                raise ValueError(f'Frozen {name} file hash mismatch: {filename}')
    return True


def build_rows(e1_dir, e2_dir, score_run):
    """Fail closed: require exact E1 pairing and 3 E2 reps per source/role."""
    e1 = {}
    for path in sorted(e1_dir.glob('*.json')):
        rec = load(path)
        rid = rec.get('run_id')
        if rid != path.stem or rid in e1:
            raise ValueError(f'Invalid or duplicate E1 run ID: {path}')
        score = score_run(path)
        if score['scoring_status'] != 'scored':
            raise ValueError(f'Unscorable E1: {rid}')
        e1[rid] = {'role': rec['model_role'], 'correct': score['exact_match'],
                   'case': score['case_id'], 'rendering': score['rendering_id']}
    weak = {rid: rec for rid, rec in e1.items() if rec['role'] == 'cheap'}
    strong = {rid: rec for rid, rec in e1.items() if rec['role'] == 'strong'}
    if not weak or len(weak) != len(strong) or len(weak) + len(strong) != len(e1):
        raise ValueError('E1 role/cardinality mismatch')
    for rid, rec in weak.items():
        peer = rid.replace('-cheap-', '-strong-', 1)
        if peer == rid or peer not in strong:
            raise ValueError(f'Unpaired E1: {rid}')
        s = strong[peer]
        if (s['case'], s['rendering']) != (rec['case'], rec['rendering']):
            raise ValueError(f'Mismatched E1 pair: {rid}')
    observed = {}
    for path in sorted(e2_dir.glob('*.json')):
        rec = load(path)
        rid = rec.get('run_id')
        match = E2_ID.fullmatch(path.stem)
        if rid != path.stem or match is None:
            raise ValueError(f'Invalid E2 ID: {path}')
        src, role, rep_text = match.groups()
        key = (src, role, int(rep_text))
        if src not in weak or rec.get('source_cheap_run_id') != src or rec.get('validator_role') != role or key in observed:
            raise ValueError(f'Invalid E2 source/role/duplicate: {rid}')
        parsed = rec.get('parsed_response')
        verdict = parsed.get('verdict') if isinstance(parsed, dict) else None
        if rec.get('success') is not True or verdict not in ('PASS', 'FAIL'):
            raise ValueError(f'Invalid E2 verdict: {rid}')
        if rec.get('response_valid') is False:
            raise ValueError(f'Explicitly invalid E2 response: {rid}')
        observed[key] = verdict
    expected = {(src, role, rep) for src in weak for role in ('cheap_validator','strong_validator') for rep in (1,2,3)}
    if set(observed) != expected:
        raise ValueError(f'E2 coverage mismatch: missing {len(expected-set(observed))}, unexpected {len(set(observed)-expected)}')
    return weak, strong, observed


def summarize(weak, strong, verdicts):
    """810 aligned slots per validator role; no fabricated model outcomes."""
    from e3_controlset_review import ReviewerProfile
    output = {'status': 'ANALYTICAL_SIMULATION_ONLY', 'source_observations':len(weak),
              'reviewer_profiles':36, 'validator_reps_per_source_role':3, 'routes':{}}
    for role in ('cheap_validator', 'strong_validator'):
        slots = []
        for source in sorted(weak):
            w = weak[source]['correct']
            s = strong[source.replace('-cheap-', '-strong-', 1)]['correct']
            for rep in (1,2,3):
                verdict = verdicts[(source,role,rep)]
                slots.append((w, s, verdict))
        n = len(slots)
        assert n == len(weak)*3
        # weak->validator->strong (observed validator, reconstructed strong)
        cascade_accuracy = sum((w if v == 'PASS' else s) for w,s,v in slots)/n
        review_inputs = {
            'weak_to_human': [(w, True) for w,s,v in slots],
            'strong_to_human': [(s, True) for w,s,v in slots],
            'weak_validator_to_human_on_fail': [(w, v == 'FAIL') for w,s,v in slots],
        }
        rows = []
        for profile in primary_grid():
            rows.append({'D':profile.D,'C':profile.C,'F':profile.F,
                         **{name:expected_routed_accuracy(items,profile) for name,items in review_inputs.items()}})
        output['routes'][role] = {
            'slots': n,
            'observed_weak_accuracy':sum(w for w,s,v in slots)/n,
            'observed_strong_accuracy':sum(s for w,s,v in slots)/n,
            'reconstructed_weak_validator_strong_accuracy': cascade_accuracy,
            'validator_fail_count':sum(v == 'FAIL' for w,s,v in slots),
            'human_review_profiles':rows,
        }
    output['limits'] = [
        'AI outcomes E1/E2 observed; cascade outcomes reconstructed; human outcomes hypothetical analytical expectations.',
        'No human review or actual human decisions occurred.',
        'Correctness-only: no replacement control sets, error-loss asymmetry, costs, delay or governance.',
        'Repeated slots correlate; 30 canonical cases are not 810 independent tasks.',
        'Only E2 validator verdicts route cases; the oracle is used solely by the evaluator/simulator.',
        'Strong-to-human is an independent modeled review of saved strong results; not a tested interaction.'
    ]
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--e1-dir', required=True, type=Path)
    parser.add_argument('--e2-dir', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--audit-report', required=True, type=Path,
                        help='Previously generated Audit 03 report with SHA-256 inventory')
    parser.add_argument('--baseline-report', type=Path,
                        help='Optional Stage 1 original report; require identical recomputed JSON')
    args = parser.parse_args()
    if not args.e1_dir.is_dir() or not args.e2_dir.is_dir():
        parser.error('Both raw input directories must exist')
    # Import only here: src.e1_score belongs to user's existing project.
    import sys
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0,str(root))
    from src.e1_score import score_run
    verify_frozen_audit(args.e1_dir, args.e2_dir, args.audit_report)
    weak, strong, verdicts = build_rows(args.e1_dir,args.e2_dir,score_run)
    result = summarize(weak,strong,verdicts)
    if args.baseline_report is not None:
        original = load(args.baseline_report)
        if result != original:
            raise ValueError('Recomputed report differs from baseline; no report written')
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with args.report.open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2)
    print('Status:',result['status'])
    print('E1 source observations:',result['source_observations'])
    for role, r in result['routes'].items():
        print(role, 'slots=',r['slots'],'FAIL=',r['validator_fail_count'],
              'weak_accuracy=',round(r['observed_weak_accuracy'],6),
              'strong_accuracy=',round(r['observed_strong_accuracy'],6))
    print('Report:',args.report)

if __name__ == '__main__':
    main()
