"""EX2-FOUNDATION-1.0 canonical encoding; not a PAP semantic amendment."""
import hashlib
import json
from collections.abc import Mapping
SCHEMA_VERSION = "EX2-FOUNDATION-1.0"
GENESIS = "0" * 64

def _checked(value):
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is str:
        value.encode("utf-8", errors="strict")
        return value
    if type(value) in (list, tuple):
        return [_checked(x) for x in value]
    if isinstance(value, Mapping):
        if any(type(k) is not str for k in value):
            raise ValueError("Only string mapping keys permitted")
        return {k: _checked(v) for k, v in value.items()}
    raise ValueError("Unsupported canonical value type")

def canonical_bytes(value) -> bytes:
    return json.dumps(_checked(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result

def strict_json(text: str):
    def reject(value):
        raise ValueError("Non-integer JSON number: " + value)
    return json.loads(text, object_pairs_hook=_pairs, parse_float=reject,
                      parse_constant=reject)

def approval_content_hash(record):
    """A.4: hash all record fields other than content_hash; no silent exclusions."""
    if set(record) != set(APPROVAL_FIELDS):
        raise ValueError("Approval field set mismatch")
    return digest({k: v for k, v in record.items() if k != "content_hash"})

APPROVAL_FIELDS = ("approval_id", "request_id", "seq", "actor_id", "vendor_id",
                   "cost_center", "amount", "approver_id", "status", "issued_at",
                   "expires_at", "policy_version", "prev_hash", "content_hash")
