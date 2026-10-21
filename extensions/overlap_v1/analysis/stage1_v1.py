"""EX1 Stage1: evidence reconciliation and frozen exact-set solver scoring. Offline."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
from extensions.overlap_v1 import offline_controls as controls
from extensions.overlap_v1.prepare import ROOT,DEFAULT_FROZEN,load,sha,write_new
from extensions.overlap_v1.policy_checks import authoritative,reference_controls
from src import e1_score

BASE=Path(__file__).parent
CELLS=('both_correct','weak_wrong_strong_correct','weak_correct_strong_wrong','both_wrong')


def require(condition,message):
    if not condition:raise ValueError(message)


def score(record,expected):
    """Same historical set equality; schema validity remains a separate field."""
    parsed=record.get('parsed_response')
    if not record.get('success'):
        return dict(scoring_status='execution_failure',exact_match=False,actual_controls=None)
    if not isinstance(parsed,dict) or not isinstance(parsed.get('controls'),list):
        return dict(scoring_status='invalid_response',exact_match=False,actual_controls=None)
    actual=parsed['controls']
    return dict(scoring_status='scored',exact_match=set(actual)==set(expected),
                actual_controls=sorted(actual))


def cell(w,s):
    return ('both_correct' if w and s else 'weak_wrong_strong_correct' if not w and s
            else 'weak_correct_strong_wrong' if w and not s else 'both_wrong')


def rate(n,d):
    return dict(numerator=n,denominator=d,value=n/d if d else None)


def summarize(rows):
    valid=[r for r in rows if r['pair_valid']]
    cases=defaultdict(list)
    for row in valid:cases[row['case_id']].append(row)
    counts=Counter({k:0 for k in CELLS})
    for row in valid:counts[cell(row['weak_correct'],row['strong_correct'])]+=1
    n=len(valid);ww=counts['weak_wrong_strong_correct']+counts['both_wrong']
    wc=counts['both_correct']+counts['weak_correct_strong_wrong']
    wrongs=counts['weak_correct_strong_wrong']+counts['both_wrong']
    return dict(planned_rendering_slots=len(rows),valid_paired_renderings=n,canonical_cases_represented=len(cases),
        joint_rendering_counts=dict(counts),
        weak_accuracy=rate(wc,n),strong_accuracy=rate(n-wrongs,n),
        strong_error_given_weak_wrong=rate(counts['both_wrong'],ww),
        strong_error_given_weak_correct=rate(counts['weak_correct_strong_wrong'],wc))


def build():
    c,pf=controls.preflight()
    current=controls.inventory(c['raw_dir'])
    frozen_inventory=load(ROOT/'extensions/overlap_v1/record_inventory_final720_v1.json')['records_sha256']
    require(current==frozen_inventory and len(current)==720,'final inventory mismatch')
    require(set(c['records'])=={j['run_id'] for j in c['jobs']},'manifest population')
    oracle=load(DEFAULT_FROZEN/'oracle_outputs_v1.json')
    om={o['case_id']:o for o in oracle}
    require(len(om)==len(oracle)==60 and set(om)==set(c['cases']),'oracle identities')
    for cid,case in c['cases'].items():
        decision=authoritative(case)
        require(set(om[cid]['controls'])==set(decision.required_controls)==reference_controls(case)
                and om[cid]['disposition']==decision.disposition,'oracle disagreement')
    quality={}
    for role in ('cheap','strong','cheap_validator','strong_validator'):
        rr=[r for r in c['records'].values() if r['job']['role']==role]
        quality[role]=dict(planned=180,records=len(rr),provider_success=sum(r['success'] for r in rr),
            completed_valid=sum(controls.usable(r) for r in rr),
            provider_failures=sum(not r['success'] for r in rr),
            successful_schema_invalid=sum(r['success'] and not r['response_valid'] for r in rr),
            provider_not_completed=sum(r['success'] and r.get('provider_completed') is not True for r in rr))
    groups=defaultdict(dict)
    solver_scores=[]
    for record in c['records'].values():
        job=record['job']
        if job['role'] not in ('cheap','strong'):continue
        expected=om[job['case_id']]['controls']
        scored=score(record,expected)
        result=dict(run_id=job['run_id'],case_id=job['case_id'],rendering_id=job['rendering_id'],
            role=job['role'],schema_valid=record['response_valid'],
            expected_controls=expected,**scored)
        solver_scores.append(result)
        groups[job['rendering_id']][job['role']]=result
    require(len(solver_scores)==360,'solver slots')
    rows=[]
    for rendering in c['renderings'].values():
        cid=rendering['case_id'];g=groups[rendering['rendering_id']]
        valid=all(role in g and g[role]['scoring_status']=='scored' and g[role]['schema_valid']
                  for role in ('cheap','strong'))
        rows.append(dict(case_id=cid,rendering_id=rendering['rendering_id'],
            level=rendering['rendering_level'],stratum=c['cases'][cid]['stratum'],pair_valid=valid,
            weak_correct=g.get('cheap',{}).get('exact_match') if valid else None,
            strong_correct=g.get('strong',{}).get('exact_match') if valid else None))
    cases=[]
    for cid,case in c['cases'].items():
        rr=[r for r in rows if r['case_id']==cid]
        complete=len(rr)==3 and all(r['pair_valid'] for r in rr)
        counts=Counter(cell(r['weak_correct'],r['strong_correct']) for r in rr if r['pair_valid'])
        cases.append(dict(case_id=cid,stratum=case['stratum'],complete_three_pairs=complete,
            valid_pairs=sum(r['pair_valid'] for r in rr),
            weak_correct_renderings=sum(r['weak_correct'] is True for r in rr),
            strong_correct_renderings=sum(r['strong_correct'] is True for r in rr),
            joint_case_weights={k:counts[k]/3 for k in CELLS} if complete else None))
    eligible={x['case_id'] for x in cases if x['complete_three_pairs']}
    primary=[r for r in rows if r['case_id'] in eligible]
    summary=summarize(primary)
    weights={k:sum(x['joint_case_weights'][k] for x in cases if x['complete_three_pairs']) for k in CELLS}
    weak_wrong=weights['weak_wrong_strong_correct']+weights['both_wrong']
    weak_correct=weights['both_correct']+weights['weak_correct_strong_wrong']
    summary['case_weighted']=dict(canonical_denominator=len(eligible),joint_case_equivalents=weights,
        weak_accuracy=rate(weak_correct,len(eligible)),
        strong_accuracy=rate(weights['both_correct']+weights['weak_wrong_strong_correct'],len(eligible)),
        strong_error_given_weak_wrong=rate(weights['both_wrong'],weak_wrong),
        strong_error_given_weak_correct=rate(weights['weak_correct_strong_wrong'],weak_correct))
    summary['case_consistency']={role:dict(
        all_three_correct=sum(x[role+'_correct_renderings']==3 for x in cases if x['complete_three_pairs']),
        mixed_correctness=sum(0<x[role+'_correct_renderings']<3 for x in cases if x['complete_three_pairs']),
        all_three_incorrect=sum(x[role+'_correct_renderings']==0 for x in cases if x['complete_three_pairs']))
        for role in ('weak','strong')}
    errors=[dict(**x,missing_controls=sorted(set(x['expected_controls'])-set(x['actual_controls'] or [])),
                 extra_controls=sorted(set(x['actual_controls'] or [])-set(x['expected_controls'])))
            for x in solver_scores if x['scoring_status']=='scored' and not x['exact_match']]
    bystratum={st:summarize([r for r in primary if r['stratum']==st])
               for st in sorted({r['stratum'] for r in rows})}
    bylevel={level:summarize([r for r in primary if r['level']==level]) for level in ('L1','L2','L3')}
    before=current
    require(controls.inventory(c['raw_dir'])==before,'raw state changed')
    return dict(version='EX1-STAGE1-1.0',scope='Stage1 only: observed solver correctness, no validator effectiveness/economics.',
        provenance=dict(design_sha256=c['design_hash'],control_sha256=None,
            final_inventory_sha256=sha(ROOT/'extensions/overlap_v1/record_inventory_final720_v1.json'),
            historical_scoring_sha256=sha(Path(e1_score.__file__)),
            analysis_code_sha256=sha(Path(__file__)),
            oracle_sha256=sha(DEFAULT_FROZEN/'oracle_outputs_v1.json'),
            tests_sha256=sha(BASE/'test_stage1_v1.py'),verifier_sha256=sha(BASE/'verify_stage1_v1.py')),
        evidence=dict(records=720,unique_manifest_ids=720,hashes_verified=720,
            public_projection_hashes_verified=pf['public_projection_hashes_verified'],canonical_cases=60,
            renderings=180,role_status=quality,reservations=0,
            provider_failure_run_ids=sorted(rid for rid,r in c['records'].items() if not r['success']),
            no_observations_modified=True,api_calls=0),
        scoring_contract='Historical e1_score.py set(actual controls)==set(authoritative controls); schema validity separate.',
        primary_summary=summary,by_stratum=bystratum,by_level=bylevel,
        cases=cases,rendering_pairs=rows,solver_scores=sorted(solver_scores,key=lambda x:x['run_id']),
        solver_errors=errors,
        limitations=['Finite model-blind selected synthetic corpus; not production prevalence.',
            'Three renderings per canonical case share facts and oracle; not independent trials.',
            'All60 complete solver cases weighted equally; average three indicators per case.',
            'Case-equivalent joint cells are fractional weighted counts, not counts of independently observed cases.',
            'L labels are presentation forms, not validated difficulty scales.',
            'Conditional probabilities with zero denominators are undefined, represented as null.',
            'Two strong-validator503s do not remove otherwise valid solver pairs.',
            'No new hypotheses, pooling with historical cohorts or statistical independence claims.'])


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    write_new(args.output,build())
    print(args.output)


if __name__=='__main__':main()
