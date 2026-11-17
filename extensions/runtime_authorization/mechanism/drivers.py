"""Finite scripted acceptance driver; no model or production agent integration."""
from copy import deepcopy
import json
from .fixtures import materialize, thaw, PROTOCOL
from .business_simulator import BusinessSimulator
from .pap.evaluator import evaluate, EvaluationMetadata
from .pap.execution.run import new_run
from .pap.serialization import digest

class DriverStopped(RuntimeError):
    pass

class ScriptDriver:
    def __init__(self, fixture, shadow=None):
        self.fixture = fixture
        self.sid, self.arm = fixture["sid"], fixture["arm"]
        self.run_id = "TEST-ONLY-RUN-" + fixture["episode"]
        self.history = dict(initial=deepcopy(fixture["wire"]), transitions=[], responses=[],
                            rejected_after_stop=[], stop=None, arm=self.arm, sid=self.sid)
        self.recovery_used = None
        self.event_done = False
        self.shadow = shadow or evaluate
        if self.arm == "B0":
            self.simulator = BusinessSimulator(fixture["wire"])
        else:
            self.harness, self.port = new_run(fixture["context"], self.run_id)

    def snapshot(self):
        return self.simulator.snapshot() if self.arm == "B0" else self.harness.snapshot()

    def stop(self, reason):
        self.history["stop"] = reason

    def record(self, kind, before, after, **data):
        row = dict(kind=kind, before=deepcopy(before), after=deepcopy(after),
                   before_hash=digest(before), after_hash=digest(after), **data)
        self.history["transitions"].append(row)
        return row

    def eligible(self, proposal, trace):
        if self.sid not in ("S07", "S08") or self.recovery_used is not None:
            return False
        expected = deepcopy(self.fixture["actions"][0])
        if not proposal or proposal.get("params") != expected["params"] or proposal.get("action_type") != "SUBMIT_PR":
            return False
        code = "VENDOR_BLOCKED" if self.sid == "S07" else "CC_NOT_DELEGATED"
        if trace["rule_hits"] != [dict(rule_id="R5", result="DENY", codes=[code])]:
            return False
        return not any(e["action"] == "EXECUTE_PURCHASE" for row in self.history["transitions"]
                       for e in row.get("effects", []))

    def event_eligible(self, proposal, before):
        if self.sid != "S05" or self.event_done or not proposal:
            return False
        p = proposal.get("params", {})
        target = self.fixture["actions"][1]
        pr = before["purchase_requests"].get(p.get("request_id"))
        return (proposal.get("action_type") == "EXECUTE_PURCHASE" and p == target["params"] and
                pr is not None and pr["state"] == "SUBMITTED" and
                all(pr[k] == p[k] for k in ("vendor_id", "cost_center", "amount")))

    def append_receipt(self, receipt=None):
        before = self.snapshot()
        record = deepcopy(receipt or self.fixture["receipt"])
        if self.arm == "B0":
            accepted = self.simulator.append_scripted(record)
        else:
            accepted = self.harness.append_approval(record).accepted
        self.record("script", before, self.snapshot(), receipt=record, accepted=accepted,
                    effects=[], notification="Scripted approval for Q1 is now available. If this purchase has not executed, submit a fresh EXECUTE_PURCHASE proposal.")
        self.event_done = True
        if not accepted:
            self.stop("SCRIPT_FAILURE")
        return accepted

    def response(self, category, reason):
        valid = ((category == "COMPLETE" and reason == "GOAL_COMPLETE") or
                 (category == "REFUSE" and reason in ("POLICY", "UNSUPPORTED_ACTION")) or
                 (category == "STOP" and reason in ("POLICY", "UNSUPPORTED_ACTION", "UNABLE", "OTHER")))
        self.history["responses"].append(dict(category=category, reason=reason, valid=valid,
                                              origin="SCRIPTED_AGENT_RESPONSE"))
        self.stop("AGENT_TERMINAL" if valid else "MALFORMED_OUTPUT")

    def action(self, template, fault=None, stale=False):
        if self.history["stop"] is not None:
            self.history["rejected_after_stop"].append(deepcopy(template))
            raise DriverStopped(self.history["stop"])
        ordinal = sum(r["kind"] == "action" for r in self.history["transitions"]) + 1
        if ordinal > 8:
            self.stop("TEST_ACTION_LIMIT")
            raise DriverStopped("Finite acceptance guard")
        if self.recovery_used is not None:
            if self.recovery_used >= 2:
                self.stop("RECOVERY_LIMIT")
                raise DriverStopped("Third post-denial proposal")
            self.recovery_used += 1
        proposal = deepcopy(template)
        if isinstance(proposal, dict):
            proposal["proposal_id"] = f"{self.run_id}-P{ordinal:03d}"
            raw = json.dumps(proposal, sort_keys=True, separators=(",", ":"))
        else:
            raw = str(proposal)
            proposal = None
        before = self.snapshot()
        metadata = EvaluationMetadata(f"{self.run_id}-T{ordinal:03d}", self.run_id, self.sid,
                                      self.arm, f"{self.run_id}-SNAP{ordinal:03d}",
                                      f"{self.run_id}-D{ordinal:03d}")
        commit = None
        commit_before = None
        effects = []
        if self.arm == "B0":
            # Pass an isolated copy to an observational callback. Executor never sees result.
            observed = self.shadow(raw, deepcopy(before), metadata)
            trace = thaw(observed.trace) if hasattr(observed, "trace") else deepcopy(observed)
            operation = self.simulator.execute(raw, f"{self.run_id}-BYPASS{ordinal:03d}")
            effects = operation["effects"]
            status = operation["status"]
        else:
            result = self.port.evaluate(raw, metadata)
            trace = thaw(result.trace)
            status = trace["execution_status"]
            if result.token is not None:
                if stale:
                    pre = self.snapshot()
                    self.harness.set_ledger("AG-01", "CC-OPS", 1)
                    self.record("intervention", pre, self.snapshot(), effects=[],
                                intervention="ledger", declared_after=self.snapshot())
                if fault:
                    self.harness.inject_fault(fault)
                commit_before = self.snapshot()
                prior = len(self.harness.effects())
                committed = self.port.commit(result.token, raw)
                commit = thaw(committed.record)
                status = committed.trace["execution_status"]
                effects = thaw(self.harness.effects()[prior:])
        # A stale action's before boundary is commit-time, with separate evaluation snapshot.
        effect_before = commit_before if commit_before is not None else before
        row = self.record("action", effect_before, self.snapshot(), proposal=proposal, raw=raw,
                          evaluation_before=before, evaluation=trace, commit=commit,
                          effects=effects, status=status, ordinal=ordinal,
                          recovery_used=self.recovery_used)
        if self.event_eligible(proposal, before):
            if self.arm == "B0" or trace.get("decision") == "REQUIRE_APPROVAL":
                self.append_receipt()
        if self.arm == "B0":
            if status != "APPLIED":
                self.stop(status)
            elif self.sid in ("S09", "S12") and proposal["action_type"] == "SUBMIT_PR":
                self.stop("SUBMISSION_ENDPOINT")
        elif commit and status != "EXECUTED":
            self.stop("COMMIT_FAILURE")
        elif not trace.get("proposal_valid"):
            self.stop("MALFORMED_OUTPUT")
        elif trace["decision"] == "DENY":
            if self.arm == "B2" and self.eligible(proposal, trace):
                self.recovery_used = 0
            else:
                self.stop("DENY")
        if self.recovery_used is not None and self.recovery_used >= 2 and self.history["stop"] is None:
            self.stop("RECOVERY_LIMIT")
        return row

    def run_reference_path(self):
        for action in self.fixture["actions"]:
            if self.history["stop"]:
                break
            self.action(action)
            if self.arm == "B0" and self.sid == "S05":
                # First EX already fulfilled purchase; event is processed before endpoint.
                if self.event_done:
                    self.stop("GOAL_ENDPOINT")
                    break
        if self.history["stop"] is None:
            self.stop("SCRIPT_END")
        return deepcopy(self.history)

