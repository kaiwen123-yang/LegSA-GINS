"""C-06 checks on the frozen rule and copied decision inputs; no metric evaluation."""

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

import pytest


REPO = Path(__file__).resolve().parents[2]
RULE = REPO / "docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md"
RECORD = REPO / "docs/paper_rebuild/CLEAN5_OFFLINE_EVALUATION_RECORD.md"
BASELINE_COMMIT = "09caf1e7e6151f18cc25dafad4a7ef5704ae62d2"
BASELINE_SHA = "4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce"
DECISION_SHA = "d9867e64d9e57caea19cfd83b7c7dfba5e9fc95e789859fefbc1820b8230ef1e"
MARKER = (
    b"## Outcome (append only, after both sequences are sealed and evaluated)\n\n"
    b"```text\n"
)
# Captured from the rule at BASELINE_COMMIT, whose complete bytes hash to BASELINE_SHA.
# Restoring this small placeholder block checks all other bytes, without requiring
# historical Git objects or any machine-local data root in the test environment.
PLACEHOLDERS = b"""BY2H yaw gate:            <PASS|FAIL>
BY2H yawRMSE  A04 / F04:  <value> / <value>
BY2H yawP95   A04 / F04:  <value> / <value>
BY2H hRMSE    A04 / F04:  <value> / <value>
BY2H upRMSE   A04 / F04:  <value> / <value>
BY2O window (input-side): <t0>..<t1>
BY2O hRMSE  full / outside  A04 / F04: <values>
BY2O upRMSE full / outside  A04 / F04: <values>
Heading test:             <PASS|FAIL>
Position bound:           <PASS|FAIL>
Proposed method:          <A04|F04>
Evidence commit / attempt: <hash> / <attempt id>
"""


def _parts(document):
    if document.count(MARKER) != 1:
        raise ValueError("exactly one Outcome block required")
    start = document.index(MARKER) + len(MARKER)
    end = document.find(b"```", start)
    if end < 0:
        raise ValueError("Outcome closing fence missing")
    return document[:start], document[start:end], document[end:]


def _assert_outcome_only(before, after):
    before_prefix, _, before_suffix = _parts(before)
    after_prefix, _, after_suffix = _parts(after)
    if (before_prefix, before_suffix) != (after_prefix, after_suffix):
        raise ValueError("bytes outside the Outcome code block changed")


def _decision():
    section = RECORD.read_bytes().split(
        b"## Frozen decision-input JSON, literal copy", 1
    )[1]
    matches = re.findall(rb"```json\n(.*?)```", section, re.S)
    assert len(matches) == 1
    assert hashlib.sha256(matches[0]).hexdigest() == DECISION_SHA
    return json.loads(matches[0])


def _outcome_fields():
    _, body, _ = _parts(RULE.read_bytes())
    pairs = [line.split(":", 1) for line in body.decode().splitlines() if line]
    assert all(len(pair) == 2 for pair in pairs)
    fields = {key.strip(): value.strip() for key, value in pairs}
    assert len(fields) == len(pairs) == 12
    return fields


def _display(metric):
    # Decimal formatting only: reuse the frozen CSV token, never calculate a metric.
    return format(Decimal(metric["source"]["raw_token"]), ".6f")


def test_rule_bytes_outside_outcome_equal_frozen_commit():
    current = RULE.read_bytes()
    prefix, _, suffix = _parts(current)
    reconstructed_baseline = prefix + PLACEHOLDERS + suffix
    assert hashlib.sha256(reconstructed_baseline).hexdigest() == BASELINE_SHA
    _assert_outcome_only(reconstructed_baseline, current)


@pytest.mark.parametrize("change", ["prefix", "suffix", "heading", "fence", "duplicate"])
def test_scope_check_rejects_any_outside_block_change(change):
    original = b"frozen\n" + MARKER + PLACEHOLDERS + b"```\nunchanged tail\n"
    updated = original.replace(PLACEHOLDERS, b"Proposed method: A04\n")
    if change == "prefix":
        updated = updated.replace(b"frozen", b"changed", 1)
    elif change == "suffix":
        updated += b" \n"
    elif change == "heading":
        updated = updated.replace(b"append only", b"editable", 1)
    elif change == "fence":
        updated = updated.replace(b"```\nunchanged", b"````\nunchanged", 1)
    else:
        updated += MARKER + b"duplicate\n```\n"
    with pytest.raises(ValueError):
        _assert_outcome_only(original, updated)


def test_scope_check_accepts_body_replacement_only():
    original = b"frozen\n" + MARKER + PLACEHOLDERS + b"```\nunchanged tail\n"
    _assert_outcome_only(original, original.replace(PLACEHOLDERS, b"copied outcome\n"))


@pytest.mark.parametrize(
    ("label", "metric"),
    [
        ("BY2H yawRMSE  A04 / F04", "yaw_rmse_deg"),
        ("BY2H yawP95   A04 / F04", "yaw_p95_deg"),
        ("BY2H hRMSE    A04 / F04", "horizontal_rmse_m"),
        ("BY2H upRMSE   A04 / F04", "up_rmse_m"),
    ],
)
def test_outcome_by2h_numbers_are_frozen_decision_tokens(label, metric):
    full = _decision()["inputs"]["BY2H"]["full"]
    expected = [_display(full[method][metric]) for method in ("A04", "F04")]
    assert re.findall(r"-?\d+\.\d+", _outcome_fields()[label]) == expected


@pytest.mark.parametrize(
    ("label", "metric"),
    [
        ("BY2O hRMSE  full / outside  A04 / F04", "horizontal_rmse_m"),
        ("BY2O upRMSE full / outside  A04 / F04", "up_rmse_m"),
    ],
)
def test_outcome_by2o_numbers_copy_full_then_outside_tokens(label, metric):
    source = _decision()["inputs"]["BY2O"]
    expected = [
        _display(source[segment][method][metric])
        for segment in ("full", "outside")
        for method in ("A04", "F04")
    ]
    assert re.findall(r"-?\d+\.\d+", _outcome_fields()[label]) == expected


def test_outcome_window_and_gate_statuses_copy_frozen_decision():
    decision, fields = _decision(), _outcome_fields()
    window = decision["inputs"]["BY2O"]["occlusion_window"]
    assert fields["BY2O window (input-side)"] == "..".join(
        _display(window[key]) for key in ("t0", "t1")
    )
    assert fields["BY2H yaw gate"] == decision["inputs"]["BY2H"]["yaw_physical_gate"]["status"]
    assert fields["Heading test"] == decision["tests"]["heading"]["status"] == "FAIL"
    assert fields["Position bound"].split(" ", 1)[0] == decision["tests"]["position"]["status"] == "FAIL"
    assert fields["Position bound"] == "FAIL (BY2H PASS; BY2O full/outside Up FAIL)"
    windows = decision["tests"]["position"]["windows"]
    assert windows["BY2H_full"]["horizontal_rmse_m"]["strict_pass"] is True
    assert windows["BY2H_full"]["up_rmse_m"]["strict_pass"] is True
    assert windows["BY2O_full"]["up_rmse_m"]["strict_pass"] is False
    assert windows["BY2O_outside"]["up_rmse_m"]["strict_pass"] is False
    assert fields["Proposed method"] == "A04"
    assert BASELINE_COMMIT in fields["Evidence commit / attempt"]
    assert decision["metric_recomputation_count"] == 0
    assert decision["reference_payload_read_count"] == 0
