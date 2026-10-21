import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CASES_FILE = (
    PROJECT_ROOT / "data" / "e1" / "canonical_cases.json"
)

RENDERINGS_FILE = (
    PROJECT_ROOT / "data" / "e1" / "renderings_v1.json"
)

VALID_LEVELS = {"L1", "L2", "L3"}


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_structure(cases, renderings):
    if not isinstance(cases, list):
        raise ValueError("Canonical cases file must contain a JSON list.")

    if not isinstance(renderings, list):
        raise ValueError("Renderings file must contain a JSON list.")

    case_ids = [c["case_id"] for c in cases]

    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Duplicate canonical case IDs found.")

    rendering_ids = [r["rendering_id"] for r in renderings]

    duplicates = [
        rid
        for rid, count in Counter(rendering_ids).items()
        if count > 1
    ]

    if duplicates:
        raise ValueError(
            f"Duplicate rendering IDs: {duplicates}"
        )

    canonical_case_ids = set(case_ids)

    grouped = {}

    for r in renderings:
        case_id = r["case_id"]
        level = r["rendering_level"]

        if case_id not in canonical_case_ids:
            raise ValueError(
                f"{r['rendering_id']}: unknown case_id {case_id}"
            )

        if level not in VALID_LEVELS:
            raise ValueError(
                f"{r['rendering_id']}: invalid level {level}"
            )

        expected_id = f"{case_id}-{level}"

        if r["rendering_id"] != expected_id:
            raise ValueError(
                f"{r['rendering_id']}: expected {expected_id}"
            )

        if not isinstance(r["text"], str) or not r["text"].strip():
            raise ValueError(
                f"{r['rendering_id']}: empty rendering text"
            )

        grouped.setdefault(case_id, set()).add(level)

    for case_id in canonical_case_ids:
        levels = grouped.get(case_id, set())

        if levels != VALID_LEVELS:
            raise ValueError(
                f"{case_id}: expected L1/L2/L3; "
                f"found {sorted(levels)}"
            )


def check_fact_markers(case, rendering):
    """
    Mechanical consistency check.

    This does NOT prove semantic equivalence.
    It checks that explicit representations of the
    canonical facts appear in the rendering.
    """

    text = rendering["text"]
    rid = rendering["rendering_id"]
    text_lower = text.lower()

    errors = []

    # Amount
    amount_marker = f"USD {case['amount_usd']:,}"

    if amount_marker not in text:
        errors.append(
            f"amount marker missing: {amount_marker}"
        )

    # Contract duration
    months = case["contract_months"]

    acceptable_duration_markers = [
        f"{months} months",
        f"{months}-month",
    ]

    if not any(
            marker in text
            for marker in acceptable_duration_markers
    ):
        errors.append(
            f"duration marker missing: "
            f"{months} months / {months}-month"
        )

    # Data classification
    classification = case["data_classification"]

    if classification not in text:
        errors.append(
            f"data classification missing: {classification}"
        )

    # Supplier status
    vendor_status = case["vendor_status"]

    if vendor_status == "approved":
        if "approved" not in text:
            errors.append("approved supplier status missing")

    elif vendor_status == "unapproved":
        if "unapproved" not in text:
            errors.append("unapproved supplier status missing")

    elif vendor_status == "prohibited":
        if "prohibited" not in text:
            errors.append("prohibited supplier status missing")

    # Deployment
    deployment = case["deployment"]

    if deployment == "external_saas":
        acceptable = [
            "external SaaS",
            "externally hosted SaaS",
        ]

        if not any(marker in text for marker in acceptable):
            errors.append("external SaaS deployment marker missing")

    elif deployment == "internal":
        acceptable = [
            "deployed internally",
            "internally deployed",
            "internal deployment",
            "deploy the service internally",
        ]

        if not any(marker in text for marker in acceptable):
            errors.append("internal deployment marker missing")

    # Exception status and scope
    exception_status = case["exception_status"]
    exception_scope = case["exception_scope"]

    if exception_status == "none":
        marker = "no exception has been approved"

        if marker not in text_lower:
            errors.append("no-exception marker missing")

    elif exception_status == "approved":

        if "approved exception" not in text:
            errors.append("approved-exception marker missing")

        if exception_scope == "vendor":
            acceptable = [
                "only to the vendor approval requirement",
                "specifically for the vendor approval requirement",
                "specifically to the vendor approval requirement",
            ]

            if not any(marker in text for marker in acceptable):
                errors.append(
                    "vendor exception scope marker missing"
                )

        elif exception_scope == "external_restricted_data":
            acceptable = [
                "only to external processing of restricted information",
                "specifically for external processing of restricted information",
                "specifically to external processing of restricted information",
                "limited specifically to external processing of restricted information",
            ]

            if not any(marker in text for marker in acceptable):
                errors.append(
                    "external restricted-data exception scope marker missing"
                )

        elif exception_scope == "both":
            vendor_markers = [
                "vendor approval requirement",
            ]

            restricted_data_markers = [
                "external processing of restricted information",
            ]

            if not (
                    any(marker in text for marker in vendor_markers)
                    and
                    any(marker in text for marker in restricted_data_markers)
            ):
                errors.append(
                    "both-exception scope marker missing"
                )

    return rid, errors


def main():
    cases = load_json(CASES_FILE)
    renderings = load_json(RENDERINGS_FILE)

    validate_structure(cases, renderings)

    cases_by_id = {
        case["case_id"]: case
        for case in cases
    }

    failures = []

    for rendering in renderings:
        case = cases_by_id[rendering["case_id"]]

        rid, errors = check_fact_markers(
            case,
            rendering,
        )

        if errors:
            failures.append((rid, errors))

    print(f"Canonical cases: {len(cases)}")
    print(f"Renderings: {len(renderings)}")
    print()

    print("Structural validation: PASSED")

    if failures:
        print("Canonical fact-marker validation: FAILED")
        print()

        for rid, errors in failures:
            print(rid)

            for error in errors:
                print(f"  - {error}")

        raise SystemExit(1)

    print("Canonical fact-marker validation: PASSED")
    print()
    print(
        "NOTE: Fact-marker validation does not prove "
        "semantic equivalence or linguistic quality."
    )


if __name__ == "__main__":
    main()