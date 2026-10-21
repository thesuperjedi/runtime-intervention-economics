# EX1 targeted weak/strong overlap extension — protocol v1

Status: prospective preparation only. No LLM calls are authorized by this protocol.
Cohort: EX1, separate from every historical E0–E3 observation and report.

## Question and falsifiable hypotheses
On this prospectively selected challenge corpus, measure joint weak/strong exact-set correctness,
strong errors conditional on weak correctness, and strong correctness in each validator FAIL queue.
Primary contrasts: P(S_wrong|W_wrong) - P(S_wrong|W_correct), and P(S_correct|FAIL_v).
Secondary signed hypotheses: escalation corrects more weak errors than it corrupts weak-correct answers;
and Delta J_v = J_cascade_v - J_strong_only < 0 at L=US$0.10.
Nonpositive correction benefit or nonnegative Delta J does not support the respective hypothesis.
These are finite-corpus descriptive contrasts, not powered tests of production hypotheses.

## Case generation, novelty and prospective selection
Seed: 20261019. No model performance enters generation, eligibility, selection or order.
Enumerate the finite product in selection_procedure_v1.json.
Collapse policy-equivalent no-information-control variants. Financial signature has five regions:
below 50,000; exactly 50,000; between thresholds; exactly 100,000; above 100,000.
Duration signature: below, exactly, or above 24 months.
Other coordinates: supplier status, information-rule branch, exception scope.
Exclude every E1 signature AFTER REMOVING the financial coordinate. Thus a candidate cannot be
a historical case with only a new name or amount. This does not imply a new policy, new control
vocabulary, independent rule family, or unique output set.

Ordered mutually exclusive eligibility:
1. Prohibited supplier -> terminal_precedence.
2. Approved exception + surviving SECURITY_REVIEW + long duration -> nonwaivable_controls.
3. Unapproved supplier + approved exception + restricted-internal/confidential-external processing,
   or restricted-external processing with scope both -> combined_interactions.
4. Applicable scoped suppression of supplier or external-restricted control -> scoped_exceptions.
5. No exception + exact monetary or duration threshold -> threshold_boundaries.
6. No exception + at least three required controls -> multiple_obligations.
All other candidates remain in the audited pool with null eligibility.

Persist and hash the validated candidate pool before selecting from its reloaded bytes.
For each stratum, rank SHA256('20261019|stratum|candidate_id'); select the lowest ten hashes.
Do not substitute or revise cases after any model output becomes available.
The finite corpus is balanced by design, not representative of procurement prevalence.
Shared rule patterns remain dependent even when canonical structures differ.

## Case and rendering inventory
60 canonical cases, ten per stratum, X001–X060.
180 renderings: L1/L2/L3 for each case, one paired solver realization per rendering.
L1 is explicit factual prose; L2 integrates facts; L3 adds policy-irrelevant administrative framing
and reorders facts. These labels are not experimentally validated difficulty scales.
All three texts encode the same seven canonical fields. A separate text parser reads rendered text,
round-trips every fact, and checks the resulting oracle controls.
Independent human semantic review is still an execution acceptance requirement.

## Frozen policy and oracle
Copy the unchanged authoritative policy text byte for byte.
Use unchanged src.e1_policy.evaluate_policy as the authoritative oracle.
Compare it against the independently encoded declarative decision table in policy_checks.py for
3,840 valid combinations, including both monetary thresholds and adjacent values, duration boundaries,
terminal prohibition with exceptions, non-waivable controls and all exception scopes.
Also check every candidate and selected rendering.
This is independent implementation agreement, not independent human policy adjudication.
The original exact-set contract is retained: compare sets of required controls.
Keep provider failures, invalid schemas and missing responses distinct from cognitive policy errors.
Do not use the stricter schema check to redefine historical set-scoring semantics.

## Models, requests and instrumentation
Weak solver and cheap validator: gemini-3.5-flash-lite.
Strong solver and strong validator: gemini-3.8-flash.
These are frozen requested identifiers; provider snapshot immutability and prospective availability
are not established locally. Any alias drift must be accepted explicitly or execution must pause.
Use original E1 solver and E2 validator prompt templates, extracted from their source AST.
Only rendered request text and the weak candidate vary; canonical JSON, strata, expected controls,
oracle disposition and strong answer are never supplied to either model.
Output schemas, temperature=0, thinking_level=low, store=false match historical specifications.
No new output-token cap is silently introduced.

Pin google-genai 2.25.0. Use the existing version-guarded zero_retry_client workaround for ALL roles.
Configure HttpRetryOptions(attempts=0), undo constructor normalization as in verified E2,
and check effective Interactions max_retries=0 before calling create.
Record configured policy separately from uninstrumented actual HTTP attempt count (null).
Preserve usage.model_dump and all SDK response telemetry without adding invocation-level counters
to normalized counters. Label serialized responses as SDK dumps, never untouched HTTP responses.
Close clients on success, failure and partial initialization.
Historical E1 retry metadata did not itself enforce this policy; document that comparability limit.

## Paired collection and manifests
720 explicit planned run IDs:
- solver_manifest_v1.json: 180 weak + 180 strong.
- cheap_validator_manifest_v1.json: 180 judgments.
- strong_validator_manifest_v1.json: 180 judgments.
execution_manifest_v1.json is the dependency-ordered union.
Blocks are case/rendering combinations ordered by a separate seed-derived hash.
Within each block solver roles are hash-ordered, followed by hash-ordered validators.
Both solvers answer independently; each validator sees the SAME weak answer only.
Strong collection is unconditional, enabling paired comparisons even on PASS cases.
Reconstructed escalation reuses that same paired strong answer under both validator roles.
There is no executed live cascade, human review, or result-informed routing.

