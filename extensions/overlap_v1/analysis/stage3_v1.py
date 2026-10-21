"""EX1 Stage3 economic reconstruction. Exact rational arithmetic; offline only."""
import argparse
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path
from extensions.overlap_v1.prepare import ROOT,load,sha,write_new
from extensions.overlap_v1 import offline_controls as controls
from extensions.overlap_v1.analysis.verify_stage2_v1 import verify as verify_stage2

BASE=Path(__file__).parent
GRID=['0','.001','.005','.008','.01','.02','.05','.1','.5','1']
ROUTES=('weak_only','strong_only','cheap_validator_cascade','strong_validator_cascade')


def require(x,message):
    if not x:raise ValueError(message)


def cost(record):
    u=record.get('usage')
    if not isinstance(u,dict):return None
    fields=('total_input_tokens','total_output_tokens','total_thought_tokens',
            'total_tokens','total_cached_tokens','total_tool_use_tokens')
    require(all(type(u.get(k)) is int and u[k]>=0 for k in fields),'unusable token counters')
    i,o,t,total,cache,tool=(u[k] for k in fields)
    require(i+o+t==total and not cache and not tool,'unsupported accounting category')
    ir,orr=(F(3,10),F(5,2)) if record['job']['role'] in ('cheap','cheap_validator') else (F(3,4),F(15,4))
    answer=(i*ir+(o+t)*orr)/1000000
    require(record['estimated_cost_usd'] is not None and abs(float(answer)-record['estimated_cost_usd'])<1e-15,
            'persisted cost mismatch')
    return answer


def winners(lines,L):
    values={name:intercept+L*slope for name,(intercept,slope) in lines.items()}
    minimum=min(values.values())
    return [name for name in lines if values[name]==minimum]


def economics(lines,n,loss_grid=GRID):
    grid=[]
    for value in loss_grid:
        L=F(value);values={name:c+L*e for name,(c,e) in lines.items()}
        ordered=sorted(set(values.values()))
        grid.append(dict(error_loss_usd=float(L),strategies={name:dict(
            expected_usd_per_result=float(v),expected_usd_for_population=float(v*n),
            signed_difference_vs_strong_usd_per_result=float(v-values['strong_only']),
            signed_difference_vs_strong_population_usd=float((v-values['strong_only'])*n))
            for name,v in values.items()},winner_labels=winners(lines,L),
            ranking_tiers=[[name for name in lines if values[name]==v] for v in ordered],
            margin_to_next_distinct_usd_per_result=float(ordered[1]-ordered[0]) if len(ordered)>1 else None))
    boundaries=[]
    points={F(0)}
    for a,b in combinations(lines,2):
        ca,ea=lines[a];cb,eb=lines[b]
        if ea==eb:
            boundaries.append(dict(routes=[a,b],kind='identical_lines' if ca==cb else 'parallel_no_crossing',
                lower_cost_route=None if ca==cb else a if ca<cb else b))
            continue
        L=(cb-ca)/(ea-eb)
        if L>=0:points.add(L)
        global_winners=winners(lines,L) if L>=0 else []
        boundaries.append(dict(routes=[a,b],kind='point_equality',error_loss_usd=float(L),
            exact_error_loss_fraction=str(L),nonnegative_domain=L>=0,
            on_global_minimum=L>=0 and a in global_winners and b in global_winners,
            global_winner_labels=global_winners))
    ordered=sorted(points)
    intervals=[]
    for i,lo in enumerate(ordered):
        hi=ordered[i+1] if i+1<len(ordered) else None
        label=winners(lines,(lo+hi)/2 if hi is not None else lo+1)
        if intervals and intervals[-1]['winner_labels']==label:
            intervals[-1]['upper_exclusive_usd']=float(hi) if hi is not None else None
        else:
            intervals.append(dict(lower_exclusive_usd=float(lo),upper_exclusive_usd=float(hi) if hi is not None else None,
                winner_labels=label))
    return dict(loss_grid=grid,pairwise_boundaries=boundaries,
        optimal_open_intervals=intervals,winners_at_zero=winners(lines,F(0)),
        tie_policy='Exact rational equality. Report all global minima; no priority/tolerance tie-breaking.',
        equations='J_route(L)=mean estimated API cost + L*(1-observed/reconstructed accuracy).',
        domain='L>=0; no extrapolation of empirical error probabilities.')


