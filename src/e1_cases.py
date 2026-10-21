import json
from pathlib import Path

from src.e1_policy import ProcurementCase, evaluate_policy


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = PROJECT_ROOT / "data" / "e1" / "canonical_cases.json"


def load_cases() -> list[ProcurementCase]:
    """
    Load canonical E1 cases from JSON and validate them
    through the ProcurementCase structure.
    """

    with CASES_FILE.open("r", encoding="utf-8") as f:
        records = json.load(f)

    cases = []

    for record in records:
        case = ProcurementCase(
            case_id=record["case_id"],
            amount_usd=record["amount_usd"],
            vendor_status=record["vendor_status"],
            data_classification=record["data_classification"],
            deployment=record["deployment"],
            contract_months=record["contract_months"],
            exception_status=record["exception_status"],
            exception_scope=record["exception_scope"],
        )

        cases.append(case)

    return cases


def main() -> None:
    cases = load_cases()

    print(f"Loaded {len(cases)} canonical cases.\n")

    for case in cases:
        decision = evaluate_policy(case)

        print(f"{case.case_id}")
        print(f"  disposition: {decision.disposition}")
        print(
            "  controls: "
            + ", ".join(decision.required_controls)
        )
        print()


if __name__ == "__main__":
    main()