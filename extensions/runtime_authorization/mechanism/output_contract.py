"""One response = one closed action OR one closed explicit terminal."""
import hashlib
import json
from .pap.contracts import Proposal, to_wire
from .pap.serialization import strict_json

class ContractError(ValueError):
    pass

PARAMS = {
    "READ_DOC": {"doc_id": "string"},
    "RECOMMEND_PURCHASE": {"item_id": "string", "vendor_id": "string", "amount": "integer", "justification": "string"},
    "SUBMIT_PR": {"request_id": "string", "item_id": "string", "vendor_id": "string", "cost_center": "string", "amount": "integer"},
    "EXECUTE_PURCHASE": {"request_id": "string", "vendor_id": "string", "cost_center": "string", "amount": "integer"},
    "APPROVE_PURCHASE": {"request_id": "string"},
}

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

def sha(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()

def response_schema():
    variants = []
    for action, params in PARAMS.items():
        properties = {name: dict(type=kind, **({"minimum": 1} if kind == "integer" else {"minLength": 1}))
                      for name, kind in params.items()}
        variants.append(dict(type="object", additionalProperties=False,
                             required=["proposal_id", "action_type", "params"],
                             properties=dict(proposal_id=dict(type="string", minLength=1),
                                 action_type=dict(type="string", enum=[action]),
                                 params=dict(type="object", additionalProperties=False,
                                             properties=properties, required=list(params)))))
    for category, reasons in (("COMPLETE", ["GOAL_COMPLETE"]),
                              ("REFUSE", ["POLICY", "UNSUPPORTED_ACTION"]),
                              ("STOP", ["POLICY", "UNSUPPORTED_ACTION", "UNABLE", "OTHER"])):
        variants.append(dict(type="object", additionalProperties=False, required=["category", "reason"],
                             properties=dict(category=dict(type="string", enum=[category]),
                                             reason=dict(type="string", enum=reasons))))
    return {"oneOf": variants}

def validate_response(text, expected_proposal_id=None):
    if type(text) is not str:
        raise ContractError("Output is not JSON text")
    try:
        value = strict_json(text)
        if type(value) is not dict:
            raise ContractError("No array, batch or primitive response")
        if set(value) == {"category", "reason"}:
            category, reason = value["category"], value["reason"]
            allowed = {"COMPLETE": ["GOAL_COMPLETE"], "REFUSE": ["POLICY", "UNSUPPORTED_ACTION"],
                       "STOP": ["POLICY", "UNSUPPORTED_ACTION", "UNABLE", "OTHER"]}
            if type(category) is not str or type(reason) is not str or reason not in allowed.get(category, []):
                raise ContractError("Invalid terminal combination")
            return dict(kind="TERMINAL", parsed=value, explicit_refusal=(category in ("REFUSE", "STOP") and reason=="POLICY"))
        result = to_wire(Proposal.from_json(text))
        if expected_proposal_id is not None and result["proposal_id"] != expected_proposal_id:
            raise ContractError("Proposal ID mismatch; no silent repair")
        return dict(kind="ACTION", parsed=result, explicit_refusal=False)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ContractError(type(exc).__name__) from None

