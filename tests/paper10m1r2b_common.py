"""Helpers for PAPER10M1R2B generated-provider tests."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest


def stage_root() -> Path:
    value = os.environ.get("PAPER10M1R2B_STAGE_ROOT")
    if not value:
        pytest.skip("PAPER10M1R2B_STAGE_ROOT is not set")
    root = Path(value)
    if not root.exists():
        pytest.skip(f"PAPER10M1R2B_STAGE_ROOT does not exist: {root}")
    return root


def provider_root() -> Path:
    value = os.environ.get("PAPER10M1R2B_PROVIDER_ROOT")
    if not value:
        pytest.skip("PAPER10M1R2B_PROVIDER_ROOT is not set")
    root = Path(value)
    if not root.exists():
        pytest.skip(f"PAPER10M1R2B_PROVIDER_ROOT does not exist: {root}")
    return root


def read_csv(relative: str) -> list[dict[str, str]]:
    path = stage_root() / relative
    assert path.exists(), f"missing generated CSV: {relative}"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(relative: str):
    path = stage_root() / relative
    assert path.exists(), f"missing generated JSON: {relative}"
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(relative: str) -> str:
    path = stage_root() / relative
    assert path.exists(), f"missing generated text file: {relative}"
    return path.read_text(encoding="utf-8")


def false_values(rows: list[dict[str, str]], field: str) -> set[str]:
    return {row[field] for row in rows}


EXPECTED_TYPES = {f"D{i:02d}" for i in range(1, 61)}
EXPECTED_METHOD_MODES = {
    "basic_dual_baseline",
    "strong_dual_yaw_baseline",
    "legsa_without_qm",
    "legsa_full_candidate_with_qm",
}
EXPECTED_ABLATION_METHODS = {
    "legsa_full_candidate_with_qm",
    "legsa_without_qm",
    "legsa_no_raw_doppler",
    "legsa_no_source_aware",
    "legsa_no_go2_roll_pitch",
    "legsa_no_go2_horizontal_velocity",
    "legsa_no_go2_joint",
    "legsa_no_qm",
    "legsa_no_fgo_feedback_or_ekf_only",
}
