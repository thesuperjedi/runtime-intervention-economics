# Runtime intervention economics

**Release candidate1.2.0-rc.1 — local publication review only.**

Prepared by **Jaidev, Independent Researcher**. Jaidev is the complete public citation name; see [attribution](ATTRIBUTION.md). No surname or optional identifiers have been inferred. No institutional affiliation is asserted. MIT applies to original author-controlled software/tests; CC BY4.0 applies to original documentation, synthetic policies and eligible data, with explicit exclusions for Gemini responses and provider telemetry. See [licence scope](LICENSE_SCOPE.md).

This repository supports a bounded study of weak/strong solvers, validators, hypothetical human review and the economics of an agent's next action. The evidence projections contain real experimental outputs, not demonstration results.

## Five-minute quick-start

Use a local copy of this directory and Python3.13.5, the verified interpreter. No installation, Gemini SDK, API key or credential setup is needed. From the repository root:

```text
python -I -S -B run_tests.py
python -I -S -B reproduce.py --full-robustness
python -I -S -B verify_package.py
```

These checks normally take less than five minutes on the preparation machine; elapsed time varies. Python's isolated mode and disabled site-packages keep the workflow independent of the private research workspace. Network connections are blocked by the scientific entry points. Do not add optimization flags: original tests use assertions.

Expected output:
- Tests finish with `OK` and `PUBLIC_TEST_COUNTS ... failures 0 errors 0`.
- Reproduction prints JSON with `"status": "PASS"`, E1 weak236/270 and strong270/270, and `"full_robustness_reproduced": true`.
- Package verification prints `"status": "PASS"`, `"observation_projections": 2880` and a bounded scan with `"findings": []`.

The exact current test count and command logs are in [RC verification](verification/final_rc_commands.json). A failure is a reason to investigate, not to bypass the check. The commands print results and do not overwrite evidence or reference reports. The standard library is sufficient; optional pinned pytest dependencies are not needed.

## Start with the findings

- [Major findings and denominators](docs/findings.md): what was observed, reconstructed and assumed.
- [Methodology](docs/methodology.md): bounded actions, exact-set scoring and study populations.
- [Reproduction contract](docs/reproduction.md): what a successful run establishes.
- [Evidence provenance](docs/provenance.md): private originals versus public projections and hashes.
- [Limitations](docs/limitations.md): dependence, missing judgments, hypothetical humans and cost uncertainty.
- [Adaptation guide with worked example](docs/adapting-a-domain.md).
- [Final publication review](FINAL_PUBLICATION_REVIEW_v1_2_rc1.md), [approved licences](LICENSE.md) and [citation metadata](CITATION.cff).

At the reference assumed error loss US$0.10, strong-only has the lowest reconstructed expected cost among the measured automated routes in E2 and EX1. This does not mean it has the lowest simple API cost per correct answer, or that it will always be correct. Validation improved weak-answer accuracy but did not automatically provide an economic advantage.

## Three different meanings of reproduction

| Activity | What this package supports | What it does not establish |
|---|---|---|
| Scientific-calculation reproduction | Recompute scoring, joins, confusion matrices, route costs, profiles and boundaries from public evidence | Invoice accuracy or deployment validity |
| Historical raw-record authenticity | Inspect original/public SHA mappings and verify current public bytes | Independently authenticate unavailable original raw records or prove their acquisition history |
| Fresh model execution | Read frozen prompts/settings as methodological documentation | Run models: no paid executor, SDK, credentials or authorization is included; fresh outputs would be new observations |

Do not describe projected-record reproduction as an untouched HTTP/raw-record audit. Original and public fingerprints are separate. Fresh model calls, if developed separately later, cannot guarantee identical historical outputs.

## Repository map

- src/: frozen oracle/scoring and supported E1/E2 analytical implementations.
- e3_phase1/: exact-set human expectations, thresholds and strong-error sensitivity.
- extensions/overlap_v1/: model-blind EX1 selection, frozen inputs and Stage1–3 analysis/verifiers.
- data/raw/: **public projections**, despite compatibility path names:540 E1,1620 E2,720 EX1.
- evidence/: compact E0 evidence; its module-level paid-call script is omitted.
- provenance/: allowlist, transformations, original/public inventories and complete package inventory.
- verification/: original preparation results and separately versioned RC checks.

EX1 retains two terminal503 failures with unknown charges. E1/E2 and EX1 are different populations and are not pooled. Renderings/repetitions are dependent. Human competence and error losses are hypothetical; costs are frozen list-price estimates, not invoices.

See [rights status](RIGHTS_AND_RELEASE_STATUS.md). No authorization for this preparation agent to publish is implied. The standard grants for covered material remain as stated; legal or security clearance is not claimed.

## Original material and generated evidence

AI-assisted development, verification and documentation are acknowledged in ATTRIBUTION.md. Gemini-generated responses are experimental evidence, not claimed as exclusive human authorship and not automatically under the author CC BY grant. Provider provenance and factual telemetry remain identifiable. Read [evidence redistribution limitations](EVIDENCE_REDISTRIBUTION_NOTICE.md) and the per-file rights inventory before downstream redistribution. Licence approval does not itself authorize publication or clear provider/third-party rights.
