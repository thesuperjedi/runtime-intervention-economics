import json
import statistics
from collections import defaultdict
from pathlib import Path

from src.e1_score import score_run


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "e1"
)

DERIVED_DIR = (
    PROJECT_ROOT
    / "data"
    / "derived"
    / "e1"
)

# v1 was generated with an analysis-code defect:
# incorrect usage-field names caused all token counts
# and costs to be reported as zero.
OUTPUT_FILE = (
    DERIVED_DIR
    / "e1_economics_v2.json"
)

# Frozen E1 list-price assumptions.
# USD per 1M tokens.
PRICING = {
    "cheap": {
        "input": 0.30,
        "output": 2.50,
    },
    "strong": {
        "input": 0.75,
        "output": 3.75,
    },
}


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def extract_usage(record):
    usage = record.get("usage")

    if not isinstance(usage, dict):
        raise RuntimeError(
            f"Missing/invalid usage object: "
            f"{record.get('run_id')}"
        )

    required = (
        "total_input_tokens",
        "total_output_tokens",
        "total_thought_tokens",
        "total_tokens",
    )

    missing = [
        name
        for name in required
        if name not in usage
    ]

    if missing:
        raise RuntimeError(
            f"Missing usage fields for "
            f"{record.get('run_id')}: "
            f"{missing}"
        )

    input_tokens = usage[
        "total_input_tokens"
    ]
    output_tokens = usage[
        "total_output_tokens"
    ]
    thought_tokens = usage[
        "total_thought_tokens"
    ]
    total_tokens = usage[
        "total_tokens"
    ]

    for name, value in (
        ("input", input_tokens),
        ("output", output_tokens),
        ("thought", thought_tokens),
        ("total", total_tokens),
    ):
        if not isinstance(value, int):
            raise RuntimeError(
                f"Non-integer {name} token count "
                f"for {record.get('run_id')}: "
                f"{value}"
            )

        if value < 0:
            raise RuntimeError(
                f"Negative {name} token count "
                f"for {record.get('run_id')}: "
                f"{value}"
            )

    calculated_total = (
        input_tokens
        + output_tokens
        + thought_tokens
    )

    if calculated_total != total_tokens:
        raise RuntimeError(
            f"Token-total mismatch for "
            f"{record.get('run_id')}: "
            f"input={input_tokens}, "
            f"output={output_tokens}, "
            f"thought={thought_tokens}, "
            f"reported total={total_tokens}"
        )

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thought_tokens": thought_tokens,
        "total_tokens": total_tokens,
    }


def estimate_cost(role, usage):
    rates = PRICING[role]

    input_cost = (
        usage["input_tokens"]
        / 1_000_000
        * rates["input"]
    )

    billed_output_tokens = (
        usage["output_tokens"]
        + usage["thought_tokens"]
    )

    output_cost = (
        billed_output_tokens
        / 1_000_000
        * rates["output"]
    )

    return input_cost + output_cost


def pct(numerator, denominator):
    if denominator == 0:
        return 0.0

    return (
        100.0
        * numerator
        / denominator
    )


