"""Separate Stage1 reproduction: raw inventory, historical scorer and Fraction aggregation."""
import argparse
from collections import Counter,defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from extensions.overlap_v1.prepare import ROOT,DEFAULT_FROZEN,load,write_new
from extensions.overlap_v1.policy_checks import reference_controls
from src import e1_score
from src.e1_policy import ProcurementCase,evaluate_policy


def verify(report):
    raw=ROOT/'data/raw/extension_overlap_v1'
    inventory=load(ROOT/'extensions/overlap_v1/record_inventory_final720_v1.json')['records_sha256']
    files=list(raw.iterdir())
    if len(files)!=720 or {p.name for p in files}!=set(inventory):raise ValueError('raw inventory')
    for p in files:
        if hashlib.sha256(p.read_bytes()).hexdigest()!=inventory[p.name]:raise ValueError('raw hash')
    manifest=load(DEFAULT_FROZEN/'execution_manifest_v1.json')['jobs']
    records={p.stem:load(p) for p in files}
    if len(manifest)!=720 or {j['run_id'] for j in manifest}!=set(records):raise ValueError('manifest identities')
    cases={x['case_id']:x for x in load(DEFAULT_FROZEN/'canonical_cases_v1.json')}
    oracles={x['case_id']:x for x in load(DEFAULT_FROZEN/'oracle_outputs_v1.json')}
    scored={}
    for job in manifest:
        rec=records[job['run_id']]
        if rec['job']!=job or rec['run_id']!=job['run_id']:raise ValueError('record identity')
        if job['role'] not in ('cheap','strong'):continue
        case=cases[job['case_id']]
        kwargs={k:case[k] for k in ('case_id','amount_usd','vendor_status','data_classification',
                                   'deployment','contract_months','exception_status','exception_scope')}
        truth=set(evaluate_policy(ProcurementCase(**kwargs)).required_controls)
        if truth!=reference_controls(case) or truth!=set(oracles[case['case_id']]['controls']):
            raise ValueError('independent oracle')
        # Adapt field names only; execute unmodified historical score_run.
        adapted=dict(rec,case_id=job['case_id'],rendering_id=job['rendering_id'],
                     model_role=job['role'],requested_model=rec['request']['model'])
        with patch.object(e1_score,'load_json',side_effect=[adapted,[case]]):
            historical=e1_score.score_run(Path('OFFLINE_ADAPTER'))
        direct=set(rec['parsed_response']['controls'])==truth
        if direct!=historical['exact_match']:raise ValueError('historical/direct score')
        scored[(job['rendering_id'],job['role'])]=direct
    reported={(x['rendering_id'],x['role']):x['exact_match'] for x in report['solver_scores']}
    if scored!=reported:raise ValueError('all360 solver scores')
    renderings=load(DEFAULT_FROZEN/'renderings_v1.json')
    pairs={}
    for render in renderings:
        rid=render['rendering_id']
        pairs[rid]=(scored[(rid,'cheap')],scored[(rid,'strong')])
    naming={(True,True):'both_correct',(False,True):'weak_wrong_strong_correct',
            (True,False):'weak_correct_strong_wrong',(False,False):'both_wrong'}
    globalcounts=Counter(naming[x] for x in pairs.values())
    if any(report['primary_summary']['joint_rendering_counts'][k]!=globalcounts[k] for k in naming.values()):
        raise ValueError('joint rendering counts')
    grouped=defaultdict(list)
    for render in renderings:grouped[render['case_id']].append(pairs[render['rendering_id']])
    weights=Counter()
    for cid,triples in grouped.items():
        if len(triples)!=3:raise ValueError('case completeness')
        for pair in triples:weights[naming[pair]]+=Fraction(1,3)
        reported_case=next(x for x in report['cases'] if x['case_id']==cid)
        if reported_case['weak_correct_renderings']!=sum(x[0] for x in triples):raise ValueError('weak case')
        if reported_case['strong_correct_renderings']!=sum(x[1] for x in triples):raise ValueError('strong case')
        for k in naming.values():
            if abs(reported_case['joint_case_weights'][k]-float(sum(Fraction(1,3) for x in triples if naming[x]==k)))>1e-12:
                raise ValueError('case joint weight')
    for k in naming.values():
        if abs(float(weights[k])-report['primary_summary']['case_weighted']['joint_case_equivalents'][k])>1e-10:
            raise ValueError('case-weighted sum')
    for group,field in [('by_stratum','stratum'),('by_level','level')]:
        for value,data in report[group].items():
            members=[rr for rr in renderings if (cases[rr['case_id']]['stratum'] if field=='stratum' else rr['rendering_level'])==value]
            counts=Counter(naming[pairs[rr['rendering_id']]] for rr in members)
            if data['valid_paired_renderings']!=len(members):raise ValueError('subgroup denominator')
            if any(data['joint_rendering_counts'][k]!=counts[k] for k in naming.values()):raise ValueError('subgroup cells')
            wwrong=sum(not pairs[rr['rendering_id']][0] for rr in members)
            wc=len(members)-wwrong
            for key,n,d in [('strong_error_given_weak_wrong',counts['both_wrong'],wwrong),
                            ('strong_error_given_weak_correct',counts['weak_correct_strong_wrong'],wc),
                            ('weak_accuracy',wc,len(members)),
                            ('strong_accuracy',len(members)-counts['both_wrong']-counts['weak_correct_strong_wrong'],len(members))]:
                got=data[key]
                if got['numerator']!=n or got['denominator']!=d or got['value']!=(n/d if d else None):
                    raise ValueError('subgroup rates')
    # Exact rational aggregate conditional recomputation.
    for key,n,d in [('strong_error_given_weak_wrong',weights['both_wrong'],weights['both_wrong']+weights['weak_wrong_strong_correct']),
                    ('strong_error_given_weak_correct',weights['weak_correct_strong_wrong'],weights['both_correct']+weights['weak_correct_strong_wrong'])]:
        expected=float(n/d) if d else None
        got=report['primary_summary']['case_weighted'][key]['value']
        if expected is None:
            if got is not None:raise ValueError('undefined conditional')
        elif abs(expected-got)>1e-12:raise ValueError('weighted conditional')
    statuses=Counter((r['job']['role'],r['success'],r['response_valid']) for r in records.values())
    for role,data in report['evidence']['role_status'].items():
        if data['records']!=sum(v for (rl,_,_),v in statuses.items() if rl==role):raise ValueError('role count')
        if data['provider_failures']!=sum(v for (rl,ok,_),v in statuses.items() if rl==role and not ok):raise ValueError('provider failures')
    return dict(status='PASS',public_projection_hashes=720,solver_scores_verified_with_historical_scorer=360,
                independent_fraction_case_aggregation=True,subgroup_tables_verified=9,
                canonical_cases=60,rendering_pairs=180,api_calls=0,
                scope='Separate implementation/check, not independent human examination.')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=verify(load(args.input));write_new(args.output,result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
