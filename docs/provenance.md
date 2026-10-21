# Evidence provenance and transformations

Every E1/E2/EX1 projection has an entry in provenance/projection_map.json with relative original path, original SHA256, public path, public SHA256, retained field names and removed field names. provenance/original_inventory.json identifies private original bytes; public_inventory.json identifies projected bytes. package_inventory.json identifies the complete release tree. None is an authenticated external signature.

Projection schema research-observation-1.0 retains scientific identities, solver/validator role, repetitions and joins, response text and parsed content, success/schema status, normalized usage, model/settings/prompt request, retry-policy evidence and unknown transport-attempt count, latency, and EX1 recorded estimate. No oracle truth is injected into model responses.

Removed: SDK-serialized/full provider responses, interaction identifiers, environment/platform strings, execution timestamps, opaque signatures and raw exception bodies. SDK version is retained separately. Failed observations retain a normalized HTTP503 category/status, missing usage and unknown cost. Actual charge USD and SGD fields remain distinct null values. No token-derived amount becomes an actual charge.

Scientific response text and prompts are copied without normalization or redaction; every retained original field is checked against the original during preparation. This is a potential redistribution concern until rights are confirmed, not a claim that synthetic outputs are automatically safe.

Known author-machine roots are replaced by a project-relative marker in reference reports/design metadata. Personal paths in JSON dictionary keys are normalized too. Scientific content is not changed.

Scientific code is byte-preserved except documented adapters:
- EX1 recovery import -> read-only offline_controls; metadata describes public hashes, not historical raw validation.
- E2 pairing import -> an offline helper; no validator/SDK import.
- EX1 preparation reads the frozen prompt templates instead of parsing absent execution modules. Installed-SDK checks are absent and represented as unverified/null, never simulated as passed.
- Scientific tests remove SDK/httpx setup only; the E2 population integration assertion reflects saved completed data.
See source_adaptations.patch and source_transforms.json for exact hashes and changes.

Public input and observation inventories are separate from frozen design fingerprints. Original EX1-1.0 fingerprint is retained as historical evidence; derivatives must never be called the same frozen bytes. Operational approvals, clearances, recovery controls and their private audit wrappers are excluded.

The E0 summary records file-derived run labels where early schemas lack a run_id. It is a compact factual projection, not an untouched response. Original hashes are included.

Preparation errors and final test results are disclosed in verification/PREPARATION_REPORT_v1.md. This package does not include the original Git history.

## Approved licensing and excluded content

See LICENSE_SCOPE.md and EVIDENCE_REDISTRIBUTION_NOTICE.md. No licence field is inserted into the frozen observation projections; their bytes and original/public hash mapping remain unchanged. provenance/rights_inventory.json separately records each file and mixed-content exclusions. AI-assisted software/documentation and Gemini-generated experimental responses are not asserted as exclusively human-authored.
