from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild import clean1r2r1_formal
from legsa_gins.paper_rebuild.clean1r2r1_formal import (
    Clean1R2R1FormalError,
    validate_active_raw_doppler_anchor,
)
from legsa_gins.paper_rebuild.formal_generation import (
    FormalGenerationError,
    _canonical_rinex_header_line,
    build_actual_conversion_execution_contract,
    build_canonical_conversion_contract,
    normalize_rinex_build_header,
    validate_raw_doppler_reproducible_build,
)
from legsa_gins.paper_rebuild.formal_provider import (
    RAW_DOPPLER_ANCHOR_ACTIVE_SHA256,
    RAW_DOPPLER_ANCHOR_CODE_FREEZE,
    RAW_DOPPLER_ANCHOR_CONVERSION_IDENTITY_SHA256,
    RAW_DOPPLER_ANCHOR_NAV_SHA256,
    RAW_DOPPLER_ANCHOR_OBS_SHA256,
    RAW_DOPPLER_ANCHOR_REPORT_COMMIT,
    RAW_DOPPLER_CONVERSION_IDENTITY_ROLE,
    RAW_DOPPLER_RINEX_NORMALIZATION_POLICY,
)
from legsa_gins.paper_rebuild.paths import load_yaml_mapping


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml"


def _frozen_build() -> dict[str, object]:
    protocol = load_yaml_mapping(PROTOCOL)
    return deepcopy(
        protocol["provider_generation"]["raw_doppler_reproducible_build"]
    )


def _header_line(left: str, label: str) -> bytes:
    line = f"{left:<60}{label:<20}".encode("ascii")
    assert len(line) == 80
    return line


def _rinex_bytes(timestamp: str, *, payload: bytes = b"epoch-data\n") -> bytes:
    build = (
        f"{'CONVBIN 2.4.3':<20}{'':<20}{timestamp:<20}"
        f"{'PGM / RUN BY / DATE':<20}"
    ).encode("ascii")
    assert len(build) == 80
    return b"\n".join(
        (
            _header_line("3.04 OBSERVATION DATA", "RINEX VERSION / TYPE"),
            build,
            _header_line("", "END OF HEADER"),
        )
    ) + b"\n" + payload


def _normalization_for(expected: str) -> dict[str, object]:
    return {
        "policy_id": RAW_DOPPLER_RINEX_NORMALIZATION_POLICY,
        "fixed_width_bytes": 80,
        "label": "PGM / RUN BY / DATE",
        "program": "CONVBIN 2.4.3",
        "run_by": "",
        "build_timestamp_utc": "20260712 104638 UTC",
        "expected_obs_sha256": expected,
        "expected_nav_sha256": expected,
    }


def _actual_paths(root: Path) -> dict[str, Path]:
    return {
        "convbin_executable": root / "raw_doppler_backend/tools/convbin_pinned_b34",
        "rebuilt_ubx": root / "raw_doppler_backend/gnss1_rebuilt.ubx",
        "rinex_obs": root / "raw_doppler_backend/rinex/gnss1.obs",
        "rinex_nav": root / "raw_doppler_backend/rinex/gnss1.nav",
        "rinex_gnav": root / "raw_doppler_backend/rinex/gnss1.gnav",
        "rinex_hnav": root / "raw_doppler_backend/rinex/gnss1.hnav",
        "rinex_qnav": root / "raw_doppler_backend/rinex/gnss1.qnav",
        "rinex_lnav": root / "raw_doppler_backend/rinex/gnss1.lnav",
        "rinex_cnav": root / "raw_doppler_backend/rinex/gnss1.cnav",
        "rinex_inav": root / "raw_doppler_backend/rinex/gnss1.inav",
    }


def test_protocol_freezes_current_clean_anchor_roles_and_exact_header() -> None:
    build = validate_raw_doppler_reproducible_build(_frozen_build())
    assert build["source_code_freeze_commit"] == RAW_DOPPLER_ANCHOR_CODE_FREEZE
    assert build["source_report_commit"] == RAW_DOPPLER_ANCHOR_REPORT_COMMIT
    assert build["runtime_reads_prior_provider_or_rinex"] is False
    assert build["expected_active_raw_doppler_sha256"] == RAW_DOPPLER_ANCHOR_ACTIVE_SHA256
    normalization = build["rinex_header_normalization"]
    assert normalization["expected_obs_sha256"] == RAW_DOPPLER_ANCHOR_OBS_SHA256
    assert normalization["expected_nav_sha256"] == RAW_DOPPLER_ANCHOR_NAV_SHA256
    assert _canonical_rinex_header_line(normalization) == (
        b"CONVBIN 2.4.3                           "
        b"20260712 104638 UTC PGM / RUN BY / DATE "
    )
    identity = build["conversion_identity"]
    assert identity == {
        "csv_field": "conversion_config_hash",
        "role": RAW_DOPPLER_CONVERSION_IDENTITY_ROLE,
        "sha256": RAW_DOPPLER_ANCHOR_CONVERSION_IDENTITY_SHA256,
        "actual_contract_sha256_claimed": False,
    }


