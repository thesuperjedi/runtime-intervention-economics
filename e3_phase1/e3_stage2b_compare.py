"""E3 Stage 2b: offline conditional comparison of frozen AI routes and hypothetical human review.

Read-only E1/E2 inputs. Exclusive-create output. No network, SDK, or model calls.
Uses existing e3_accuracy_replay audit gate, joins and E1 historical scorer.
Currency: USD frozen token-price convention. Human cost H and error loss L are
user-specified HYPOTHETICAL USD parameters, never observed quantities.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from e3_accuracy_replay import build_rows, load, verify_frozen_audit, E2_ID

PRICES = {
    'cheap': (0.30, 2.50),
    'strong': (0.75, 3.75),
}
ROLES = ('cheap_validator', 'strong_validator')
ROUTES = ('weak_only', 'strong_only', 'weak_validator_strong_on_fail',
          'weak_human_all', 'weak_validator_human_on_fail')
TIE_ABS_USD = 1e-12

def consistent_winner(costs, routes):
    """Stable route preference when differences are within tie tolerance."""
    best = routes[0]
    for route in routes[1:]:
        if costs[route] < costs[best] - TIE_ABS_USD:
            best = route
    return best

EXPECTED_BY_ROLE = {
    'cheap_validator': {'PASS': 727, 'FAIL': 83, 'correct_pass':702, 'wrong_pass':25, 'wrong_fail':77, 'correct_fail':6},
    'strong_validator': {'PASS': 708, 'FAIL': 102, 'correct_pass':708, 'wrong_pass':0, 'wrong_fail':102, 'correct_fail':0},
}


def nonnegative_number(x, label):
    if type(x) not in (float, int) or not math.isfinite(x) or x < 0:
        raise ValueError(f'{label} must be a finite nonnegative number: {x!r}')
    return float(x)


def estimated_cost(record, role):
    """Frozen E1 pricing: input  and output+thought; reject unknown usage."""
    if role not in PRICES:
        raise ValueError('unknown price role')
    usage = record.get('usage')
    if not isinstance(usage, dict):
        raise ValueError(f"missing usage: {record.get('run_id')}")
    keys = ('total_input_tokens','total_output_tokens','total_thought_tokens',
            'total_tokens','total_cached_tokens','total_tool_use_tokens')
    for key in keys:
        if type(usage.get(key)) is not int or usage[key] < 0:
            raise ValueError(f"unsupported token field {key}: {record.get('run_id')}")
    i,o,t,total,cache,tool = (usage[k] for k in keys)
    if i+o+t != total or cache != 0 or tool != 0:
        raise ValueError(f"token accounting not covered by frozen price convention: {record.get('run_id')}")
    ir,orr = PRICES[role]
    return (i*ir+(o+t)*orr)/1_000_000


def read_costed_slots(e1_dir, e2_dir, weak, strong, verdicts):
    weak_cost, strong_cost = {}, {}
    for folder in (e1_dir,):
        for path in sorted(folder.glob('*.json')):
            r=load(path)
            rid=r['run_id']
            target=weak_cost if rid in weak else strong_cost if rid in strong else None
            if target is None:
                raise ValueError(f'unexpected E1 record {rid}')
            target[rid] = estimated_cost(r, 'cheap' if rid in weak else 'strong')
    costs={}
    for path in sorted(e2_dir.glob('*.json')):
        r=load(path)
        match=E2_ID.fullmatch(path.stem)
        if match is None: raise ValueError(f'Invalid E2 filename {path.name}')
        src,role,rep=match.groups()
        key=(src,role,int(rep))
        if key in costs or key not in verdicts or r.get('run_id') != path.stem:
            raise ValueError(f'E2 cost join failed: {path.name}')
        # Source role cross-checked by build_rows(); pricing role is frozen by validator role.
        costs[key]=estimated_cost(r, 'cheap' if role=='cheap_validator' else 'strong')
    if set(costs)!=set(verdicts) or set(weak_cost)!=set(weak) or set(strong_cost)!=set(strong):
        raise ValueError('incomplete cost coverage')
    slots={}
    for role in ROLES:
        rows=[]
        for src in sorted(weak):
            peer=src.replace('-cheap-','-strong-',1)
            for rep in (1,2,3):
                key=(src,role,rep)
                rows.append(dict(source=src, rep=rep, weak_correct=bool(weak[src]['correct']),
                                 strong_correct=bool(strong[peer]['correct']),
                                 verdict=verdicts[key], weak_cost=weak_cost[src],
                                 strong_cost=strong_cost[peer], validator_cost=costs[key]))
        if len(rows)!=810: raise ValueError(f'{role}: unexpected slot count')
        slots[role]=rows
    return slots


def close(a,b,label):
    if not isinstance(a,(int,float)) or isinstance(a,bool) or not math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10):
        raise ValueError(f'{label}: Stage 1 mismatch ({a} != {b})')


def aggregate_baseline(slots, loss):
    n=len(slots)
    records={}
    for route in ROUTES[:3]:
        money=0.; correct=0.
        for s in slots:
            w=s['weak_correct']; st=s['strong_correct']; fail=s['verdict']=='FAIL'
            if route=='weak_only':
                c=s['weak_cost']; y=w
            elif route=='strong_only':
                c=s['strong_cost']; y=st
            else:
                c=s['weak_cost']+s['validator_cost']+(s['strong_cost'] if fail else 0)
                y=st if fail else w
            money+=c;correct+=int(y)
        accuracy=correct/n
        records[route]={'accuracy':accuracy, 'api_cost_usd_per_slot':money/n,
                        'review_rate':0., 'human_cost_usd_per_slot':0.,
                        'error_loss_usd_per_slot':loss*(1-accuracy),
                        'total_expected_usd_per_slot':money/n+loss*(1-accuracy),
                        'basis':'observed solver correctness; reconstructed cascade' if route.endswith('on_fail') else 'frozen E1 solver observations'}
    return records


def analyze(stage1, slots_by_role, loss, human_cost):
    loss=nonnegative_number(loss,'loss-usd')
    human_cost=nonnegative_number(human_cost,'review-usd')
    if stage1.get('status')!='ANALYTICAL_SIMULATION_ONLY' or stage1.get('source_observations')!=270 or stage1.get('reviewer_profiles')!=36:
        raise ValueError('invalid Stage 1 header')
    if set(stage1.get('routes',{}))!=set(ROLES): raise ValueError('Stage 1 role mismatch')
    result={'status':'STAGE2B_CONDITIONAL_ONLY','currency':'USD',
            'pricing_basis':{'cheap_input_per_million':0.30,'cheap_output_plus_thought_per_million':2.50,
                             'strong_input_per_million':0.75,'strong_output_plus_thought_per_million':3.75,
                             'source':'frozen E1 list-price convention, NOT independently invoice-verified'},
            'assumptions':{'error_loss_usd_per_incorrect_result':loss, 'human_review_usd_per_routed_case':human_cost,
                           'error_loss_equal_for_all_wrong_final_sets':True,'human_parameters':'hypothetical D,C,F; unchanged per case and queue'},
            'routes':{},'limitations':[
              'Billing SGD totals are external corroboration only; not assigned to individual historical calls.',
              'E1 strong outputs reused counterfactually; live cascades and human decisions were NOT executed.',
              '810 slots per validator role repeat 270 frozen solver realizations; only 30 canonical cases.',
              'Costs are estimated from normalized tokens using frozen USD rates, not actual invoices.',
              'No human measurements, asymmetric losses, delays, human approval authority or deployment validity.',
              'Frozen raw SHA checks require trusted Audit 03; scorer and policy dependencies are not cryptographically bound.',
              'Routing acts only on saved PASS/FAIL verdict, not oracle truth.',
              'Existing stronger preflight remains an independent prerequisite.'
            ]}
    profiles={(d,c,f) for d in (.25,.5,.75,1.) for c in (.5,.75,1.) for f in (0.,.05,.15)}
    for role in ROLES:
        slots=slots_by_role[role]; n=len(slots)
        if n!=810: raise ValueError('unexpected slot count')
        ref=stage1['routes'][role]
        if ref.get('slots')!=n or ref.get('validator_fail_count')!=sum(s['verdict']=='FAIL' for s in slots):
            raise ValueError('Stage 1 slot or FAIL mismatch')
        observed={'PASS':sum(s['verdict']=='PASS' for s in slots), 'FAIL':sum(s['verdict']=='FAIL' for s in slots),
                  'correct_pass':sum(s['verdict']=='PASS' and s['weak_correct'] for s in slots),
                  'wrong_pass':sum(s['verdict']=='PASS' and not s['weak_correct'] for s in slots),
                  'correct_fail':sum(s['verdict']=='FAIL' and s['weak_correct'] for s in slots),
                  'wrong_fail':sum(s['verdict']=='FAIL' and not s['weak_correct'] for s in slots)}
        if observed != EXPECTED_BY_ROLE[role]:
            raise ValueError(f'{role}: E2 confusion totals mismatch {observed}')
        baselines=aggregate_baseline(slots,loss)
        close(ref.get('observed_weak_accuracy'),baselines['weak_only']['accuracy'],'weak baseline')
        close(ref.get('observed_strong_accuracy'),baselines['strong_only']['accuracy'],'strong baseline')
        close(ref.get('reconstructed_weak_validator_strong_accuracy'),
              baselines['weak_validator_strong_on_fail']['accuracy'],'cascade baseline')
        if len(ref.get('human_review_profiles',[]))!=36: raise ValueError('incomplete profile grid')
        baseline_best=consistent_winner({r: baselines[r]['total_expected_usd_per_slot'] for r in ROUTES[:3]}, ROUTES[:3])
        baseline_cost=baselines[baseline_best]['total_expected_usd_per_slot']
        out_profiles=[]; seen=set()
        for p in ref['human_review_profiles']:
            d,c,f=(p[k] for k in ('D','C','F'))
            key=(d,c,f)
            if key not in profiles or key in seen: raise ValueError('bad profile')
            seen.add(key)
            dc=d*c
            direct_correct=sum((1-f) if s['weak_correct'] else dc for s in slots)/n
            selective_correct=sum((1-f if s['weak_correct'] else dc) if s['verdict']=='FAIL' else int(s['weak_correct']) for s in slots)/n
            close(p.get('weak_to_human'),direct_correct,'direct human Stage 1')
            close(p.get('weak_validator_to_human_on_fail'),selective_correct,'selective human Stage 1')
            close(p.get('strong_to_human'),sum((1-f if s['strong_correct'] else dc) for s in slots)/n,'strong-human Stage 1')
            rows={}
            for route,accuracy,review_rate,api in (
                ('weak_human_all',direct_correct,1.,baselines['weak_only']['api_cost_usd_per_slot']),
                ('weak_validator_human_on_fail',selective_correct,observed['FAIL']/n,
                 sum(s['weak_cost']+s['validator_cost'] for s in slots)/n)):
                no_human=api+loss*(1-accuracy)
                total=no_human+human_cost*review_rate
                threshold=(baseline_cost-no_human)/review_rate if review_rate>0 else None
                rows[route]={'accuracy':accuracy,'api_cost_usd_per_slot':api,
                             'review_rate':review_rate,'human_cost_usd_per_slot':human_cost*review_rate,
                             'error_loss_usd_per_slot':loss*(1-accuracy),
                             'total_expected_usd_per_slot':total,
                             'break_even_review_usd_vs_best_automated':threshold,
                             'cheaper_than_best_automated_at_assumptions':total<baseline_cost-TIE_ABS_USD,
                             'basis':'hypothetical human analytical expectation'}
            allrows={**baselines,**rows}
            winner=consistent_winner({r: allrows[r]['total_expected_usd_per_slot'] for r in ROUTES}, ROUTES)
            out_profiles.append({'D':d,'C':c,'F':f,'comparison':rows,
                                 'minimum_expected_cost_route_at_assumptions':winner,
                                 'minimum_expected_cost_usd_per_slot':allrows[winner]['total_expected_usd_per_slot']})
        result['routes'][role]={'source_slots':n,'distinct_e1_sources':270,'observed_confusion':observed,
                               'automated_baselines':baselines,
                               'best_automated_at_assumptions':baseline_best,
                               'profiles':out_profiles}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('e1-dir','e2-dir','audit-report','stage1-report','report'):
        p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--error-loss-usd',type=float,required=True,help='ASSUMED equal loss per incorrect result; not empirical')
    p.add_argument('--review-cost-usd',type=float,required=True,help='ASSUMED human cost per routed review; not empirical')
    a=p.parse_args()
    import sys
    root=Path(__file__).resolve().parent.parent
    sys.path.insert(0,str(root))
    from src.e1_score import score_run
    verify_frozen_audit(a.e1_dir,a.e2_dir,a.audit_report)
    weak,strong,verdicts=build_rows(a.e1_dir,a.e2_dir,score_run)
    slots=read_costed_slots(a.e1_dir,a.e2_dir,weak,strong,verdicts)
    output=analyze(load(a.stage1_report),slots,a.error_loss_usd,a.review_cost_usd)
    output['inputs']={'audit_report_sha256':hashlib.sha256(a.audit_report.read_bytes()).hexdigest(),
                      'stage1_report_sha256':hashlib.sha256(a.stage1_report.read_bytes()).hexdigest()}
    a.report.parent.mkdir(parents=True,exist_ok=True)
    with a.report.open('x',encoding='utf-8') as stream:
        json.dump(output,stream,indent=2,allow_nan=False)
        stream.write('\n')
    print('Status:',output['status'])
    for role,s in output['routes'].items():
        print(role,'slots=',s['source_slots'],'FAIL=',s['observed_confusion']['FAIL'],
              'best_automated=',s['best_automated_at_assumptions'])
    print('Report:',a.report)

if __name__=='__main__':
    main()
