"""Byte-preserving, input-event amendment of the two C-02 contracts."""
from __future__ import annotations
from hashlib import sha256
import re
import yaml
from .revalidation import HUMAN_PROTOCOL_STATEMENT, AMENDMENT_REASON

AMENDMENT_KEYS = {"contract_version", "supersedes_v1_sha256", "amended_before_unblinding",
    "amendment_reason", "human_protocol_statement", "amendment_code_commit", "event_window_report_sha256"}
EDITED_SECTIONS = {"window_contract", "initialization_contract"}


def sections(text):
    matches = list(re.finditer(r"(?m)^([A-Za-z_][A-Za-z0-9_]*):", text))
    result = {}
    for index, match in enumerate(matches):
        if match[1] in result:
            raise ValueError("Duplicate top-level contract section")
        result[match[1]] = text[match.start():matches[index+1].start() if index+1<len(matches) else len(text)]
    return text[:matches[0].start()] if matches else text, result


def update_initialization(text, updates):
    """Keep untouched initialization token spelling and comments as frozen."""
    matches = list(re.finditer(r"(?m)^  ([A-Za-z_][A-Za-z0-9_]*):", text))
    if not matches:
        raise ValueError("Initialization section has no canonical fields")
    parts = {match[1]: text[match.start():matches[index+1].start() if index+1<len(matches) else len(text)]
             for index, match in enumerate(matches)}
    for key, value in updates.items():
        fragment = yaml.safe_dump({key: value}, allow_unicode=True, sort_keys=False)
        parts[key] = "".join("  " + line for line in fragment.splitlines(keepends=True))
    return text[:matches[0].start()] + "".join(parts.values())


def validate_amendment(old_text, new_text):
    prefix, old = sections(old_text)
    new_prefix, new = sections(new_text)
    if new_prefix != prefix or set(new) != set(old) | AMENDMENT_KEYS:
        raise ValueError("Amendment changed contract prefix or unauthorized top-level keys")
    for key in set(old) - EDITED_SECTIONS:
        if old[key] != new[key]:
            raise ValueError("Unauthorized contract section byte change: " + key)
    values = yaml.safe_load(new_text)
    if (values["contract_version"] != 2 or values["supersedes_v1_sha256"] != sha256(old_text.encode()).hexdigest()
            or values["amended_before_unblinding"] is not True
            or values["human_protocol_statement"] != HUMAN_PROTOCOL_STATEMENT):
        raise ValueError("Contract amendment provenance mismatch")
    return {"passed": True, "unchanged_sections": sorted(set(old)-EDITED_SECTIONS),
        "supersedes_v1_sha256": values["supersedes_v1_sha256"]}


def amend_contract(old_text, event, event_sha256, code_commit):
    old = yaml.safe_load(old_text)
    if event.get("ready_for_v2_contract") is not True or event["dataset_id"] != old["identity"]["dataset_id"]:
        raise ValueError("Cannot amend without this sequence's event gate PASS")
    window = event["v2_window"]
    original_window = old["window_contract"]
    keep = ("three_stream_common_coverage", "epoch_association", "stream_clock_note",
            "first_common_epoch", "last_common_epoch", "stream_ranges",
            "no_method_specific_window", "preserve_internal_missing_epochs")
    replacement = {key: original_window[key] for key in keep if key in original_window}
    replacement.update(rule="event_onset_v2", **window,
        unadjusted_start_formula="floor(max(t_on_g, t_on_b))",
        t_start_formula="unadjusted start; if first propagation IMU >= start is delayed >1.0 s, floor(that IMU time)",
        t_end_formula="floor(last_common_epoch) - 9.0",
        constants=event["constants"], kick={key: value for key, value in event["kick"].items()
            if key in ("status", "kick_time_R1", "detector_source_sha256", "constants")},
        t_on_g=event["t_on_g"], t_on_b=event["t_on_b"], delta_t_onset_ms=event["delta_t_onset_ms"],
        v1_window={key: original_window[key] for key in ("rule", "t_start", "t_end")},
        v1_to_v2={key: {"v1": original_window[key], "v2": window[key]} for key in ("t_start", "t_end")})
    for key in ("event_report_relative_path", "event_attempt", "onset_censored_b", "onset_censored_g",
                "body_onset_interval_R1", "gnss_onset_interval_R1", "delta_t_onset_interval_ms",
                "clock_consistency_gate", "xcorr_gate", "propagation_start_adjustment",
                "preserve_internal_dropout", "kick_dropout_hypothesis"):
        replacement[key] = event[key]
    replacement["adjusted_for_imu_dropout"] = event["propagation_start_adjustment"]["adjusted"]
    initialization = dict(old["initialization_contract"])
    updates = event["initialization_v2"]
    allowed = {"initpos", "initatt", "position_epoch_R1", "yaw_epoch_R1", "yaw_ned_deg_0_360",
               "yaw_wrap180_equivalent_deg", "source_provenance"}
    if set(updates) - allowed or not {"initpos", "initatt", "position_epoch_R1", "yaw_epoch_R1"} <= set(updates):
        raise ValueError("Initialization amendment has unauthorized or missing fields")
    initialization.update(updates)
    additions = {"contract_version": 2, "supersedes_v1_sha256": sha256(old_text.encode()).hexdigest(),
        "amended_before_unblinding": True, "amendment_reason": AMENDMENT_REASON +
        " Second amendment: censored-onset fallback and IMU-availability shift are input-side, pre-unblinding rules. " +
        "Event report SHA-256: " + event_sha256 + ".",
        "human_protocol_statement": HUMAN_PROTOCOL_STATEMENT, "amendment_code_commit": code_commit,
        "event_window_report_sha256": event_sha256}
    prefix, parts = sections(old_text)
    parts["window_contract"] = yaml.safe_dump({"window_contract": replacement}, allow_unicode=True, sort_keys=False)
    parts["initialization_contract"] = update_initialization(parts["initialization_contract"], updates)
    text = prefix + "".join(parts.values()) + yaml.safe_dump(additions, allow_unicode=True, sort_keys=False)
    validate_amendment(old_text, text)
    return text
