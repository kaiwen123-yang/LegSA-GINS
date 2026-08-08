from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild"
SCRIPT = SCRIPT_DIR / "generate_canonical541_providers.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("canonical541_provider_promotion", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
normalize = MODULE.normalize_promoted_resolved_path


def test_prepromotion_internal_path_survives_atomic_rename_and_strict_resolution(tmp_path):
    provider_root = tmp_path / "provider"
    cases = provider_root / ".staging_attempt/CASES"
    actual = cases / "D01_seed_00/02_PROVIDERS/gnss_position_provider.csv"
    actual.parent.mkdir(parents=True)
    actual.write_text("provider\n", encoding="utf-8")
    finalized = provider_root / "FINALIZED"

    recorded = normalize(actual_path=actual, cases_root=cases, finalized=finalized)
    assert recorded == finalized / "D01_seed_00/02_PROVIDERS/gnss_position_provider.csv"
    assert ".staging_attempt" not in recorded.parts
    assert not recorded.exists()

    os.replace(cases, finalized)
    assert recorded.resolve(strict=True) == (
        finalized / "D01_seed_00/02_PROVIDERS/gnss_position_provider.csv"
    ).resolve(strict=True)


def test_external_pointer_preserves_exact_resolved_path(tmp_path):
    provider_root = tmp_path / "provider"
    cases = provider_root / ".staging_attempt/CASES"
    cases.mkdir(parents=True)
    finalized = provider_root / "FINALIZED"
    external = tmp_path / "fresh_base/raw_doppler_provider.csv"
    external.parent.mkdir(parents=True)
    external.write_text("fresh external\n", encoding="utf-8")

    recorded = normalize(actual_path=external, cases_root=cases, finalized=finalized)
    assert recorded == external.resolve(strict=True)


def test_resume_with_cases_root_equal_finalized_is_identity(tmp_path):
    provider_root = tmp_path / "provider"
    finalized = provider_root / "FINALIZED"
    actual = finalized / "C00_clean_normal/02_PROVIDERS/combined.gnss"
    actual.parent.mkdir(parents=True)
    actual.write_text("clean\n", encoding="utf-8")

    recorded = normalize(actual_path=actual, cases_root=finalized, finalized=finalized)
    assert recorded == actual.resolve(strict=True)


def test_stale_sibling_staging_path_is_rejected(tmp_path):
    provider_root = tmp_path / "provider"
    current = provider_root / ".staging_current/CASES"
    current.mkdir(parents=True)
    stale = provider_root / ".staging_old/CASES/D01/provider.csv"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="stale internal provider staging path"):
        normalize(actual_path=stale, cases_root=current,
                  finalized=provider_root / "FINALIZED")
