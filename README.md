# Runtime intervention economics

Controlled experiments on when an additional AI call is worth its cost: weak and strong solvers, AI validators, escalation, hypothetical human review, and the economic consequences of errors.

By **Jaidev, Independent Researcher**. No institutional affiliation is asserted. See [ATTRIBUTION.md](ATTRIBUTION.md).

Companion article: **"When Is Another AI Call Worth It?"** (Medium) — https://aiadvances.org/when-more-ai-calls-dont-pay-off-3d4c40d00969?source=friends_link&sk=f11a10c1199695a38582e39d700cfc34

## The question

When does an extra AI intervention (validate, retry, escalate to a stronger model, involve a human) improve an outcome enough to justify its cost and consequences?

This repository studies one narrow part of that question, which I call **WORTH**: whether an action's expected benefit exceeds its execution cost and the cost of errors. It does not study **ALLOWED**: whether an action is permitted or required by governance rules. Both matter for agentic systems, but this work does not implement or validate a runtime governance architecture or control plane.

## Study design

- **Task:** given a synthetic procurement policy and a scenario, return the exact set of applicable controls.
- **Ground truth:** a frozen policy specification and a deterministic executable oracle. An answer is correct only if its control set exactly matches the oracle's, ignoring order.
- **Models:** a weaker solver (Gemini 3.5 Flash-Lite) and a stronger solver (Gemini 3.8 Flash), each also used as a validator. "Weaker" and "stronger" describe roles and observed performance here, not general rankings.
- **Real API calls** with frozen prompts and settings, recorded responses and token usage, and preserved failures.
- **Strategies compared:** weak-only, strong-only, cheap-validator cascade, strong-validator cascade.
- **Important:** the model and validator calls were collected independently. The cascade strategies were **reconstructed afterwards** from saved responses, validator decisions and token usage. They were not run as live agent workflows.

| Stage | What it did |
|---|---|
| E0 | Instrumentation and evidence retention |
| E1 | 30 cases × 3 renderings × 3 repetitions per model, scored against the oracle |
| E2 | 1,620 real validator judgments (810 per validator role) |
| E3 | Mathematical simulation of human review (**no human participants**) |
| EX1 | 60 new cases × 3 renderings across six constructed policy structures |

## Key findings

All findings apply only to this synthetic task and these models.

**Solver accuracy**

| | Weaker solver | Stronger solver |
|---|---:|---:|
| E1 (270 observations) | 236 correct | 270 correct |
| EX1 (180 observations) | 131 correct | 180 correct |

The weaker solver's EX1 errors were concentrated in specific rule structures: scoped exceptions (25 errors in 30 presentations) and combined rule interactions (14 in 30).

**Validators make errors too.** In E2, the cheaper validator produced 25 false accepts and 6 false rejects; the stronger validator produced none. In EX1, the cheaper validator falsely accepted 24 of the 49 incorrect weak-solver answers.

**Strategy comparison** (EX1, 58 cases / 174 presentations with complete data for all four roles; costs are token-derived estimates at list prices, not invoices):

| Strategy | Correct / 174 | API cost per result | API cost per correct result |
|---|---:|---:|---:|
| Weak-only | 125 | $0.000380 | $0.000529 |
| Strong-only | 174 | $0.001466 | $0.001466 |
| Cheap-validator cascade | 150 | $0.001279 | $0.001483 |
| Strong-validator cascade | 174 | $0.002437 | $0.002437 |

**Economics under an assumed error loss.** Modeled cost per result = API cost per result + (observed error proportion × assumed loss per error).

- Below an assumed loss of about **$0.00385 per error**, weak-only has the lowest modeled cost. Above it, strong-only does.
- At an illustrative loss of $0.10 per error, strong-only is clearly preferable.
- Neither reconstructed cascade had the lowest modeled cost at any nonnegative uniform loss.

**Interpretation.** In this setup, validation improved the weak solver's accuracy but did not pay for itself. This does not show that validation or cascades are uneconomic in general. Other models, prices, validators, error structures and routing designs could change the result.

Full denominators and caveats: [docs/findings.md](docs/findings.md).

## What this is not

- Not a validated agentic control plane or governance system.
- Not evidence of general model capability or failure rates. The cases are synthetic and chosen to expose particular policy structures.
- Not proof that a model has zero error probability. Perfect scores on bounded synthetic cases are observations, not guarantees.
- Not an empirical study of human reviewers. E3 uses hypothetical parameters.
- Not a turnkey evaluation platform. Adapting it takes real work (see below).
- Not a claim of novelty relative to the cascading, routing and learning-to-defer literature.

## Quick start

Use a local copy of this directory and Python 3.13.5 (the verified interpreter). No installation, Gemini SDK, API key or credentials are needed. From the repository root:

