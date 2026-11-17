"""Typed, immutable valid-state records (PAP A.3-A.10); not an evaluator.
Malformed/injected canonical inputs remain source text, not coerced into these types.
"""
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from types import MappingProxyType, UnionType
from typing import get_args, get_origin, get_type_hints, Union
from datetime import datetime
import re
from .serialization import strict_json

class Action(StrEnum):
    READ_DOC = "READ_DOC"
    RECOMMEND_PURCHASE = "RECOMMEND_PURCHASE"
    SUBMIT_PR = "SUBMIT_PR"
    EXECUTE_PURCHASE = "EXECUTE_PURCHASE"
    APPROVE_PURCHASE = "APPROVE_PURCHASE"
class Decision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
class Basis(StrEnum):
    NONE_REQUIRED = "NONE_REQUIRED"
    AUTONOMY = "AUTONOMY"
    APPROVAL = "APPROVAL"
class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"
    CONSUMED = "CONSUMED"
class PRStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    EXECUTED = "EXECUTED"
class RegistryStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
class VendorStatus(StrEnum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
class DocumentClass(StrEnum):
    PUBLIC_POLICY = "PUBLIC_POLICY"
    DEPT_INTERNAL = "DEPT_INTERNAL"
    RESTRICTED = "RESTRICTED"
class Classification(StrEnum):
    NONE = "NONE"
    CONSUMED = "CONSUMED"
    NEGATIVE = "NEGATIVE"
    INTEGRITY = "INTEGRITY"
    CURABLE = "CURABLE"
    VALID = "VALID"
class ExecutionStatus(StrEnum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    EXECUTED = "EXECUTED"
    NOT_EXECUTED_DENIED = "NOT_EXECUTED_DENIED"
    NOT_EXECUTED_PENDING = "NOT_EXECUTED_PENDING"
    NOT_EXECUTED_STALE = "NOT_EXECUTED_STALE"
    NOT_EXECUTED_TOKEN_REJECTED = "NOT_EXECUTED_TOKEN_REJECTED"
    EXECUTION_ERROR = "EXECUTION_ERROR"

RULE_CODES = {
    "R1": ("GATE_ERROR","UNKNOWN_ACTION","SCHEMA_INVALID","TC_INVALID","REF_NOT_FOUND",
           "APPROVAL_SEQ_TIE","APPROVAL_SEQ_INVALID","APPROVAL_HASH_INVALID","STATE_INCONSISTENT"),
    "R2": ("AGENT_PROHIBITED",),
    "R3": ("DELEGATION_INACTIVE","SCOPE_NOT_DELEGATED"),
    "R4": ("DOC_RESTRICTED","DOC_DEPT_MISMATCH"),
    "R5": ("VENDOR_BLOCKED","CC_NOT_DELEGATED","OVER_CEILING"),
    "R6": ("REQUEST_ID_DUPLICATE","PR_NOT_SUBMITTED","PR_OWNER_MISMATCH","PARAM_MISMATCH","LAUNDERING_BLOCKED"),
    "R7": ("APPROVAL_PENDING","APPROVAL_EXPIRED","APPROVAL_STALE_POLICY","APPROVER_INACTIVE",
           "APPROVER_LIMIT","APPROVAL_ABSENT","LEDGER_EXCEEDED"),
    "R8": ("APPROVAL_REJECTED","APPROVAL_REVOKED","BINDING_MISMATCH","SELF_APPROVAL"),
}
COMMIT_CODES = ("TOKEN_USED","PROPOSAL_HASH_MISMATCH","STALE_TC_VERSION","TOOL_ERROR")
TRANSITIONS = {
    None: (ApprovalStatus.PENDING, ApprovalStatus.APPROVED),
    ApprovalStatus.PENDING: (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED),
    ApprovalStatus.APPROVED: (ApprovalStatus.APPROVED, ApprovalStatus.REVOKED, ApprovalStatus.CONSUMED),
    ApprovalStatus.REJECTED: (), ApprovalStatus.REVOKED: (), ApprovalStatus.CONSUMED: (),
}

def _type(value, hint):
    origin, args = get_origin(hint), get_args(hint)
    if origin in (UnionType, Union):
        if not any(_matches(value, a) for a in args):
            raise ValueError("Wrong union type")
    elif origin is tuple:
        if type(value) is not tuple:
            raise ValueError("Expected immutable tuple")
        if len(args) == 2 and args[1] is Ellipsis:
            for item in value: _type(item, args[0])
        elif len(args) != len(value):
            raise ValueError("Tuple length")
        else:
            for item, arg in zip(value, args): _type(item, arg)
    elif origin is Mapping:
        if not isinstance(value, Mapping):
            raise ValueError("Expected mapping")
        for key, item in value.items():
            _type(key, args[0]); _type(item, args[1])
    elif hint in (int, str, bool, type(None)):
        if type(value) is not hint:
            raise ValueError("Wrong primitive type")
        if hint is str:
            if not value: raise ValueError("Empty string")
            value.encode("utf-8", errors="strict")
    elif not isinstance(value, hint):
        raise ValueError("Wrong record or enum type")

def _matches(value, hint):
    try: _type(value, hint); return True
    except (TypeError, ValueError): return False

def _freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if type(value) is tuple:
        return tuple(_freeze(v) for v in value)
    return value

class Schema:
    def __post_init__(self):
        hints = get_type_hints(type(self))
        for f in fields(self):
            value = getattr(self, f.name)
            _type(value, hints[f.name])
            if f.name in {"amount","seq"} and value < 1:
                raise ValueError("Amount and sequence must be positive integers")
            if f.name in {"tc_state_version","gate_latency_us"} and value is not None and value < 0:
                raise ValueError("Nonnegative implementation counter required")
            if f.name in {"issued_at","expires_at","valid_from","valid_to","t_eval"} and value is not None:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{6})?Z",value):
                    raise ValueError("Schema requires UTC timestamp string")
                datetime.fromisoformat(value.replace("Z","+00:00"))
            if f.name in {"prev_hash","content_hash","proposal_hash","trusted_context_hash"}:
                if not re.fullmatch("[0-9a-f]{64}",value):
                    raise ValueError("Expected lowercase SHA-256")
            object.__setattr__(self, f.name, _freeze(value))

@dataclass(frozen=True)
class ReadDoc(Schema):
    doc_id: str
@dataclass(frozen=True)
class RecommendPurchase(Schema):
    item_id: str
    vendor_id: str
    amount: int
    justification: str
@dataclass(frozen=True)
class SubmitPR(Schema):
    request_id: str
    item_id: str
    vendor_id: str
    cost_center: str
    amount: int
@dataclass(frozen=True)
class ExecutePurchase(Schema):
    request_id: str
    vendor_id: str
    cost_center: str
    amount: int
@dataclass(frozen=True)
class ApprovePurchase(Schema):
    request_id: str

PARAMS = {Action.READ_DOC: ReadDoc, Action.RECOMMEND_PURCHASE: RecommendPurchase,
          Action.SUBMIT_PR: SubmitPR, Action.EXECUTE_PURCHASE: ExecutePurchase,
          Action.APPROVE_PURCHASE: ApprovePurchase}
@dataclass(frozen=True)
class Proposal(Schema):
    proposal_id: str
    action_type: Action
    params: ReadDoc | RecommendPurchase | SubmitPR | ExecutePurchase | ApprovePurchase
    def __post_init__(self):
        super().__post_init__()
        if type(self.params) is not PARAMS[self.action_type]:
            raise ValueError("Action/parameter mismatch")
    @classmethod
    def from_json(cls, text):
        data = strict_json(text)
        if type(data) is not dict or set(data) != {"proposal_id","action_type","params"}:
            raise ValueError("Closed proposal envelope")
        action = Action(data["action_type"])
        params = data["params"]
        if type(params) is not dict or set(params) != {f.name for f in fields(PARAMS[action])}:
            raise ValueError("Closed action parameters")
        return cls(data["proposal_id"],action,PARAMS[action](**params))

@dataclass(frozen=True)
class Delegation(Schema):
    actor_id: str
    principal_id: str
    role: str
    scopes: tuple[Action, ...]
    departments: tuple[str, ...]
    cost_centers: tuple[str, ...]
    max_amount: int
    valid_from: str
    valid_to: str
@dataclass(frozen=True)
class TrustedActor(Schema):
    actor_id: str
    delegation: Delegation
    delegation_version: str
@dataclass(frozen=True)
class Approver(Schema):
    approver_id: str
    principal_id: str
    limit: int
    status: RegistryStatus
@dataclass(frozen=True)
class Document(Schema):
    classification: DocumentClass
    department: str | None
@dataclass(frozen=True)
class PurchaseRequest(Schema):
    request_id: str
    state: PRStatus
    submitted_by: str
    item_id: str
    vendor_id: str
    cost_center: str
    amount: int
@dataclass(frozen=True)
class ApprovalRecord(Schema):
    approval_id: str
    request_id: str
    seq: int
    actor_id: str
    vendor_id: str
    cost_center: str
    amount: int
    approver_id: str | None
    status: ApprovalStatus
    issued_at: str
    expires_at: str | None
    policy_version: str
    prev_hash: str
    content_hash: str
@dataclass(frozen=True)
class ApprovalChainState(Schema):
    """An unevaluated chain. No governing record or validity is inferred here."""
    request_id: str
    records: tuple[ApprovalRecord, ...]
@dataclass(frozen=True)
class Signature(Schema):
    submitted_by: str
    item_id: str
    vendor_id: str
    cost_center: str
    amount: int
@dataclass(frozen=True)
class NegativeSignature(Schema):
    request_id: str
    signature: Signature
@dataclass(frozen=True)
class AutonomyLedger(Schema):
    entries: Mapping[tuple[str, str], int]
    def __post_init__(self):
        super().__post_init__()
        if any(v < 0 for v in self.entries.values()):
            raise ValueError("Malformed ledger belongs in raw fault fixture")
@dataclass(frozen=True)
class TrustedContext(Schema):
    actor: TrustedActor
    approvers: Mapping[str, Approver]
    documents: Mapping[str, Document]
    vendors: Mapping[str, VendorStatus]
    cost_centers: tuple[str, ...]
    purchase_requests: Mapping[str, PurchaseRequest]
    approval_chains: Mapping[str, ApprovalChainState]
    negative_index: tuple[NegativeSignature, ...]
    ledger: AutonomyLedger
    t_eval: str
    policy_version: str
    tc_state_version: int

@dataclass(frozen=True)
class RuleHit(Schema):
    rule_id: str
    result: Decision
    codes: tuple[str, ...]
    def __post_init__(self):
        super().__post_init__()
        permitted = RULE_CODES.get(self.rule_id)
        if not permitted or not self.codes or any(c not in permitted for c in self.codes):
            raise ValueError("Unknown rule/code")
        if len(set(self.codes)) != len(self.codes) or tuple(sorted(self.codes,key=permitted.index)) != self.codes:
            raise ValueError("Codes must be unique and in A.8 priority")
        if self.rule_id == "R1" and len(self.codes) != 1:
            raise ValueError("R1 has one code")
        if self.result != (Decision.REQUIRE_APPROVAL if self.rule_id == "R7" else Decision.DENY):
            raise ValueError("Rule/result vocabulary mismatch")

@dataclass(frozen=True)
class AuthorizationDecision(Schema):
    decision_id: str
    decision: Decision
    deciding_rule_id: str | None
    reason_code: str | None
    rule_hits: tuple[RuleHit, ...]
    classification: Classification | None
    authorization_basis: Basis | None
    def __post_init__(self):
        super().__post_init__()
        ids = tuple(h.rule_id for h in self.rule_hits)
        if len(set(ids)) != len(ids) or ids != tuple(sorted(ids)):
            raise ValueError("Rule hits must be unique and ordered")
        if self.decision == Decision.ALLOW:
            if self.rule_hits or self.deciding_rule_id is not None or self.reason_code is not None or self.authorization_basis is None:
                raise ValueError("Malformed ALLOW record")
        else:
            matches = [h for h in self.rule_hits if h.result == self.decision]
            if not matches or self.deciding_rule_id != matches[0].rule_id or self.reason_code != matches[0].codes[0] or self.authorization_basis is not None:
                raise ValueError("Decision provenance mismatch")

@dataclass(frozen=True)
class AuthorizationToken(Schema):
    decision_id: str
    proposal_hash: str
    tc_state_version: int
    basis: Basis
@dataclass(frozen=True)
class StoreEvent(Schema):
    code: str
    request_id: str
    def __post_init__(self):
        super().__post_init__()
        if self.code not in RULE_CODES["R1"][5:8]:
            raise ValueError("Store event must carry a chain-failure code")
@dataclass(frozen=True)
class CommitOutcome(Schema):
    execution_status: ExecutionStatus
    commit_code: str | None
    tool_invocation_id: str | None
    store_events: tuple[StoreEvent, ...]
    def __post_init__(self):
        super().__post_init__()
        if self.commit_code is not None and self.commit_code not in COMMIT_CODES:
            raise ValueError("Unknown commit code")
    # Deliberately NO token-consumption field/default: P5-12 remains OPEN.
@dataclass(frozen=True)
class AuditEvent(Schema):
    """Core typed A.10 trace; auxiliary raw/oracle/usage evidence stays separate."""
    trace_id: str
    run_id: str
    case_id: str
    condition: str
    trusted_context_ref: str
    trusted_context_hash: str
    actor_id: str
    role: str
    delegation_version: str
    t_eval: str
    policy_version: str
    tc_state_version: int
    proposal_valid: bool
    authorization: AuthorizationDecision
    token_id: str | None
    commit: CommitOutcome
    ledger_before: AutonomyLedger
    ledger_after: AutonomyLedger
    gate_latency_us: int | None

def to_wire(value):
    """Explicit schema projection, not frozen-source normalization."""
    if isinstance(value, AutonomyLedger):
        return {"entries": [{"actor_id": actor, "cost_center": cc, "amount": amount}
                            for (actor, cc), amount in sorted(value.entries.items())]}
    if is_dataclass(value):
        return {f.name: to_wire(getattr(value,f.name)) for f in fields(value)}
    if isinstance(value, StrEnum): return value.value
    if isinstance(value, Mapping):
        if any(type(k) is not str for k in value):
            raise ValueError("Project composite-key ledgers as sorted entry lists explicitly")
        return {k: to_wire(v) for k,v in value.items()}
    if type(value) is tuple: return [to_wire(v) for v in value]
    return value
