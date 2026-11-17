"""Serialized, capability-separated PAP-0.5 state and commit implementation.
Only isolated in-memory snapshots/effects. No filesystem/network/SDK/real purchases.
"""
from dataclasses import dataclass
from threading import Lock
from .. import contracts as c
from ..evaluator import evaluate,EvaluationMetadata,_snapshot,_immutable,_context,_time
from ..chain_validation import inspect_chain,ContextShapeError
from ..serialization import digest,approval_content_hash
from .tools import _SyntheticTools,SyntheticToolError

class AuthorizationRequired(PermissionError):
    """No authentic ALLOW token for this run; not a new PAP commit code."""
class UnresolvedTokenLifecycle(RuntimeError):
    """Non-conformance guard: P5-12 OPEN; no retry semantics selected."""
class SerializedRunError(RuntimeError):
    pass
class _ConsumedAppendRejected(RuntimeError):
    def __init__(self,event):
        self.event=event
        super().__init__("CONSUMED append rejected: "+event["code"])

@dataclass(frozen=True)
class AppendResult:
    accepted: bool
    event: object
@dataclass(frozen=True)
class CommitResult:
    trace: object
    record: object

def _rebuild_index(tc):
    entries=[]
    for request,chain in tc["approval_chains"].items():
        inspection=inspect_chain(chain["records"])
        if not inspection.valid:
            continue  # Index entries derive only from structurally valid chains (A.4/L7).
        g=inspection.governing
        if g is not None and g["status"] in ("REJECTED","REVOKED"):
            pr=tc["purchase_requests"][request]
            entries.append(dict(request_id=request,signature={k:pr[k] for k in
                ("submitted_by","item_id","vendor_id","cost_center","amount")}))
    return sorted(entries,key=lambda e:e["request_id"])

def _validate_initial(tc,allow_injected):
    # Reuse the evaluator's read-only shape checks without making any decision.
    _context(tc,c.Action.READ_DOC,{})
    raw=tc["ledger"]
    if type(raw) is not dict or set(raw)!={"entries"} or type(raw["entries"]) is not list:
        raise ContextShapeError("Initialized ledger required for a controlled run")
    keys=[]
    for entry in raw["entries"]:
        if type(entry) is not dict or set(entry)!={"actor_id","cost_center","amount"}:
            raise ContextShapeError("Malformed ledger entry")
        keys.append((entry["actor_id"],entry["cost_center"]))
    if len(keys)!=len(set(keys)): raise ContextShapeError("Duplicate ledger keys")
    c.AutonomyLedger({(e["actor_id"],e["cost_center"]):e["amount"] for e in raw["entries"]})
    digest(tc)
    if not allow_injected:
        for chain in tc["approval_chains"].values():
            if not inspect_chain(chain["records"]).valid:
                raise ContextShapeError("Invalid initial chain requires explicit trusted fault-fixture flag")

def _serialized(method):
    def guarded(self,*args,**kwargs):
        if not self._operation_lock.acquire(blocking=False):
            raise SerializedRunError("Concurrent/reentrant operation blocked")
        try: return method(self,*args,**kwargs)
        finally: self._operation_lock.release()
    return guarded

