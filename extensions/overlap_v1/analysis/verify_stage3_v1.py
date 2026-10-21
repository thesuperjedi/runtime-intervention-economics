"""Raw-record Stage3 reproduction; independent integer token tariffs and envelope inequalities."""
import argparse
from fractions import Fraction as Q
from itertools import combinations
from pathlib import Path
import hashlib
from extensions.overlap_v1.prepare import ROOT,DEFAULT_FROZEN,load,write_new
from extensions.overlap_v1.policy_checks import authoritative,reference_controls
from extensions.overlap_v1.analysis.verify_stage2_v1 import verify as verify_stage2
BASE=Path(__file__).parent


def check(x,message):
    if not x:raise ValueError(message)


def near(a,b):
    check(abs(a-float(b))<1e-11,'numeric mismatch')


def token_cost(r):
    u=r.get('usage')
    if u is None:return None
    check(all(type(u.get(k)) is int and u[k]>=0 for k in ('total_input_tokens','total_output_tokens',
        'total_thought_tokens','total_tokens','total_cached_tokens','total_tool_use_tokens')),'usage')
    check(u['total_input_tokens']+u['total_output_tokens']+u['total_thought_tokens']==u['total_tokens']
          and not u['total_cached_tokens'] and not u['total_tool_use_tokens'],'usage accounting')
    cheap=r['job']['role'] in ('cheap','cheap_validator')
    return Q((6 if cheap else 15)*u['total_input_tokens']+
             (50 if cheap else 75)*(u['total_output_tokens']+u['total_thought_tokens']),20000000)


def optimal_regions(lines):
    """Intersect all affine inequalities directly, independently of pairwise sampling."""
    regions={}
    for name,(ci,ei) in lines.items():
        low=Q(0);high=None;possible=True
        for other,(cj,ej) in lines.items():
            d=ei-ej;rhs=cj-ci
            if d>0:high=rhs/d if high is None else min(high,rhs/d)
            elif d<0:low=max(low,rhs/d)
            elif rhs<0:possible=False
        if possible and (high is None or high>=low):
            regions[name]=(low,high)
    return regions


def verify_economics(economic,lines,n):
    for item in economic['loss_grid']:
        L=Q(str(item['error_loss_usd']))
        values={name:c+L*e for name,(c,e) in lines.items()}
        low=min(values.values())
        check(item['winner_labels']==[k for k in lines if values[k]==low],'grid winners')
        tiers=[[k for k in lines if values[k]==value] for value in sorted(set(values.values()))]
        check(item['ranking_tiers']==tiers,'rank tiers')
        for name,value in values.items():
            a=item['strategies'][name]
            near(a['expected_usd_per_result'],value);near(a['expected_usd_for_population'],value*n)
            near(a['signed_difference_vs_strong_usd_per_result'],value-values['strong_only'])
            near(a['signed_difference_vs_strong_population_usd'],(value-values['strong_only'])*n)
    check([Q(str(x['error_loss_usd'])) for x in economic['loss_grid']]==
          [Q(x) for x in ['0','.001','.005','.008','.01','.02','.05','.1','.5','1']],'loss grid')
    boundaries=economic['pairwise_boundaries']
    check(len(boundaries)==len(list(combinations(lines,2))),'boundary count')
    regions=optimal_regions(lines)
    for got,(a,b) in zip(boundaries,combinations(lines,2)):
        check(got['routes']==[a,b],'boundary pair')
        ca,ea=lines[a];cb,eb=lines[b]
        if ea==eb:
            check(got['kind']==('identical_lines' if ca==cb else 'parallel_no_crossing'),'parallel classification')
            check(got['lower_cost_route']==(None if ca==cb else a if ca<cb else b),'parallel dominance')
        else:
            L=(cb-ca)/(ea-eb)
            check(got['kind']=='point_equality' and got['exact_error_loss_fraction']==str(L),'exact boundary')
            near(got['error_loss_usd'],L)
            check(got['nonnegative_domain']==(L>=0),'boundary domain')
            minima=[k for k,(c,e) in lines.items() if c+L*e==min(cc+L*ee for cc,ee in lines.values())] if L>=0 else []
            check(got['global_winner_labels']==minima,'boundary winner labels')
            check(got['on_global_minimum']==(a in minima and b in minima),'dominated equality')
    # Independently derived regions must exactly cover each reported open winner interval.
    intervals=economic['optimal_open_intervals']
    check(intervals[0]['lower_exclusive_usd']==0 and intervals[-1]['upper_exclusive_usd'] is None,'envelope coverage')
    previous=0
    for interval in intervals:
        check(interval['lower_exclusive_usd']==previous,'envelope continuity')
        lo=Q(str(interval['lower_exclusive_usd']))
        hi=Q(str(interval['upper_exclusive_usd'])) if interval['upper_exclusive_usd'] is not None else None
        sample=(lo+hi)/2 if hi is not None else lo+1
        expected=[name for name,(lower,upper) in regions.items()
                  if lower<sample and (upper is None or sample<upper)]
        check(interval['winner_labels']==expected,'global envelope from inequalities')
        for name in expected:
            lower,upper=regions[name]
            near(interval['lower_exclusive_usd'],lower)
            if upper is None:check(interval['upper_exclusive_usd'] is None,'unbounded envelope')
            else:near(interval['upper_exclusive_usd'],upper)
        previous=interval['upper_exclusive_usd']
    at0=min(c for c,e in lines.values())
    check(economic['winners_at_zero']==[k for k,(c,e) in lines.items() if c==at0],'zero winner')


