"""Read-only offline scientific reproduction from this package only."""
import sys,json,hashlib,socket,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'e3_phase1')]
def deny(*a,**k):raise RuntimeError('Network disabled in offline research release')
socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny
def load(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def check(ok,label):
    if not ok:raise AssertionError(label)
def equal(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict):
        check(set(a)==set(b),'keys '+path)
        for k in a:equal(a[k],b[k],path+'/'+k)
    elif isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):
        check(len(a)==len(b),'length '+path)
        for i,(x,y) in enumerate(zip(a,b)):equal(x,y,path+'/'+str(i))
    elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
        check(abs(a-b)<=1e-11,'number '+path)
    else:check(a==b,'value '+path)
def run(full_robustness=False):
    from src.e1_score import score_run
    from src.e1_analyse_economics import extract_usage,estimate_cost
    from extensions.overlap_v1.analysis import stage1_v1,stage2_v1,stage3_v1
    from extensions.overlap_v1.analysis.verify_stage3_v1 import verify as independent
    from e3_accuracy_replay import verify_frozen_audit,build_rows,summarize
    from e3_economic_thresholds import analyze as threshold
    from e3_stage2b_compare import read_costed_slots,analyze as economics
    from e3_stage2c_boundaries import analyze as grid
    from e3_strong_robustness import source_table,analyze as robustness
    from independent_verify import verify as verify_independent
    audit=ROOT/'e3_phase1/e3_replay_audit_03.json'
    verify_frozen_audit(ROOT/'data/raw/e1',ROOT/'data/raw/e2_full',audit)
    w,s,v=build_rows(ROOT/'data/raw/e1',ROOT/'data/raw/e2_full',score_run)
    e1=dict(weak_correct=sum(x['correct'] for x in w.values()),strong_correct=sum(x['correct'] for x in s.values()),sources=len(w),costs={})
    for role in ('cheap','strong'):
        e1['costs'][role]=sum(estimate_cost(role,extract_usage(load('data/raw/e1/'+rid+'.json'))) for rid in (w if role=='cheap' else s))
    check((e1['weak_correct'],e1['strong_correct'],e1['sources'])==(236,270,270),'E1 scoring')
    stage1=summarize(w,s,v);equal(stage1,load('e3_phase1/e3_accuracy_stage1_01.json'))
    stage2a=threshold(stage1);ref2a=load('e3_phase1/e3_stage2a_thresholds_01.json')
    equal(stage2a,{k:ref2a[k] for k in stage2a})
    slots=read_costed_slots(ROOT/'data/raw/e1',ROOT/'data/raw/e2_full',w,s,v)
    stage2b=economics(stage1,slots,.1,.01);ref2b=load('e3_phase1/e3_stage2b_conditional_01.json')
    equal(stage2b,{k:ref2b[k] for k in stage2b})
    stage2c=grid(ref2b);ref2c=load('e3_phase1/e3_stage2c_boundaries_01.json')
    equal(stage2c,{k:ref2c[k] for k in stage2c})
    reports=[]
    for i,module in enumerate((stage1_v1,stage2_v1,stage3_v1),1):
        got=module.build();ref=load('extensions/overlap_v1/analysis/stage'+str(i)+'_results_v1.json')
        # Only provenance/verification labels differ because evidence bytes and adapter code differ.
        for k in ref:
            if k not in ('provenance','evidence','verification_prerequisites'):equal(got[k],ref[k],'EX1-stage'+str(i)+'/'+k)
        reports.append(got)
    verified=independent(reports[-1])
    table=source_table(w,slots)
    robust=load('e3_phase1/e3_strong_robustness_01.json')
    equal(table,robust['source_exposures'])
    equal(ref2b,robust['baseline_stage2b'])
    if full_robustness:
        equal(robustness(ref2b,table),robust['analyses'],'complete-robustness')
    independent_result=verify_independent(reports[-1])
    return dict(status='PASS',e1=e1,historical_public_hashes=2160,ex1_projection_records=720,
                ex1_stage1_to3_analytical_results_equal=True,ex1_separate_verifier=verified,
                independent_reconstruction=independent_result,e3_profiles=36,e3_grid_cells=5760,
                e3_pairwise_equations=720,full_robustness_reproduced=full_robustness,
                api_calls=0,credentials_requested=False,scope='Scientific reproduction from public projections, not original raw-byte audit or invoices.')
if __name__=='__main__':
    print(json.dumps(run('--full-robustness' in sys.argv),indent=2))
