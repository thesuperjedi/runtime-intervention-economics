# Domain adaptation: executable boundary and illustrative refunds

The released mechanism is procurement-specific. It is modifiable source, not a validated domain plug-in architecture. Historical calculations, deterministic demonstrations and future domain experiments are separate activities.

## Actual code and dependencies

| Released file/functions | Responsibility and required domain change |
|---|---|
| mechanism/pap/contracts.py: Action, PARAMS, Proposal, TrustedContext, PurchaseRequest, ApprovalRecord, AutonomyLedger | Replace procurement vocabulary, typed action parameters, actor/delegation, workflow state and accounting schema. Closed parameter validation must match new actions. |
| mechanism/pap/serialization.py: canonical_bytes, digest, APPROVAL_FIELDS, approval_content_hash; chain_validation.py: inspect_chain | Preserve or deliberately redefine canonical binding, chain transitions and approval fields. These primitives are reusable only after domain-specific field/transition review. |
| mechanism/pap/evaluator.py: _context, _classify, evaluate | Implement the new policy's actual scope, threshold, approval, denial and precedence semantics. PAP-0.5 itself remains frozen; create a distinct new policy/version. |
| mechanism/pap/execution/run.py: new_run, _RunCore.authorize/commit/_append_to, AgentPort, TrustedHarness | Preserve local issued-token identity, proposal/state-version binding, trusted-writer separation and transaction/rollback. Replace procurement-specific PR/ledger/approval effects deliberately. |
| mechanism/pap/execution/tools.py: _SyntheticTools.invoke | Replace the permitted local effect vocabulary. Do not add a real payment/refund endpoint to this offline package. |
| mechanism/fixtures.json and fixtures.py: load_protocol, typed, materialize, rebind, ledger_amount | Define prospective synthetic initial states, action templates, trusted approval records, goal/effect predicates and ledger oracle. Rebind local test IDs and regenerate approval hashes; do not simply rename labels. |
| mechanism/drivers.py: ScriptDriver.eligible, event_eligible, action, response | Define exact eligible denial and trusted-event timing, bounds and stop rules for the new policy. This driver encodes procurement and fixed scenario assumptions. |
| mechanism/business_simulator.py: BusinessSimulator.execute, accounting_receipt | Maintain independent B0 business behavior if using that treatment. Do not let shadow decisions control baseline effects. |
| mechanism/scoring.py: expected_transition, policy_evidence, expression, build_view, summarize | Define the new independent completion/effect/accounting checks and unknown-outcome interpretation; permission alone is not completion. |
| mechanism/output_contract.py: PARAMS, response_schema, validate_response | Update the closed action/terminal schema and validation without format extraction or repair. |
| mechanism/recovery.py: RecoverySession.__init__/answer/result | Establish independently verified seed eligibility; preserve harness-versus-continuation provenance and the explicit two-response/two-proposal budget or prospectively approve a new design. |
| mechanism/offline_guard.py: install; demonstrate.py; tests/test_mechanism.py | Keep offline isolation and write new domain-specific positive/negative demonstrations. The guard is diagnostic, not a malicious-code sandbox. |
| shared/model_conditions.json; studies/*/PROTOCOL.md and scenarios.json | Prospectively define prompts, observations, conditions and analysis endpoints. The demo has no model request builder or provider configuration executor. |
| reproduce.py: validate, outcomes, reconstruct, verify_reference, money, resource | Define distinct new populations, contrasts, denominators, pricing and missingness; preserve old study data unchanged. This is arithmetic, not admission enforcement. |
| analysis/reference.json; studies/*/evidence.json; tests/test_release.py; provenance maps; verify_package.py | Keep old datasets separate. Supply new source references, exact file/field allowlists, reference calculations and rights review for any new study. |

Reusable parts include canonical encoding, local capability binding, transactional work-buffer pattern and evidence/predicate machinery. Their current types, approval fields, ceilings, ledger updates, scenario IDs and recovery rules remain procurement-specific. Python object capabilities do not create a production authentication service or hostile-process security boundary.

## Illustrative refunds — NOT EXECUTED OR VALIDATED

1. Define REFUND action fields such as synthetic order, claimant and amount in contracts and output_contract; specify their exact types and closed schema.
2. Create a distinct refund policy: actor/claimant authority, paid/refundable balance, limits, external-approval rules and duplicate protection. Implement these in evaluate; do not reuse procurement vendor/centre checks under new names.
3. Replace PR SUBMITTED/EXECUTED state and autonomy ledger with requested/approved/refunded states and refundable-balance accounting. Adjust only the new policy's commit transitions; retain authentic local capability and stale/replay checks.
4. Keep execution synthetic and effect-only. No real payment tool or credential. A permitted proposal is not a completed refund.
5. Independently verify a refund effect and remaining balance in the oracle. A success assertion without an effect, a duplicate or a mismatched approval must fail.
6. Establish a reachable alternative and exact eligible denial before a recovery experiment. Do not assert that a lower amount or trusted approval is automatically permitted.
7. Define a new population, failure handling and denominators before collecting outcomes. New scripted tests are not evidence of model recovery and must not overwrite EX2/EX2-R.

This is a newly written adaptation illustration, not an executable refund policy, legal determination, historical observation or validated generic adapter. Only the original procurement demonstrations are runnable here.
