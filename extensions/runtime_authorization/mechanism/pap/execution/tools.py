"""Capability-checked in-memory synthetic effects; no real tools or external I/O."""
class SyntheticToolError(RuntimeError):
    pass

class _SyntheticTools:
    __slots__=("__commit_cap",)
    def __init__(self,commit_cap):
        self.__commit_cap=commit_cap
    def invoke(self,cap,work_effects,proposal,invocation_id,*,fail=False):
        if cap is not self.__commit_cap:
            raise PermissionError("Protected synthetic tool requires commit capability")
        if proposal.action_type.value not in ("READ_DOC","RECOMMEND_PURCHASE","SUBMIT_PR","EXECUTE_PURCHASE"):
            raise SyntheticToolError("No protected synthetic tool for this action")
        from ..contracts import to_wire
        # Effects exist only in the transaction's unpublished work buffer.
        work_effects.append(dict(tool_invocation_id=invocation_id,action=proposal.action_type.value,
                                 params=to_wire(proposal.params),proposal_id=proposal.proposal_id))
        if fail:
            raise SyntheticToolError("Injected synthetic tool failure after staged effect")
