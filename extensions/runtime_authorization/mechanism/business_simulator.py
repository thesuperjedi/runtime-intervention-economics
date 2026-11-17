"""Acceptance-only B0 business executor. No evaluator, shadow or commit imports."""
from copy import deepcopy
from datetime import datetime
from .fixtures import typed
from .pap import contracts as c
from .pap.chain_validation import inspect_chain
from .pap.serialization import approval_content_hash

def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def accounting_receipt(tc, params):
    """Independent simulator accounting criterion; never an execution permission."""
    chain = tc["approval_chains"].get(params["request_id"], {"records": []})
    inspection = inspect_chain(chain["records"])
    if not inspection.valid or inspection.governing is None:
        return None
    record = dict(inspection.governing)
    approver = tc["approvers"].get(record["approver_id"])
    if record["status"] != "APPROVED" or not approver:
        return None
    binding = all(record[k] == params[k] for k in ("request_id", "vendor_id", "cost_center", "amount"))
    if not (binding and record["actor_id"] == tc["actor"]["actor_id"] and
            record["policy_version"] == tc["policy_version"] and
            instant(record["issued_at"]) <= instant(tc["t_eval"]) < instant(record["expires_at"]) and
            approver["status"] == "ACTIVE" and approver["limit"] >= params["amount"] and
            approver["principal_id"] != tc["actor"]["delegation"]["principal_id"]):
        return None
    return record

class BusinessSimulator:
    def __init__(self, initial):
        self.state = deepcopy(initial)

    def snapshot(self):
        return deepcopy(self.state)

    def append_scripted(self, record):
        work = self.snapshot()
        req = record["request_id"]
        old = work["approval_chains"].get(req, {"request_id": req, "records": []})
        candidate = old["records"] + [deepcopy(record)]
        if record["status"] not in ("PENDING", "APPROVED", "REJECTED", "REVOKED"):
            raise ValueError("No scripted CONSUMED writer")
        if not inspect_chain(candidate).valid:
            return False
        work["approval_chains"][req] = dict(request_id=req, records=candidate)
        # Suite's only public event is a matching APPROVED receipt; no negative script.
        if record["status"] != "APPROVED":
            raise ValueError("Outside acceptance event scope")
        work["tc_state_version"] += 1
        self.state = work
        return True

    def execute(self, raw, operation_id):
        """Pure business input: raw proposal only. Shadow cannot enter this API."""
        try:
            proposal = c.to_wire(c.Proposal.from_json(raw))
        except (ValueError, TypeError):
            return dict(status="INTERFACE_INVALID", effects=[])
        action, params = proposal["action_type"], proposal["params"]
        if action == "APPROVE_PURCHASE":
            return dict(status="INTERFACE_UNSUPPORTED", effects=[])
        work = self.snapshot()
        if ("vendor_id" in params and params["vendor_id"] not in work["vendors"]) or (
                "cost_center" in params and params["cost_center"] not in work["cost_centers"]) or (
                action == "READ_DOC" and params["doc_id"] not in work["documents"]):
            return dict(status="OPERATION_FAILED", effects=[])
        accounting = None
        if action == "SUBMIT_PR":
            if params["request_id"] in work["purchase_requests"]:
                return dict(status="OPERATION_FAILED", effects=[])
            work["purchase_requests"][params["request_id"]] = dict(
                params, state="SUBMITTED", submitted_by=work["actor"]["actor_id"])
        elif action == "EXECUTE_PURCHASE":
            pr = work["purchase_requests"].get(params["request_id"])
            if (not pr or pr["state"] != "SUBMITTED" or
                pr["submitted_by"] != work["actor"]["actor_id"] or
                any(pr[k] != params[k] for k in ("vendor_id", "cost_center", "amount"))):
                return dict(status="OPERATION_FAILED", effects=[])
            receipt = accounting_receipt(work, params)
            pr["state"] = "EXECUTED"
            if receipt:
                record = dict(receipt, approval_id=operation_id + ":simulated-receipt",
                              seq=receipt["seq"] + 1, status="CONSUMED",
                              issued_at=work["t_eval"], prev_hash=receipt["content_hash"])
                record["content_hash"] = approval_content_hash(record)
                records = work["approval_chains"][params["request_id"]]["records"]
                if not inspect_chain(records + [record]).valid:
                    raise ValueError("Simulator receipt bookkeeping failure")
                records.append(record)
                accounting = "SIMULATED_RECEIPT_CONSUMPTION"
            else:
                entries = work["ledger"]["entries"]
                entry = next((r for r in entries if
                              (r["actor_id"], r["cost_center"]) ==
                              (work["actor"]["actor_id"], params["cost_center"])), None)
                if entry is None:
                    entries.append(dict(actor_id=work["actor"]["actor_id"],
                                        cost_center=params["cost_center"], amount=params["amount"]))
                else:
                    entry["amount"] += params["amount"]
                entries.sort(key=lambda r: (r["actor_id"], r["cost_center"]))
                accounting = "BYPASS_EXPOSURE_DEBIT"
        if action in ("SUBMIT_PR", "EXECUTE_PURCHASE"):
            work["tc_state_version"] += 1
        typed(work, c.TrustedContext)
        self.state = work
        effect = dict(operation_id=operation_id, action=action, params=params,
                      proposal_id=proposal["proposal_id"], accounting=accounting,
                      provenance="BYPASS_SIMULATOR", qualified_commit_ref=None,
                      token=None, authenticated_tool_invocation_id=None)
        return dict(status="APPLIED", effects=[effect])

