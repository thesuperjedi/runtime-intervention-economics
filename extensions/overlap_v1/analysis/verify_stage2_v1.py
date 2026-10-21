"""Separate raw-record Stage2 reproduction; never calls analysis aggregation."""
import argparse
from collections import Counter,defaultdict
from fractions import Fraction
import hashlib
from pathlib import Path
from extensions.overlap_v1.prepare import ROOT,DEFAULT_FROZEN,load,write_new
from extensions.overlap_v1.policy_checks import authoritative,reference_controls
from extensions.overlap_v1.analysis.verify_stage1_v1 import verify as verify_stage1

BASE=Path(__file__).parent
ROLES=('cheap_validator','strong_validator')


def check(condition,message):
    if not condition:raise ValueError(message)


def metrics(rows):
    valid=[r for r in rows if r['status']=='valid' and r['pair_valid']]
    cells=Counter()
    totals=Counter()
    for r in valid:
        w,s,v=r['weak_correct'],r['strong_correct'],r['verdict']
        key={('PASS',True):'true_accept',('PASS',False):'false_accept',
             ('FAIL',True):'false_reject',('FAIL',False):'true_reject'}[(v,w)]
        cells[key]+=1
        totals['weak_correct']+=w;totals['strong_correct']+=s
        totals['final_correct']+=(w if v=='PASS' else s)
        totals['pass_count']+=v=='PASS';totals['fail_count']+=v=='FAIL'
        if v=='FAIL':
            totals['fail_weak_wrong']+=not w;totals['fail_weak_correct']+=w
            totals['fail_strong_correct']+=s;totals['fail_strong_wrong']+=not s
            totals['corrections']+=not w and s;totals['corruptions']+=w and not s
            totals['failed_repairs']+=not w and not s
    return valid,cells,totals


def verify_summary(rows,got,weighted):
    valid,c,t=metrics(rows);n=len(valid)
    check(got['planned_slots']==len(rows) and got['valid_judgments']==n,'denominators')
    check(got['status_counts']==dict(Counter(r['status'] for r in rows)),'statuses')
    check(got['canonical_cases_represented']==len({r['case_id'] for r in valid}),'case denominators')
    for k in ('true_accept','false_accept','true_reject','false_reject'):
        check(got['confusion'][k]==c[k],'confusion '+k)
    def ratio(g,n,d):
        check(g==dict(numerator=n,denominator=d,value=n/d if d else None),'rate')
    ratio(got['FAR'],c['false_accept'],c['false_accept']+c['true_reject'])
    ratio(got['FRR'],c['false_reject'],c['false_reject']+c['true_accept'])
    ratio(got['cascade_accuracy'],t['final_correct'],n)
    ratio(got['escalation_rate'],t['fail_count'],n)
    ratio(got['weak_accuracy_same_population'],t['weak_correct'],n)
    ratio(got['strong_accuracy_same_population'],t['strong_correct'],n)
    for k,source in [('weak_errors_detected','true_reject'),('weak_errors_accepted','false_accept'),
                     ('correct_weak_unnecessarily_escalated','false_reject')]:
        check(got[k]==c[source],'routing count')
    for k in ('corrections','corruptions','failed_repairs','pass_count'):
        check(got[k]==t[k],'outcome count')
    q=got['fail_queue']
    check(q['size']==t['fail_count'],'queue size')
    for k in ('weak_wrong','weak_correct','strong_correct','strong_wrong'):
        check(q[k]==t['fail_'+k],'queue composition')
    ratio(q['strong_correctness'],t['fail_strong_correct'],t['fail_count'])
    check(got['net_corrections']==t['corrections']-t['corruptions'],'net corrections')
    if weighted:
        bycase=defaultdict(list)
        for row in valid:bycase[row['case_id']].append(row)
        weights=Counter()
        for rr in bycase.values():
            _,cc,tt=metrics(rr)
            for key in ('true_accept','false_accept','true_reject','false_reject'):
                weights[key]+=Fraction(cc[key],len(rr))
            for key in ('final_correct','fail_count','fail_strong_correct'):
                weights[key]+=Fraction(tt[key],len(rr))
        g=got['case_weighted'];check(g['canonical_denominator']==len(bycase),'weighted cases')
        for k in ('true_accept','false_accept','true_reject','false_reject'):
            check(abs(g['confusion_case_equivalents'][k]-float(weights[k]))<1e-10,'weighted confusion')
        for key,num,den in [('FAR',weights['false_accept'],weights['false_accept']+weights['true_reject']),
                            ('FRR',weights['false_reject'],weights['false_reject']+weights['true_accept']),
                            ('cascade_accuracy',weights['final_correct'],len(bycase)),
                            ('escalation_rate',weights['fail_count'],len(bycase)),
                            ('fail_strong_correctness',weights['fail_strong_correct'],weights['fail_count'])]:
            ratio(g[key],float(num),float(den))


