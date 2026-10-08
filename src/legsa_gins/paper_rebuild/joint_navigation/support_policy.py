"""Canonical full source policies; observed-group edits use replacement semantics."""
from __future__ import annotations

import hashlib
import math


def canonical_policy(policy):
    components, assigned = [], set()
    for item in policy:
        arcs = tuple(sorted(set(item["arc_ids"])))
        if not arcs or item["mode"] == "fixed":
            continue
        if assigned.intersection(arcs):
            raise ValueError("each support arc must belong to exactly one source policy component")
        assigned.update(arcs)
        components.append((item["mode"], arcs, float(item.get("effective_from", -math.inf))))
    return tuple(dict(group_id="component:"+hashlib.sha256(repr(component).encode()).hexdigest()[:20],
                      mode=component[0], arc_ids=component[1], effective_from=component[2])
                 for component in sorted(components))


def policy_identity(policy):
    canonical = canonical_policy(policy)
    content = tuple((item["mode"], item["arc_ids"], item["effective_from"]) for item in canonical)
    return "policy:"+hashlib.sha256(repr(content).encode()).hexdigest()


def replace_group(policy, arc_ids, model, group_id):
    affected, result = set(arc_ids), []
    for old in policy:
        remainder = set(old["arc_ids"])-affected
        if remainder:
            result.append({**old, "arc_ids": tuple(sorted(remainder))})
    result.append(dict(group_id=group_id, arc_ids=tuple(arc_ids), mode=model, effective_from=-math.inf))
    return canonical_policy(result)


def policy_readout(policy):
    # JSON null denotes all history. Internal policies keep -inf for _models_at.
    return [{**item, "effective_from": None if item["effective_from"] == -math.inf else item["effective_from"]}
            for item in canonical_policy(policy)]