def main():
    raw_files = sorted(
        RAW_DIR.glob("E1F-*.json")
    )

    if len(raw_files) != 540:
        raise RuntimeError(
            "Expected 540 E1F records; "
            f"found {len(raw_files)}."
        )

    observations = {}

    for path in raw_files:
        record = load_json(path)
        score = score_run(path)

        if record.get("success") is not True:
            raise RuntimeError(
                "Economics analysis expected "
                "successful execution: "
                f"{record.get('run_id')}"
            )

        role = record["model_role"]

        if role not in PRICING:
            raise RuntimeError(
                f"Unknown model role: {role}"
            )

        rendering_id = record[
            "rendering_id"
        ]

        try:
            rep = int(
                record["run_id"].rsplit(
                    "-R",
                    1,
                )[1]
            )
        except Exception as exc:
            raise RuntimeError(
                "Could not parse repetition from "
                f"{record['run_id']}"
            ) from exc

        key = (
            rendering_id,
            rep,
        )

        usage = extract_usage(record)

        cost = estimate_cost(
            role,
            usage,
        )

        observation = {
            "run_id": record["run_id"],
            "rendering_id":
                rendering_id,
            "case_id":
                record["case_id"],
            "rendering_level":
                record["rendering_level"],
            "rep":
                rep,
            "role":
                role,
            "exact_match":
                score["exact_match"],
            "latency_ms":
                record.get("latency_ms"),
            **usage,
            "list_price_cost_usd":
                cost,
        }

        observations.setdefault(
            key,
            {},
        )

        if role in observations[key]:
            raise RuntimeError(
                "Duplicate paired observation: "
                f"{key} {role}"
            )

        observations[key][role] = (
            observation
        )

    if len(observations) != 270:
        raise RuntimeError(
            "Expected 270 paired "
            "realizations; "
            f"found {len(observations)}."
        )

    incomplete = [
        key
        for key, pair
        in observations.items()
        if set(pair)
        != {"cheap", "strong"}
    ]

    if incomplete:
        raise RuntimeError(
            "Incomplete cheap/strong pairs: "
            f"{incomplete[:10]}"
        )

    # ----------------------------------------------
    # Underlying model statistics.
    # ----------------------------------------------

    model_stats = {}

    for role in ("cheap", "strong"):
        rows = [
            pair[role]
            for pair
            in observations.values()
        ]

        costs = [
            row[
                "list_price_cost_usd"
            ]
            for row in rows
        ]

        correct = sum(
            int(row["exact_match"])
            for row in rows
        )

        model_stats[role] = {
            "calls":
                len(rows),
            "correct":
                correct,
            "accuracy_pct":
                pct(
                    correct,
                    len(rows),
                ),
            "input_tokens":
                sum(
                    row["input_tokens"]
                    for row in rows
                ),
            "output_tokens":
                sum(
                    row["output_tokens"]
                    for row in rows
                ),
            "thought_tokens":
                sum(
                    row["thought_tokens"]
                    for row in rows
                ),
            "total_tokens":
                sum(
                    row["total_tokens"]
                    for row in rows
                ),
            "total_list_price_cost_usd":
                sum(costs),
            "mean_call_cost_usd":
                statistics.mean(costs),
            "median_call_cost_usd":
                statistics.median(costs),
            "min_call_cost_usd":
                min(costs),
            "max_call_cost_usd":
                max(costs),
        }

    # ----------------------------------------------
    # Strategy reconstruction.
    # ----------------------------------------------

    strategies = {
        "cheap_only": {
            "calls": 0,
            "cheap_calls": 0,
            "strong_calls": 0,
            "correct_final": 0,
            "cost_usd": 0.0,
        },
        "strong_only": {
            "calls": 0,
            "cheap_calls": 0,
            "strong_calls": 0,
            "correct_final": 0,
            "cost_usd": 0.0,
        },
        "cascade": {
            "calls": 0,
            "cheap_calls": 0,
            "strong_calls": 0,
            "correct_final": 0,
            "cost_usd": 0.0,
            "escalations": 0,
        },
        "oracle_routing": {
            "calls": 0,
            "cheap_calls": 0,
            "strong_calls": 0,
            "correct_final": 0,
            "cost_usd": 0.0,
        },
    }

    cascade_by_level = defaultdict(
        lambda: {
            "realizations": 0,
            "escalations": 0,
            "cost_usd": 0.0,
        }
    )

    pair_details = []

    for key in sorted(observations):
        cheap = observations[
            key
        ]["cheap"]

        strong = observations[
            key
        ]["strong"]

        # Cheap only.
        s = strategies["cheap_only"]

        s["calls"] += 1
        s["cheap_calls"] += 1
        s["cost_usd"] += (
            cheap[
                "list_price_cost_usd"
            ]
        )
        s["correct_final"] += int(
            cheap["exact_match"]
        )

        # Strong only.
        s = strategies["strong_only"]

        s["calls"] += 1
        s["strong_calls"] += 1
        s["cost_usd"] += (
            strong[
                "list_price_cost_usd"
            ]
        )
        s["correct_final"] += int(
            strong["exact_match"]
        )

        # Perfect-validator cascade.
        s = strategies["cascade"]

        s["calls"] += 1
        s["cheap_calls"] += 1
        s["cost_usd"] += (
            cheap[
                "list_price_cost_usd"
            ]
        )

        escalated = (
            not cheap["exact_match"]
        )

        if escalated:
            s["calls"] += 1
            s["strong_calls"] += 1
            s["escalations"] += 1
            s["cost_usd"] += (
                strong[
                    "list_price_cost_usd"
                ]
            )

            final_correct = (
                strong["exact_match"]
            )

        else:
            final_correct = True

        s["correct_final"] += int(
            final_correct
        )

        level = cheap[
            "rendering_level"
        ]

        level_stats = (
            cascade_by_level[level]
        )

        level_stats[
            "realizations"
        ] += 1

        level_stats[
            "escalations"
        ] += int(escalated)

        level_stats[
            "cost_usd"
        ] += cheap[
            "list_price_cost_usd"
        ]

        if escalated:
            level_stats[
                "cost_usd"
            ] += strong[
                "list_price_cost_usd"
            ]

        # Oracle-routing baseline.
        s = strategies[
            "oracle_routing"
        ]

        s["calls"] += 1

        if cheap["exact_match"]:
            selected = cheap
            s["cheap_calls"] += 1
        else:
            selected = strong
            s["strong_calls"] += 1

        s["cost_usd"] += (
            selected[
                "list_price_cost_usd"
            ]
        )

        s["correct_final"] += int(
            selected["exact_match"]
        )

        pair_details.append(
            {
                "rendering_id":
                    cheap[
                        "rendering_id"
                    ],
                "rep":
                    cheap["rep"],
                "level":
                    level,
                "cheap_correct":
                    cheap[
                        "exact_match"
                    ],
                "strong_correct":
                    strong[
                        "exact_match"
                    ],
                "escalated":
                    escalated,
                "cheap_cost_usd":
                    cheap[
                        "list_price_cost_usd"
                    ],
                "strong_cost_usd":
                    strong[
                        "list_price_cost_usd"
                    ],
            }
        )

    # ----------------------------------------------
    # Derived strategy metrics.
    # ----------------------------------------------

    for name, s in strategies.items():
        s["final_accuracy_pct"] = pct(
            s["correct_final"],
            270,
        )

        if s["correct_final"] > 0:
            s[
                "cost_per_correct_result_usd"
            ] = (
                s["cost_usd"]
                / s["correct_final"]
            )
        else:
            s[
                "cost_per_correct_result_usd"
            ] = None

    cascade = strategies[
        "cascade"
    ]

    strong_only = strategies[
        "strong_only"
    ]

    cascade[
        "escalation_rate_pct"
    ] = pct(
        cascade["escalations"],
        270,
    )

    savings_vs_strong = (
        strong_only["cost_usd"]
        - cascade["cost_usd"]
    )

    savings_pct_vs_strong = pct(
        savings_vs_strong,
        strong_only["cost_usd"],
    )

    # Primary E1 convention:
    # deterministic validator monetary/API
    # cost = $0.
    #
    # Sensitivity analysis:
    # validate after every cheap call and
    # again after every escalated strong call.
    validator_invocations = (
        270
        + cascade["escalations"]
    )

    if savings_vs_strong > 0:
        validator_break_even = (
            savings_vs_strong
            / validator_invocations
        )
    else:
        validator_break_even = 0.0

    for level, values in (
        cascade_by_level.items()
    ):
        values[
            "escalation_rate_pct"
        ] = pct(
            values["escalations"],
            values["realizations"],
        )

    result = {
        "experiment": "E1",
        "analysis_version": "2.0",
        "supersedes":
            "e1_economics_v1.json",
        "supersession_reason":
            "v1 used incorrect usage-field "
            "names and therefore reported "
            "zero tokens and zero cost.",
        "pricing_basis": {
            "type":
                "frozen_list_price_estimate",
            "currency":
                "USD",
            "per_million_tokens":
                PRICING,
            "usage_basis":
                "normalized total_input_tokens, "
                "total_output_tokens, and "
                "total_thought_tokens from "
                "raw E1F evidence",
            "validator_primary_monetary_cost_usd":
                0.0,
            "note":
                "List-price estimate, not "
                "invoiced provider charge.",
        },
        "paired_realizations":
            270,
        "underlying_model_stats":
            model_stats,
        "strategies":
            strategies,
        "cascade_by_rendering_level":
            dict(cascade_by_level),
        "comparison": {
            "cascade_savings_vs_strong_usd":
                savings_vs_strong,
            "cascade_savings_pct_vs_strong":
                savings_pct_vs_strong,
            "validator_invocations":
                validator_invocations,
            "validator_break_even_mean_cost_per_check_usd":
                validator_break_even,
        },
        "pair_details":
            pair_details,
    }

    DERIVED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "x",
        encoding="utf-8",
    ) as f:
        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False,
        )

    # ----------------------------------------------
    # Console report.
    # ----------------------------------------------

    print("E1 ECONOMICS V2")
    print("===============")

    print()
    print("Underlying model calls")
    print("----------------------")

    for role in (
        "cheap",
        "strong",
    ):
        s = model_stats[role]

        print(f"{role}:")
        print(
            f"  calls:          "
            f"{s['calls']}"
        )
        print(
            f"  correct:        "
            f"{s['correct']}"
        )
        print(
            f"  accuracy:       "
            f"{s['accuracy_pct']:.2f}%"
        )
        print(
            f"  input tokens:   "
            f"{s['input_tokens']}"
        )
        print(
            f"  output tokens:  "
            f"{s['output_tokens']}"
        )
        print(
            f"  thought tokens: "
            f"{s['thought_tokens']}"
        )
        print(
            f"  total tokens:   "
            f"{s['total_tokens']}"
        )
        print(
            f"  total cost:     "
            f"${s['total_list_price_cost_usd']:.6f}"
        )
        print(
            f"  mean call cost: "
            f"${s['mean_call_cost_usd']:.6f}"
        )
        print(
            f"  median cost:    "
            f"${s['median_call_cost_usd']:.6f}"
        )
        print(
            f"  cost range:     "
            f"${s['min_call_cost_usd']:.6f}"
            f" - "
            f"${s['max_call_cost_usd']:.6f}"
        )

    print()
    print("Strategy reconstruction")
    print("-----------------------")

    for name in (
        "cheap_only",
        "strong_only",
        "cascade",
        "oracle_routing",
    ):
        s = strategies[name]

        print(name)
        print(
            f"  calls:          "
            f"{s['calls']}"
        )
        print(
            f"  cheap calls:    "
            f"{s['cheap_calls']}"
        )
        print(
            f"  strong calls:   "
            f"{s['strong_calls']}"
        )
        print(
            f"  correct final:  "
            f"{s['correct_final']}/270"
        )
        print(
            f"  final accuracy: "
            f"{s['final_accuracy_pct']:.2f}%"
        )
        print(
            f"  total cost:     "
            f"${s['cost_usd']:.6f}"
        )
        print(
            f"  cost/correct:   "
            f"${s['cost_per_correct_result_usd']:.8f}"
        )

        if name == "cascade":
            print(
                f"  escalations:    "
                f"{s['escalations']}/270 "
                f"({s['escalation_rate_pct']:.2f}%)"
            )

    print()
    print("Cascade vs strong-only")
    print("----------------------")
    print(
        f"Savings: "
        f"${savings_vs_strong:.6f}"
    )
    print(
        f"Savings percentage: "
        f"{savings_pct_vs_strong:.2f}%"
    )

    print()
    print("Validator sensitivity")
    print("---------------------")
    print(
        "Validator checks under cascade: "
        f"{validator_invocations}"
    )
    print(
        "Break-even mean validator "
        "cost/check: "
        f"${validator_break_even:.8f}"
    )

    print()
    print("Cascade escalation by level")
    print("---------------------------")

    for level in sorted(
        cascade_by_level
    ):
        s = cascade_by_level[
            level
        ]

        print(
            f"{level}: "
            f"{s['escalations']}/"
            f"{s['realizations']} "
            f"({s['escalation_rate_pct']:.2f}%)"
        )

    print()
    print(
        "Derived result written: "
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()