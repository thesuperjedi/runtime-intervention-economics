"""Separate public-record reconstruction: no imports of primary analysis/scoring."""
import json
from pathlib import Path
from fractions import Fraction as Q
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parent
def load(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def check(x,label):
    if not x:raise AssertionError(label)

def historical():
    from extensions.overlap_v1.policy_checks import reference_controls
    cases={x['case_id']:x for x in load('data/e1/canonical_cases.json')}
    raw={p.stem:json.loads(p.read_text()) for p in (ROOT/'data/raw/e1').glob('*.json')}
    scores={k:r['success'] and set(r['parsed_response']['controls'])==reference_controls(cases[r['case_id']]) for k,r in raw.items()}
    def cost(r,cheap):
        u=r['usage']
        return Q((6 if cheap else 15)*u['total_input_tokens']+(50 if cheap else 75)*(u['total_output_tokens']+u['total_thought_tokens']),20000000)
    weak={k:r for k,r in raw.items() if r['model_role']=='cheap'}
    check(len(raw)==540 and len(weak)==270,'E1 population')
    check(sum(scores[k] for k in weak)==236 and sum(scores[k] for k in raw if k not in weak)==270,'E1 truth')
    perfect=sum((cost(r,True)+(cost(raw[k.replace('-cheap-','-strong-')],False) if not scores[k] else 0) for k,r in weak.items()),Q(0))
    oracle=sum((cost(r,True) if scores[k] else cost(raw[k.replace('-cheap-','-strong-')],False) for k,r in weak.items()),Q(0))
    check(perfect==Q(15597065,100000000) and oracle==Q(14397755,100000000),'ideal E1 route costs')
    out={}
    for role in ('cheap_validator','strong_validator'):
        cm=Counter();money=Q(0);correct=0
        for path in (ROOT/'data/raw/e2_full').glob('*.json'):
            r=json.loads(path.read_text())
            if r['validator_role']!=role:continue
            src=r['source_cheap_run_id'];peer=r['paired_strong_run_id'];passed=r['parsed_response']['verdict']=='PASS';w=scores[src]
            cm[('TA' if w else 'FA') if passed else ('FR' if w else 'TR')]+=1
            correct+=w if passed else scores[peer]
            money+=cost(raw[src],True)+cost(r,role=='cheap_validator')+(0 if passed else cost(raw[peer],False))
        check(sum(cm.values())==810,'E2 population')
        check(cm['FA']==(25 if role=='cheap_validator' else 0) and cm['FR']==(6 if role=='cheap_validator' else 0),'E2 errors')
        ref=load('e3_phase1/e3_stage2b_conditional_01.json')['routes'][role]['automated_baselines']['weak_validator_strong_on_fail']
        check(abs(float(money/810)-ref['api_cost_usd_per_slot'])<1e-12 and abs(correct/810-ref['accuracy'])<1e-12,'E2 cost/correct')
        out[role]=dict(confusion=dict(cm),slots=810,cascade_correct=correct,cascade_total_usd=float(money))
    return dict(E1_weak_correct=236,E1_strong_correct=270,E1_denominator=270,perfect_validator_estimate_usd=float(perfect),oracle_routing_estimate_usd=float(oracle),E2=out)

def verify(report):
    from extensions.overlap_v1.policy_checks import reference_controls
    cases={x['case_id']:x for x in load('extensions/overlap_v1/frozen/canonical_cases_v1.json')}
    rows={p.stem:json.loads(p.read_text()) for p in (ROOT/'data/raw/extension_overlap_v1').glob('*.json')}
    jobs=load('extensions/overlap_v1/frozen/execution_manifest_v1.json')['jobs']
    check(set(rows)=={x['run_id'] for x in jobs} and len(rows)==720,'inventory')
    scores={};costs={};status=Counter()
    for rid,r in rows.items():
        j=r['job'];role=j['role'];status[(role,r['success'])]+=1
        if role in ('cheap','strong'):
            scores[rid]=r['success'] and set(r['parsed_response']['controls'])==reference_controls(cases[j['case_id']])
        u=r.get('usage')
        if u is None:costs[rid]=None;continue
        cheap=role in ('cheap','cheap_validator')
        costs[rid]=Q((6 if cheap else 15)*u['total_input_tokens']+(50 if cheap else 75)*(u['total_output_tokens']+u['total_thought_tokens']),20000000)
    check(sum(v for (r,s),v in status.items() if s)==718,'success count')
    populations={}
    for role in ('cheap_validator','strong_validator'):
        cm=Counter();eligible=[]
        for cid in cases:
            rr=[x for x in rows.values() if x['job']['case_id']==cid and x['job']['role']==role]
            if len(rr)==3 and all(x['success'] and x['response_valid'] for x in rr):eligible.append(cid)
        populations[role]=eligible
        for r in rows.values():
            j=r['job']
            if j['role']!=role or not r['success']:continue
            correct=scores[j['source_cheap_run_id']];passed=r['parsed_response']['verdict']=='PASS'
            cm[('TA' if correct else 'FA') if passed else ('FR' if correct else 'TR')]+=1
        check(dict(cm)==({'TA':128,'FA':24,'TR':25,'FR':3} if role=='cheap_validator' else {'TA':129,'TR':49}),'full validator confusion')
    common=set(populations['cheap_validator'])&set(populations['strong_validator'])
    check(len(common)==58,'common complete cases')
    route_correct={};route_cost={}
    for route in ('weak_only','strong_only','cheap_validator_cascade','strong_validator_cascade'):
        correct=0;total=Q(0)
        for j in jobs:
            if j['role']!='cheap' or j['case_id'] not in common:continue
            wr=j['run_id'];sr=j['paired_strong_run_id']
            if route=='weak_only':correct+=scores[wr];total+=costs[wr]
            elif route=='strong_only':correct+=scores[sr];total+=costs[sr]
            else:
                role='cheap_validator' if route=='cheap_validator_cascade' else 'strong_validator'
                vr=next(x for x in rows.values() if x['job']['rendering_id']==j['rendering_id'] and x['job']['role']==role)
                failed=vr['parsed_response']['verdict']=='FAIL'
                correct+=scores[sr] if failed else scores[wr]
                total+=costs[wr]+costs[vr['run_id']]+(costs[sr] if failed else 0)
        got=report['primary_common58']['strategies'][route]
        check(correct==got['correct_results'],'route correctness')
        check(abs(float(total)-got['api_cost_total_usd'])<1e-13,'route cost')
        route_correct[route]=correct;route_cost[route]=total
    cut=(route_cost['strong_only']-route_cost['weak_only'])/49
    check(cut==Q(1888393,490000000),'global threshold')
    known=sum((x for x in costs.values() if x is not None),Q(0))
    check(known==Q(7291317,10000000) and sum(x is None for x in costs.values())==2,'research charges')
    return dict(status='PASS',historical=historical(),canonical_cases=60,common_cases=58,common_renderings=174,
                route_correct=route_correct,route_cost_usd={k:float(v) for k,v in route_cost.items()},
                exact_weak_strong_boundary=str(cut),known_research_usd=float(known),unknown_charge_records=2)
