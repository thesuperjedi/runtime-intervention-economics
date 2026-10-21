# Release candidate1.1.0-rc.1 — final review preparation

## Changes from local package1.0

Created a separate candidate from the explicit verified2996-file prior inventory. Previous package, document ZIP and frozen research originals are preserved.

Updated README with a five-minute isolated/offline quick-start, expected outputs, links to findings and three distinct reproduction claims. Added a findings guide with denominators and evidence classes. Expanded domain adaptation with specific replacement points, hard-coded population guards and a clearly labelled expense-policy example.

Added ATTRIBUTION.md: Independent Researcher is the only confirmed author description. Public name, GitHub identity, optional email and ORCID are pending. No institution, DOI, publication detail or licence is inferred.

Added LICENCE_OPTIONS.md: MIT/Apache-2.0 code and CC BY4.0/CC0 data options for owner discussion only. No operative licence text or SPDX declaration is applied.

Added a draft CITATION.cff with verified project title/type/version and empty authors list. It is deliberately not schema-valid until a public author name is confirmed. This unresolved gate is explicitly reported, never counted as a successful citation validation.

The only executable infrastructure adjustment is adding .cff to the bounded scanner's file-type allowlist so that the citation is scanned rather than treated as an unexpected extension. Scientific implementations and experimental evidence are unchanged. Documentation checks are added separately.

## Executed checks

Using Python3.13.5 and only each candidate's local entry points:
- python -I -S -B run_tests.py:114 passed;0 failures/errors/skips.
- python -I -S -B reproduce.py --full-robustness:PASS.
- python -I -S -B scan_release.py:PASS_BOUNDED_SCAN; no findings.
- python -I -S -B verify_package.py:performed after the updated manifest is sealed; final return is recorded by the local sealing verifier.

See rc1_commands.json for exact executed scientific command logs and rc1_reproduction.json for results. Independent computational reconstruction again reproduces E1/E2 scoring and costs, EX1 Stages1–3,36 E3 profiles,5760 grid cells,720 equations and the full saved strong-error analyses. It is not independent human review or raw acquisition authentication.

The copy/verification helpers exceeded the terminal capture window during file work. Their completion was checked from persisted inventory/results and process completion rather than treating a timeout as success. Final preservation evidence is in rc1_preservation.json.

## Publication assessment

Prepared for review; **not authorized or fully ready for publication**. Blocking decisions:
1. Confirm preferred public author/citation name.
2. Confirm GitHub username/repository identity before any public URL is filled.
3. Confirm public email/ORCID or explicitly omit them.
4. Select code and data/documentation licences and their scope after ownership review.
5. Resolve applicable provider-output/data redistribution rights.
6. Validate completed citation and separately approve publication.

No new scientific experiment is required for these decisions. No paid model calls, remote repository creation or publication occurred. Optional dependency pins remain unchanged and unused; standard-library reproduction was tested with site-packages disabled. No cross-platform, security-clearance or legal-approval claim is made.

Exact candidate files and hashes are in provenance/PACKAGED_FILES.txt and provenance/package_inventory.json. The prior package fingerprint is recorded in provenance/release_candidate_v1_1_rc1.json; original/public observation fingerprints remain separate.