def verify(report):
    raw=ROOT/'data/raw/extension_overlap_v1'
    inv=load(ROOT/'extensions/overlap_v1/record_inventory_final720_v1.json')['records_sha256']
    check({p.name for p in raw.iterdir()}==set(inv),'raw inventory')
    for name,h in inv.items():check(hashlib.sha256((raw/name).read_bytes()).hexdigest()==h,'raw hash')
    records={name[:-5]:load(raw/name) for name in inv}
    verify_stage2(load(BASE/'stage2_results_v1.json'))
    cases={x['case_id']:x for x in load(DEFAULT_FROZEN/'canonical_cases_v1.json')}
    renders=load(DEFAULT_FROZEN/'renderings_v1.json')
    jobs={(x['rendering_id'],x['role']):x for x in load(DEFAULT_FROZEN/'execution_manifest_v1.json')['jobs']}
    def rec(rid,role):return records[jobs[(rid,role)]['run_id']]
    common={cid for cid in cases if all(
        rec(x['rendering_id'],'strong_validator')['success'] and
        rec(x['rendering_id'],'strong_validator')['response_valid']
        for x in renders if x['case_id']==cid)}
    check(len(common)==58,'common raw population')
    populations=[('primary_common58',common),('supplementary_cheap60',set(cases))]
    for key,ids in populations:
        data=report[key];check(set(data['case_ids'])==ids,'population ids')
        selected=[x for x in renders if x['case_id'] in ids];n=len(selected)
        check(data['canonical_cases']==len(ids) and data['evaluated_renderings']==n,'denominators')
        lines={}
        for route,got in data['strategies'].items():
            total=Q(0);nc=0;components={k:Q(0) for k in ('weak','validator','escalation','strong_only')}
            charged_calls=escalations=0
            for render in selected:
                rid=render['rendering_id'];case=cases[render['case_id']]
                truth=set(authoritative(case).required_controls)
                check(truth==reference_controls(case),'oracle consistency')
                w=rec(rid,'cheap');s=rec(rid,'strong')
                wcorrect=set(w['parsed_response']['controls'])==truth
                scorrect=set(s['parsed_response']['controls'])==truth
                comp={k:Q(0) for k in components};verdict=None
                if route=='weak_only':
                    comp['weak']=token_cost(w);correct=wcorrect;used=[w['run_id']]
                elif route=='strong_only':
                    comp['strong_only']=token_cost(s);correct=scorrect;used=[s['run_id']]
                else:
                    v=rec(rid,'cheap_validator' if route=='cheap_validator_cascade' else 'strong_validator')
                    check(v['success'] and v['response_valid'],'resolved validator required')
                    verdict=v['parsed_response']['verdict'];check(verdict in ('PASS','FAIL'),'verdict')
                    comp['weak']=token_cost(w);comp['validator']=token_cost(v)
                    used=[w['run_id'],v['run_id']];correct=wcorrect
                    if verdict=='FAIL':
                        comp['escalation']=token_cost(s);used.append(s['run_id']);correct=scorrect;escalations+=1
                check(len(used)==len(set(used)),'duplicate charged invocation')
                row=next(x for x in data['route_rows'][route] if x['rendering_id']==rid)
                check(row['correct']==correct and row['verdict']==verdict and row['charged_run_ids']==used,'route reconstruction')
                for k,v in comp.items():near(row['components_usd'][k],v);components[k]+=v
                near(row['api_cost_usd'],sum(comp.values()))
                nc+=correct;total+=sum(comp.values());charged_calls+=len(used)
            check(got['correct_results']==nc and got['incorrect_results']==n-nc,'correctness')
            near(got['accuracy'],Q(nc,n));near(got['api_cost_total_usd'],total)
            near(got['api_cost_usd_per_evaluated_result'],total/n)
            if nc:near(got['cost_per_correct_complete_resolved_usd'],total/nc)
            else:check(got['cost_per_correct_complete_resolved_usd'] is None,'zero correct denominator')
            check(got['cost_per_correct_denominator']==nc,'cost/correct denominator')
            for k,v in components.items():near(got['component_totals_usd'][k],v)
            check(got['hypothetical_model_invocations']==charged_calls and got['reconstructed_escalations']==escalations,'route calls')
            lines[route]=(total/n,Q(n-nc,n))
        verify_economics(data['economics'],lines,n)
    known=Q(0);unknown=[]
    for rid,r in records.items():
        value=token_cost(r)
        if value is None:unknown.append(rid)
        else:known+=value
    near(report['research_expenditure']['known_token_derived_usd'],known)
    check(sorted(unknown)==report['research_expenditure']['unknown_charge_run_ids'],'unknown charges')
    check(report['research_expenditure']['actual_logical_attempts']==720,'actual attempts')
    return dict(status='PASS',public_projection_hashes_verified=720,primary_cases=58,primary_renderings=174,
        supplementary_cases=60,supplementary_renderings=180,
        independent_integer_tariff_reconstruction=True,route_calls_costs_accuracy_verified=True,
        exact_pairwise_boundaries_verified=9,global_envelope_verified_by_affine_inequalities=True,
        unknown_charge_records=len(unknown),api_calls=0,
        independence='Separate computational verifier; no independent human examination claimed.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=verify(load(a.input));write_new(a.output,result);print(result)


if __name__=='__main__':main()
