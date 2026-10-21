# E0 instrumentation evidence

E0 was a small harness probe, not a procurement-policy accuracy experiment. Five saved E0B records include four exact EVAL0_GEMINI_OK responses and one invalid-model failure. Early record schemas differ. evidence/e0_summary.json preserves response text and usage with original hashes, while omitting personal/provider metadata.

The original later source src/eval0_gemini.py records request settings, completion/error status, SDK-serialized provider data, input/candidate/thought/cache counts, wall-clock latency and exact-response evaluation. It persists using exclusive creation. Its current RUN_ID is R006, but no R006 observation is part of this evidence. Current source is not proof of the exact source used for all earlier records.

Automatic function calling disabled is not SDK transport retries disabled. An experiment field saying one attempt cannot prove one HTTP attempt. SDK model_dump is serialization, not untouched HTTP bytes.

The original script reads a credential and calls the model at module scope; it is deliberately not included in the offline release. This document describes the instrumentation rather than providing a paid example.

The successful saved usage records show16 prompt and8 candidate tokens,24 total, with nullable thought/cache counts. Unknown values are not evidence of zero billed cost. E0 recorded actual_provider_charge_usd and reference_cost_usd as unknown in later instrumentation. There is no invoice-verified E0 cost result to reproduce.

The E1/E2/EX1 tariffs are different frozen research conventions. Do not apply their normalized token formula silently to E0's different usage representation.
