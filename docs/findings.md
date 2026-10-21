# Major findings and their evidence classes

These are descriptive or conditional findings for bounded synthetic populations. References below are bundled reports, not fresh model executions. They retain historical provenance statements; public release fingerprints are separate.

| Finding | Evidence class and denominator | Reference |
|---|---|---|
| E1 weak236/270; strong270/270 | Observed solver outputs scored by frozen exact-set oracle;30 canonical cases,90 renderings,3 realizations | [E1 final analysis](../data/derived/e1/e1_final_analysis_v1.json) |
| E1 weak cost0.0950729 USD; strong0.3698235 USD | Token-derived list-price estimates, not provider invoices | [Corrected E1 economics](../data/derived/e1/e1_economics_v2.json) |
| E2 cheap TA702/FA25/TR77/FR6; strong TA708/FA0/TR102/FR0 | Observed validator judgments;810 correlated slots per role attached to270 frozen sources | [Historical comparison](../e3_phase1/e3_stage2b_conditional_01.json) |
| E2 reconstructed final correctness785/810 cheap cascade;810/810 strong cascade | Reconstruction from saved judgments and paired E1 strong responses | [Stage2b](../e3_phase1/e3_stage2b_conditional_01.json) |
| Human value depends on D/C/F, review cost and error loss | Hypothetical competence plus deterministic expectations;36 profiles | [Stage2a](../e3_phase1/e3_stage2a_thresholds_01.json), [Stage2c](../e3_phase1/e3_stage2c_boundaries_01.json) |
| Strong-error burden and placement can reverse rankings | Hypothetical perturbations of fixed observed inputs, not measured future error rates | [Strong-error sensitivity](../e3_phase1/e3_strong_robustness_01.json) |
| EX1 weak131/180; strong180/180 | Observed outputs;60 new canonical cases,3 renderings | [EX1 Stage1](../extensions/overlap_v1/analysis/stage1_results_v1.json) |
| EX1 cheap full-population TA128/FA24/TR25/FR3; strong complete-case TA125/FA0/TR49/FR0 | Cheap60 cases/180 renderings; strong58 complete cases/174 renderings; two missing judgments not imputed | [EX1 Stage2](../extensions/overlap_v1/analysis/stage2_results_v1.json) |

## EX1 comparable economic population

All four routes below use the same58 cases/174 renderings. Costs are reconstructed USD estimates:

| Route | Correct /174 | Total API estimate USD |
|---|---:|---:|
| Weak-only |125|0.0661712|
| Strong-only |174|0.2550105|
| Cheap-validator cascade |150|0.2224608|
| Strong-validator cascade |174|0.42402395|

Source: [EX1 Stage3](../extensions/overlap_v1/analysis/stage3_results_v1.json). The assumed equal loss per wrong result changes rankings: weak-only is optimal below about0.0038538632653061225 USD/error, strong-only above, with a tie at that boundary. Neither validator cascade is globally cheapest for any nonnegative loss in this four-route comparison.

At L=0.10 USD/error, strong-only wins. Weak-only still has lower simple API cost per correct result; do not substitute one metric for the other. Research-wide known EX1 token estimates total0.7291317 USD plus two unknown failed-call charges, not any route's cost.

## What remains unresolved

No strong-solver errors were observed in E1 or EX1. Their overlap with weak errors under strong failure remains empirically unidentified. Cheap-validator false acceptance is observed; a shared causal mechanism is not isolated. Human performance was not measured. These tasks and limited actions do not establish production reliability or governance permission.
