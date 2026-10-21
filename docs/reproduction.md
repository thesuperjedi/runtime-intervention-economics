# Reproduction contract

Run the three README commands from a clean copy. No credentials, network, installed SDK or private workspace are needed. Python3.13.5 is the verified interpreter; other versions/platforms have not been qualified. Runtime dependencies are empty. Optional pytest tooling is pinned separately.

run_tests.py runs original applicable scientific tests, function-style E1 policy tests, and public-package tests. Paid-runner tests are excluded because paid execution modules are absent. EX1 scientific tests retain all scoring/routing assertions; SDK/HTTP mocks are replaced by socket blocking. One old E2 integration test is adapted from an empty pre-execution population to the completed public population. Synthetic missing/failed/malformed tests remain.

reproduce.py reconstructs:
- E1 exact-set scores, frozen token estimates and ideal references.
- E2 observed confusion and reconstructed route economics.
- E3 Stage1, Stage2a, Stage2b and all Stage2c fields, including human-winning lists and equations.
- EX1 all Stage1–3 scientific result fields, excluding provenance and verification bookkeeping that necessarily differs for projected bytes.
- With --full-robustness, the complete saved nonzero strong-error analyses, not only their zero-error baseline.

A separate independent_verify.py derives truth from the independent policy table and computes routes/costs with integer tariffs and rational arithmetic. Existing separate EX1 verifiers also run. Computational independence is not independent human examination.

Reference reports retain historical provenance hashes and limitations as reference statements. A hash inside a reference report does not claim to hash a public derivative. Original/public mapping and current public inventories are authoritative for release bytes.

Directory names data/raw and Audit03 filenames remain for compatibility. Their contents are explicitly projected or derivative; original raw-byte verification is unavailable without private originals. Report equivalence covers scientific results, not identical provenance headers.

Raw entry points can create analysis outputs or new preparation designs when explicitly invoked; use the read-only commands above for reproduction. Never regenerate over bundled reference reports. The provided verification uses only in-memory recalculation and stdout.

No claim is made to reproduce future model responses, actual provider charges or genuine human behaviour.

## Release candidate1.1.0-rc.1: interpretation and attribution

The five-minute entry points in README distinguish three activities: calculation reproduction from public projections; inspection of historical raw-record provenance; and fresh model execution. Only the first is fully supported here. Public/source mappings do not independently authenticate private original bytes, and no fresh execution facility is shipped.

The RC adds documentation checks and a draft citation; it changes no scientific inputs, outputs, scoring or economic equations. Historical verification files remain as prior-preparation evidence. Current RC checks are separately versioned in verification/rc1_commands.json.

CITATION.cff contains verified project metadata and intentionally empty authors pending public-name confirmation. It is not yet a valid final CFF citation. Attribution and licence decisions must be settled before public release.

### Subsequent owner confirmation

Jaidev is now the complete confirmed public citation name, with Independent Researcher as the professional designation. The earlier citation-pending statement above describes the initial RC preparation. Current citation/attribution files and verification/author_confirmation_v1.json supersede that identity blocker. No surname, institution or optional identifier has been added. Publication and licensing gates remain.

## Final-review candidate1.2.0-rc.1

Approved MIT/CC BY scope notices are now included, with generated responses and provider telemetry excluded from automatic author licensing. Earlier licence-pending reports remain historical evidence. Current command logs and preservation checks are separately versioned under verification/final_rc_*.json. All scientific input/projection/reference bytes are unchanged from the parent candidate.
