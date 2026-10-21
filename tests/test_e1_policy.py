from src.e1_policy import ProcurementCase, evaluate_policy
import itertools

def test_simple_approved_purchase():
    case = ProcurementCase(
        case_id="T001",
        amount_usd=25_000,
        vendor_status="approved",
        data_classification="internal",
        deployment="internal",
        contract_months=12,
        exception_status="none",
        exception_scope="none",
    )

    result = evaluate_policy(case)

    assert result.disposition == "CONTROLLED"
    assert result.required_controls == (
        "STANDARD_FINANCIAL_APPROVAL",
    )


def test_multiple_controls():
    case = ProcurementCase(
        case_id="T002",
        amount_usd=127_000,
        vendor_status="unapproved",
        data_classification="restricted",
        deployment="external_saas",
        contract_months=30,
        exception_status="none",
        exception_scope="none",
    )

    result = evaluate_policy(case)

    assert result.disposition == "CONTROLLED"
    assert result.required_controls == (
        "SENIOR_FINANCIAL_APPROVAL",
        "SUPPLIER_DUE_DILIGENCE",
        "ENHANCED_SECURITY_REVIEW",
        "CONTRACT_REVIEW",
    )


def test_prohibited_vendor_is_terminal():
    case = ProcurementCase(
        case_id="T003",
        amount_usd=250_000,
        vendor_status="prohibited",
        data_classification="restricted",
        deployment="external_saas",
        contract_months=36,
        exception_status="approved",
        exception_scope="both",
    )

    result = evaluate_policy(case)

    assert result.disposition == "PROHIBITED"
    assert result.required_controls == ("PROHIBITED",)


def test_vendor_exception_is_scoped():
    case = ProcurementCase(
        case_id="T004",
        amount_usd=80_000,
        vendor_status="unapproved",
        data_classification="restricted",
        deployment="external_saas",
        contract_months=12,
        exception_status="approved",
        exception_scope="vendor",
    )

    result = evaluate_policy(case)

    assert result.required_controls == (
        "ENHANCED_FINANCIAL_APPROVAL",
        "ENHANCED_SECURITY_REVIEW",
    )


def test_both_exception_suppresses_two_controls():
    case = ProcurementCase(
        case_id="T005",
        amount_usd=80_000,
        vendor_status="unapproved",
        data_classification="restricted",
        deployment="external_saas",
        contract_months=30,
        exception_status="approved",
        exception_scope="both",
    )

    result = evaluate_policy(case)

    assert result.required_controls == (
        "ENHANCED_FINANCIAL_APPROVAL",
        "CONTRACT_REVIEW",
    )


def test_financial_boundary_50000():
    case = ProcurementCase(
        case_id="T006",
        amount_usd=50_000,
        vendor_status="approved",
        data_classification="public",
        deployment="internal",
        contract_months=12,
        exception_status="none",
        exception_scope="none",
    )

    result = evaluate_policy(case)

    assert result.required_controls == (
        "STANDARD_FINANCIAL_APPROVAL",
    )


def test_financial_boundary_100000():
    case = ProcurementCase(
        case_id="T007",
        amount_usd=100_000,
        vendor_status="approved",
        data_classification="public",
        deployment="internal",
        contract_months=12,
        exception_status="none",
        exception_scope="none",
    )

    result = evaluate_policy(case)

    assert result.required_controls == (
        "ENHANCED_FINANCIAL_APPROVAL",
    )


def test_contract_boundary_24_months():
    case = ProcurementCase(
        case_id="T008",
        amount_usd=20_000,
        vendor_status="approved",
        data_classification="public",
        deployment="internal",
        contract_months=24,
        exception_status="none",
        exception_scope="none",
    )

    result = evaluate_policy(case)

    assert "CONTRACT_REVIEW" not in result.required_controls