def population(context,pairs,slots,caseids,roles=ROUTES):
    selected=[p for p in pairs if p['case_id'] in caseids]
    require(len(selected)==3*len(caseids),'incomplete primary case triplets')
    jobs={(j['rendering_id'],j['role']):j for j in context['jobs']}
    byslot={(r['rendering_id'],r['validator_role']):r for r in slots}
    rows={role:[] for role in roles}
    for pair in selected:
        rid=pair['rendering_id']
        wr=context['records'][jobs[(rid,'cheap')]['run_id']]
        sr=context['records'][jobs[(rid,'strong')]['run_id']]
        wc,sc=cost(wr),cost(sr)
        require(wc is not None and sc is not None,'unknown solver cost')
        for route in roles:
            components=dict(weak=F(0),validator=F(0),escalation=F(0),strong_only=F(0))
            verdict=None;used=[]
            if route=='weak_only':
                components['weak']=wc;correct=pair['weak_correct'];used=[wr['run_id']]
            elif route=='strong_only':
                components['strong_only']=sc;correct=pair['strong_correct'];used=[sr['run_id']]
            else:
                role='cheap_validator' if route=='cheap_validator_cascade' else 'strong_validator'
                slot=byslot[(rid,role)]
                require(slot['status']=='valid' and slot['verdict'] in ('PASS','FAIL'),'unresolved route')
                vr=context['records'][slot['run_id']];vc=cost(vr)
                require(vc is not None,'unknown validator cost')
                verdict=slot['verdict'];components['weak']=wc;components['validator']=vc
                used=[wr['run_id'],vr['run_id']]
                if verdict=='FAIL':components['escalation']=sc;used.append(sr['run_id'])
                correct=pair['weak_correct'] if verdict=='PASS' else pair['strong_correct']
            rows[route].append(dict(case_id=pair['case_id'],rendering_id=rid,correct=correct,verdict=verdict,
                charged_run_ids=used,components_usd={k:float(v) for k,v in components.items()},
                api_cost_usd=float(sum(components.values()))))
    summaries={};lines={};n=len(selected)
    for route,rr in rows.items():
        total=sum(F(str(r['api_cost_usd'])) for r in rr)
        # Reconstruct exactly from charged raw calls; float row values are presentation only.
        total=sum((sum((cost(context['records'][rid]) for rid in row['charged_run_ids']),F(0)) for row in rr),F(0))
        nc=sum(r['correct'] for r in rr)
        mean=total/n;error=F(n-nc,n);lines[route]=(mean,error)
        component_totals={key:sum(F(str(r['components_usd'][key])) for r in rr)
                          for key in ('weak','validator','escalation','strong_only')}
        summaries[route]=dict(canonical_cases=len(caseids),evaluated_renderings=n,correct_results=nc,
            incorrect_results=n-nc,accuracy=nc/n,api_cost_total_usd=float(total),
            api_cost_usd_per_evaluated_result=float(mean),
            case_weighting='Equal case weights after averaging3 renderings; equals rendering mean on complete triplets.',
            cost_per_correct_complete_resolved_usd=float(total/nc) if nc else None,
            cost_per_correct_denominator=nc,
            cost_per_correct_interpretation='Total reconstructed route cost / correct results on this complete-case resolved population; not unconditional operational cost per correct.',
            component_totals_usd={k:float(v) for k,v in component_totals.items()},
            hypothetical_model_invocations=sum(len(r['charged_run_ids']) for r in rr),
            reconstructed_escalations=sum(r['verdict']=='FAIL' for r in rr))
    return dict(case_ids=sorted(caseids),canonical_cases=len(caseids),evaluated_renderings=n,
                strategies=summaries,economics=economics(lines,n),route_rows=rows)