def verify(report):
    inventory=load(ROOT/'extensions/overlap_v1/record_inventory_final720_v1.json')['records_sha256']
    raw=ROOT/'data/raw/extension_overlap_v1'
    check({p.name for p in raw.iterdir()}==set(inventory),'inventory')
    for name,h in inventory.items():check(hashlib.sha256((raw/name).read_bytes()).hexdigest()==h,'raw hash')
    cases={c['case_id']:c for c in load(DEFAULT_FROZEN/'canonical_cases_v1.json')}
    renders={r['rendering_id']:r for r in load(DEFAULT_FROZEN/'renderings_v1.json')}
    stage1=load(BASE/'stage1_results_v1.json');verify_stage1(stage1)
    records={p.stem:load(p) for p in raw.iterdir()}
    jobs=load(DEFAULT_FROZEN/'execution_manifest_v1.json')['jobs']
    check(len(jobs)==720 and len({j['run_id'] for j in jobs})==720,'manifest uniqueness')
    allrows=[]
    for j in jobs:
        rec=records[j['run_id']];check(rec['job']==j and rec['run_id']==j['run_id'],'identity')
        if j['role'] not in ROLES:continue
        case=cases[j['case_id']];truth=set(authoritative(case).required_controls)
        check(truth==reference_controls(case),'oracle')
        weak=records[j['source_cheap_run_id']]
        strong=records[j['paired_strong_run_id']]
        w=set(weak['parsed_response']['controls'])==truth
        s=set(strong['parsed_response']['controls'])==truth
        if not rec['success']:status='provider_failure';v=None
        elif rec.get('provider_completed') is not True:status='provider_not_completed';v=None
        elif not rec['response_valid'] or rec['parsed_response'] not in ({'verdict':'PASS'},{'verdict':'FAIL'}):
            status='malformed_response';v=None
        else:status='valid';v=rec['parsed_response']['verdict']
        allrows.append(dict(run_id=j['run_id'],case_id=j['case_id'],rendering_id=j['rendering_id'],
            level=renders[j['rendering_id']]['rendering_level'],stratum=case['stratum'],
            validator_role=j['role'],status=status,pair_valid=True,weak_correct=w,strong_correct=s,
            verdict=v,confusion_cell={('PASS',True):'true_accept',('PASS',False):'false_accept',
                ('FAIL',True):'false_reject',('FAIL',False):'true_reject'}.get((v,w)),
            cascade_correct=(w if v=='PASS' else s) if v else None))
    check({r['run_id']:r for r in allrows}=={r['run_id']:r for r in report['slots']},'all360 slots')
    eligible={role:{cid for cid in cases if sum(r['case_id']==cid and r['validator_role']==role
                and r['status']=='valid' for r in allrows)==3} for role in ROLES}
    common=eligible[ROLES[0]]&eligible[ROLES[1]]
    check(set(report['evidence']['common_complete_case_ids'])==common,'common cases')
    views_verified=0
    for role in ROLES:
        rr=[r for r in allrows if r['validator_role']==role]
        check(set(report['roles'][role]['complete_case_ids'])==eligible[role],'eligible cases')
        populations=[('primary_complete_cases',[r for r in rr if r['case_id'] in eligible[role]],True),
                     ('available_renderings_descriptive',rr,False),
                     ('common_paired_cases',[r for r in rr if r['case_id'] in common],True)]
        for name,rows,weighted in populations:
            view=report['roles'][role][name]
            verify_summary(rows,view['overall'],weighted);views_verified+=1
            for st in view['by_stratum']:
                verify_summary([r for r in rows if r['stratum']==st],view['by_stratum'][st],weighted);views_verified+=1
            for level in ('L1','L2','L3'):
                verify_summary([r for r in rows if r['level']==level],view['by_level'][level],weighted);views_verified+=1
    unresolved=[r for r in allrows if r['status']!='valid']
    check({r['run_id'] for r in report['unresolved_slots']}=={r['run_id'] for r in unresolved},'unresolved slots')
    return dict(status='PASS',public_projection_hashes_verified=720,validator_slots_reconstructed=360,
        summaries_independently_verified=views_verified,cheap_complete_cases=len(eligible[ROLES[0]]),
        strong_complete_cases=len(eligible[ROLES[1]]),common_cases=len(common),
        missing_verdicts=len(unresolved),api_calls=0,
        independence='Separate computational reproduction, not independent human review.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=verify(load(a.input));write_new(a.output,result);print(result)


if __name__=='__main__':main()
