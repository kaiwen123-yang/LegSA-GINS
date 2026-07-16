from __future__ import annotations

import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean2_runner import (
    Clean2RunError,
    _compare_nav_std,
    _formal_numeric_output_health,
    _require_phase_predecessors,
    _write_solver_file_open_audit,
    validate_attempt_rows,
)


def _numeric_line(count: int, *, time_index: int, time: float) -> str:
    values = [0.0] * count
    values[time_index] = time
    return " ".join(str(value) for value in values)


def test_exact_nav11_std22_health_is_finite_row_and_time_exact(tmp_path):
    nav = tmp_path / "KF_GINS_Navresult.nav"
    std = tmp_path / "KF_GINS_STD.txt"
    nav.write_text(
        "\n".join(_numeric_line(11, time_index=1, time=value) for value in (1.0, 2.0)) + "\n",
        encoding="utf-8",
    )
    std.write_text(
        "\n".join(_numeric_line(22, time_index=0, time=value) for value in (1.0, 2.0)) + "\n",
        encoding="utf-8",
    )
    health = _formal_numeric_output_health({"exact_nav": nav, "exact_std": std})
    assert health["nav_row_count"] == health["std_row_count"] == 2
    assert health["nav_column_count"] == 11
    assert health["std_column_count"] == 22
    assert health["timestamps_exact"] is True

    std.write_text(_numeric_line(21, time_index=0, time=1.0) + "\n", encoding="utf-8")
    with pytest.raises(Clean2RunError, match="22 finite columns"):
        _formal_numeric_output_health({"exact_nav": nav, "exact_std": std})


def test_solver_file_open_audit_requires_inputs_and_zero_raw_trace(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    config = tmp_path / "config.yaml"
    imu = tmp_path / "imu.txt"
    gnss = tmp_path / "gnss.txt"
    for path in (config, imu, gnss):
        path.write_text(path.name, encoding="utf-8")
    strace = attempt / "SOLVER_FILE_OPEN_TRACE.raw"
    strace.write_text("openat evidence\n", encoding="utf-8")
    bindings = {
        "runtime_config_path": str(config),
        "shared_provider_paths": {
            "imu": str(imu),
            "raw_doppler": str(tmp_path / "unused-rd"),
            "go2_roll_pitch": str(tmp_path / "unused-rp"),
            "go2_horizontal_velocity": str(tmp_path / "unused-hv"),
        },
        "case_gnss_path": str(gnss),
    }
    row = {
        "run_id": "R001_C00_single",
        "run_order": 1,
        "feature_RD": False,
        "feature_RP": False,
        "feature_HV": False,
    }
    monkeypatch.setattr(
        "legsa_gins.paper_rebuild.clean2_runner.parse_strace_openat_paths",
        lambda *_args, **_kwargs: [config.resolve(), imu.resolve(), gnss.resolve()],
    )
    audit = _write_solver_file_open_audit(
        strace_path=strace,
        attempt_root=attempt,
        row=row,
        bindings=bindings,
        raw_root=raw_root,
        command_cwd=tmp_path,
    )
    assert audit["required_input_open_counts"] == {
        "runtime_config": 1,
        "propagation_imu": 1,
        "case_gnss": 1,
    }
    assert audit["raw_root_open_count"] == audit["trace_open_count"] == 0
    assert str(tmp_path) not in json.dumps(audit)

    bad_attempt = tmp_path / "bad-attempt"
    bad_attempt.mkdir()
    bad_trace = bad_attempt / "SOLVER_FILE_OPEN_TRACE.raw"
    bad_trace.write_text("openat evidence\n", encoding="utf-8")
    raw_file = raw_root / "unexpected.csv"
    raw_file.write_text("raw", encoding="utf-8")
    monkeypatch.setattr(
        "legsa_gins.paper_rebuild.clean2_runner.parse_strace_openat_paths",
        lambda *_args, **_kwargs: [config.resolve(), imu.resolve(), gnss.resolve(), raw_file.resolve()],
    )
    with pytest.raises(Clean2RunError, match="EVIDENCE_CONTAMINATION"):
        _write_solver_file_open_audit(
            strace_path=bad_trace,
            attempt_root=bad_attempt,
            row=row,
            bindings=bindings,
            raw_root=raw_root,
            command_cwd=tmp_path,
        )


def test_phase_predecessor_order_is_structural_factorial_controlled(monkeypatch, tmp_path):
    called: list[str] = []
    monkeypatch.setattr(
        "legsa_gins.paper_rebuild.clean2_runner._validate_completed_phase",
        lambda _runtime, phase, _rows: called.append(phase),
    )
    _require_phase_predecessors(tmp_path, "sentinel_loo", [])
    assert called == ["structural_gate", "factorial_remaining", "controlled_canonical"]


def test_attempt_audit_requires_one_pass_or_one_authorized_retry():
    rows = [
        {
            "run_id": "R001", "run_order": 1, "attempt_number": 1,
            "technical_retry": False, "retry_reason": "", "metric_driven_rerun": False,
            "returncode": 0, "terminal_status": "PASS",
        },
        {
            "run_id": "R002", "run_order": 2, "attempt_number": 1,
            "technical_retry": False, "retry_reason": "I/O_transient",
            "metric_driven_rerun": False, "returncode": 1,
            "terminal_status": "RETRYABLE_TECHNICAL_FAILURE",
        },
        {
            "run_id": "R002", "run_order": 2, "attempt_number": 2,
            "technical_retry": True, "retry_reason": "I/O_transient",
            "metric_driven_rerun": False, "returncode": 0, "terminal_status": "PASS",
        },
    ]
    registry = [{"run_id": "R001", "run_order": 1}, {"run_id": "R002", "run_order": 2}]
    audit = validate_attempt_rows(
        rows, registry_rows=registry, required_run_ids={"R001", "R002"}
    )
    assert audit["run_count"] == 2
    assert audit["technical_retry_run_count"] == 1
    assert audit["all_terminal_pass"] is True


def test_c00_structural_parity_uses_all_frozen_rmse_and_per_row_std_max(tmp_path):
    nav = tmp_path / "nav.txt"
    std = tmp_path / "std.txt"
    nav.write_text(_numeric_line(11, time_index=1, time=1.0) + "\n", encoding="utf-8")
    std.write_text(_numeric_line(22, time_index=0, time=1.0) + "\n", encoding="utf-8")
    tolerance = {
        "timestamp_abs_max_sec": 1.0e-9,
        "horizontal_rmse_m": 0.02, "horizontal_max_m": 0.1,
        "up_rmse_m": 0.02, "up_max_m": 0.1,
        "velocity_3d_rmse_mps": 0.002, "velocity_3d_max_mps": 0.01,
        "roll_rmse_deg": 0.002, "pitch_rmse_deg": 0.002,
        "yaw_rmse_deg": 0.002, "attitude_max_abs_deg": 0.01,
        "std_max_normalized_rmse": 0.01, "std_max_normalized_max": 0.05,
    }
    result = _compare_nav_std(nav, nav, std, std, tolerance)
    assert result["passed"] is True
    assert set(result["gate_fields"]) == set(tolerance)
    assert result["std_normalization_definition"].startswith("per_row_max")
