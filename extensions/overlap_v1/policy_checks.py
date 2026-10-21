"""Independent offline policy and rendering checks for the prospective extension."""
import itertools
import re

FIELDS = ('amount_usd', 'vendor_status', 'data_classification', 'deployment',
          'contract_months', 'exception_status', 'exception_scope')


def reference_controls(c):
    """Declarative decision table, independent of e1_policy helpers."""
    if c['vendor_status'] == 'prohibited':
        return {'PROHIBITED'}
    a = c['amount_usd']
    result = {next(name for condition, name in (
        (a <= 50000, 'STANDARD_FINANCIAL_APPROVAL'),
        (50000 < a <= 100000, 'ENHANCED_FINANCIAL_APPROVAL'),
        (a > 100000, 'SENIOR_FINANCIAL_APPROVAL')) if condition)}
    scope = c['exception_scope'] if c['exception_status'] == 'approved' else 'none'
    rows = (
        (c['vendor_status'] == 'unapproved' and scope not in ('vendor', 'both'), 'SUPPLIER_DUE_DILIGENCE'),
        (c['data_classification'] == 'restricted' and c['deployment'] == 'external_saas'
         and scope not in ('external_restricted_data', 'both'), 'ENHANCED_SECURITY_REVIEW'),
        ((c['data_classification'] == 'confidential' and c['deployment'] == 'external_saas')
         or (c['data_classification'] == 'restricted' and c['deployment'] == 'internal'), 'SECURITY_REVIEW'),
        (c['contract_months'] > 24, 'CONTRACT_REVIEW'))
    result.update(name for condition, name in rows if condition)
    return result


def authoritative(c):
    from src.e1_policy import ProcurementCase, evaluate_policy
    return evaluate_policy(ProcurementCase(case_id=c.get('case_id', 'CHECK'),
                                          **{f: c[f] for f in FIELDS}))


def exhaustive_oracle_check():
    count = 0
    # Includes exact thresholds and adjacent values; broader than selection pool.
    for a, vendor, data, deployment, months, scope in itertools.product(
            (0, 49999, 50000, 50001, 99999, 100000, 100001, 125000),
            ('approved', 'unapproved', 'prohibited'),
            ('public', 'internal', 'confidential', 'restricted'),
            ('internal', 'external_saas'), (12, 23, 24, 25, 36),
            ('none', 'vendor', 'external_restricted_data', 'both')):
        c = dict(zip(FIELDS, (a, vendor, data, deployment, months,
                            'none' if scope == 'none' else 'approved', scope)))
        expected = reference_controls(c)
        actual = set(authoritative(c).required_controls)
        if expected != actual:
            raise ValueError(f'oracle disagreement: {c}')
        count += 1
    return dict(checked_combinations=count, disagreements=0,
                method='independently encoded declarative decision table vs unchanged E1 oracle',
                limitation='Shared interpretation risk remains; not independent human policy adjudication.')


def parse_rendered_facts(text):
    """Read text only, not rendering metadata or generator fact dictionaries."""
    amount = re.findall(r'USD ([0-9,]+)', text)
    vendor = re.findall(r'supplier (?:is|whose status is) (approved|unapproved|prohibited)', text)
    data = re.findall(r'classified as (public|internal|confidential|restricted)', text)
    duration = re.findall(r'([0-9]+)[ -]month', text)
    if not (len(amount) == len(vendor) == len(data) == len(duration) == 1):
        raise ValueError('rendering facts missing or ambiguous')
    internal = 'deployed internally' in text
    external = 'external SaaS deployment' in text
    if internal == external:
        raise ValueError('deployment missing/ambiguous')
    scopes = re.findall(r'approved exception is explicitly limited to (vendor|external_restricted_data|both)', text)
    absent = 'No exception has been approved.' in text
    if (absent and scopes) or (not absent and len(scopes) != 1):
        raise ValueError('exception missing/ambiguous')
    return dict(amount_usd=int(amount[0].replace(',', '')), vendor_status=vendor[0],
                data_classification=data[0], deployment='internal' if internal else 'external_saas',
                contract_months=int(duration[0]), exception_status='none' if absent else 'approved',
                exception_scope='none' if absent else scopes[0])


def check_rendering(case, rendering):
    actual = parse_rendered_facts(rendering['text'])
    if actual != {f: case[f] for f in FIELDS}:
        raise ValueError('rendering changes canonical facts')
    if reference_controls(actual) != set(authoritative(case).required_controls):
        raise ValueError('rendered facts change oracle result')
    return True
