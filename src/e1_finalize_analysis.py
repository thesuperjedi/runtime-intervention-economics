import json
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

ECONOMICS_FILE = (
    PROJECT_ROOT
    / "data"
    / "derived"
    / "e1"
    / "e1_economics_v2.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "derived"
    / "e1"
    / "e1_final_analysis_v1.json"
)


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def money(value):
    return f"${value:.8f}"


def main():
    economics = load_json(ECONOMICS_FILE)

    strategies = economics["strategies"]

    cascade_model_cost = (
        strategies["cascade"]["cost_usd"]
    )

    strong_model_cost = (
        strategies["strong_only"]["cost_usd"]
    )

    base_saving = (
        strong_model_cost
        - cascade_model_cost
    )

    escalations = (
        strategies["cascade"]["escalations"]
    )

    realizations = economics[
        "paired_realizations"
    ]

    cascade_checks = (
        realizations + escalations
    )

    strong_checks = realizations

    # --------------------------------------------------
    # Validator sensitivity
    # --------------------------------------------------

    # Scenario A:
    # Validator is treated as an additional control cost
    # of the cascade only.
    #
    # Cascade total:
    # cascade_model_cost + cascade_checks * V
    #
    # Strong-only:
    # strong_model_cost
    scenario_a_break_even = (
        base_saving / cascade_checks
    )

    # Scenario B:
    # Every accepted result must be validated.
    #
    # Cascade:
    # cascade_model_cost + cascade_checks * V
    #
    # Strong-only:
    # strong_model_cost + strong_checks * V
    #
    # Only the EXTRA validation count matters:
    # cascade_checks - strong_checks = escalations.
    extra_checks = (
        cascade_checks - strong_checks
    )

    scenario_b_break_even = (
        base_saving / extra_checks
        if extra_checks > 0
        else None
    )

    sensitivity_costs = [
        0.0,
        0.0001,
        0.00025,
        0.0005,
        0.00070346,
        0.001,
        0.002,
        0.005,
        0.006,
        0.0063,
        0.007,
    ]

    sensitivity_rows = []

    for validator_cost in sensitivity_costs:

        # Scenario A
        cascade_a = (
            cascade_model_cost
            + cascade_checks
            * validator_cost
        )

        strong_a = strong_model_cost

        saving_a = (
            strong_a - cascade_a
        )

        # Scenario B
        cascade_b = (
            cascade_model_cost
            + cascade_checks
            * validator_cost
        )

        strong_b = (
            strong_model_cost
            + strong_checks
            * validator_cost
        )

        saving_b = (
            strong_b - cascade_b
        )

        sensitivity_rows.append(
            {
                "validator_cost_per_check_usd":
                    validator_cost,
                "scenario_a": {
                    "cascade_total_usd":
                        cascade_a,
                    "strong_total_usd":
                        strong_a,
                    "cascade_saving_usd":
                        saving_a,
                    "cascade_cheaper":
                        saving_a > 0,
                },
                "scenario_b": {
                    "cascade_total_usd":
                        cascade_b,
                    "strong_total_usd":
                        strong_b,
                    "cascade_saving_usd":
                        saving_b,
                    "cascade_cheaper":
                        saving_b > 0,
                },
            }
        )

    # --------------------------------------------------
    # Cheap-model failure structure
    # --------------------------------------------------

    case_stats = defaultdict(
        lambda: {
            "total": 0,
            "failures": 0,
            "L1": {
                "total": 0,
                "failures": 0,
            },
            "L2": {
                "total": 0,
                "failures": 0,
            },
            "L3": {
                "total": 0,
                "failures": 0,
            },
            "failure_patterns": defaultdict(int),
        }
    )

    raw_files = sorted(
        RAW_DIR.glob(
            "E1F-*-cheap-*.json"
        )
    )

    if len(raw_files) != 270:
        raise RuntimeError(
            "Expected 270 cheap E1F records; "
            f"found {len(raw_files)}."
        )

    total_failures = 0

    for path in raw_files:
        run = load_json(path)
        scored = score_run(path)

        case_id = scored["case_id"]
        rendering_id = scored[
            "rendering_id"
        ]

        level = rendering_id.rsplit(
            "-",
            1,
        )[1]

        if level not in {
            "L1",
            "L2",
            "L3",
        }:
            raise RuntimeError(
                f"Unexpected level: {level}"
            )

        stats = case_stats[case_id]

        stats["total"] += 1
        stats[level]["total"] += 1

        if not scored["exact_match"]:
            total_failures += 1

            stats["failures"] += 1
            stats[level]["failures"] += 1

            expected = tuple(
                scored["expected_controls"]
            )

            actual = tuple(
                scored["actual_controls"]
                if scored["actual_controls"]
                is not None
                else []
            )

            pattern = (
                f"expected={expected} "
                f"actual={actual}"
            )

            stats[
                "failure_patterns"
            ][pattern] += 1

    if total_failures != 34:
        raise RuntimeError(
            "Expected 34 cheap-model "
            f"failures; found {total_failures}."
        )

    failure_cases = {}

    for case_id in sorted(case_stats):
        stats = case_stats[case_id]

        if stats["failures"] == 0:
            continue

        failure_cases[case_id] = {
            "total_realizations":
                stats["total"],
            "failures":
                stats["failures"],
            "failure_rate_pct":
                (
                    100.0
                    * stats["failures"]
                    / stats["total"]
                ),
            "by_level": {
                level: {
                    "total":
                        stats[level]["total"],
                    "failures":
                        stats[level]["failures"],
                }
                for level in (
                    "L1",
                    "L2",
                    "L3",
                )
            },
            "failure_patterns": [
                {
                    "pattern": pattern,
                    "count": count,
                }
                for pattern, count
                in sorted(
                    stats[
                        "failure_patterns"
                    ].items(),
                    key=lambda item:
                        (
                            -item[1],
                            item[0],
                        ),
                )
            ],
        }

    ranked_failure_cases = sorted(
        failure_cases.items(),
        key=lambda item: (
            -item[1]["failures"],
            item[0],
        ),
    )

    top_three_failures = sum(
        stats["failures"]
        for _, stats
        in ranked_failure_cases[:3]
    )

    top_three_share = (
        100.0
        * top_three_failures
        / total_failures
    )

    result = {
        "experiment": "E1",
        "analysis":
            "final_validator_and_failure_analysis",
        "validator_sensitivity": {
            "base_model_costs": {
                "cascade_usd":
                    cascade_model_cost,
                "strong_only_usd":
                    strong_model_cost,
                "cascade_model_saving_usd":
                    base_saving,
            },
            "counts": {
                "realizations":
                    realizations,
                "escalations":
                    escalations,
                "cascade_validator_checks":
                    cascade_checks,
                "strong_only_validator_checks_if_universal":
                    strong_checks,
                "extra_cascade_checks_under_universal_validation":
                    extra_checks,
            },
            "scenario_a": {
                "definition":
                    "Validator cost charged only "
                    "to the cascade.",
                "break_even_validator_cost_per_check_usd":
                    scenario_a_break_even,
            },
            "scenario_b": {
                "definition":
                    "Every accepted result must "
                    "be validated; both cascade "
                    "and strong-only incur "
                    "validator cost.",
                "break_even_validator_cost_per_check_usd":
                    scenario_b_break_even,
            },
            "sensitivity_rows":
                sensitivity_rows,
        },
        "cheap_failure_structure": {
            "total_cheap_observations":
                270,
            "total_failures":
                total_failures,
            "cases_with_any_failure":
                len(failure_cases),
            "top_three_failure_cases":
                [
                    case_id
                    for case_id, _
                    in ranked_failure_cases[:3]
                ],
            "top_three_failure_count":
                top_three_failures,
            "top_three_failure_share_pct":
                top_three_share,
            "cases":
                failure_cases,
        },
    }

    OUTPUT_FILE.parent.mkdir(
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

    # --------------------------------------------------
    # Console output
    # --------------------------------------------------

    print(
        "E1 FINAL ANALYSIS"
    )
    print(
        "================="
    )

    print()
    print(
        "VALIDATOR SENSITIVITY"
    )
    print(
        "---------------------"
    )

    print(
        "Cascade model-call cost: "
        f"{money(cascade_model_cost)}"
    )

    print(
        "Strong-only model-call cost: "
        f"{money(strong_model_cost)}"
    )

    print(
        "Base cascade saving: "
        f"{money(base_saving)}"
    )

    print()
    print(
        "Scenario A — validator charged "
        "only to cascade"
    )

    print(
        f"  Cascade checks: {cascade_checks}"
    )

    print(
        "  Break-even validator cost/check: "
        f"{money(scenario_a_break_even)}"
    )

    print()
    print(
        "Scenario B — universal validation"
    )

    print(
        f"  Cascade checks:    "
        f"{cascade_checks}"
    )

    print(
        f"  Strong-only checks:"
        f" {strong_checks}"
    )

    print(
        f"  Extra cascade checks: "
        f"{extra_checks}"
    )

    print(
        "  Break-even validator cost/check: "
        f"{money(scenario_b_break_even)}"
    )

    print()
    print(
        "Sensitivity table"
    )

    print(
        "validator      "
        "A saving       "
        "B saving"
    )

    for row in sensitivity_rows:
        v = row[
            "validator_cost_per_check_usd"
        ]

        a = row[
            "scenario_a"
        ][
            "cascade_saving_usd"
        ]

        b = row[
            "scenario_b"
        ][
            "cascade_saving_usd"
        ]

        print(
            f"${v:<12.8f} "
            f"${a:<13.8f} "
            f"${b:<13.8f}"
        )

    print()
    print(
        "CHEAP-MODEL FAILURE STRUCTURE"
    )
    print(
        "-----------------------------"
    )

    print(
        f"Failures: "
        f"{total_failures}/270"
    )

    print(
        "Cases with >=1 failure: "
        f"{len(failure_cases)}/30"
    )

    print()

    print(
        "Case  Fail/9   L1   L2   L3"
    )

    for case_id, stats in (
        ranked_failure_cases
    ):
        print(
            f"{case_id:<5} "
            f"{stats['failures']}/9"
            f"      "
            f"{stats['by_level']['L1']['failures']}/3"
            f"  "
            f"{stats['by_level']['L2']['failures']}/3"
            f"  "
            f"{stats['by_level']['L3']['failures']}/3"
        )

    print()
    print(
        "Top 3 failure cases: "
        + ", ".join(
            case_id
            for case_id, _
            in ranked_failure_cases[:3]
        )
    )

    print(
        "Failures in top 3: "
        f"{top_three_failures}/"
        f"{total_failures} "
        f"({top_three_share:.2f}%)"
    )

    print()
    print(
        "Failure patterns"
    )
    print(
        "----------------"
    )

    for case_id, stats in (
        ranked_failure_cases
    ):
        print()
        print(
            f"{case_id}:"
        )

        for item in stats[
            "failure_patterns"
        ]:
            print(
                f"  {item['count']}x "
                f"{item['pattern']}"
            )

    print()
    print(
        "Derived result written: "
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()