"""New publication arithmetic only. Does not evaluate policy or rescore evidence."""
from pathlib import Path
from decimal import Decimal
from collections import Counter
import json

ROOT = Path(__file__).resolve().parent
MODELS = ("gemini", "claude")
ARMS = ("B0", "B1", "B2")
EP_KEYS = set("key ordinal model scenario arm repetition finalized goal permitted qualified stop decisions effects unpermitted_effects effect_provenance action_attempts evaluated_attempts explicit_policy_response safe_refusal interface_refusal recovery_success".split())
RP_KEYS = set("key ordinal model condition denial_type repetition finalized stop seed_verified compliant_recovery goal_achieved model_generations model_proposals model_policy_evaluations published_effects unpermitted_effects sequence_categories duplicate_submission".split())
CALL_KEYS = set("episode_key call model input generated cached thinking generation_status count_status reservation_usd".split())
STOPS = set("GOAL_COMPLETE AGENT_TERMINAL MALFORMED_OUTPUT DENY OPERATION_FAILED INPUT_LIMIT SUBMISSION_ENDPOINT INTERFACE_UNSUPPORTED".split())

def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def require(ok, label):
    if not ok:
        raise ValueError(label)

def natural(v):
    return type(v) is int and v >= 0

def boolean(v):
    return type(v) is bool

def exact(obj, keys, label):
    require(type(obj) is dict and set(obj) == keys, label)