## Outcomes and canonical-case denominators
For a complete rendering pair, write W,S in {0,1} for historical exact-set correctness.
Report all four joint cells and P(S_wrong|W_wrong), P(S_wrong|W_correct).
For each role report P(S_correct|FAIL), P(S_correct|PASS), weak/strong overlap inside FAIL,
weak errors repaired on FAIL and weak-correct answers corrupted on FAIL.
Zero conditioning denominators are undefined, never imputed as zero.
Secondary: true/false accepts/rejects, FAR among weak-wrong judgments and FRR among weak-correct judgments;
cascade correctness Y = W on PASS and S on FAIL.

Primary joint analysis uses canonical cases with all three valid paired renderings;
role-specific routing analysis additionally requires all three valid judgments for that role.
Cross-role comparisons use the common complete-case population.
Report excluded and partially observed cases, all 60 planned canonical cases, all 180 planned
rendering slots and every attempted/valid denominator separately.
No silent available-case renormalization. Supplementary partial observations may be shown descriptively.
Provider failures/invalid responses are separate from valid-but-wrong model answers.
Unknown routes and costs stay unresolved. Known failed-call usage/cost is retained.

Each included case has equal weight; average its three rendering indicators or costs first.
Conditional rates are ratios of summed case-averaged joint/conditioning indicators.
Use case-cluster stability summaries and leave-one-family-out descriptive checks, never independent-180 tests.
Sixty selected canonical cases do NOT establish sub-1% failure probabilities or production validity.
No result-dependent sample expansion, early success stop, significance search or failure hunting.

## Economics
Primary price convention, USD per million:
cheap input .30, output+thought 2.50; strong input .75, output+thought 3.75.
Normalized input/output/thought only; require supported categories and no unknown-as-zero accounting.
Actual research expenditure includes all unconditional solver and validator calls.
Reconstructed route cost: C_w + C_v + 1[FAIL]*C_s.
Strong-only reference cost: C_s. Weak-only reference: C_w.
J = estimated API cost + L*(1-accuracy); retain L grid [0,.001,.005,.008,.01,.02,.05,.1,.5,1].
Any human comparisons remain hypothetical with unchanged D/C/F and H=.01; no human behaviour is observed.
Keep token-derived USD estimates, execution allowance debits and invoice evidence in separate fields.
Never allocate aggregate SGD bills to calls or silently convert currencies.

Historical role-mean projection: approximately US$0.69 for all 720 calls.
Each-role historical-max projection: approximately US$1.76; five times that projection: US$8.78.
US$10 is an anticipated estimate allowance, NOT a guaranteed billing ceiling.
New cases can exceed historical token usage; prospective prices and availability require external confirmation.
Budget guard debits max(role allowance, known token estimate) and checks the next call before starting.
A call can exceed its allowance. Unknown usage pauses execution; no zero-cost assumption.
Provider billing controls are not verified by this preparation.

## Execution controls and stopping
Dry-run is the default and creates no raw output directory or observations.
Paid execution needs --execute, --execution-approval, and a positive bounded --max-new-calls.
The approval must reference the exact design SHA, user authorization, independent semantic review,
prospective price/model confirmation, and acknowledgment of alias/retry comparability limitations.
The supplied approval TEMPLATE is false/unapproved and must never authorize execution.
At most 720 planned logical attempts; no replacements or automatic retries.
Exclusive batch/run reservations and exclusive JSON creation prevent duplicate concurrent calls.
Existing records require --remaining-only and verified identities/requests/cost metadata.
Failed, malformed or unknown-cost historical extension records require investigation; no silent rerun.
Interrupts or ambiguous persistence retain reservations; never reclaim merely from age or dead PID.
Pause on provider/initialization/persistence failure, malformed response, unknown usage, integrity drift,
or estimated budget exhaustion. No stopping based on accuracy, winner, or observed error count.

## Pre-execution independent checklist
- Confirm design_manifest_v1.sha256 against the separately reviewed design fingerprint.
- Verify every preparation/code/policy/SDK fingerprint and historical inventory.
- Reproduce the model-blind candidate pool and exact selection, strata and all rendering facts.
- Review policy semantics and all rendering templates; record independent semantic review.
- Confirm current model identifiers/availability, prices/currency and any provider billing limits.
- Pass extension tests and existing E2 zero-retry instrumentation tests, with network blocked.
- Confirm all 720 IDs, pair/dependency links, role counts and zero reservations/unexpected artifacts.
- Verify zero effective retry configuration for both solver and validator clients.
- Approve only the reviewed bounded batch; default dry-run alone never grants paid authorization.
- Preserve E0–E3 as separate historical populations and retain every extension outcome.

## Preparation commands (offline)
python -B -m unittest discover -s extensions/overlap_v1 -p 'test_*.py' -v
python -B -m extensions.overlap_v1.prepare
python -B -m extensions.overlap_v1.run_manifest --preflight-report extensions/overlap_v1/preflight_v1.json

Use the project interpreter selected by PyCharm. Generation and reports use exclusive-create.
The design SHA binds the file inventory; its own hash is stored separately to avoid self-reference.
Source changes or case changes after freezing require a new version and renewed review.