class _RunCore:
    def __init__(self,initial,run_id,allow_injected):
        if type(run_id) is not str or not run_id: raise ValueError("Explicit run ID required")
        tc=_snapshot(c.to_wire(initial) if isinstance(initial,c.TrustedContext) else initial)
        _validate_initial(tc,allow_injected)
        self._operation_lock=Lock()
        self.__run_id=run_id
        self.__script_cap=object()
        self.__commit_cap=object()
        self.__harness_cap=object()
        self.__tools=_SyntheticTools(self.__commit_cap)
        self.__bundle=dict(tc=tc,effects=[],sessions={},active=None,evaluations=[],
                           commits=[],store_events=[],anomalies=[])
        self.__fault=None
        self.__busy=False
    def harness(self):
        return TrustedHarness(self,self.__harness_cap,self.__script_cap)
    def agent(self):
        return AgentPort(self.authorize,self.commit)
    def _guard_idle(self):
        if self.__busy: raise SerializedRunError("Concurrent/reentrant operation blocked")
    @_serialized
    def inspect(self,cap,what):
        if cap is not self.__harness_cap: raise PermissionError("Trusted inspection capability required")
        if what=="tc": return _snapshot(self.__bundle["tc"])
        if what=="effects": return _snapshot(self.__bundle["effects"])
        if what=="audit":
            return _immutable(_snapshot({k:self.__bundle[k] for k in ("evaluations","commits","store_events","anomalies")}))
        raise ValueError("Unknown inspection")
    @_serialized
    def authorize(self,raw,metadata):
        self._guard_idle()
        if not isinstance(metadata,EvaluationMetadata) or metadata.run_id!=self.__run_id:
            raise ValueError("Evaluation metadata must bind to this run")
        b=self.__bundle
        if b["active"] is not None: raise SerializedRunError("Complete previous proposal first")
        if metadata.decision_id in b["sessions"]: raise ValueError("Duplicate decision ID")
        result=evaluate(raw,b["tc"],metadata)
        work=_snapshot(b)
        work["evaluations"].append(_snapshot(result.trace))
        work["sessions"][metadata.decision_id]=dict(result=result,lifecycle="FRESH" if result.token else "NO_TOKEN")
        if result.token is not None: work["active"]=metadata.decision_id
        self.__bundle=work
        return result

    def _append_to(self,tc,record,cap):
        if cap is self.__script_cap:
            if record.get("status") not in ("PENDING","APPROVED","REJECTED","REVOKED"):
                raise PermissionError("Script writer cannot append CONSUMED or unknown status")
        elif cap is self.__commit_cap:
            if record.get("status")!="CONSUMED":
                raise PermissionError("Commit writer can append CONSUMED only")
        else: raise PermissionError("Approval-store writer capability required")
        request=record["request_id"]
        old=tc["approval_chains"].get(request,{"request_id":request,"records":[]})
        inspection=inspect_chain(old["records"]+[_snapshot(record)])
        if not inspection.valid:
            return {"code":inspection.failure_code,"request_id":request}
        tc["approval_chains"][request]={"request_id":request,"records":old["records"]+[_snapshot(record)]}
        previous=tc["negative_index"]
        new=_rebuild_index(tc)
        # Legal terminal transitions cannot remove a permanent negative signature.
        if any(entry not in new for entry in previous):
            raise ContextShapeError("Negative index is permanent within a run")
        tc["negative_index"]=new
        return None

    @_serialized
    def scripted_append(self,cap,record):
        self._guard_idle()
        if cap is not self.__script_cap: raise PermissionError("Script capability required")
        if type(record) is not dict: raise ValueError("Append requires a record mapping")
        b=self.__bundle; work=_snapshot(b)
        event=self._append_to(work["tc"],_snapshot(record),cap)
        if event:
            # Audit/store events are not authority-bearing TC writes.
            rejected=_snapshot(b); rejected["store_events"].append(event)
            self.__bundle=rejected
            return AppendResult(False,_immutable(event))
        work["tc"]["tc_state_version"]=b["tc"]["tc_state_version"]+1
        self.__bundle=work
        return AppendResult(True,None)

    @_serialized
    def intervention(self,cap,kind,args):
        self._guard_idle()
        if cap is not self.__harness_cap: raise PermissionError("Harness capability required")
        b=self.__bundle; work=_snapshot(b);tc=work["tc"]
        if kind=="scopes":
            values=args[0]
            if type(values) not in (list,tuple): raise ValueError("Scope array required")
            tc["actor"]["delegation"]["scopes"]=[c.Action(x).value for x in values]
        elif kind=="ledger":
            actor,cc,amount=args
            c.AutonomyLedger({(actor,cc):amount})
            entries=tc["ledger"]["entries"]
            entries[:]=[e for e in entries if (e["actor_id"],e["cost_center"])!=(actor,cc)]
            entries.append(dict(actor_id=actor,cost_center=cc,amount=amount))
            entries.sort(key=lambda e:(e["actor_id"],e["cost_center"]))
        elif kind=="clock":
            if b["active"] is not None: raise SerializedRunError("Clock changes only between proposals")
            value=args[0]
            if _time(value)<_time(tc["t_eval"]): raise ValueError("Logical clock cannot move backward")
            tc["t_eval"]=value
        else: raise ValueError("Unsupported trusted intervention")
        _context(tc,c.Action.READ_DOC,{})
        tc["tc_state_version"]=b["tc"]["tc_state_version"]+1
        self.__bundle=work

    @_serialized
    def fault(self,cap,point):
        self._guard_idle()
        if cap is not self.__harness_cap: raise PermissionError("Harness capability required")
        if point not in (None,"tool_failure","after_tool","after_pr","after_ledger",
                         "before_consumed","consumed_reject","consumed_failure","after_consumed","before_publish"):
            raise ValueError("Unknown controlled fault")
        self.__fault=point

    @_serialized
    def commit(self,token,proposal_raw):
        self._guard_idle()
        b=self.__bundle
        if not isinstance(token,c.AuthorizationToken):
            raise AuthorizationRequired("Commit requires an authentic ALLOW token")
        entry=b["sessions"].get(token.decision_id)
        if entry is None or entry["result"].token is not token:
            raise AuthorizationRequired("Unissued/forged/cross-run token")
        if entry["lifecycle"]=="UNRESOLVED":
            raise UnresolvedTokenLifecycle("P5-12 OPEN: subsequent presentation after unsuccessful commit is unsupported; spent/unused status is not asserted")
        if entry["lifecycle"] not in ("FRESH","USED"):
            raise AuthorizationRequired("No authorized token")
        result=entry["result"]
        number=len(b["commits"])+1
        commit_id=self.__run_id+":commit:"+str(number)
        tc_before=b["tc"]
        point=self.__fault
        def finish(work,status,code,*,tool_id=None,events=(),anomalies=(),first=True,failure_detail=None):
            trace=_snapshot(result.trace)
            trace.update(execution_status=status,commit_code=code,tool_invocation_id=tool_id,
                ledger_before=_snapshot(tc_before.get("ledger")),ledger_after=_snapshot(work["tc"].get("ledger")),
                store_events=list(events),error={"code":code,"message":failure_detail or "Controlled commit did not execute"} if code else None)
            record=dict(commit_id=commit_id,run_id=self.__run_id,decision_id=token.decision_id,
                token=c.to_wire(token),verified_issued_token=True,authorization_basis=token.basis.value,
                tc_version_before=tc_before["tc_state_version"],tc_version_after=work["tc"]["tc_state_version"],
                implementation_diagnostics={"configured_fault":point},
                token_lifecycle_conformance="SUCCESS_USED" if status=="EXECUTED" else
                    "SUCCESS_REPLAY_REJECTED" if code=="TOKEN_USED" else "P5-12_OPEN_UNRESOLVED",
                trace=trace)
            work["commits"].append(record)
            work["store_events"].extend(_snapshot(list(events)))
            work["anomalies"].extend(_snapshot(list(anomalies)))
            if first:
                work["sessions"][token.decision_id]["lifecycle"]="USED" if status=="EXECUTED" else "UNRESOLVED"
                work["active"]=None
            self.__bundle=work  # one atomic in-process publication of TC/effects/audit/token bookkeeping
            if first: self.__fault=None
            return CommitResult(_immutable(trace),_immutable(record))
        if entry["lifecycle"]=="USED":
            return finish(_snapshot(b),"NOT_EXECUTED_TOKEN_REJECTED","TOKEN_USED",first=False)
        if b["active"]!=token.decision_id: raise SerializedRunError("Token is not the active proposal")
        try:
            presented=c.Proposal.from_json(proposal_raw)
            same=digest(c.to_wire(presented))==token.proposal_hash
        except (ValueError,TypeError,UnicodeError): same=False
        if not same:
            return finish(_snapshot(b),"NOT_EXECUTED_TOKEN_REJECTED","PROPOSAL_HASH_MISMATCH")
        if tc_before["tc_state_version"]!=token.tc_state_version:
            return finish(_snapshot(b),"NOT_EXECUTED_STALE","STALE_TC_VERSION")
        applicable={None,"tool_failure","after_tool","before_publish"}
        if presented.action_type==c.Action.SUBMIT_PR: applicable.add("after_pr")
        if presented.action_type==c.Action.EXECUTE_PURCHASE:
            applicable.add("after_pr")
            applicable.update({"after_ledger"} if token.basis==c.Basis.AUTONOMY else
                {"before_consumed","consumed_reject","consumed_failure","after_consumed"})
        if point not in applicable:
            raise ValueError("Trusted fault point does not apply to this operation; no execution attempted")
        work=_snapshot(b); tc=work["tc"]
        invocation_id=commit_id+":tool"
        def fault_at(stage):
            if point==stage: raise SyntheticToolError("Injected failure: "+stage)
        self.__busy=True
        try:
            # AV-1: the only call site of the capability-checked protected tool.
            self.__tools.invoke(self.__commit_cap,work["effects"],presented,invocation_id,fail=point=="tool_failure")
            fault_at("after_tool")
            p=c.to_wire(presented.params)
            if presented.action_type==c.Action.SUBMIT_PR:
                if p["request_id"] in tc["purchase_requests"]: raise SyntheticToolError("Unexpected duplicate at commit")
                tc["purchase_requests"][p["request_id"]]=dict(p,state="SUBMITTED",submitted_by=tc["actor"]["actor_id"])
                fault_at("after_pr")
            elif presented.action_type==c.Action.EXECUTE_PURCHASE:
                pr=tc["purchase_requests"][p["request_id"]]
                if pr["state"]!="SUBMITTED": raise SyntheticToolError("Unexpected PR state at commit")
                pr["state"]="EXECUTED"
                fault_at("after_pr")
                if token.basis==c.Basis.AUTONOMY:
                    actor=tc["actor"]["actor_id"];cc=p["cost_center"];entries=tc["ledger"]["entries"]
                    current=next((e for e in entries if (e["actor_id"],e["cost_center"])==(actor,cc)),None)
                    if current is None:
                        entries.append(dict(actor_id=actor,cost_center=cc,amount=p["amount"]))
                    else: current["amount"]+=p["amount"]
                    entries.sort(key=lambda e:(e["actor_id"],e["cost_center"]))
                    fault_at("after_ledger")
                elif token.basis==c.Basis.APPROVAL:
                    fault_at("before_consumed")
                    g=inspect_chain(tc["approval_chains"][p["request_id"]]["records"]).governing
                    record=dict(g)
                    record.update(approval_id=commit_id+":consumed",seq=g["seq"]+1,status="CONSUMED",
                        issued_at=tc["t_eval"],prev_hash=g["content_hash"])
                    if point=="consumed_reject": record["seq"]+=1
                    record["content_hash"]=approval_content_hash(record)
                    fault_at("consumed_failure")
                    event=self._append_to(tc,record,self.__commit_cap)
                    if event: raise _ConsumedAppendRejected(event)
                    fault_at("after_consumed")
                else: raise SyntheticToolError("Unexpected EX basis")
            if presented.action_type in (c.Action.SUBMIT_PR,c.Action.EXECUTE_PURCHASE):
                tc["tc_state_version"]=tc_before["tc_state_version"]+1
            fault_at("before_publish")
            return finish(work,"EXECUTED",None,tool_id=invocation_id)
        except Exception as exc:
            events=(exc.event,) if isinstance(exc,_ConsumedAppendRejected) else ()
            anomalies=({"kind":"CONSUMED_APPEND_REJECTED","commit_id":commit_id,"store_code":exc.event["code"],
                        "fault_injected":point=="consumed_reject"},) if events else ()
            return finish(_snapshot(b),"EXECUTION_ERROR","TOOL_ERROR",events=events,anomalies=anomalies,
                failure_detail=type(exc).__name__+": "+str(exc))
        finally:
            self.__busy=False

