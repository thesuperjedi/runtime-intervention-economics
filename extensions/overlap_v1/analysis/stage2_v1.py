"""EX1 Stage2 validator effectiveness only. Frozen observed verdicts; no economics."""
import argparse
from collections import Counter,defaultdict
from fractions import Fraction
from pathlib import Path
from extensions.overlap_v1.prepare import ROOT,load,sha,write_new
from extensions.overlap_v1 import offline_controls as controls
from extensions.overlap_v1.analysis.verify_stage1_v1 import verify as verify_stage1

BASE=Path(__file__).parent
ROLES=('cheap_validator','strong_validator')
CELLS=('true_accept','false_accept','true_reject','false_reject')


def require(condition,message):
    if not condition:raise ValueError(message)


def ratio(n,d):
    return dict(numerator=n,denominator=d,value=n/d if d else None)


def classify(weak_correct,verdict):
    if verdict not in ('PASS','FAIL'):raise ValueError('no valid verdict')
    return ('true_accept' if weak_correct else 'false_accept') if verdict=='PASS' else (
        'false_reject' if weak_correct else 'true_reject')


def response_status(record):
    if record is None:return 'missing_record'
    if record.get('success') is not True:return 'provider_failure'
    if record.get('provider_completed') is not True:return 'provider_not_completed'
    parsed=record.get('parsed_response')
    if (record.get('response_valid') is not True or not isinstance(parsed,dict)
            or set(parsed)!={'verdict'} or parsed['verdict'] not in ('PASS','FAIL')):
        return 'malformed_response'
    return 'valid'


def indicators(row):
    w,s,v=row['weak_correct'],row['strong_correct'],row['verdict']
    final=w if v=='PASS' else s
    return dict(**{key:int(classify(w,v)==key) for key in CELLS},
        weak_correct=int(w),strong_correct=int(s),pass_count=int(v=='PASS'),fail_count=int(v=='FAIL'),
        fail_weak_wrong=int(v=='FAIL' and not w),fail_weak_correct=int(v=='FAIL' and w),
        fail_strong_correct=int(v=='FAIL' and s),fail_strong_wrong=int(v=='FAIL' and not s),
        corrections=int(v=='FAIL' and not w and s),corruptions=int(v=='FAIL' and w and not s),
        failed_repairs=int(v=='FAIL' and not w and not s),
        final_correct=int(final))


def summary(rows,case_weighted=False):
    valid=[r for r in rows if r['status']=='valid' and r['pair_valid']]
    n=len(valid)
    totals=Counter()
    bycase=defaultdict(list)
    for row in valid:
        totals.update(indicators(row));bycase[row['case_id']].append(row)
    result=dict(planned_slots=len(rows),valid_judgments=n,canonical_cases_represented=len(bycase),
        status_counts=dict(Counter(r['status'] for r in rows)),
        confusion={k:totals[k] for k in CELLS},
        FAR=ratio(totals['false_accept'],totals['false_accept']+totals['true_reject']),
        FRR=ratio(totals['false_reject'],totals['false_reject']+totals['true_accept']),
        fail_queue=dict(size=totals['fail_count'],weak_wrong=totals['fail_weak_wrong'],
            weak_correct=totals['fail_weak_correct'],strong_correct=totals['fail_strong_correct'],
            strong_wrong=totals['fail_strong_wrong'],
            strong_correctness=ratio(totals['fail_strong_correct'],totals['fail_count'])),
        weak_errors_detected=totals['true_reject'],weak_errors_accepted=totals['false_accept'],
        correct_weak_unnecessarily_escalated=totals['false_reject'],
        corrections=totals['corrections'],corruptions=totals['corruptions'],failed_repairs=totals['failed_repairs'],
        pass_count=totals['pass_count'],escalation_rate=ratio(totals['fail_count'],n),
        weak_accuracy_same_population=ratio(totals['weak_correct'],n),
        strong_accuracy_same_population=ratio(totals['strong_correct'],n),
        cascade_accuracy=ratio(totals['final_correct'],n),
        net_corrections=totals['corrections']-totals['corruptions'])
    if case_weighted:
        weights=Counter()
        for rr in bycase.values():
            for row in rr:
                for key,val in indicators(row).items():weights[key]+=Fraction(val,len(rr))
        def wr(key,den):return ratio(float(weights[key]),float(den))
        result['case_weighted']=dict(canonical_denominator=len(bycase),
            confusion_case_equivalents={k:float(weights[k]) for k in CELLS},
            FAR=wr('false_accept',weights['false_accept']+weights['true_reject']),
            FRR=wr('false_reject',weights['false_reject']+weights['true_accept']),
            fail_strong_correctness=wr('fail_strong_correct',weights['fail_count']),
            cascade_accuracy=wr('final_correct',len(bycase)),
            escalation_rate=wr('fail_count',len(bycase)))
    return result


def view(rows,case_weighted):
    return dict(overall=summary(rows,case_weighted),
        by_stratum={st:summary([r for r in rows if r['stratum']==st],case_weighted)
                    for st in sorted({r['stratum'] for r in rows})},
        by_level={level:summary([r for r in rows if r['level']==level],case_weighted)
                  for level in ('L1','L2','L3')})


