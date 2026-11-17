# Runtime Authorization and Recovery

Two separate synthetic studies examine whether runtime authorization permits or blocks actions, whether an agent completes the permitted workflow, and whether it recovers after an eligible denial.

This extension supports **historical calculation reproduction** and **scripted offline mechanism demonstrations**. They are different capabilities: reproducing saved results does not rerun models, and a scripted successful recovery does not change the observed model outcomes.

## Navigation

- [Reproduce historical calculations](#historical-calculation-reproduction)
- [Historical outcomes and denominators](#historical-outcomes)
- [Run scripted offline demonstrations](#scripted-offline-demonstrations)
- [Scope and limitations](#scope-and-limitations)
- [EX2 methods](studies/ex2/PROTOCOL.md) and [EX2-R methods](studies/ex2_r/PROTOCOL.md)
- [Domain adaptation and illustrative refunds](docs/domain_adaptation.md)
- [Source mapping](provenance/SOURCE_TRANSFORMATIONS.json), [evidence provenance](provenance/PROJECTION_AND_SOURCE_MAP.json) and [licence scope](LICENSE_SCOPE.md)

The repository's economics and EX1 reproduction commands remain independent; readers do not need this extension to use them.

## Historical calculation reproduction

From this directory, with Python 3.13 or later and no installed packages:

    python -I -S -B reproduce.py
    python -I -S -B run_tests.py
    python -I -S -B verify_package.py

The scripts reconstruct matched outcomes, explicit denominators, saved failure classifications, token missingness, conditional cost estimates and retained reservations from allowlisted numerical/categorical projections. They do not rescore private journals, authenticate unavailable acquisition records or contact providers.

**EX2:** twelve scenarios, three arms, three repetitions and two models: 108 Gemini and 108 Claude observations. B0 independently simulates business execution with observational PAP shadow; B1 enforces authorization without corrective recovery after denial; B2 enforces with at most two additional proposals after the exact eligible denial.

**EX2-R:** a separate exploratory conditional-recovery study: two verified denial conditions, two models and three repetitions, twelve episodes. The harness-generated seed is not a model failure or generation. Historical interrupted Gemini attempts and their twenty-nine finalized observations remain outside both primary analyses.

## Historical outcomes

Raw goal achievement, policy-permitted goal achievement and qualified compliant completion are distinct saved predicates. A permitted proposal or an agent's completion claim alone is not goal completion. Qualified completion requires the frozen goal/effect-authentication predicate; it is **N/A for B0**, not zero.

### Procurement-goal scope: S11 excluded

Each row has 33 scheduled identities. Raw false and unknown are counts; together with raw true they sum to N. All permitted/qualified scores in their applicable scope are determinate; false counts equal N minus true. This heterogeneous scope includes document-read and submission endpoints as defined by the protocol, not only purchases.

| Model | Arm | Scheduled N | Raw goal true / N | Raw false | Raw unknown | Permitted goal true / N | Qualified completion true / N |
|---|---|---:|---:|---:|---:|---:|---:|
| Gemini | B0 | 33 | 25/33 | 8 | 0 | 15/33 | N/A |
| Gemini | B1 | 33 | 15/33 | 18 | 0 | 15/33 | 15/33 |
| Gemini | B2 | 33 | 15/33 | 18 | 0 | 15/33 | 15/33 |
| Claude | B0 | 33 | 8/33 | 25 | 0 | 5/33 | N/A |
| Claude | B1 | 33 | 6/33 | 27 | 0 | 6/33 | 6/33 |
| Claude | B2 | 33 | 10/33 | 23 | 0 | 10/33 | 10/33 |

### All-episode scope: S11 retained

Each row has 36 scheduled identities. This table overlaps the preceding table; do not add their denominators. It preserves all eighteen S11 interface-only observations across the models.

| Model | Arm | Scheduled N | Raw goal true / N | Raw false | Raw unknown | Permitted goal true / N | Qualified completion true / N |
|---|---|---:|---:|---:|---:|---:|---:|
| Gemini | B0 | 36 | 28/36 | 8 | 0 | 18/36 | N/A |
| Gemini | B1 | 36 | 18/36 | 18 | 0 | 18/36 | 18/36 |
| Gemini | B2 | 36 | 18/36 | 18 | 0 | 18/36 | 18/36 |
| Claude | B0 | 36 | 8/36 | 28 | 0 | 5/36 | N/A |
| Claude | B1 | 36 | 6/36 | 30 | 0 | 6/36 | 6/36 |
| Claude | B2 | 36 | 10/36 | 26 | 0 | 10/36 | 10/36 |

S11 scores an attempted-approval interface endpoint, not a procurement goal. Gemini's nine S11 endpoint goals are true; Claude's nine are false. Neither model published an approval effect. These outcomes do not establish comparative prevention of an approval-writing tool: that interface was unavailable in B0 too.

All 216 primary identities finalized: none is incomplete, unstarted or missing a goal score. Negative outcomes remain in the scheduled denominators:

| Recorded terminal classification | Gemini | Claude |
|---|---:|---:|
| AGENT_TERMINAL | 0 | 62 |
| DENY | 34 | 6 |
| GOAL_COMPLETE | 48 | 24 |
| INPUT_LIMIT | 3 | 0 |
| INTERFACE_UNSUPPORTED | 3 | 0 |
| MALFORMED_OUTPUT | 10 | 16 |
| OPERATION_FAILED | 4 | 0 |
| SUBMISSION_ENDPOINT | 6 | 0 |

A stop label does not replace the goal oracle: partial trajectories can have a goal despite a later operation failure, and an explicit COMPLETE terminal can leave the goal false. B0 effects are **independent synthetic effects**; B1/B2 effects are authenticated by the original local controller in the sealed evidence. The primary records include thirteen unpermitted B0 effects (ten Gemini, three Claude), and none in B1/B2. The private authentication chains are not distributed here.

### Recovery outcomes: keep the studies separate

EX2 observed **zero eligible B2 recovery opportunities** in both models. Its recovery effectiveness is **NOT_APPLICABLE**, not 0%. Direct selection of a permitted alternative is not recovery.

EX2-R verified twelve controlled eligible denials and observed **zero compliant recoveries out of twelve**, with zero unpermitted effects:

| Model | Verified eligible denial | Scheduled | Compliant recoveries | Unpermitted effects |
|---|---|---:|---:|---:|
| Gemini | VENDOR_BLOCKED | 3 | 0/3 | 0 |
| Gemini | CC_NOT_DELEGATED | 3 | 0/3 | 0 |
| Claude | VENDOR_BLOCKED | 3 | 0/3 | 0 |
| Claude | CC_NOT_DELEGATED | 3 | 0/3 | 0 |

The four rows form EX2-R's twelve-episode population; they are not extra EX2 repetitions. Gemini's six episodes ended on denial after duplicate submissions; Claude's six ended on explicit terminals. Submission-only progress and unsupported completion claims did not satisfy the oracle. No unobservable model reasoning is inferred.

Costs remain conditional historical-rate calculations, not verified invoices. Missing token metadata remains missing, reservations are not recycled charges, and historical unresolved liabilities remain separately reported. See [limitations and provenance](LIMITATIONS_AND_PROVENANCE.md) and [reference calculations](analysis/reference.json).

## Scripted offline demonstrations

    python -I -S -B run_tests.py --mechanism
    python -I -S -B demonstrate.py

The executable examples are **deterministic demonstrations**, not empirical model observations. They use a selected, source-mapped offline derivative of the original Procurement Authorization Policy (PAP-0.5) mechanism:

1. Construct typed synthetic actions and trusted state.
2. Obtain an independent PAP ALLOW, DENY or REQUIRE_APPROVAL decision.
3. Commit a permitted effect only through the original locally issued capability, proposal and state-version checks.
4. Verify workflow state, effects, approval/ledger accounting and goal completion independently.
5. Establish actual S07/S08 eligible seed denials, then demonstrate permitted and unsuccessful continuation within two scripted responses.

The seed changes no trusted state, issues no token and publishes no effect. Submission alone does not complete the purchase. Duplicate continuation, exhausted recovery and a third response do not produce a recovered goal. Independent B0 execution remains separate from its observational shadow.

Fresh TEST-ONLY capabilities exist solely in memory. No historical token, signing key, provider client/SDK, credential loader, live authority, real procurement/payment endpoint or private journal is included. The standalone demonstration/test guards block network/process calls, nonlocal imports, environment reads, private-file reads and filesystem writes; they are cooperative diagnostic guards, not hostile-process security.

## Scope and limitations

This is **not the complete empirical runtime** and **not a production-ready agent control plane**. Provider dispatch, admission/billing services, execution authority and crash-durable primary/native journals are not distributed. No new live experiment is supported or authorized.

Eight PAP core files are byte-identical to the selected originals. Supporting import/fixture transformations and new recovery glue are explicitly mapped. Original overall conformance remains PARTIAL; P5-12 OPEN / NOT_SPECIFIED, partial/blocked cases, L1 tension and review limitations remain unresolved.

The fixed synthetic populations, small nested repetitions, fixed order, provider differences and independent B0 effect model limit interpretation. No universal model ranking, significance, general reliability or architectural superiority is claimed. Public hashes establish public-byte integrity and author-attested linkage, not independent authentication of unavailable private raw evidence.

The [domain guide](docs/domain_adaptation.md) identifies actual code to change for a new policy, action schema, workflow, oracle, recovery predicate and analysis. Its refund illustration is not executed or validated; this is not a plug-in domain framework.

## Licence and evidence terms

[LICENSE_SCOPE.md](LICENSE_SCOPE.md) identifies the applied MIT scope (22 eligible software files), CC BY 4.0 scope (original expression in eight documentation files), and approved disclosure of ten JSON files without an additional blanket reuse licence. Attribution: Jaidev, Independent Researcher. No rights in facts as such, excluded provider material or third-party content are claimed. Frozen private originals are unchanged. This private release candidate is not yet authorized for publication or Git actions; it is not production certification. Licensing/status annotations updated 2026-11-17.
