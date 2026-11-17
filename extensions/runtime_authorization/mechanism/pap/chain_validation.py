"""PAP A.4 read-only chain inspection; no append/store mutation."""
from dataclasses import dataclass
from types import MappingProxyType
from . import contracts as c
from .serialization import APPROVAL_FIELDS, GENESIS, approval_content_hash
class ContextShapeError(ValueError):
    pass
@dataclass(frozen=True)
class ChainInspection:
    valid: bool
    failure_code: str | None
    governing: object
def inspect_chain(records):
    if type(records) not in (list,tuple):
        raise ContextShapeError("Approval records must be an array")
    for record in records:
        if type(record) is not dict or set(record)!=set(APPROVAL_FIELDS):
            raise ContextShapeError("Malformed approval record fields")
        if type(record["seq"]) is not int:
            raise ContextShapeError("Malformed seq type")
        if type(record["prev_hash"]) is not str or type(record["content_hash"]) is not str:
            raise ContextShapeError("Malformed hash type")
        try:
            shape=dict(record,seq=1,prev_hash=GENESIS,content_hash=GENESIS)
            shape["status"]=c.ApprovalStatus(shape["status"])
            c.ApprovalRecord(**shape)
        except (ValueError,TypeError) as exc:
            raise ContextShapeError("Malformed approval record") from exc
    def invalid(code): return ChainInspection(False,code,None)
    seqs=[r["seq"] for r in records]
    if len(set(seqs))!=len(seqs): return invalid("APPROVAL_SEQ_TIE")
    ordered=sorted(records,key=lambda r:r["seq"])
    if [r["seq"] for r in ordered]!=list(range(1,len(ordered)+1)):
        return invalid("APPROVAL_SEQ_INVALID")
    previous=None
    for record in ordered:
        status=c.ApprovalStatus(record["status"])
        if status not in c.TRANSITIONS[previous]: return invalid("APPROVAL_SEQ_INVALID")
        previous=status
    previous=GENESIS
    for record in ordered:
        if record["prev_hash"]!=previous or record["content_hash"]!=approval_content_hash(record):
            return invalid("APPROVAL_HASH_INVALID")
        previous=record["content_hash"]
    return ChainInspection(True,None,MappingProxyType(dict(ordered[-1])) if ordered else None)