def build():
    manifest=load(BASE/'stage1_analysis_manifest_v1.json')
    for name,h in manifest['files_sha256'].items():
        require(sha(BASE/name)==h,'Stage1 artifact changed: '+name)
    stage1=load(BASE/'stage1_results_v1.json');verification=verify_stage1(stage1)
    c,pf=controls.preflight()
    before=controls.inventory(c['raw_dir'])
    require(before==load(ROOT/'extensions/overlap_v1/record_inventory_final720_v1.json')['records_sha256'],
            'raw inventory mismatch')
    pairs={r['rendering_id']:r for r in stage1['rendering_pairs']}
    rows=[]
    jobs={(j['rendering_id'],j['role']):j for j in c['jobs']}
    for render in c['renderings'].values():
        pair=pairs[render['rendering_id']]
        for role in ROLES:
            job=jobs[(render['rendering_id'],role)]
            rec=c['records'].get(job['run_id'])
            status=response_status(rec)
            verdict=rec['parsed_response']['verdict'] if status=='valid' else None
            valid=status=='valid' and pair['pair_valid']
            rows.append(dict(run_id=job['run_id'],case_id=render['case_id'],
                rendering_id=render['rendering_id'],level=render['rendering_level'],
                stratum=c['cases'][render['case_id']]['stratum'],validator_role=role,status=status,
                pair_valid=pair['pair_valid'],weak_correct=pair['weak_correct'],
                strong_correct=pair['strong_correct'],verdict=verdict,
                confusion_cell=classify(pair['weak_correct'],verdict) if valid else None,
                cascade_correct=(pair['weak_correct'] if verdict=='PASS' else pair['strong_correct']) if valid else None))
    eligibility={}
    for role in ROLES:
        eligibility[role]=sorted(cid for cid in c['cases']
            if len([r for r in rows if r['case_id']==cid and r['validator_role']==role
                    and r['status']=='valid' and r['pair_valid']])==3)
    common=sorted(set(eligibility[ROLES[0]])&set(eligibility[ROLES[1]]))
    roles={}
    for role in ROLES:
        rr=[r for r in rows if r['validator_role']==role]
        eligible=set(eligibility[role])
        roles[role]=dict(complete_case_ids=eligibility[role],
            excluded_case_ids=sorted(set(c['cases'])-eligible),
            primary_complete_cases=view([r for r in rr if r['case_id'] in eligible],True),
            available_renderings_descriptive=view(rr,False),
            common_paired_cases=view([r for r in rr if r['case_id'] in common],True),
            valid_rows_excluded_from_primary=[r['run_id'] for r in rr
                if r['case_id'] not in eligible and r['status']=='valid' and r['pair_valid']])
    require(controls.inventory(c['raw_dir'])==before,'raw evidence changed')
    return dict(version='EX1-STAGE2-1.0',scope='Validator effectiveness only. No economic calculations.',
        provenance=dict(scientific_sha256=c['design_hash'],recovery_control_sha256=None,
            stage1_results_sha256=sha(BASE/'stage1_results_v1.json'),
            stage1_manifest_sha256=sha(BASE/'stage1_analysis_manifest_v1.json'),
            raw_inventory_sha256=sha(ROOT/'extensions/overlap_v1/record_inventory_final720_v1.json'),
            analysis_sha256=sha(Path(__file__)),verifier_sha256=sha(BASE/'verify_stage2_v1.py'),
            tests_sha256=sha(BASE/'test_stage2_v1.py')),
        evidence=dict(records=720,public_projection_hashes_verified=720,adapter_hash_check_count=pf['public_projection_hashes_verified'],
            stage1_verification=verification,solver_case_denominator=60,planned_validator_slots_per_role=180,
            common_complete_case_ids=common,common_case_denominator=len(common),api_calls=0),
        definitions=dict(true_accept='Correct weak answer + PASS',false_accept='Incorrect weak answer + PASS',
            true_reject='Incorrect weak answer + FAIL',false_reject='Correct weak answer + FAIL',
            FAR='false_accept/(false_accept+true_reject)',FRR='false_reject/(false_reject+true_accept)',
            cascade='Weak correctness on recorded PASS; paired strong correctness on recorded FAIL.',
            primary='All3 valid solver pairs and validator judgments required per case; equal canonical weights.',
            available='Supplementary available-rendering description, not primary complete-case evidence.'),
        roles=roles,slots=rows,unresolved_slots=[r for r in rows if r['status']!='valid'],
        limitations=['Renderings share canonical facts; no independent180-case inference.',
            'Primary role-specific populations differ; compare roles on common58 cases.',
            'Case-equivalent counts are weighted totals, not independent cases.',
            'Unknown verdicts/routes remain null; no fallback or imputation.',
            'Provider failures do not count as cognitive validator errors.',
            'Observed conditional strong correctness is finite-corpus evidence, not guaranteed future repair.',
            'Cascade outcomes reconstructed from frozen independent solver outputs; no live cascade execution.',
            'No economic conclusions or new predeclared hypotheses.'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();write_new(args.output,build());print(args.output)


if __name__=='__main__':main()