```
python -I -S -B run_tests.py
python -I -S -B reproduce.py --full-robustness
python -I -S -B verify_package.py
```

Expected output:

- Tests finish with `OK` and `PUBLIC_TEST_COUNTS ... failures 0 errors 0`.
- Reproduction prints JSON with `"status": "PASS"`, E1 weak 236/270 and strong 270/270, and `"full_robustness_reproduced": true`.
- Package verification prints `"status": "PASS"`, `"observation_projections": 2880` and a bounded scan with `"findings": []`.

Do not add Python optimization flags, because the tests use assertions. The standard library is sufficient. The commands print results and do not overwrite evidence. Network connections are blocked by the scientific entry points. Command logs are in [verification/final_rc_commands.json](verification/final_rc_commands.json).

## Three meanings of "reproduction"

| Activity | What this package supports | What it does not establish |
|---|---|---|
| Scientific-calculation reproduction | Recompute scoring, joins, confusion matrices, route costs, profiles and boundaries from public evidence | Invoice accuracy or deployment validity |
| Historical raw-record authenticity | Inspect original-to-public SHA mappings and verify current public bytes | Independent authentication of unavailable original raw records or their acquisition history |
| Fresh model execution | Read frozen prompts and settings as methodological documentation | Running models: no paid executor, SDK or credentials are included, and fresh outputs would be new observations |

Projected-record reproduction is not an untouched raw-record audit. Fresh model calls cannot guarantee identical historical outputs.

## Repository map

- `src/`: frozen oracle, scoring, and E1/E2 analysis code
- `e3_phase1/`: exact-set human-review expectations, thresholds, strong-error sensitivity
- `extensions/overlap_v1/`: model-blind EX1 selection, frozen inputs, Stage 1–3 analysis and verifiers
- `data/raw/`: public projections of recorded observations (despite the path name): 540 E1, 1,620 E2, 720 EX1
- `evidence/`: compact E0 evidence (its paid-call script is omitted)
- `provenance/`: allowlist, transformations, original and public inventories, package inventory
- `verification/`: verification results and command logs
- `docs/`: findings, methodology, reproduction, provenance, limitations, adaptation guide

## Documentation

- [Findings and denominators](docs/findings.md): what was observed, reconstructed and assumed
- [Methodology](docs/methodology.md): bounded actions, exact-set scoring, study populations
- [Reproduction contract](docs/reproduction.md): what a successful run establishes
- [Evidence provenance](docs/provenance.md): private originals versus public projections and hashes
- [Limitations](docs/limitations.md)
- [Adapting to another domain](docs/adapting-a-domain.md), with a worked example

## Limitations

- Renderings and repetitions of the same case are statistically dependent. The number of independent cases is much smaller than the number of observations.
- E1/E2 and EX1 are different populations and are not pooled.
- EX1 has two terminal HTTP 503 failures (stronger-validator calls) with unknown charges. They were preserved, and the main comparison uses the common complete population.
- Human-review competence and error losses are hypothetical.
- Costs are frozen list-price estimates, not invoice-reconciled amounts.
- Validator and solver errors may be correlated, since they come from related models and share policy structures.
- Only one model family, one synthetic domain and one validator design were tested.

## Adapting the method

To reuse this approach, you would need to define your own bounded decision problem, build representative boundary, exception and interaction cases, establish trustworthy expected answers (for example with a deterministic oracle), choose your own models, prompts, validators and interventions, record real usage and failures, model the consequences of errors in your domain, replace hypothetical human-review assumptions with defensible estimates, and verify the modified experiment before interpreting results. See [docs/adapting-a-domain.md](docs/adapting-a-domain.md).

One possible application is measuring how reliably models interpret selected requirements of an organizational policy over a deliberately constructed case set. That would evaluate AI-assisted interpretation, not certify the policy or establish regulatory compliance.

## Licence, attribution and citation

- Original software and tests: **MIT**. Original documentation, synthetic policies and eligible data: **CC BY 4.0**. Gemini-generated responses and provider telemetry are excluded from these grants. See [LICENSE.md](LICENSE.md) and [LICENSE_SCOPE.md](LICENSE_SCOPE.md).
- Gemini responses are experimental evidence, not claimed as exclusive human authorship. Read the [evidence redistribution notice](EVIDENCE_REDISTRIBUTION_NOTICE.md) and [rights status](RIGHTS_AND_RELEASE_STATUS.md) before redistributing data.
- AI-assisted development, verification and documentation are acknowledged in [ATTRIBUTION.md](ATTRIBUTION.md).
- Legal or security clearance is not claimed.
- To cite this work, see [CITATION.cff](CITATION.cff).