def test_wall_clock_header_normalization_is_byte_reproducible_across_attempt_roots(
    tmp_path: Path,
) -> None:
    canonical = _rinex_bytes("20260712 104638 UTC")
    expected = hashlib.sha256(canonical).hexdigest()
    normalization = _normalization_for(expected)
    outputs: list[bytes] = []
    for index, timestamp in enumerate(("20260716 010203 UTC", "20270101 235959 UTC")):
        attempt = tmp_path / f"attempt-{index}"
        attempt.mkdir()
        rinex = attempt / "fresh.obs"
        original = _rinex_bytes(timestamp)
        rinex.write_bytes(original)
        audit = normalize_rinex_build_header(
            rinex, normalization=normalization, role="obs"
        )
        outputs.append(rinex.read_bytes())
        assert audit["source_sha256"] == hashlib.sha256(original).hexdigest()
        assert audit["normalized_sha256"] == expected
        assert audit["changed_line_count"] == 1
        assert audit["only_build_timestamp_field_changed"] is True
    assert outputs == [canonical, canonical]


def test_normalizer_changes_header_only_and_rejects_any_other_byte_drift(
    tmp_path: Path,
) -> None:
    canonical = _rinex_bytes("20260712 104638 UTC")
    expected = hashlib.sha256(canonical).hexdigest()
    normalization = _normalization_for(expected)
    source = tmp_path / "fresh.nav"
    original = _rinex_bytes("20301231 235959 UTC")
    source.write_bytes(original)
    audit = normalize_rinex_build_header(
        source, normalization=normalization, role="nav"
    )
    assert source.read_bytes() == canonical
    assert audit["non_target_bytes_sha256"] == hashlib.sha256(
        b"".join(
            line
            for line in original.splitlines(keepends=True)
            if b"PGM / RUN BY / DATE" not in line
        )
    ).hexdigest()

    drifted = tmp_path / "drifted.nav"
    drifted_original = _rinex_bytes("20301231 235959 UTC", payload=b"changed\n")
    drifted.write_bytes(drifted_original)
    with pytest.raises(FormalGenerationError, match="differs from current-clean anchor"):
        normalize_rinex_build_header(
            drifted, normalization=normalization, role="nav"
        )
    assert drifted.read_bytes() == drifted_original


def test_canonical_contract_is_attempt_root_independent_but_execution_is_not(
    tmp_path: Path,
) -> None:
    build = validate_raw_doppler_reproducible_build(_frozen_build())
    generation = {
        "raw_doppler_min_sat": 5,
        "raw_doppler_std_floor_mps": 0.2,
        "raw_doppler_covariance_policy": "conservative_isotropic_max_ecef_std_floor_0p2_mps",
    }
    source_position = {
        "utc_year": 2026,
        "utc_month": 3,
        "utc_day": 6,
        "gps_week": 2408,
        "leap_seconds": 18,
        "lat_deg": 40.0,
        "lon_deg": 116.0,
        "height_m": 10.0,
        "selected_status_row_number": 2,
        "selected_status_fields_sha256": "a" * 64,
    }
    first = build_canonical_conversion_contract(
        aliases=build["canonical_path_aliases"],
        source_position=source_position,
        generation=generation,
    )
    second = build_canonical_conversion_contract(
        aliases=build["canonical_path_aliases"],
        source_position=source_position,
        generation=generation,
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert "/tmp/" not in json.dumps(first, sort_keys=True)

    roots = [tmp_path / "attempt-one", tmp_path / "attempt-two"]
    for root in roots:
        root.mkdir()
    executions = [
        build_actual_conversion_execution_contract(
            provider_root=root, paths=_actual_paths(root)
        )
        for root in roots
    ]
    assert executions[0]["provider_root"] != executions[1]["provider_root"]
    assert executions[0]["actual_command"] != executions[1]["actual_command"]


def test_canonical_alias_and_actual_execution_reject_absolute_or_escaped_paths(
    tmp_path: Path,
) -> None:
    build = _frozen_build()
    build["canonical_path_aliases"]["rinex_obs"] = "/tmp/attempt/rinex.obs"
    with pytest.raises(FormalGenerationError, match="alias is unsafe"):
        validate_raw_doppler_reproducible_build(build)

    root = tmp_path / "attempt"
    root.mkdir()
    paths = _actual_paths(root)
    paths["rinex_obs"] = tmp_path / "escaped.obs"
    with pytest.raises(FormalGenerationError, match="escaped provider root"):
        build_actual_conversion_execution_contract(provider_root=root, paths=paths)


def test_conversion_compatibility_identity_cannot_claim_actual_contract_role() -> None:
    build = _frozen_build()
    build["conversion_identity"]["role"] = "actual_conversion_contract_sha256"
    build["conversion_identity"]["actual_contract_sha256_claimed"] = True
    with pytest.raises(FormalGenerationError, match="identity role is ambiguous"):
        validate_raw_doppler_reproducible_build(build)


def test_active_rebased_raw_doppler_hash_is_a_hard_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active = tmp_path / "RAW_DOPPLER_VELOCITY.csv"
    active.write_bytes(b"time,vn\n66.0,1.0\n")
    expected = hashlib.sha256(active.read_bytes()).hexdigest()
    monkeypatch.setattr(
        clean1r2r1_formal, "RAW_DOPPLER_ANCHOR_ACTIVE_SHA256", expected
    )
    contract = {"expected_active_raw_doppler_sha256": expected}
    assert validate_active_raw_doppler_anchor(active, contract) == expected
    active.write_bytes(active.read_bytes() + b"67.0,1.1\n")
    with pytest.raises(
        Clean1R2R1FormalError,
        match="BLOCKED_CLEAN2_BASE_PROVIDER_PARITY_FAILED",
    ):
        validate_active_raw_doppler_anchor(active, contract)
