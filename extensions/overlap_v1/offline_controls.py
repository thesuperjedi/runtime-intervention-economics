"""PUBLIC ADAPTER: read-only projection integrity, identities and dependencies.
Not a recovery runner. No approvals, SDK, credentials or execution capability.
"""
import json,hashlib
from pathlib import Path
from extensions.overlap_v1.prepare import ROOT,DEFAULT_FROZEN,load,sha
def require(ok,message):
    if not ok:raise ValueError(message)
def inventory(folder):
    return {p.name:sha(p) for p in sorted(Path(folder).iterdir()) if p.is_file()}
def usable(r):
    return bool(r and r.get('success') is True and r.get('response_valid') is True and r.get('provider_completed') is True)
def preflight():
    raw=ROOT/'data/raw/extension_overlap_v1'
    inv=load(ROOT/'extensions/overlap_v1/record_inventory_final720_v1.json')['records_sha256']
    require(len(inv)==720 and inventory(raw)==inv,'public EX1 projection inventory')
    jobs=load(DEFAULT_FROZEN/'execution_manifest_v1.json')['jobs']
    require(len(jobs)==len({j['run_id'] for j in jobs})==720,'manifest duplicates/population')
    records={p.stem:load(p) for p in raw.iterdir()}
    require(set(records)=={j['run_id'] for j in jobs},'manifest identities')
    cases={x['case_id']:x for x in load(DEFAULT_FROZEN/'canonical_cases_v1.json')}
    renderings={x['rendering_id']:x for x in load(DEFAULT_FROZEN/'renderings_v1.json')}
    require(len(cases)==60 and len(renderings)==180,'case/rendering population')
    config=load(DEFAULT_FROZEN/'execution_config_v1.json')
    for j in jobs:
        r=records[j['run_id']]
        require(r['run_id']==j['run_id'] and r['job']==j,'record/job identity')
        require(r.get('public_projection_schema')=='research-observation-1.0','projection schema')
        require(renderings[j['rendering_id']]['case_id']==j['case_id'] and j['case_id'] in cases,'case join')
        for dep in j['dependencies']:
            require(dep in records and usable(records[dep]),'dependency validity')
        if j['role'].endswith('validator'):
            require(r['job']['source_cheap_run_id']==j['source_cheap_run_id'] and r['job']['paired_strong_run_id']==j['paired_strong_run_id'],'validator pairing')
        req=r['request'];role=j['role']
        require(req['model']==config['models'][role] and req['generation_config']==config['inference'],'model/settings')
        require(req['store'] is False,'store policy')
        schema=config['response_schemas']['validator' if role.endswith('validator') else 'solver']
        require(req['response_format']==dict(type='text',mime_type='application/json',schema=schema),'response schema')
        retry=r['retry_policy']
        require(retry['intended']['automatic_retry'] is False and retry['effective_sdk']['interactions_max_retries']==0
                and retry['effective_sdk']['http_retry_options']['attempts']==0,'recorded retry policy')
        require(r['http_execution']['attempt_count'] is None and r['http_execution']['attempt_count_instrumented'] is False,'attempt telemetry')
        if r['success']:
            require(usable(r) and isinstance(r.get('usage'),dict),'successful schema/usage')
            parsed=json.loads(r['response_text'])
            require(parsed==r['parsed_response'],'text/parsed mismatch')
            if j['role'].endswith('validator'):
                require(set(parsed)=={'verdict'} and parsed['verdict'] in ('PASS','FAIL'),'validator schema')
            else:
                require(set(parsed)=={'controls'} and isinstance(parsed['controls'],list) and all(isinstance(x,str) for x in parsed['controls']),'solver schema')
        else:
            require(r.get('failure',{}).get('http_status')==503 and r.get('usage') is None and r.get('estimated_cost_usd') is None,'terminal failure/unknown cost')
    return dict(raw_dir=raw,records=records,jobs=jobs,cases=cases,renderings=renderings,
                design_hash=sha(DEFAULT_FROZEN/'design_manifest_v1.json'),control_hash=None),dict(public_projection_hashes_verified=720)