def test_policy_across_systematic_combinations():

    amounts = [
        49_999,
        50_000,
        50_001,
        99_999,
        100_000,
        100_001,
    ]

    vendors = [
        "approved",
        "unapproved",
        "prohibited",
    ]

    data_classes = [
        "public",
        "internal",
        "confidential",
        "restricted",
    ]

    deployments = [
        "internal",
        "external_saas",
    ]

    durations = [
        12,
        24,
        25,
        36,
    ]

    exceptions = [
        ("none", "none"),
        ("approved", "vendor"),
        ("approved", "external_restricted_data"),
        ("approved", "both"),
    ]

    combinations_checked = 0

    for (
        amount,
        vendor,
        data_class,
        deployment,
        duration,
        exception,
    ) in itertools.product(
        amounts,
        vendors,
        data_classes,
        deployments,
        durations,
        exceptions,
    ):

        exception_status, exception_scope = exception

        case = ProcurementCase(
            case_id="SYSTEMATIC_TEST",
            amount_usd=amount,
            vendor_status=vendor,
            data_classification=data_class,
            deployment=deployment,
            contract_months=duration,
            exception_status=exception_status,
            exception_scope=exception_scope,
        )

        result = evaluate_policy(case)

        combinations_checked += 1

        # ----------------------------------------------------
        # Rule 1:
        # prohibited vendor must always terminate the case.
        # ----------------------------------------------------

        if vendor == "prohibited":
            assert result.disposition == "PROHIBITED"
            assert result.required_controls == ("PROHIBITED",)
            continue

        # Everything below concerns permissible vendors.

        assert result.disposition == "CONTROLLED"

        controls = set(result.required_controls)

        # ----------------------------------------------------
        # Rule 2:
        # exactly one financial approval must always exist.
        # ----------------------------------------------------

        financial_controls = {
            "STANDARD_FINANCIAL_APPROVAL",
            "ENHANCED_FINANCIAL_APPROVAL",
            "SENIOR_FINANCIAL_APPROVAL",
        }

        assert len(controls & financial_controls) == 1

        # ----------------------------------------------------
        # Rule 3:
        # financial thresholds must behave correctly.
        # ----------------------------------------------------

        if amount <= 50_000:
            assert "STANDARD_FINANCIAL_APPROVAL" in controls

        elif amount <= 100_000:
            assert "ENHANCED_FINANCIAL_APPROVAL" in controls

        else:
            assert "SENIOR_FINANCIAL_APPROVAL" in controls

        # ----------------------------------------------------
        # Rule 4:
        # contract review appears iff duration > 24 months.
        # ----------------------------------------------------

        assert (
            ("CONTRACT_REVIEW" in controls)
            == (duration > 24)
        )

        # ----------------------------------------------------
        # Rule 5:
        # supplier due diligence.
        # ----------------------------------------------------

        vendor_exception_applies = (
            exception_status == "approved"
            and exception_scope in {"vendor", "both"}
        )

        should_require_due_diligence = (
            vendor == "unapproved"
            and not vendor_exception_applies
        )

        assert (
            ("SUPPLIER_DUE_DILIGENCE" in controls)
            == should_require_due_diligence
        )

        # ----------------------------------------------------
        # Rule 6:
        # enhanced security review.
        # ----------------------------------------------------

        security_exception_applies = (
            exception_status == "approved"
            and exception_scope in {
                "external_restricted_data",
                "both",
            }
        )

        should_require_enhanced_security = (
            data_class == "restricted"
            and deployment == "external_saas"
            and not security_exception_applies
        )

        assert (
            ("ENHANCED_SECURITY_REVIEW" in controls)
            == should_require_enhanced_security
        )

        # ----------------------------------------------------
        # Rule 7:
        # ordinary security review.
        # ----------------------------------------------------

        should_require_security_review = (
            (
                data_class == "confidential"
                and deployment == "external_saas"
            )
            or
            (
                data_class == "restricted"
                and deployment == "internal"
            )
        )

        assert (
            ("SECURITY_REVIEW" in controls)
            == should_require_security_review
        )

    # Make sure we really checked the intended state space.

    assert combinations_checked == 2304