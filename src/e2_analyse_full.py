"""Read-only E2F scoring; prints JSON to stdout, never writes raw/derived files.

Only valid verdicts reconstruct a cascade: PASS retains cheap, FAIL uses the
frozen paired strong response. Missing/failed/invalid validators have unresolved
routing, not an invented fail-open/fail-closed policy. Costs are list-price
estimates, never invoice verified. Repetitions are descriptive, not independent
canonical cases. Historical cheap/strong costs are counterfactual reused costs.
Cost per correct is a complete-case, resolved-route estimate, not unconditional
operational cost per correct: observations with unresolved routing or unknown
cost are excluded. Known validator costs for unresolved outcomes are reported
separately, without imputing unknown costs or inventing escalation routes.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from src.e1_score import score_run
from src.e1_analyse_economics import extract_usage, estimate_cost
from src.offline_join import paired_strong_run_id

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def estimated_record_cost(record, role):
    if record is None:
        return None
    try:
        usage = extract_usage(record)
    except RuntimeError:
        return None
    raw = record["usage"]
    # Frozen E1 accounting does not price cached or tool categories separately.
    if raw.get("total_cached_tokens", 0) or raw.get("total_tool_use_tokens", 0):
        return None
    return estimate_cost(role, usage)


def validator_status(record):
    if record is None:
        return "missing", None
    if record.get("success") is not True:
        return "failed", None
    try:
        parsed = json.loads(record["response_text"])
    except (KeyError, TypeError, ValueError):
        return "malformed", None
    if not (isinstance(parsed, dict) and set(parsed) == {"verdict"}
            and isinstance(parsed["verdict"], str)
            and parsed["verdict"] in {"PASS", "FAIL"}):
        return "malformed", None
    if "parsed_response" in record and record["parsed_response"] != parsed:
        raise ValueError("Persisted parsed_response disagrees with response_text")
    if "response_valid" in record and record["response_valid"] is not True:
        raise ValueError("Persisted validity flag disagrees with verdict")
    return "valid", parsed["verdict"]


def score_observation(cheap_correct, strong_correct, validator,
                      cheap_cost, strong_cost, role):
    status, verdict = validator_status(validator)
    classification = None
    final_correct = None
    escalation = None
    if status == "valid":
        classification = ("true_accept" if cheap_correct else "false_accept") if verdict == "PASS" else (
            "false_reject" if cheap_correct else "true_reject")
        escalation = verdict == "FAIL"
        final_correct = strong_correct if escalation else cheap_correct
    validator_cost = estimated_record_cost(validator, role)
    escalation_cost = (strong_cost if escalation else 0.0) if escalation is not None else None
    parts = (cheap_cost, validator_cost, escalation_cost)
    total = sum(parts) if all(v is not None for v in parts) else None
    return dict(status=status, verdict=verdict, classification=classification,
                cheap_correct=cheap_correct, strong_correct=strong_correct,
                final_correct=final_correct, escalation=escalation,
                model_call_cost_estimate_usd=cheap_cost,
                validator_cost_estimate_usd=validator_cost,
                escalation_cost_estimate_usd=escalation_cost,
                total_cost_estimate_usd=total)


def ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def summarize(rows):
    counts = Counter(r["classification"] for r in rows if r["classification"])
    statuses = Counter(r["status"] for r in rows)
    valid = [r for r in rows if r["status"] == "valid"]
    complete = [r for r in valid if r["total_cost_estimate_usd"] is not None]
    cost_correct = sum(r["final_correct"] for r in complete)
    categories = ("model_call", "validator", "escalation", "total")
    costs = {}
    for category in categories:
        key = category + "_cost_estimate_usd"
        known = [r[key] for r in rows if r[key] is not None]
        costs[category] = {"known_subtotal_usd": sum(known),
                           "known_count": len(known), "unknown_count": len(rows)-len(known),
                           "complete_total_usd": sum(known) if len(known)==len(rows) else None}
    unresolved_validator_costs = {}
    for status in ("failed", "malformed", "missing"):
        category_rows = [r for r in rows if r["status"] == status]
        known = [r["validator_cost_estimate_usd"] for r in category_rows
                 if r["validator_cost_estimate_usd"] is not None]
        unresolved_validator_costs[status] = {
            "observation_count": len(category_rows),
            "known_validator_cost_count": len(known),
            "known_validator_cost_sum_estimate_usd": sum(known),
            "unknown_validator_cost_count": len(category_rows) - len(known),
        }
    return {
        "observations": len(rows), "canonical_cases": len({r.get("case_id") for r in rows}),
        "statuses": dict(statuses), "confusion": {k:counts[k] for k in
            ("true_accept","false_accept","true_reject","false_reject")},
        "FAR_valid_verdicts": ratio(counts["false_accept"], counts["false_accept"]+counts["true_reject"]),
        "FRR_valid_verdicts": ratio(counts["false_reject"], counts["false_reject"]+counts["true_accept"]),
        "incorrect_cheap_valid_coverage": ratio(sum(not r["cheap_correct"] for r in valid),
                                               sum(not r["cheap_correct"] for r in rows)),
        "correct_cheap_valid_coverage": ratio(sum(r["cheap_correct"] for r in valid),
                                             sum(r["cheap_correct"] for r in rows)),
        "final_accuracy_resolved_only": ratio(sum(r["final_correct"] for r in valid), len(valid)),
        "unresolved_final_results": len(rows)-len(valid),
        "escalations": sum(r["escalation"] is True for r in rows),
        "costs": costs,
        "unresolved_validator_costs": unresolved_validator_costs,
        "cost_per_correct_complete_subset": {
            "description": (
                "Complete-case, resolved-route list-price estimate; excludes "
                "observations with unresolved routing or unknown cost; "
                "not unconditional operational cost per correct result"
            ),
            "excluded_observation_count": len(rows) - len(complete),
            "estimated_usd": sum(r["total_cost_estimate_usd"] for r in complete)/cost_correct if cost_correct else None,
            "rows_with_resolved_route_and_cost": len(complete), "correct_results": cost_correct},
    }


def analyse(manifest_path):
    manifest = load(manifest_path)
    config = load(ROOT / manifest["execution_config"])
    raw = ROOT / config["artifacts"]["e1_raw_dir"]
    results = []
    planned = set()
    source_ids = manifest["source_cheap_run_ids"]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Duplicate source IDs")
    for source_id in source_ids:
        cheap_path = raw / (source_id + ".json")
        strong_id = paired_strong_run_id(source_id)
        strong_path = raw / (strong_id + ".json")
        cheap, strong = load(cheap_path), load(strong_path)
        for record, identifier, role in ((cheap,source_id,"cheap"),(strong,strong_id,"strong")):
            if record["run_id"] != identifier or record["model_role"] != role or record["success"] is not True:
                raise ValueError("Invalid frozen source identity/success")
        for key in ("case_id","rendering_id","rendering_level"):
            if cheap[key] != strong[key]:
                raise ValueError("Source pairing mismatch")
        cheap_score, strong_score = score_run(cheap_path), score_run(strong_path)
        for validator_role in manifest["validator_roles"]:
            pricing_role = "cheap" if validator_role == "cheap_validator" else "strong"
            for rep in range(1,manifest["repetitions"]+1):
                run_id = f'{manifest["run_namespace"]}-{source_id}-{validator_role}-R{rep:03d}'
                if run_id in planned:
                    raise ValueError("Duplicate planned run")
                planned.add(run_id)
                path = ROOT / manifest["raw_output_dir"] / (run_id+".json")
                validator = load(path) if path.exists() else None
                if validator is not None:
                    expected = {"run_id":run_id, "experiment":"E2", "source_cheap_run_id":source_id,
                        "paired_strong_run_id":strong_id, "validator_role":validator_role,
                        "requested_model":config["validators"][validator_role]["model"],
                        "candidate_controls":cheap["parsed_response"]["controls"],
                        "case_id":cheap["case_id"],"rendering_id":cheap["rendering_id"],
                        "rendering_level":cheap["rendering_level"]}
                    if any(validator.get(k) != v for k,v in expected.items()):
                        raise ValueError(f"Validator identity mismatch: {path}")
                row = score_observation(cheap_score["exact_match"],strong_score["exact_match"],
                    validator,estimated_record_cost(cheap,"cheap"),estimated_record_cost(strong,"strong"),pricing_role)
                row.update(run_id=run_id,case_id=cheap["case_id"],rendering_id=cheap["rendering_id"],
                           source_cheap_run_id=source_id,validator_role=validator_role,repetition=rep)
                results.append(row)
    per_rep = {f"{role}/R{rep:03d}":summarize([r for r in results if r["validator_role"]==role and r["repetition"]==rep])
               for role in manifest["validator_roles"] for rep in range(1,manifest["repetitions"]+1)}
    per_model = {role:summarize([r for r in results if r["validator_role"]==role]) for role in manifest["validator_roles"]}
    per_case = {f"{role}/{case}":summarize([r for r in results if r["validator_role"]==role and r["case_id"]==case])
                for role in manifest["validator_roles"] for case in sorted({r["case_id"] for r in results})}
    return {"accounting":"Frozen E1 list-price estimates; invoice_verified=false; output+thought; no invocation-counter addition",
        "routing":"Only valid PASS/FAIL resolved; failed/malformed/missing routes unresolved",
        "aggregation":"Descriptive only; 30 canonical cases, shared source realizations and repetitions are dependent; no IID tests or confidence intervals",
        "cost_components": {
            "model_call": "Historical E1 cheap-call list-price estimates reused in reconstructed cascades",
            "validator": "Newly incurred E2 validator calls, estimated from reported usage; unknown usage remains unknown",
            "escalation": "Reconstructed use of historical paired E1 strong-call estimates; unresolved routes have no assigned escalation cost",
            "invoice_verified": False,
        },
        "historical_costs":"Cheap and paired strong reused counterfactually per cascade; not newly incurred E2 API charges",
        "per_model_repetition":per_rep,"per_model":per_model,"per_canonical_case":per_case,"observations":results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", default="config/e2_full_manifest_v1.json")
    args = parser.parse_args()
    print(json.dumps(analyse(ROOT / args.manifest), indent=2))
