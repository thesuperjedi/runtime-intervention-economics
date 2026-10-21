from dataclasses import dataclass
from typing import Literal


VendorStatus = Literal["approved", "unapproved", "prohibited"]
DataClassification = Literal[
    "public",
    "internal",
    "confidential",
    "restricted",
]
Deployment = Literal["internal", "external_saas"]
ExceptionStatus = Literal["none", "approved"]
ExceptionScope = Literal[
    "none",
    "vendor",
    "external_restricted_data",
    "both",
]


@dataclass(frozen=True)
class ProcurementCase:
    case_id: str
    amount_usd: float
    vendor_status: VendorStatus
    data_classification: DataClassification
    deployment: Deployment
    contract_months: int
    exception_status: ExceptionStatus
    exception_scope: ExceptionScope


@dataclass(frozen=True)
class PolicyDecision:
    disposition: Literal["CONTROLLED", "PROHIBITED"]
    required_controls: tuple[str, ...]


def validate_case(case: ProcurementCase) -> None:
    """
    Validate internal consistency of the hidden structured case.
    """

    if case.amount_usd < 0:
        raise ValueError("amount_usd cannot be negative")

    if case.contract_months <= 0:
        raise ValueError("contract_months must be positive")

    if (
        case.exception_status == "none"
        and case.exception_scope != "none"
    ):
        raise ValueError(
            "exception_scope must be 'none' when "
            "exception_status is 'none'"
        )

    if (
        case.exception_status == "approved"
        and case.exception_scope == "none"
    ):
        raise ValueError(
            "approved exception must have an explicit scope"
        )


def exception_covers(
    case: ProcurementCase,
    control: str,
) -> bool:
    """
    Return True only when an approved exception explicitly
    suppresses the specified exception-capable control.
    """

    if case.exception_status != "approved":
        return False

    if control == "SUPPLIER_DUE_DILIGENCE":
        return case.exception_scope in {"vendor", "both"}

    if control == "ENHANCED_SECURITY_REVIEW":
        return case.exception_scope in {
            "external_restricted_data",
            "both",
        }

    return False


def evaluate_policy(case: ProcurementCase) -> PolicyDecision:
    """
    Deterministically calculate E1 Policy v1.0 ground truth.
    """

    validate_case(case)

    # --------------------------------------------------------
    # V3 — Prohibited vendor is terminal.
    # --------------------------------------------------------

    if case.vendor_status == "prohibited":
        return PolicyDecision(
            disposition="PROHIBITED",
            required_controls=("PROHIBITED",),
        )

    controls: list[str] = []

    # --------------------------------------------------------
    # Financial authority — exactly one must apply.
    # --------------------------------------------------------

    if case.amount_usd > 100_000:
        controls.append("SENIOR_FINANCIAL_APPROVAL")

    elif case.amount_usd > 50_000:
        controls.append("ENHANCED_FINANCIAL_APPROVAL")

    else:
        controls.append("STANDARD_FINANCIAL_APPROVAL")

    # --------------------------------------------------------
    # Supplier control.
    # --------------------------------------------------------

    if case.vendor_status == "unapproved":
        if not exception_covers(
            case,
            "SUPPLIER_DUE_DILIGENCE",
        ):
            controls.append("SUPPLIER_DUE_DILIGENCE")

    # --------------------------------------------------------
    # Information-risk controls.
    # --------------------------------------------------------

    if (
        case.data_classification == "restricted"
        and case.deployment == "external_saas"
    ):
        if not exception_covers(
            case,
            "ENHANCED_SECURITY_REVIEW",
        ):
            controls.append("ENHANCED_SECURITY_REVIEW")

    elif (
        case.data_classification == "confidential"
        and case.deployment == "external_saas"
    ):
        controls.append("SECURITY_REVIEW")

    elif (
        case.data_classification == "restricted"
        and case.deployment == "internal"
    ):
        controls.append("SECURITY_REVIEW")

    # public/internal classifications generate no
    # additional information-security control.

    # --------------------------------------------------------
    # Contract-duration control.
    # --------------------------------------------------------

    if case.contract_months > 24:
        controls.append("CONTRACT_REVIEW")

    return PolicyDecision(
        disposition="CONTROLLED",
        required_controls=tuple(controls),
    )