def validate(ex2, recovery):
    exact(ex2, {"schema", "scope", "episodes", "calls", "eligible_recovery_opportunities"}, "EX2 bundle fields")
    exact(recovery, {"schema", "scope", "episodes", "calls"}, "Recovery bundle fields")
    require(ex2["schema"] == "EX2_PUBLIC_FACTS_1" and ex2["scope"] == "PRIMARY_EX2_ONLY", "EX2 version")
    require(recovery["schema"] == "EX2R_PUBLIC_FACTS_1" and recovery["scope"] == "CONTROLLED_RECOVERY_ONLY", "Recovery version")
    expected = [(m, f"S{s:02d}", a, r) for m in MODELS for s in range(1, 13) for a in ARMS for r in range(1, 4)]
    require(len(ex2["episodes"]) == 216, "216 population")
    for ordinal, (e, identity) in enumerate(zip(ex2["episodes"], expected), 1):
        exact(e, EP_KEYS, "EX2 episode fields")
        m, s, a, r = identity
        require((e["model"], e["scenario"], e["arm"], e["repetition"]) == identity and e["ordinal"] == ordinal, "EX2 fixed order")
        require(e["key"] == f"{m}-{s}-{a}-R{r:02d}", "Public identity")
        require(e["finalized"] is True and e["stop"] in STOPS, "Finalized classification")
        for k in ("goal", "permitted", "explicit_policy_response", "safe_refusal", "interface_refusal", "recovery_success"):
            require(boolean(e[k]), "Boolean outcome")
        require(e["qualified"] is None if a == "B0" else boolean(e["qualified"]), "Qualified applicability")
        require(not e["permitted"] or e["goal"], "Permitted implies goal")
        require(not e["qualified"] or e["permitted"], "Qualified implies permitted")
        require(e["effect_provenance"] == ("INDEPENDENT_SYNTHETIC" if a == "B0" else "AUTHENTICATED_NATIVE"), "Effect provenance")
        for k in ("effects", "unpermitted_effects", "action_attempts", "evaluated_attempts"):
            require(natural(e[k]), "Count")
        require(e["unpermitted_effects"] <= e["effects"], "Effect count consistency")
        require(set(e["decisions"]) <= {"ALLOW", "DENY", "REQUIRE_APPROVAL"} and all(natural(v) for v in e["decisions"].values()), "Decisions")
        require(sum(e["decisions"].values()) == e["evaluated_attempts"], "Decision denominator")
        require(e["evaluated_attempts"] <= e["action_attempts"], "Attempt denominator")
    exact(ex2["eligible_recovery_opportunities"], set(MODELS), "Eligible summary")
    require(all(natural(v) for v in ex2["eligible_recovery_opportunities"].values()), "Eligible counts")
    sequence = [("gemini", "S07", 1), ("claude", "S07", 1), ("claude", "S08", 1), ("gemini", "S08", 1),
                ("claude", "S07", 2), ("gemini", "S07", 2), ("gemini", "S08", 2), ("claude", "S08", 2),
                ("gemini", "S07", 3), ("claude", "S07", 3), ("claude", "S08", 3), ("gemini", "S08", 3)]
    require(len(recovery["episodes"]) == 12, "12 recovery population")
    for i, (e, identity) in enumerate(zip(recovery["episodes"], sequence), 1):
        exact(e, RP_KEYS, "Recovery episode fields")
        require((e["model"], e["condition"], e["repetition"]) == identity and e["ordinal"] == i and e["key"] == f"recovery-{i:02d}", "Recovery fixed order")
        require(e["denial_type"] == ("VENDOR_BLOCKED" if e["condition"] == "S07" else "CC_NOT_DELEGATED"), "Seed condition")
        for k in ("finalized", "seed_verified", "compliant_recovery", "goal_achieved", "duplicate_submission"):
            require(boolean(e[k]), "Recovery outcome")
        require(e["finalized"] and e["seed_verified"], "Verified complete seed")
        for k in ("model_generations", "model_proposals", "model_policy_evaluations", "published_effects", "unpermitted_effects"):
            require(natural(e[k]), "Recovery count")
        require(e["model_proposals"] <= e["model_generations"] <= 2 and e["model_policy_evaluations"] <= e["model_proposals"], "Recovery bound")
        require(e["stop"] in STOPS, "Recovery stop")
        require(len(e["sequence_categories"]) == e["model_generations"], "Recovery sequence")
        for event in e["sequence_categories"]:
            if event.get("kind") == "ACTION":
                exact(event, {"kind", "action"}, "Action categories")
                require(event["action"] in {"SUBMIT_PR", "EXECUTE_PURCHASE", "READ_DOC", "RECOMMEND_PURCHASE", "APPROVE_PURCHASE"}, "Action label")
            else:
                exact(event, {"kind", "response_type", "reason_code"}, "Terminal categories")
                require(event["kind"] == "TERMINAL" and event["response_type"] in {"COMPLETE", "STOP", "REFUSE"} and event["reason_code"] in {"GOAL_COMPLETE", "POLICY", "UNABLE", "UNSUPPORTED_ACTION"}, "Terminal label")
    for bundle, limit in ((ex2, 8), (recovery, 2)):
        eps = {e["key"]: e for e in bundle["episodes"]}
        seen = set()
        for c in bundle["calls"]:
            exact(c, CALL_KEYS, "Call fields")
            require(c["episode_key"] in eps and c["model"] == eps[c["episode_key"]]["model"], "Call identity")
            require(natural(c["call"]) and 1 <= c["call"] <= limit, "Call limit")
            key = (c["episode_key"], c["call"])
            require(key not in seen, "Duplicate call")
            seen.add(key)
            for k in ("input", "generated"):
                require(natural(c[k]), "Required usage")
            for k in ("cached", "thinking"):
                require(c[k] is None or natural(c[k]), "Optional usage")
            require(c["cached"] is None or c["cached"] <= c["input"], "Cache subset")
            require(c["thinking"] is None or c["thinking"] <= c["generated"], "Thinking subset")
            require(c["generation_status"] == c["count_status"] == "SETTLED", "Settlement")
            require(Decimal(c["reservation_usd"]) >= 0, "Reservation")
        for e in eps.values():
            nums = sorted(c["call"] for c in bundle["calls"] if c["episode_key"] == e["key"])
            require(nums == list(range(1, len(nums) + 1)), "Call ordering")
            if bundle is recovery:
                require(len(nums) == e["model_generations"], "Recovery generation join")
    return True

def money(c, rates):
    rate = rates[c["model"]]
    # Missing cache counts receive no credit, not a claim of observed zero cache.
    credit = c["cached"] if c["cached"] is not None else 0
    return ((Decimal(c["input"] - credit) * Decimal(rate["input"])) +
            Decimal(credit) * Decimal(rate["cached_input"]) +
            Decimal(c["generated"]) * Decimal(rate["output"])) / Decimal(1000000)