def build():
    for stage in ('stage1','stage2'):
        manifest=load(BASE/(stage+'_analysis_manifest_v1.json'))
        for name,h in manifest['files_sha256'].items():
            require(sha(BASE/name)==h,'prior analytical artifact changed: '+name)
    stage1=load(BASE/'stage1_results_v1.json');stage2=load(BASE/'stage2_results_v1.json')
    verified=verify_stage2(stage2)
    context,pf=controls.preflight()
    raw_before=controls.inventory(context['raw_dir'])
    pairs=stage1['rendering_pairs'];slots=stage2['slots']
    common=set(stage2['evidence']['common_complete_case_ids'])
    primary=population(context,pairs,slots,common)
    supplement=population(context,pairs,slots,set(context['cases']),
        ('weak_only','strong_only','cheap_validator_cascade'))
    research={}
    for role in ('cheap','strong','cheap_validator','strong_validator'):
        rr=[r for r in context['records'].values() if r['job']['role']==role]
        known=[cost(r) for r in rr if r.get('usage') is not None]
        research[role]=dict(actual_logical_attempts=len(rr),successful_responses=sum(r['success'] for r in rr),
            known_token_estimate_usd=float(sum(known,F(0))),unknown_cost_count=sum(r.get('usage') is None for r in rr),
            actual_provider_charge_usd=None)
    # Historical comparator is a separate already-verified cohort, never pooled.
    historical_path=ROOT/'e3_phase1/e3_stage2b_conditional_01.json'
    historical=load(historical_path)
    historical_routes={role:dict(source_slots=data['source_slots'],distinct_e1_sources=data['distinct_e1_sources'],
        observed_confusion=data['observed_confusion'],automated_baselines=data['automated_baselines'])
        for role,data in historical['routes'].items()}
    require(controls.inventory(context['raw_dir'])==raw_before,'raw evidence changed')
    return dict(version='EX1-STAGE3-1.0',scope='Economic analysis only; no final E0-E3 synthesis.',
        provenance=dict(design_sha256=context['design_hash'],control_sha256=None,
            raw_inventory_sha256=sha(ROOT/'extensions/overlap_v1/record_inventory_final720_v1.json'),
            stage1_results_sha256=sha(BASE/'stage1_results_v1.json'),stage2_results_sha256=sha(BASE/'stage2_results_v1.json'),
            historical_comparison_sha256=sha(historical_path),analysis_sha256=sha(Path(__file__)),
            verifier_sha256=sha(BASE/'verify_stage3_v1.py'),tests_sha256=sha(BASE/'test_stage3_v1.py')),
        verification_prerequisites=verified,
        accounting=dict(currency='USD',basis='Frozen normalized input plus output+thought list-price estimates; not invoice verified.',
            rates_per_million=dict(cheap_input=.30,cheap_output_plus_thought=2.50,strong_input=.75,strong_output_plus_thought=3.75),
            invocation_level_counters_added=False,invoice_verified=False,
            research_vs_routes='Research incurred all720 logical attempts. Reconstructed route charges only its listed run IDs; conditional strong answer distinct from strong-validator call.',
            error_loss='Assumed equal monetary loss per wrong final control set; not empirically measured harm.'),
        primary_common58=primary,supplementary_cheap60=supplement,
        research_expenditure=dict(by_role=research,known_token_derived_usd=sum(r['known_token_estimate_usd'] for r in research.values()),
            actual_logical_attempts=720,unknown_charge_run_ids=sorted(rid for rid,r in context['records'].items() if r.get('usage') is None),
            actual_provider_charges=None),
        historical_comparison=dict(source=str(historical_path.relative_to(ROOT)),population='Historical E1:30 canonical cases,90 renderings,270 source realizations; E2:3 validator repetitions,810 slots per role.',
            routes=historical_routes,no_pooling=True,
            caveats=['EX1:60 new model-blind structural cases,180 solver pairs,one validator judgment per role/rendering.',
                'E1 perfect-validator cascade is an oracle reference without an actual paid validator; not equivalent to either measured validator route.',
                'Historical solver outputs and retries differ; EX1 enforces zero SDK retries.',
                'Shared pricing convention does not equal comparable population prevalence or paired experimental evidence.']),
        exclusions=dict(primary_cases=sorted(set(context['cases'])-common),
            missing_strong_validator_slots=['X013-L1','X032-L2'],
            primary_all_strategies_exclude_all6_renderings_of_these2_cases=True,
            research_costs_retain_all_known_calls=True,no_imputed_verdict_or_escalation=True,
            unknown_costs_not_zero=True),
        limitations=['Reconstructed list-price route costs,not observed live-cascade invoices.',
            '60 or58 canonical cases;renderings not independent cases;no IID inference.',
            'Mean error-loss assumes same loss for every wrong answer and no latency/operational/human costs.',
            'All observed strong solver answers correct;strong-only loss slope0 is finite-corpus evidence.',
            'Supplementary60-case rankings must not be paired against common58 results.',
            'Exact pairwise equalities can be dominated;report global minimum intervals separately.',
            'Unknown provider charges excluded from known research estimate,not assumed zero.',
            'No API calls,frozen modifications or Stage4 synthesis.'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();write_new(a.output,build());print(a.output)


if __name__=='__main__':main()
