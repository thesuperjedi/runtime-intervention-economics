"""Model-blind, offline preparation. Creates a NEW immutable versioned artifact set."""
import argparse
import ast
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path

from extensions.overlap_v1.policy_checks import (
    FIELDS, authoritative, check_rendering, exhaustive_oracle_check, reference_controls,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
SEED = 20261019
STRATA = ('threshold_boundaries', 'multiple_obligations', 'scoped_exceptions',
          'nonwaivable_controls', 'terminal_precedence', 'combined_interactions')
ROLES = ('cheap', 'strong', 'cheap_validator', 'strong_validator')
LEVELS = ('L1', 'L2', 'L3')
DEFAULT_FROZEN = BASE / 'frozen'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        if isinstance(value, str): stream.write(value)
        else: stream.write(json.dumps(value, indent=2, allow_nan=False)+'\n')


def signature(c):
    a, m = c['amount_usd'], c['contract_months']
    d, p = c['data_classification'], c['deployment']
    info = ('restricted_external' if d == 'restricted' and p == 'external_saas' else
            'restricted_internal' if d == 'restricted' else
            'confidential_external' if d == 'confidential' and p == 'external_saas' else
            'no_information_control')
    return (0 if a < 50000 else 1 if a == 50000 else 2 if a < 100000 else 3 if a == 100000 else 4,
            c['vendor_status'], info, 0 if m < 24 else 1 if m == 24 else 2, c['exception_scope'])


def stratum(c):
    v, scope, info = c['vendor_status'], c['exception_scope'], signature(c)[2]
    controls = reference_controls(c)
    # Ordered mutually exclusive predicates, frozen before model execution.
    if v == 'prohibited': return 'terminal_precedence'
    if scope != 'none' and 'SECURITY_REVIEW' in controls and c['contract_months'] > 24:
        return 'nonwaivable_controls'
    if scope != 'none' and v == 'unapproved' and (
            info in ('restricted_internal', 'confidential_external')
            or (info == 'restricted_external' and scope == 'both')):
        return 'combined_interactions'
    suppressed = ((v == 'unapproved' and scope in ('vendor', 'both'))
                  or (info == 'restricted_external' and scope in ('external_restricted_data', 'both')))
    if suppressed: return 'scoped_exceptions'
    if scope == 'none':
        if c['amount_usd'] in (50000, 100000) or c['contract_months'] == 24:
            return 'threshold_boundaries'
        if len(controls) >= 3: return 'multiple_obligations'
    return None


def candidate_pool(historical):
    # Excludes even historical signatures with the financial coordinate removed:
    # no selected case can be just an amount/name variant of an old case.
    old_nonfinancial = {signature(c)[1:] for c in historical}
    unique = {}
    for a, v, d, p, m, scope in itertools.product(
            (40000, 50000, 75000, 100000, 125000),
            ('approved', 'unapproved', 'prohibited'),
            ('public', 'confidential', 'restricted'), ('internal', 'external_saas'),
            (12, 24, 36), ('none', 'vendor', 'external_restricted_data', 'both')):
        c = dict(zip(FIELDS, (a, v, d, p, m, 'none' if scope == 'none' else 'approved', scope)))
        key = signature(c)
        if key[1:] in old_nonfinancial: continue
        unique.setdefault(key, c)  # First product-order representative of policy-equivalent facts.
    pool = []
    for key, c in sorted(unique.items()):
        c = dict(c, candidate_id='CP-'+digest(key)[:16], structural_signature=list(key),
                 stratum=stratum(c))
        controls = sorted(authoritative(c).required_controls)
        if set(controls) != reference_controls(c): raise ValueError('candidate oracle mismatch')
        c['oracle_controls'] = controls
        pool.append(c)
    if len({c['candidate_id'] for c in pool}) != len(pool): raise ValueError('candidate collision')
    return pool


def select_cases(pool, seed=SEED):
    selected = []
    for group in STRATA:
        eligible = [c for c in pool if c['stratum'] == group]
        ranked = sorted(eligible, key=lambda c: hashlib.sha256(
            f"{seed}|{group}|{c['candidate_id']}".encode()).hexdigest())
        if len(ranked) < 10: raise ValueError(f'insufficient model-blind pool: {group}')
        for c in ranked[:10]:
            selected.append(dict(c, selection_rank_sha256=hashlib.sha256(
                f"{seed}|{group}|{c['candidate_id']}".encode()).hexdigest(),
                case_id=f'X{len(selected)+1:03d}'))
    return selected


def render(c, level):
    amount = f"{c['amount_usd']:,}"
    v, d, m = c['vendor_status'], c['data_classification'], c['contract_months']
    deployment = 'will be deployed internally' if c['deployment'] == 'internal' else 'will use an external SaaS deployment'
    exception = ('No exception has been approved.' if c['exception_status'] == 'none' else
                 f"An approved exception is explicitly limited to {c['exception_scope']}.")
    if level == 'L1':
        text = (f"The purchase costs USD {amount}. The supplier is {v}. The information is classified as {d}. "
                f"The service {deployment}. The agreement is for {m} months. {exception}")
    elif level == 'L2':
        text = (f"The procurement team proposes a {m}-month agreement, valued at USD {amount}, "
                f"with a supplier whose status is {v}. The information is classified as {d}, "
                f"and the service {deployment}. {exception}")
    elif level == 'L3':
        text = (f"The operations team has assembled a request for its regional workflow. "
                f"The service {deployment}, and the information is classified as {d}. "
                f"The supplier is {v}. The commercial note records a {m}-month agreement "
                f"and a total purchase value of USD {amount}. {exception}")
    else: raise ValueError('unknown rendering level')
    result = dict(rendering_id=c['case_id']+'-'+level, case_id=c['case_id'],
                  rendering_level=level, text=text)
    check_rendering(c, result)
    return result


def historical_prompt_templates():
    """PUBLIC ADAPTER: frozen literal templates; execution modules intentionally absent."""
    return load(DEFAULT_FROZEN/'prompt_templates_v1.json')


def schemas(allowed):
    return dict(
        solver={'type':'object','properties':{'controls':{'type':'array',
                'items':{'type':'string','enum':allowed},'uniqueItems':True}},
                'required':['controls'],'additionalProperties':False},
        validator={'type':'object','properties':{'verdict':{'type':'string','enum':['PASS','FAIL']}},
                   'required':['verdict'],'additionalProperties':False})


def jobs(cases):
    # Randomized deterministic BLOCK order; within each block both solver results
    # precede validator requests. Never depends on oracle or model correctness.
    blocks = [(c['case_id'], level) for c in cases for level in LEVELS]
    blocks.sort(key=lambda x: digest([SEED, 'block-order', x]))
    result = []
    for case, level in blocks:
        solver_ids = {r:f'EX1-{case}-{level}-{r}-R001' for r in ('cheap', 'strong')}
        for roles in (('cheap','strong'), ('cheap_validator','strong_validator')):
            ordered = sorted(roles, key=lambda r: digest([SEED, case, level, r]))
            for role in ordered:
                result.append(dict(run_id=solver_ids[role] if role in solver_ids else
                                   f'EX1-{case}-{level}-{role}-R001',
                                   case_id=case, rendering_id=case+'-'+level, role=role, repetition=1,
                                   source_cheap_run_id=solver_ids['cheap'],
                                   paired_strong_run_id=solver_ids['strong'],
                                   dependencies=[] if role in solver_ids else list(solver_ids.values())))
    if len(result) != 720 or len({j['run_id'] for j in result}) != 720:
        raise ValueError('planned identity mismatch')
    return result


def budget():
    prices = {'cheap':(.30,2.50),'strong':(.75,3.75),
              'cheap_validator':(.30,2.50),'strong_validator':(.75,3.75)}
    costs = defaultdict(list)
    for folder in (ROOT/'data/raw/e1', ROOT/'data/raw/e2_full'):
        for p in sorted(folder.glob('*.json')):
            r = load(p)
            role = r.get('model_role', r.get('validator_role'))
            u = r['usage']; ir, out = prices[role]
            costs[role].append((u['total_input_tokens']*ir+
                               (u['total_output_tokens']+u['total_thought_tokens'])*out)/1e6)
    stats = {role:dict(records=len(values), mean_usd=sum(values)/len(values),
                       historical_max_usd=max(values), guard_allowance_usd=5*max(values))
             for role, values in costs.items()}
    return dict(currency='USD', basis='frozen E1 normalized token-price convention; not invoice charges',
                role_statistics=stats, planned_attempts=720,
                mean_projection_usd=180*sum(s['mean_usd'] for s in stats.values()),
                historical_max_projection_usd=180*sum(s['historical_max_usd'] for s in stats.values()),
                five_times_max_projection_usd=180*sum(s['guard_allowance_usd'] for s in stats.values()),
                anticipated_allowance_usd=10., guaranteed_billing_ceiling=False,
                prospective_prices_verified=False,
                limitations=['New challenges can use more tokens; historical maxima are not bounds.',
                             'One call can exceed allowance; missing usage is not zero cost.',
                             'No invoice FX reconciliation; prospective price/model availability require confirmation.'])


def historical_inventory():
    inventory = {}
    for folder in ('config','data','e3_phase1','reports','src','tests'):
        for path in sorted((ROOT/folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                inventory[path.relative_to(ROOT).as_posix()] = sha(path)
    return inventory


def build(out=DEFAULT_FROZEN):
    out = Path(out)
    if out.exists(): raise FileExistsError('freeze directory must be new; never overwrite a frozen design')
    out.mkdir(parents=True)
    before = historical_inventory()
    historical = load(ROOT/'data/e1/canonical_cases.json')
    pool = candidate_pool(historical)
    oracle_checks = exhaustive_oracle_check()
    # Persist and hash the validated pool BEFORE final selection.
    write_new(out/'candidate_pool_v1.json', pool)
    pool_hash = sha(out/'candidate_pool_v1.json')
    committed_pool = load(out/'candidate_pool_v1.json')
    selected = select_cases(committed_pool)
    cases = [{**{f:c[f] for f in FIELDS}, 'case_id':c['case_id'], 'stratum':c['stratum'],
              'candidate_id':c['candidate_id'], 'structural_signature':c['structural_signature'],
              'selection_rank_sha256':c['selection_rank_sha256']} for c in selected]
    renderings = [render(c, level) for c in cases for level in LEVELS]
    old_non = {signature(c)[1:] for c in historical}
    if any(signature(c)[1:] in old_non for c in cases): raise ValueError('historical structural duplicate')
    oracle = [dict(case_id=c['case_id'], disposition=authoritative(c).disposition,
                   controls=sorted(authoritative(c).required_controls)) for c in cases]
    conf1 = load(ROOT/'config/e1_execution_v1.json')
    conf2 = load(ROOT/'config/e2_execution_v1.json')
    config = dict(design_version='EX1-1.0', models={**{k:v['model'] for k,v in conf1['models'].items()},
                  **{k:v['model'] for k,v in conf2['validators'].items()}},
                  inference=conf1['inference'], store=False, automatic_retry=False,
                  google_genai_version='2.25.0', model_snapshot_ids_verified=False,
                  raw_output_dir='data/raw/extension_overlap_v1', response_schemas=schemas(conf1['allowed_controls']),
                  allowed_controls=conf1['allowed_controls'],
                  retry_controls=dict(helper='src.e2_validate.retry_settings + zero_retry_client',
                      http_retry_options_attempts=0, interactions_max_retries=0,
                      applies_to='all solver AND validator calls', observed_attempt_count=None,
                      note='Runtime effective retry check before call; HTTP attempts not instrumented.'),
                  stop_on_provider_failure=True, stop_on_invalid_response=True, stop_on_unknown_usage=True,
                  automatic_retries_or_replacement_cases=False, max_total_attempted_calls=720)
    if conf1['inference'] != conf2['inference']: raise ValueError('historical inference mismatch')
    templates = historical_prompt_templates()
    plan = jobs(cases)
    stats = dict(candidate_pool_size=len(pool), eligible_candidates=sum(c['stratum'] is not None for c in pool),
                 candidates_by_stratum=dict(Counter(c['stratum'] or 'ineligible' for c in pool)),
                 selected_by_stratum=dict(Counter(c['stratum'] for c in cases)),
                 selected_canonical_cases=60, renderings=180, solver_calls=360,
                 validator_calls_per_role=180, total_planned_calls=720,
                 historical_full_signatures=len({signature(c) for c in historical}),
                 historical_nonfinancial_signatures=len(old_non),
                 selected_full_signatures=len({signature(c) for c in cases}),
                 selected_nonfinancial_signatures=len({signature(c)[1:] for c in cases}),
                 overlap_with_historical_nonfinancial_signatures=0,
                 selected_oracle_control_sets=len({tuple(o['controls']) for o in oracle}),
                 rendering_fact_roundtrips=180,
                 caveat='New interacting configurations; finite shared rules and terminal outcomes remain correlated.')
    manifest = dict(format='EX1-explicit-jobs-v1', design_version='EX1-1.0',
                    execution_config='execution_config_v1.json', jobs=plan,
                    default_mode='dry-run', paid_execution_authorized=False)
    values = {
        'canonical_cases_v1.json':cases, 'oracle_outputs_v1.json':oracle, 'renderings_v1.json':renderings,
        'execution_config_v1.json':config, 'prompt_templates_v1.json':templates,
        'execution_manifest_v1.json':manifest,
        'solver_manifest_v1.json':dict(manifest, jobs=[j for j in plan if j['role'] in ('cheap','strong')]),
        'cheap_validator_manifest_v1.json':dict(manifest, jobs=[j for j in plan if j['role']=='cheap_validator']),
        'strong_validator_manifest_v1.json':dict(manifest, jobs=[j for j in plan if j['role']=='strong_validator']),
        'selection_procedure_v1.json':dict(seed=SEED, procedure='SHA256(seed|stratum|candidate_id); lowest ten per stratum',
            pool_persisted_before_selection=True, committed_pool_sha256=pool_hash,
            domain=dict(amounts=[40000,50000,75000,100000,125000],
                        vendors=['approved','unapproved','prohibited'],
                        classifications=['public','confidential','restricted'],
                        deployments=['internal','external_saas'], months=[12,24,36],
                        scopes=['none','vendor','external_restricted_data','both']),
            novelty='Reject all historical nonfinancial signatures; collapse equivalent no-information-control states.',
            stratum_assignment='Ordered predicates in prepare.stratum; terminal, nonwaivable, combined, scoped, threshold, multiple.',
            case_order='Fixed STRATA order and selection rank; execution blocks hash-randomized independently.',
            no_model_performance_used=True, model_blind_inputs=['historical canonical cases only; no model outputs']),
        'inventory_v1.json':stats, 'oracle_verification_v1.json':oracle_checks,
        'budget_v1.json':budget(), 'historical_inventory_v1.json':before,
        'execution_approval_template_v1.json':dict(approved=False, design_manifest_sha256=None,
            user_approval_reference=None, independent_semantic_review_reference=None,
            prospective_pricing_and_model_availability_reference=None, max_new_calls=None,
            aliases_and_historical_retry_difference_accepted=False),
    }
    for name, value in values.items(): write_new(out/name, value)
    policy = (ROOT/'config/policies/e1_policy_v1.txt').read_bytes()
    with (out/'policy_v1.txt').open('xb') as stream: stream.write(policy)
    if historical_inventory() != before: raise ValueError('historical evidence changed')
    # PUBLIC ADAPTER: no installed-SDK validation; paid execution is absent.
    hashes = {p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}
    code_hashes = {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(BASE.glob('*.py'))}
    code_hashes[(BASE/'PROTOCOL_v1.md').relative_to(ROOT).as_posix()] = sha(BASE/'PROTOCOL_v1.md')
    design = dict(schema_version='1.0', design_id='EX1-1.0', status='FROZEN_PREPARATION_NOT_AUTHORIZED',
                  files_sha256=hashes, code_and_protocol_sha256=code_hashes,
                  installed_google_genai_version=None,
                  sdk_retry_source=None,
                  retry_translation_offline=None,
                  historical_evidence_unchanged=True, historical_file_count=len(before),
                  primary_outcomes=['joint weak/strong exact correctness among valid paired outputs',
                    'P(strong_wrong | weak_wrong) and P(strong_wrong | weak_correct)',
                    'P(strong_correct | validator_FAIL), separately for each validator'],
                  secondary_outcomes=['validator confusion/FAR/FRR with explicit denominators',
                    'reconstructed cascade accuracy and corrections minus corruptions',
                    'normalized token-derived USD costs and expected cost differences',
                    'loss sensitivity grid L=[0,.001,.005,.008,.01,.02,.05,.1,.5,1]'],
                  aggregation='Equal canonical-case weight; average three renderings within case. Renderings are NOT independent cases.',
                  missing_data='No replacement/rerun. Report all planned/attempted/valid denominators; no invented routes or unknown costs.',
                  comparisons='Separate prospective corpus; never silently pool with E1/E2. Human routes remain hypothetical D/C/F.',
                  acceptance_criteria=[
                    'Explicit approval linked to this design SHA before any paid call.',
                    'Independent semantic review of templates/cases and prospective model/price confirmation.',
                    'Offline inventory, oracle, request-equivalence and zero-retry tests passed.',
                    'No records/reservations before first batch; verify identity/integrity for resumption.',
                    'Zero effective SDK retries checked at runtime for all roles.',
                    'Max 720 planned attempted calls; no outcome-dependent stopping.',
                    'US$10 conservative estimate guard, NOT a billing ceiling; no automatic retries.',
                    'Technical failure/invalid response/unknown usage/ambiguous persistence pauses execution.'],
                  unresolved=['Model identifiers are provider aliases; snapshot immutability/availability not verified locally.',
                    'Prospective provider prices not verified; frozen USD convention is comparative only.',
                    'HTTP attempt counts uninstrumented; SDK policy is configured evidence, not observed transport count.',
                    'Independent human semantic review and explicit paid approval are pending.',
                    '60 selected canonical cases do not establish sub-1% error rates or production validity.'])
    write_new(out/'design_manifest_v1.json', design)
    write_new(out/'design_manifest_v1.sha256', sha(out/'design_manifest_v1.json')+'  design_manifest_v1.json\n')
    print(json.dumps(stats, indent=2))
    print('Frozen design SHA256:',sha(out/'design_manifest_v1.json'))
    return design


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=DEFAULT_FROZEN)
    build(p.parse_args().output)


if __name__=='__main__': main()