def resource(calls, rates):
    optional = lambda name: sum(c[name] for c in calls if c[name] is not None) if any(c[name] is not None for c in calls) else None
    return dict(generations=len(calls), counts=len(calls), input=sum(c["input"] for c in calls),
                generated=sum(c["generated"] for c in calls), cached_reported_sum=optional("cached"),
                cache_present=sum(c["cached"] is not None for c in calls), cache_missing=sum(c["cached"] is None for c in calls),
                thinking_reported_sum=optional("thinking"), thinking_present=sum(c["thinking"] is not None for c in calls),
                thinking_missing=sum(c["thinking"] is None for c in calls),
                conditional_usd=str(sum((money(c, rates) for c in calls), Decimal(0))),
                retained_usd=str(sum((Decimal(c["reservation_usd"]) for c in calls), Decimal(0))))

def outcomes(rows):
    qualified = [r["qualified"] for r in rows if r["qualified"] is not None]
    return dict(scheduled=len(rows), goal_true=sum(r["goal"] is True for r in rows),
                goal_false=sum(r["goal"] is False for r in rows), goal_unknown=sum(r["goal"] is None for r in rows),
                permitted_true=sum(r["permitted"] is True for r in rows),
                qualified_true=sum(qualified) if qualified else None, qualified_denominator=len(qualified),
                unpermitted_effects=sum(r["unpermitted_effects"] for r in rows), effects=sum(r["effects"] for r in rows),
                decisions=dict(sum((Counter(r["decisions"]) for r in rows), Counter())),
                stops=dict(Counter(r["stop"] for r in rows)))

def reconstruct(ex2=None, recovery=None, reference=None):
    ex2 = ex2 if ex2 is not None else load("studies/ex2/evidence.json")
    recovery = recovery if recovery is not None else load("studies/ex2_r/evidence.json")
    reference = reference if reference is not None else load("analysis/reference.json")
    validate(ex2, recovery)
    rates = reference["rates_usd_per_million"]
    results = {}
    for model in MODELS:
        results[model] = {}
        for arm in ARMS:
            results[model][arm] = {}
            for scope in ("ALL_EPISODES", "PRIMARY_EXCLUDING_S11"):
                rows = [e for e in ex2["episodes"] if e["model"] == model and e["arm"] == arm and (scope == "ALL_EPISODES" or e["scenario"] != "S11")]
                keys = {e["key"] for e in rows}
                cs = [c for c in ex2["calls"] if c["episode_key"] in keys]
                outcome, usage = outcomes(rows), resource(cs, rates)
                amount = Decimal(usage["conditional_usd"])
                ratios = {k: str(amount / Decimal(outcome[k])) if outcome[k] else None for k in ("goal_true", "permitted_true", "qualified_true")}
                results[model][arm][scope] = {"outcomes": outcome, "resources": usage, "conditional_cost_per_scope_matched_success": ratios}
    matched = {}
    for model in MODELS:
        matched[model] = {}
        for metric in ("goal", "permitted"):
            for left, right in (("B1", "B0"), ("B2", "B1")):
                index = {(e["scenario"], e["arm"], e["repetition"]): e for e in ex2["episodes"] if e["model"] == model}
                values = Counter((index[(f"S{s:02d}", left, r)][metric], index[(f"S{s:02d}", right, r)][metric])
                                 for s in range(1, 13) if s != 11 for r in range(1, 4))
                matched[model][f"{metric}:{left}/{right}"] = {str(a) + "/" + str(b): values[a, b] for a in (True, False) for b in (True, False)}
    rr = {}
    for m in MODELS:
        eps = [e for e in recovery["episodes"] if e["model"] == m]
        rr[m] = dict(scheduled=len(eps), verified_seeds=sum(e["seed_verified"] for e in eps),
                     compliant_recoveries=sum(e["compliant_recovery"] for e in eps),
                     unpermitted_effects=sum(e["unpermitted_effects"] for e in eps),
                     resources=resource([c for c in recovery["calls"] if c["model"] == m], rates),
                     by_condition={s:dict(scheduled=3, compliant=sum(e["compliant_recovery"] for e in eps if e["condition"] == s),
                         resources=resource([c for c in recovery["calls"] if c["episode_key"] in {e["key"] for e in eps if e["condition"] == s}], rates),
                         duplicate_submissions=sum(e["duplicate_submission"] for e in eps if e["condition"] == s),
                         model_policy_evaluations=sum(e["model_policy_evaluations"] for e in eps if e["condition"] == s)) for s in ("S07", "S08")})
    scenario_vectors = {m:{f"S{s:02d}":{a:[e["goal"] for e in ex2["episodes"] if e["model"] == m and e["scenario"] == f"S{s:02d}" and e["arm"] == a] for a in ARMS} for s in range(1,13)} for m in MODELS}
    cross = {}
    for arm in ARMS:
        cross[arm] = {}
        for metric in ("goal", "permitted", "qualified"):
            if metric == "qualified" and arm == "B0":
                cross[arm][metric] = "NOT_APPLICABLE"
                continue
            index = {(e["model"], e["scenario"], e["repetition"]):e for e in ex2["episodes"] if e["arm"] == arm}
            pairs = Counter((index[("gemini",f"S{s:02d}",r)][metric], index[("claude",f"S{s:02d}",r)][metric]) for s in range(1,13) if s != 11 for r in range(1,4))
            cross[arm][metric] = {str(a)+"/"+str(b):pairs[a,b] for a in (True,False) for b in (True,False)}
    return {"EX2": results, "matched": matched, "cross_model_matches":cross, "scenario_goal_vectors":scenario_vectors, "EX2R": rr,
            "EX2_recovery": {m: {"eligible": ex2["eligible_recovery_opportunities"][m], "effectiveness": "NOT_APPLICABLE" if ex2["eligible_recovery_opportunities"][m] == 0 else "SEE_SOURCE"} for m in MODELS},
            "interpretation": "Arithmetic on author-attested public projections; no policy replay, historical authentication or live provider validation."}

