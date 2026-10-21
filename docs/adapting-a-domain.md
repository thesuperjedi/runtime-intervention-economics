# Adapting the methodology to another rule-based domain

Keep new cases, observations and results separate from E1/E2/EX1. The bundled evidence reproduces published calculations; it is not a default dataset for estimating a different domain.

## Replacement map

| Replace or define | Current entry point | Preserve or decide explicitly |
|---|---|---|
| Policy and version | config/policies/e1_policy_v1.txt | Rule precedence, threshold inclusivity and authoritative interpretation |
| Structured inputs and oracle | src/e1_policy.py: ProcurementCase/evaluate_policy | Deterministic validation; independent boundary tests |
| Independent reference rules | extensions/overlap_v1/policy_checks.py | Independently encode the new policy; do not reuse procurement labels blindly |
| Candidate generation/selection | extensions/overlap_v1/prepare.py | Model-blind selection, seed, strata, novelty rules and frozen pool |
| Cases and presentations | data/e1/ and EX1 frozen cases/renderings | Canonical IDs, semantic equivalence and case-level dependence |
| Prompt/output contract | EX1 frozen prompt_templates_v1.json and response_schemas in execution_config_v1.json | New control vocabulary; distinguish schema validity from correctness |
| Scoring loader | src/e1_score.py | Replace the hard-coded procurement case loader; retain or explicitly version exact-set semantics |
| Observation joins | public observation schema and src/offline_join.py | New ID scheme requires a new explicit pairing adapter; never rely on historical ID substitution |
| Analysis populations | E2 and EX1 analysis modules | Replace hard-coded study counts and frozen expected-confusion assertions in new copies |
| Human assumptions | E3 D/C/F grid | Hypothetical parameters must not become measured reviewer evidence |
| Prices and loss assumptions | Frozen E1 tariff and E3/EX1 economic equations | New prices belong to a new version; keep estimates separate from invoices |

E3 modules deliberately enforce historical counts such as270/810 and36 profiles. EX1 enforces60/180/720 and complete-case rules. For a new study, change these guards to the prospectively frozen design; do not disable integrity checks or overwrite original results.

## Worked example: expense-policy control sets

**Illustrative specification only: not experimental evidence, not a new model run.**

Suppose a new policy requires:
- MANAGER_APPROVAL when amount_usd is strictly greater than1000.
- SECURITY_REVIEW when information is confidential and sent externally.
- Otherwise no control.

An illustrative pure oracle is:

```python
def expense_controls(amount_usd, confidential, external):
    if amount_usd < 0:
        raise ValueError("negative amount")
    required = set()
    if amount_usd > 1000:
        required.add("MANAGER_APPROVAL")
    if confidential and external:
        required.add("SECURITY_REVIEW")
    return required
```

Freeze at least the boundary examples999,1000,1001 and the confidential/external truth table. For1001/confidential/external, the exact required set is both controls. Returning only MANAGER_APPROVAL is schema-valid if the list contract is met but scientifically incorrect. Order does not matter under exact-set scoring; partial credit is not silently introduced.

For that same case:
- Validator PASS retains the weak answer; it would be a false accept if weak omitted SECURITY_REVIEW.
- Validator FAIL routes to the paired strong answer.
- If strong contains both controls, escalation repairs the answer; if it is also wrong, it does not.
- Route estimate is weak cost+validator cost, plus strong cost only on FAIL. No oracle truth selects the branch.

These are logical examples, not observations. Three narrative renderings of this one expense remain one canonical case. Freeze other cases before testing models; do not select only cases on which one model fails.

## Prospective workflow

1. Resolve policy ambiguities with domain review, then freeze oracle and independent reference tests.
2. Freeze the model-blind pool, selected cases, renderings, manifests and scientific endpoints before performance inspection.
3. Define failures, malformed responses, missingness, pairing and complete-case denominators.
4. Test every solver-correctness×PASS/FAIL combination, zero denominators, unknown costs and ties.
5. Apply new usage/price/loss assumptions to the new evidence only; report canonical-case results.
6. Develop fresh execution separately if wanted. This repository has no paid runner, credential workflow or model-call authorization.

Demo fixtures stay labelled and separate. Never replace experimental records with examples while retaining a published-reproduction claim.
