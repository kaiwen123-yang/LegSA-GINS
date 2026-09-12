"""CLEAN5 module expectations derived from the existing frozen method registries."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..canonical541.ablation_registry import ABLATION_METHODS, validate_ablation_methods
from ..canonical541.full_method_registry import FULL_METHODS, validate_full_methods
from ..final_v23_clean_parity import METHOD_FEATURES
from ..manifest import sha256_file
from .runtime_config import METHODS

FEATURE_TRANSLATION = {
    "dual": "dual_yaw", "receiver": "receiver_velocity", "raw": "raw_doppler",
    "source_aware": "source_aware", "go2_roll_pitch": "go2_rp", "go2_horizontal": "go2_hv",
}
C00_MODULE_ACTION_SHA256 = "b6d8a1fbaf90b13cef4888d6e19c0f3472497add8876b27b9d5a014e792cd446"
C00_METRIC_FLAGS = {
    "gnss_position_update_count": "position_update",
    "receiver_velocity_update_count": "receiver_velocity",
    "dual_yaw_attempt_count": "dual_yaw",
    "raw_doppler_update_count": "raw_doppler",
    "source_aware_evaluation_count": "source_aware",
    "source_aware_changed_weight_count": "source_aware",
    "go2_rp_update_count": "go2_rp",
    "go2_hv_update_count": "go2_hv",
}


def profile_flags(effective_profile: str) -> dict[str, bool]:
    """Cross-check the parity features, full registry and RD/SA/RP/HV bit registry."""
    if effective_profile not in METHODS.values():
        raise ValueError(f"unknown CLEAN5 effective profile: {effective_profile}")
    validate_full_methods()
    validate_ablation_methods()
    matches = [row for row in (*FULL_METHODS, *ABLATION_METHODS)
               if row.effective_profile == effective_profile]
    if not matches or any(dict(row.flags) != dict(matches[0].flags) for row in matches):
        raise ValueError("frozen full/ablation registry feature disagreement")
    flags = dict(matches[0].flags)
    for full in (row for row in FULL_METHODS if row.effective_profile == effective_profile):
        expected = METHOD_FEATURES[full.name]
        if any(type(expected[key]) is not bool or expected[key] != flags[target]
               for key, target in FEATURE_TRANSLATION.items()):
            raise ValueError("parity METHOD_FEATURES differs from canonical full registry")
    if effective_profile.startswith("AB"):
        # This checks the canonical registry's interpretation, not a new bit order.
        for bit, key in zip(effective_profile[2:], ("raw_doppler", "source_aware", "go2_rp", "go2_hv")):
            if flags[key] != (bit == "1"):
                raise ValueError("canonical ablation bit mapping drift")
    return flags


def verify_canonical_patterns(path: str | Path) -> dict[str, Any]:
    """Check only frozen C00 module zero/nonzero patterns, never accuracy metrics."""
    source = Path(path)
    if source.is_symlink() or not source.is_file() or sha256_file(source) != C00_MODULE_ACTION_SHA256:
        raise ValueError("Canonical module-action source SHA256 mismatch")
    selected = {}
    with source.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            method, metric = row.get("method_id"), row.get("metric_name")
            if row.get("case_family") != "clean" or method not in METHODS or metric not in C00_METRIC_FLAGS:
                continue
            key = (method, metric)
            if key in selected:
                raise ValueError("duplicate Canonical C00 module-action row")
            if row.get("worst_case_id") != "C00_clean_normal" or any(
                    row.get(field) != "1" for field in ("count", "finite_count", "non_null_count")):
                raise ValueError("Canonical module pattern is not one finite C00 value")
            number = float(row["mean"])
            if not number.is_integer() or number < 0 or any(float(row[field]) != number for field in ("min", "max")):
                raise ValueError("Canonical C00 module count is not a consistent nonnegative integer")
            expected = profile_flags(METHODS[method])[C00_METRIC_FLAGS[metric]]
            if (number > 0) != expected:
                raise ValueError(f"Canonical C00 feature pattern mismatch: {method}/{metric}")
            selected[key] = bool(number > 0)
    if len(selected) != len(METHODS) * len(C00_METRIC_FLAGS):
        raise ValueError("Canonical C00 module pattern table lacks required rows")
    return {"passed": True, "source_sha256": C00_MODULE_ACTION_SHA256,
            "case_id": "C00_clean_normal", "source_role": "frozen module activation pattern only",
            "metric_order": list(C00_METRIC_FLAGS),
            "patterns": {method: "".join("1" if selected[(method, metric)] else "0"
                                        for metric in C00_METRIC_FLAGS) for method in METHODS},
            "out_of_scope_counter_gate_source": "native manifest; absent from aggregate summary"}