def verify_reference(result, ex2, reference):
    for r in reference["ex2_resources"]:
        eps = [e for e in ex2["episodes"] if e["model"] == r["model"] and (r["arm"] == "ALL" or e["arm"] == r["arm"]) and (r["scope"] == "ALL_EPISODES" or e["scenario"] != "S11")]
        keys = {e["key"] for e in eps}
        calls = [c for c in ex2["calls"] if c["episode_key"] in keys]
        t = resource(calls, reference["rates_usd_per_million"])
        o = outcomes(eps)
        fields = {"generations":"generations", "count_calls":"counts", "input_tokens":"input", "generated_tokens":"generated", "cached_input_reported_sum":"cached_reported_sum",
                  "cache_fields_present":"cache_present", "cache_fields_missing":"cache_missing", "thinking_reported_sum":"thinking_reported_sum",
                  "thinking_fields_present":"thinking_present", "thinking_fields_missing":"thinking_missing"}
        for a, b in fields.items():
            require(r[a] == t[b], "Reference resource " + a)
        require(r["generation_settlements"] == len(calls), "Reference settlements")
        require(Decimal(r["conditional_usd"]) == Decimal(t["conditional_usd"]), "Reference cost")
        require(Decimal(r["retained_reservations_usd"]) == Decimal(t["retained_usd"]), "Reference reservation")
        for a,b in (("scheduled","scheduled"),("goal_true","goal_true"),("policy_permitted_goal_true","permitted_true"),("qualified_goal_true","qualified_true")):
            require(r[a] == o[b], "Reference outcome " + a)
    for m in MODELS:
        require(reference["ex2_stops"][m] == dict(Counter(e["stop"] for e in ex2["episodes"] if e["model"] == m)), "Stop references")
        rr = result["EX2R"][m]["resources"]; ref = reference["ex2r_by_model"][m]
        require(rr["generations"] == ref["generation_attempts"] == ref["generation_settlements"], "Recovery generations")
        require(rr["counts"] == ref["count_attempts"] == ref["count_settlements"], "Recovery counts")
        require(Decimal(rr["conditional_usd"]) == Decimal(ref["conditional_usd"]), "Recovery cost")
        require(Decimal(rr["retained_usd"]) == Decimal(ref["retained_usd"]), "Recovery reservation")
    return True

def main():
    ex2, recovery, ref = load("studies/ex2/evidence.json"), load("studies/ex2_r/evidence.json"), load("analysis/reference.json")
    result = reconstruct(ex2, recovery, ref)
    verify_reference(result, ex2, ref)
    print(json.dumps({"status":"PASS", "results":result}, indent=2))

if __name__ == "__main__":
    main()
