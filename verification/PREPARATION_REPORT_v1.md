# Public research package preparation1.0

Status: **offline scientific preparation complete; publication not authorized**.

## Scope and inventory

Created a new allowlisted directory without Git history. Included scientific source, supported tests, frozen policy/cases/renderings/configurations and scientific reference reports. Excluded paid executors, recovery implementation, approvals, incident-clearance identities, personal attestations, SDK dumps, credentials, environment files, existing ZIPs, prototypes/backups and obsolete zero-cost economics.

Exact files and hashes are enumerated in provenance/package_inventory.json; human-readable paths in provenance/PACKAGED_FILES.txt. Inputs and references derive from provenance/allowlist.json; source edits have original/public SHA256 and a unified patch. Generated adapters/docs/verifiers are listed by the package inventory.

Preserved540 E1,1620 E2 and720 EX1 projected records. Two terminal EX1 HTTP503 failures remain failed with unknown usage and charges. All retained original fields were compared for equality. Local original hashes reconcile to frozen E1/E2 Audit03 and final720 EX1 inventories.3149 protected original files remained unchanged during the final preparation checks.

## Public-only results

Using Python3.13.5 with -I -S -B, without site-packages, SDK, credentials or network:
-108 scientific tests passed;0 failures,0 errors,0 skips.
-E1 weak236/270,strong270/270; frozen solver cost estimates reproduce.
-E2 cheap TA702/FA25/TR77/FR6; strong TA708/FA0/TR102/FR0. Reconstructed correctness785/810 and810/810.
-EX1 Stages1–3 analytical results reproduce. Strong missing judgments remain missing; common economics58 cases/174 renderings.
-EX1 common weak125/174,strong174/174,cheap cascade150/174,strong cascade174/174.
-EX1 reconstructed total USD costs: weak0.0661712,strong0.2550105,cheap cascade0.2224608,strong cascade0.42402395.
-Independent integer-tariff reconstruction gives boundary1888393/490000000 USD assumed loss per error.
-E3 all36 profiles,5760 grid cells,720 pairwise equations and full saved strong-error sensitivity analyses reproduce.
-Research known EX1 token estimate0.7291317 USD; two failed-call charges unknown.

No amount above is invoice verified. Human competence/error-loss/strong-error scenarios remain hypothetical. Separate verifiers are computational checks, not independent human examination.

## Commands and actual exit status

From the package:
1. python -I -S -B run_tests.py — exit0;108 passed.
2. python -I -S -B reproduce.py --full-robustness — exit0.
3. python -I -S -B scan_release.py — exit0; no bounded-scan findings.
4. python -I -S -B verify_package.py — final package integrity command; see finalization results.

The private preparation also ran verify_original_projection_v1.py — exit0,2880 original hashes and retained fields verified. Private helpers remain outside the public package. Detailed logs/results are in verification/commands_v1.json, tests_v1.json, reproduction_v1.json and original_projection_verification_v1.json.

## Preparation problems corrected and disclosed

The initial builder stopped at an older E0 schema lacking top-level run_id; it was resumed using the saved filename label and original hash. A public import adaptation briefly duplicated a bookkeeping keyword; this was corrected. A test-setup replacement initially removed a synthetic helper; restored it using the original AST function boundary. Old E2 integration assumptions described an empty pre-execution directory; public tests now assert completed coverage, retaining synthetic missingness tests. Request-schema validation was corrected to compare the recorded text/mime/schema envelope. Latent SDK verification imports in preparation were removed and their validation status set to null rather than claimed passed. An initial scanner self-match was its own path regex, not a personal path.

The initial final-package command also exposed an isolated-mode sibling-import omission; the verifier now explicitly loads its own package directory. None of these intermediate failures was counted as a passing verification, and no original was edited.

## Publication blockers

No licences selected; authorship/ownership and provider output/data redistribution terms require confirmation. No legal approval, independent security clearance or publication authorization is claimed. Python3.13.5 is verified; another platform/interpreter has not been tested. Original raw-byte authenticity cannot be independently established from projections alone. Optional pytest dependencies are pinned but were not installed or used; stdlib reproduction requires none.

A final allowlist review and explicit owner publication approval remain necessary. No remote repository, GitHub push, API call or new experiment was performed.
