import json
from collections import Counter, defaultdict
from pathlib import Path

from src.e1_score import score_run


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MANIFEST_FILE = (
    PROJECT_ROOT
    / "config"
    / "e1_full_manifest_v1.json"
)

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

OUTPUT_FILE = (
    DERIVED_DIR
    / "e1_full_scored_v1.json"
)

EXPECTED_MODELS = {
    "cheap": "gemini-3.5-flash-lite",
    "strong": "gemini-3.8-flash",
}

EXPECTED_EXECUTION_CONFIG_VERSION = "1.0-pilot"


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def expected_run_ids(manifest):
    expected = set()

    namespace = manifest["run_namespace"]

    for rendering_id in manifest["renderings"]:
        for role in manifest["model_roles"]:
            for rep in range(
                1,
                manifest["repetitions"] + 1,
            ):
                expected.add(
                    f"{namespace}-"
                    f"{rendering_id}-"
                    f"{role}-"
                    f"R{rep:03d}"
                )

    return expected


def pct(numerator, denominator):
    if denominator == 0:
        return 0.0

    return 100.0 * numerator / denominator


def main():
    manifest = load_json(MANIFEST_FILE)

    raw_files = sorted(
        RAW_DIR.glob("E1F-*.json")
    )

    expected_ids = expected_run_ids(manifest)

    raw_records = []
    integrity_issues = []

    for path in raw_files:
        try:
            record = load_json(path)
        except Exception as exc:
            integrity_issues.append(
                {
                    "type": "unreadable_json",
                    "file": str(path),
                    "detail": str(exc),
                }
            )
            continue

        raw_records.append(
            (path, record)
        )

    observed_ids = [
        record.get("run_id")
        for _, record in raw_records
    ]

    observed_id_set = set(observed_ids)

    # --------------------------------------------------
    # Manifest reconciliation.
    # --------------------------------------------------

    missing_ids = sorted(
        expected_ids - observed_id_set
    )

    unexpected_ids = sorted(
        observed_id_set - expected_ids
    )

    duplicate_run_ids = sorted(
        run_id
        for run_id, count
        in Counter(observed_ids).items()
        if count > 1
    )

    if missing_ids:
        integrity_issues.append(
            {
                "type": "missing_run_ids",
                "count": len(missing_ids),
                "run_ids": missing_ids,
            }
        )

    if unexpected_ids:
        integrity_issues.append(
            {
                "type": "unexpected_run_ids",
                "count": len(unexpected_ids),
                "run_ids": unexpected_ids,
            }
        )

    if duplicate_run_ids:
        integrity_issues.append(
            {
                "type": "duplicate_run_ids",
                "count": len(duplicate_run_ids),
                "run_ids": duplicate_run_ids,
            }
        )

    # --------------------------------------------------
    # Per-record integrity checks.
    # --------------------------------------------------

    role_counts = Counter()
    level_counts = Counter()
    success_counts = Counter()

    rendering_role_rep_counts = Counter()

    for path, record in raw_records:
        run_id = record.get("run_id")
        role = record.get("model_role")
        rendering_id = record.get(
            "rendering_id"
        )

        level = record.get(
            "rendering_level"
        )

        success = record.get("success")

        role_counts[role] += 1
        level_counts[level] += 1
        success_counts[success] += 1

        expected_model = EXPECTED_MODELS.get(role)

        if expected_model is None:
            integrity_issues.append(
                {
                    "type": "unknown_model_role",
                    "run_id": run_id,
                    "value": role,
                }
            )

        elif record.get(
            "requested_model"
        ) != expected_model:
            integrity_issues.append(
                {
                    "type":
                        "unexpected_requested_model",
                    "run_id": run_id,
                    "expected": expected_model,
                    "actual": record.get(
                        "requested_model"
                    ),
                }
            )

        if record.get(
            "execution_config_version"
        ) != EXPECTED_EXECUTION_CONFIG_VERSION:
            integrity_issues.append(
                {
                    "type":
                        "unexpected_execution_config_version",
                    "run_id": run_id,
                    "expected":
                        EXPECTED_EXECUTION_CONFIG_VERSION,
                    "actual": record.get(
                        "execution_config_version"
                    ),
                }
            )

        if success is not True:
            integrity_issues.append(
                {
                    "type":
                        "execution_not_successful",
                    "run_id": run_id,
                    "success": success,
                }
            )

        if not isinstance(
            rendering_id,
            str,
        ):
            integrity_issues.append(
                {
                    "type":
                        "invalid_rendering_id",
                    "run_id": run_id,
                    "value": rendering_id,
                }
            )
            continue

        if level not in {
            "L1",
            "L2",
            "L3",
        }:
            integrity_issues.append(
                {
                    "type":
                        "unexpected_rendering_level",
                    "run_id": run_id,
                    "value": level,
                }
            )

        # Parse repetition from run ID.
        try:
            rep_text = run_id.rsplit(
                "-R",
                1,
            )[1]

            rep = int(rep_text)

        except Exception:
            integrity_issues.append(
                {
                    "type":
                        "invalid_run_id_rep",
                    "run_id": run_id,
                }
            )
            continue

        rendering_role_rep_counts[
            (
                rendering_id,
                role,
                rep,
            )
        ] += 1

        parsed = record.get(
            "parsed_response"
        )

        if isinstance(parsed, dict):
            controls = parsed.get(
                "controls"
            )

            if isinstance(
                controls,
                list,
            ):
                if len(controls) != len(
                    set(controls)
                ):
                    integrity_issues.append(
                        {
                            "type":
                                "duplicate_controls",
                            "run_id": run_id,
                            "controls": controls,
                        }
                    )

    # --------------------------------------------------
    # Verify every intended tuple exactly once.
    # --------------------------------------------------

    for rendering_id in manifest[
        "renderings"
    ]:
        for role in manifest[
            "model_roles"
        ]:
            for rep in range(
                1,
                manifest["repetitions"] + 1,
            ):
                count = (
                    rendering_role_rep_counts[
                        (
                            rendering_id,
                            role,
                            rep,
                        )
                    ]
                )

                if count != 1:
                    integrity_issues.append(
                        {
                            "type":
                                "tuple_count_not_one",
                            "rendering_id":
                                rendering_id,
                            "model_role":
                                role,
                            "rep":
                                rep,
                            "count":
                                count,
                        }
                    )

    # --------------------------------------------------
    # Score every readable observation.
    # --------------------------------------------------

    scored = []

    for path, _ in raw_records:
        result = score_run(path)
        scored.append(result)

    overall_total = len(scored)

    overall_correct = sum(
        1
        for result in scored
        if result["exact_match"]
    )

    scoring_status_counts = Counter(
        result["scoring_status"]
        for result in scored
    )

    by_role = defaultdict(
        lambda: {
            "total": 0,
            "correct": 0,
        }
    )

    by_level = defaultdict(
        lambda: {
            "total": 0,
            "correct": 0,
        }
    )

    by_role_level = defaultdict(
        lambda: {
            "total": 0,
            "correct": 0,
        }
    )

    incorrect = []

    for result in scored:
        role = result["model_role"]

        rendering_id = result[
            "rendering_id"
        ]

        level = rendering_id.rsplit(
            "-",
            1,
        )[1]

        by_role[role]["total"] += 1
        by_level[level]["total"] += 1

        key = f"{role}:{level}"

        by_role_level[key]["total"] += 1

        if result["exact_match"]:
            by_role[role]["correct"] += 1
            by_level[level]["correct"] += 1
            by_role_level[key][
                "correct"
            ] += 1

        else:
            incorrect.append(result)

    def add_accuracy(mapping):
        output = {}

        for key, values in sorted(
            mapping.items()
        ):
            total = values["total"]
            correct = values["correct"]

            output[key] = {
                "total": total,
                "correct": correct,
                "incorrect":
                    total - correct,
                "accuracy_pct":
                    pct(correct, total),
            }

        return output

    summary = {
        "experiment": "E1",
        "run_namespace": "E1F",
        "integrity": {
            "raw_files_found":
                len(raw_files),
            "readable_records":
                len(raw_records),
            "expected_run_ids":
                len(expected_ids),
            "unique_observed_run_ids":
                len(observed_id_set),
            "missing_run_ids":
                len(missing_ids),
            "unexpected_run_ids":
                len(unexpected_ids),
            "duplicate_run_ids":
                len(duplicate_run_ids),
            "role_counts":
                dict(role_counts),
            "rendering_level_counts":
                dict(level_counts),
            "success_counts": {
                str(key): value
                for key, value
                in success_counts.items()
            },
            "integrity_issue_count":
                len(integrity_issues),
            "integrity_issues":
                integrity_issues,
        },
        "scoring": {
            "total": overall_total,
            "correct": overall_correct,
            "incorrect":
                overall_total
                - overall_correct,
            "accuracy_pct":
                pct(
                    overall_correct,
                    overall_total,
                ),
            "scoring_status_counts":
                dict(scoring_status_counts),
            "by_role":
                add_accuracy(by_role),
            "by_level":
                add_accuracy(by_level),
            "by_role_level":
                add_accuracy(
                    by_role_level
                ),
            "incorrect_observations":
                incorrect,
        },
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
            summary,
            f,
            indent=2,
            ensure_ascii=False,
        )

    # --------------------------------------------------
    # Console report.
    # --------------------------------------------------

    print("E1F INTEGRITY")
    print("-------------")
    print(
        f"Raw files found:       "
        f"{len(raw_files)}"
    )
    print(
        f"Readable records:      "
        f"{len(raw_records)}"
    )
    print(
        f"Expected observations: "
        f"{len(expected_ids)}"
    )
    print(
        f"Unique run IDs:        "
        f"{len(observed_id_set)}"
    )
    print(
        f"Missing run IDs:       "
        f"{len(missing_ids)}"
    )
    print(
        f"Unexpected run IDs:    "
        f"{len(unexpected_ids)}"
    )
    print(
        f"Duplicate run IDs:     "
        f"{len(duplicate_run_ids)}"
    )
    print(
        f"Integrity issues:      "
        f"{len(integrity_issues)}"
    )

    print()
    print(
        f"Role counts:  "
        f"{dict(role_counts)}"
    )
    print(
        f"Level counts: "
        f"{dict(level_counts)}"
    )
    print(
        f"Success:      "
        f"{dict(success_counts)}"
    )

    print()
    print("E1F CORRECTNESS")
    print("---------------")
    print(
        f"Overall: "
        f"{overall_correct}/"
        f"{overall_total} "
        f"({pct(overall_correct, overall_total):.2f}%)"
    )

    print()
    print("By model role:")

    for key, values in add_accuracy(
        by_role
    ).items():
        print(
            f"  {key:6} "
            f"{values['correct']}/"
            f"{values['total']} "
            f"({values['accuracy_pct']:.2f}%)"
        )

    print()
    print("By rendering level:")

    for key, values in add_accuracy(
        by_level
    ).items():
        print(
            f"  {key:2} "
            f"{values['correct']}/"
            f"{values['total']} "
            f"({values['accuracy_pct']:.2f}%)"
        )

    print()
    print("By role and level:")

    for key, values in add_accuracy(
        by_role_level
    ).items():
        print(
            f"  {key:10} "
            f"{values['correct']}/"
            f"{values['total']} "
            f"({values['accuracy_pct']:.2f}%)"
        )

    print()
    print(
        "Incorrect observations: "
        f"{len(incorrect)}"
    )

    for result in incorrect:
        print(
            f"  {result['run_id']}"
        )
        print(
            f"    expected: "
            f"{result['expected_controls']}"
        )
        print(
            f"    actual:   "
            f"{result['actual_controls']}"
        )

    print()
    print(
        f"Derived result written: "
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()