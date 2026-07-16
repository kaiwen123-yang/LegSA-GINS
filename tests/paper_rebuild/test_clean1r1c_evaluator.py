from __future__ import annotations

import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.evaluator import (
    EVALUATOR_PROFILE_V2,
    EVALUATOR_PROTOCOL_ID_V2,
    EvaluatorContractError,
    build_row_level_errors,
    derive_reference_timing_profile,
    freeze_evaluator_contract,
    load_frozen_evaluator,
    reference_yaw_enu_to_solver_ned_deg,
    wrap_signed_deg,
)


ROOT = Path(__file__).resolve().parents[2]
TRACKED_CONTRACT = ROOT / "configs/paper_rebuild/evaluator_contract.yaml"
REFERENCE_RELATIVE = "BY2/hash-locked-trace.csv"
DIGEST = "a" * 64


class _PoisonReferencePath:
    def __fspath__(self) -> str:
        raise AssertionError("freeze must not resolve or open the trace path")


def _freeze(tmp_path: Path):
    return freeze_evaluator_contract(
        TRACKED_CONTRACT,
        _PoisonReferencePath(),  # type: ignore[arg-type]
        tmp_path / "freeze",
        reference_relative_path=REFERENCE_RELATIVE,
        expected_reference_sha256=DIGEST,
        verified_source_hashes={REFERENCE_RELATIVE: DIGEST},
    )


def _reference_row(time: float, *, height: float = 0.0, yaw: float = 0.0) -> dict[str, str]:
    return {
        "time": str(time),
        "lat": "0",
        "lon": "0",
        "height": str(height),
        "yaw": str(yaw),
        "pitch": "0",
        "roll": "0",
    }


def _solver_row(time: float, *, height: float = 0.0, yaw: float = 0.0) -> dict[str, str]:
    return {
        "time": str(time),
        "lat_deg": "0",
        "lon_deg": "0",
        "height_m": str(height),
        "yaw_deg": str(yaw),
    }


def test_v2_freeze_uses_only_hash_lock_binding_and_is_formal_ready(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    assert frozen.ready is True
    assert frozen.terminal_status == "READY_FOR_OFFLINE_EVALUATION"
    payload = load_frozen_evaluator(frozen.contract_path, require_ready=True)
    assert payload["protocol_id"] == EVALUATOR_PROTOCOL_ID_V2
    assert payload["profile"] == EVALUATOR_PROFILE_V2
    assert payload["formal_metrics_authorized"] is True
    assert payload["method_output_read_during_freeze"] is False
    assert payload["trace_read_during_freeze"] is False
    assert payload["position_same_source_mounting_caveat"] is True
    assert payload["independent_ground_truth"] is False
    assert payload["point_compensation_in_evaluator"] is False
    assert payload["reference"]["sha256"] == DIGEST
    assert payload["reference"]["payload_read_during_freeze"] is False
    audit = json.loads(frozen.reference_schema_audit_path.read_text(encoding="utf-8"))
    assert audit["trace_read_during_freeze"] is False
    assert audit["hash_lock_binding_verified"] is True
    assert audit["schema_validation_phase"] == "offline_evaluation_only"


def test_v2_freeze_rejects_missing_hash_lock_binding(tmp_path: Path) -> None:
    with pytest.raises(EvaluatorContractError, match="hash-lock binding is missing"):
        freeze_evaluator_contract(
            TRACKED_CONTRACT,
            _PoisonReferencePath(),  # type: ignore[arg-type]
            tmp_path / "freeze",
            reference_relative_path=REFERENCE_RELATIVE,
            expected_reference_sha256=DIGEST,
            verified_source_hashes={REFERENCE_RELATIVE: "b" * 64},
        )
    assert not (tmp_path / "freeze").exists()


def test_v2_unwraps_yaw_and_linearly_interpolates_reference_ecef() -> None:
    reference = [
        _reference_row(100.0, height=0.0, yaw=179.0),
        _reference_row(101.0, height=2.0, yaw=-179.0),
        _reference_row(102.0, height=4.0, yaw=-177.0),
    ]
    solver = [
        _solver_row(0.5, height=2.0, yaw=-91.0),
        _solver_row(3.0, height=0.0, yaw=0.0),
    ]
    rows = build_row_level_errors(
        solver,
        reference,
        source_time_origin_seconds=100.0,
    )
    matched = rows[0]
    assert matched["matched"] is True
    assert matched["reference_left_time"] == pytest.approx(100.0)
    assert matched["reference_right_time"] == pytest.approx(101.0)
    assert matched["interpolation_fraction"] == pytest.approx(0.5)
    assert matched["horizontal_position_error_m"] == pytest.approx(0.0, abs=1.0e-8)
    assert matched["up_error_m"] == pytest.approx(1.0, abs=1.0e-6)
    assert matched["position_3d_error_m"] == pytest.approx(1.0, abs=1.0e-6)
    # ENU yaw 179 -> -179 unwraps through 180; NED reference is wrap360(90-180)=270.
    assert matched["yaw_error_deg"] == pytest.approx(-1.0)
    assert rows[1]["matched"] is False
    assert rows[1]["unmatched_reason"] == "outside_reference_extent"


def test_v2_gap_formula_blocks_sparse_bracket_and_retains_unmatched() -> None:
    reference = [_reference_row(float(value)) for value in range(100, 201)]
    reference.append(_reference_row(210.0))
    timing = derive_reference_timing_profile(reference)
    assert timing["median_dt_seconds"] == pytest.approx(1.0)
    assert timing["p99_dt_seconds"] == pytest.approx(1.0)
    assert timing["max_allowed_bracket_gap_seconds"] == pytest.approx(3.0)
    rows = build_row_level_errors(
        [_solver_row(205.0)],
        reference,
        source_time_origin_seconds=0.0,
    )
    assert len(rows) == 1
    assert rows[0]["matched"] is False
    assert rows[0]["unmatched_reason"] == "reference_bracket_gap_exceeds_gate"
    assert rows[0]["reference_bracket_gap_seconds"] == pytest.approx(10.0)


def test_v2_duplicate_reference_fails_and_extrapolation_is_forbidden() -> None:
    duplicate = [_reference_row(100.0), _reference_row(100.0)]
    with pytest.raises(EvaluatorContractError, match="Duplicate or nonmonotonic reference timestamp"):
        build_row_level_errors(
            [_solver_row(0.0)],
            duplicate,
            source_time_origin_seconds=100.0,
        )

    reference = [_reference_row(100.0), _reference_row(101.0)]
    rows = build_row_level_errors(
        [_solver_row(-1.0), _solver_row(2.0)],
        reference,
        source_time_origin_seconds=100.0,
    )
    assert [row["matched"] for row in rows] == [False, False]
    assert all(row["unmatched_reason"] == "outside_reference_extent" for row in rows)


def test_v2_cardinal_conversion_and_signed_wrap() -> None:
    assert reference_yaw_enu_to_solver_ned_deg(0.0) == pytest.approx(90.0)
    assert reference_yaw_enu_to_solver_ned_deg(90.0) == pytest.approx(0.0)
    assert reference_yaw_enu_to_solver_ned_deg(180.0) == pytest.approx(270.0)
    assert reference_yaw_enu_to_solver_ned_deg(-90.0) == pytest.approx(180.0)
    assert wrap_signed_deg(181.0) == pytest.approx(-179.0)
    assert wrap_signed_deg(-181.0) == pytest.approx(179.0)