class AgentPort:
    """Only agent-facing methods. No state/store/tool handle or writer interface."""
    __slots__=("__evaluate","__commit")
    def __init__(self,authorize,commit):
        self.__evaluate=authorize;self.__commit=commit
    def evaluate(self,proposal_raw,metadata):
        return self.__evaluate(proposal_raw,metadata)
    def commit(self,token,proposal_raw):
        return self.__commit(token,proposal_raw)

class TrustedHarness:
    """Trusted test/scenario control; never passed to the agent-facing interface."""
    __slots__=("__core","__harness_cap","__script_cap")
    def __init__(self,core,harness_cap,script_cap):
        self.__core=core;self.__harness_cap=harness_cap;self.__script_cap=script_cap
    def snapshot(self): return self.__core.inspect(self.__harness_cap,"tc")
    def effects(self): return self.__core.inspect(self.__harness_cap,"effects")
    def audit(self): return self.__core.inspect(self.__harness_cap,"audit")
    def append_approval(self,record): return self.__core.scripted_append(self.__script_cap,record)
    def change_scopes(self,scopes): return self.__core.intervention(self.__harness_cap,"scopes",(scopes,))
    def set_ledger(self,actor,cc,amount): return self.__core.intervention(self.__harness_cap,"ledger",(actor,cc,amount))
    def advance_clock(self,value): return self.__core.intervention(self.__harness_cap,"clock",(value,))
    def inject_fault(self,point): return self.__core.fault(self.__harness_cap,point)

def new_run(initial_context,run_id,*,allow_injected_state=False):
    core=_RunCore(initial_context,run_id,allow_injected_state)
    return core.harness(),core.agent()
