import argparse
import json
from pathlib import Path

from src.e1_policy import ProcurementCase, evaluate_policy


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CASES_FILE = (
    PROJECT_ROOT / "data" / "e1" / "canonical_cases.json"
)


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def score_run(run_file):
    run = load_json(run_file)
    cases = load_json(CASES_FILE)

    case_data = next(
        c for c in cases
        if c["case_id"] == run["case_id"]
    )

    case = ProcurementCase(
        case_id=case_data["case_id"],
        amount_usd=case_data["amount_usd"],
        vendor_status=case_data["vendor_status"],
        data_classification=case_data[
            "data_classification"
        ],
        deployment=case_data["deployment"],
        contract_months=case_data["contract_months"],
        exception_status=case_data["exception_status"],
        exception_scope=case_data["exception_scope"],
    )

    decision = evaluate_policy(case)
    expected_controls = list(decision.required_controls)

    parsed = run.get("parsed_response")

    if not run["success"]:
        actual_controls = None
        exact_match = False
        scoring_status = "execution_failure"

    elif not isinstance(parsed, dict):
        actual_controls = None
        exact_match = False
        scoring_status = "invalid_response"

    elif not isinstance(parsed.get("controls"), list):
        actual_controls = None
        exact_match = False
        scoring_status = "invalid_response"

    else:
        actual_controls = parsed["controls"]

        exact_match = (
            set(actual_controls)
            == set(expected_controls)
        )

        scoring_status = "scored"

    return {
        "run_id": run["run_id"],
        "case_id": run["case_id"],
        "rendering_id": run["rendering_id"],
        "model_role": run["model_role"],
        "requested_model": run["requested_model"],
        "oracle_disposition": decision.disposition,
        "scoring_status": scoring_status,
        "expected_controls": sorted(expected_controls),
        "actual_controls": (
            sorted(actual_controls)
            if actual_controls is not None
            else None
        ),
        "exact_match": exact_match,
    }


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "run_file",
        help="Path to raw E1 run JSON file",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    run_file = Path(args.run_file)

    if not run_file.is_absolute():
        run_file = PROJECT_ROOT / run_file

    if not run_file.exists():
        raise FileNotFoundError(
            f"Run file not found: {run_file}"
        )

    result = score_run(run_file)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()