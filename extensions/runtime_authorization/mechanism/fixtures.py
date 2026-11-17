"""Acceptance-only materialization. Imports frozen contracts read-only."""
from copy import deepcopy
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from collections.abc import Mapping
from typing import get_args, get_origin, get_type_hints, Union
from types import UnionType
import hashlib
import json

from .pap import contracts as c
from .pap.serialization import approval_content_hash, digest, GENESIS
from .pap.chain_validation import inspect_chain

SOURCE = Path(__file__).resolve().with_name("fixtures.json")
def load_protocol():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    if set(data) != {"test_only", "protocol"} or data["test_only"] is not True:
        raise ValueError("Only the approved synthetic fixture projection is supported")
    return data["protocol"]
PROTOCOL = load_protocol()


def thaw(value):
    if isinstance(value, Mapping):
        return {k: thaw(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [thaw(v) for v in value]
    return value.value if isinstance(value, Enum) else value

def typed(value, hint):
    """Convert explicit wire fields without adding authorization defaults."""
    if hint is c.AutonomyLedger:
        if set(value) != {"entries"}:
            raise ValueError("Ledger fields")
        entries = {}
        for row in value["entries"]:
            if set(row) != {"actor_id", "cost_center", "amount"}:
                raise ValueError("Ledger entry fields")
            key = (row["actor_id"], row["cost_center"])
            if key in entries:
                raise ValueError("Duplicate ledger entry")
            entries[key] = row["amount"]
        return c.AutonomyLedger(entries)
    origin, args = get_origin(hint), get_args(hint)
    if origin in (Union, UnionType):
        if value is None and type(None) in args:
            return None
        candidates = [a for a in args if a is not type(None)]
        if len(candidates) != 1:
            raise ValueError("Unsupported union")
        return typed(value, candidates[0])
    if origin is tuple:
        if type(value) is not list:
            raise ValueError("Expected wire array")
        return tuple(typed(v, args[0]) for v in value)
    if origin is Mapping:
        if type(value) is not dict:
            raise ValueError("Expected wire mapping")
        return {k: typed(v, args[1]) for k, v in value.items()}
    if isinstance(hint, type) and issubclass(hint, Enum):
        return hint(value)
    if isinstance(hint, type) and is_dataclass(hint):
        names = {f.name for f in fields(hint)}
        if type(value) is not dict or set(value) != names:
            raise ValueError("Closed " + hint.__name__)
        hints = get_type_hints(hint)
        return hint(**{k: typed(v, hints[k]) for k, v in value.items()})
    if type(value) is not hint:
        raise ValueError("Wrong primitive")
    return value

def merge(default, override):
    result = deepcopy(default)
    for key, value in override.items():
        if key not in result:
            # Registry keys are new, whereas closed TC keys are checked by typed().
            result[key] = deepcopy(value)
        elif type(value) is dict and type(result[key]) is dict:
            result[key] = merge(result[key], value)
        elif type(value) is not type(result[key]):
            raise ValueError("Override changes field type")
        else:
            result[key] = deepcopy(value)
    return result

def rebind(value, replacements):
    if isinstance(value, dict):
        return {replace(k, replacements): rebind(v, replacements) for k, v in value.items()}
    if isinstance(value, list):
        return [rebind(v, replacements) for v in value]
    return replace(value, replacements) if isinstance(value, str) else value

def replace(text, replacements):
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def materialize(sid, arm="B1", repetition=1):
    if sid not in PROTOCOL["locked_design"]["scenario_ids"] or arm not in ("B0", "B1", "B2") or repetition not in (1, 2, 3):
        raise ValueError("Unknown fixture identity")
    source = next(s for s in PROTOCOL["scenarios"] if s["id"] == sid)
    reference = merge(PROTOCOL["materialization"]["common_initial_tc"], source["tc_overrides"])
    if reference != source["reference_initial_tc"]:
        raise ValueError("Reference context differs from explicit merge")
    episode = f"TEST-ONLY-{sid}-{arm}-R{repetition:02d}"
    replacements = {f"EX2-{sid}-R{i}": f"{episode}-Q{i:02d}" for i in (1, 2)}
    scenario = rebind(source, replacements)
    wire = rebind(reference, replacements)
    for chain in wire["approval_chains"].values():
        previous = GENESIS
        for record in chain["records"]:
            record["prev_hash"] = previous
            record["content_hash"] = approval_content_hash(record)
            previous = record["content_hash"]
        if not inspect_chain(chain["records"]).valid:
            raise ValueError("Rebound initial chain invalid")
    context = typed(wire, c.TrustedContext)
    if c.to_wire(context) != wire:
        raise ValueError("Typed roundtrip differs")
    actions = scenario["reference_action_templates"]
    for i, action in enumerate(actions, 1):
        action["proposal_id"] = f"{episode}-P{i:03d}"
        c.Proposal.from_json(json.dumps(action))
    receipt = None
    if sid in ("S05", "S06"):
        receipt = rebind(PROTOCOL["approval_fixtures"]["reference_records"][sid], replacements)
        receipt["content_hash"] = approval_content_hash(receipt)
        instance = next(x for x in PROTOCOL["approval_fixtures"]["episode_instances"] if x["episode_id"] == episode)
        if receipt["content_hash"] != instance["content_hash"]:
            raise ValueError("Episode approval hash disagrees with protocol")
        if not inspect_chain([receipt]).valid:
            raise ValueError("Receipt structural failure")
    return dict(sid=sid, arm=arm, episode=episode, scenario=scenario,
                context=context, wire=wire, actions=actions, receipt=receipt)

def ledger_amount(tc):
    return next((r["amount"] for r in tc["ledger"]["entries"]
                 if (r["actor_id"], r["cost_center"]) == ("AG-01", "CC-OPS")), 0)

