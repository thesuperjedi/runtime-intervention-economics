# Observation projection schema1.0

The JSON Schema defines permitted top-level fields. This is a compatibility projection, not a uniform provider response schema. E1/E2 retain their historical schema_version; public_projection_schema identifies the new release representation.

E1 uses model_role and top-level case/rendering IDs. E2 uses validator_role, source_cheap_run_id and paired_strong_run_id. EX1 uses the immutable job object, including role/repetition/source/paired/dependency IDs. Unknown fields are not admitted.

usage contains the original normalized counters unchanged: total_input_tokens,total_output_tokens,total_thought_tokens,total_tokens,total_cached_tokens,total_tool_use_tokens. Null is unknown; never zero-fill. Invocation counters and opaque dumps are excluded and never added.

response_text and parsed_response are copied unchanged where present. Absence in an original failure remains absence; neither indicates a verdict. success and response_valid are distinct. Historical retry policy is retained as evidence; a null http_execution.attempt_count is unobserved.

request contains the historical prompt/model/settings/schema representation unchanged. It is data, never executed. sdk_version is extracted from historical environment metadata where needed. Failure raw bodies become failure.category/http_status/usage_unknown only.

estimated_cost_usd, where originally recorded, remains an estimate. actual_provider_charge_usd and actual_provider_charge_sgd remain distinct null fields. Public records add no invoice information.

No timestamps, host identities, interaction IDs, signatures or full provider dumps are shipped. Paths under data/raw are compatibility paths; their contents are projections with new hashes.
