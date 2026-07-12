from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.evidence import BY2_TRACE_RELATIVE_PATH
from legsa_gins.paper_rebuild.clean1r2r1_formal import (
    METHOD_ORDER,
    RUN_DIRECTORIES,
    Clean1R2R1FormalError,
    _assert_parity_gate,
    auxiliary_generation_plan,
    module_counters,
    normalize_runtime_config,
    seal_auxiliary_file_open_audit,
    validate_four_method_seal,
)
from legsa_gins.paper_rebuild.final_v23_clean_parity import active_runtime_config
from legsa_gins.paper_rebuild.manifest import sha256_file


def test_auxiliary_plan_has_no_trace_and_keeps_15col_base_separate() -> None:
    plan = auxiliary_generation_plan()
    assert plan["actual_raw_read_roles"] == (
        "gnss1_status", "gnss2_status", "gnss1_raw", "go2_body"
    )
    assert plan["trace_read_during_generation"] is False
    assert plan["compatibility_generated_imu_gnss_solver_eligible"] is False
    assert plan["common_solver_base_roles"] == (
        "imu_runtime_input", "gnss_runtime_input"
    )


def test_auxiliary_trace_audit_requires_exact_four_raw_opens(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    relatives = ["fix/g1.csv", "fix/g2.csv", "fix/raw.csv", "go2/body.txt"]
    for relative in relatives:
        path = raw / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")
    trace_reference = raw / BY2_TRACE_RELATIVE_PATH
    trace_reference.parent.mkdir(parents=True, exist_ok=True)
    trace_reference.write_text("offline only", encoding="utf-8")
    manifest = tmp_path / "CLEAN1R2R1_AUXILIARY_MANIFEST.json"
    manifest.write_text(json.dumps({
        "trace_open_count": None,
        "trace_open_audit_sealed": False,
        "actual_source_read_set": [
            {"relative_path": relative} for relative in relatives
        ],
    }), encoding="utf-8")
    trace = tmp_path / "open.raw"
    trace.write_text("".join(
        f'openat(AT_FDCWD, "{raw / relative}", O_RDONLY) = 3\n'
        for relative in relatives
    ), encoding="utf-8")
    audit = seal_auxiliary_file_open_audit(
        auxiliary_manifest=manifest,
        strace_path=trace,
        raw_root=raw,
        code_root=tmp_path,
    )
    assert audit["passed"] is True
    sealed = json.loads(manifest.read_text(encoding="utf-8"))
    assert sealed["trace_open_count"] == 0
    assert sealed["trace_open_audit_sealed"] is True


def test_method_order_is_exact_and_each_config_shares_common_base(tmp_path: Path) -> None:
    assert METHOD_ORDER == (
        "single_antenna_EKF",
        "basic_dual_yaw_EKF",
        "strong_dual_yaw_EKF",
        "LegSA_Paper_V1",
    )
    assert [name.split("_", 1)[0] for name in RUN_DIRECTORIES] == ["01", "02", "03", "04"]
    imu, gnss = tmp_path / "common.imu", tmp_path / "common.gnss"
    aux = {
        "raw_doppler": tmp_path / "raw.csv",
        "go2_roll_pitch": tmp_path / "att.csv",
        "go2_horizontal_velocity": tmp_path / "vel.csv",
    }
    for method in METHOD_ORDER:
        text = active_runtime_config(
            imu, gnss, tmp_path / method,
            method_id=method,
            auxiliary_paths=aux if method == "LegSA_Paper_V1" else {},
            run_id=method,
        )
        assert f'imupath: "{imu}"' in text
        assert f'gnsspath: "{gnss}"' in text
        if method == "LegSA_Paper_V1":
            assert f'raw_doppler_factor_path: "{aux["raw_doppler"]}"' in text
            assert "enable_raw_doppler: true" in text
            assert "enable_source_aware: true" in text
        else:
            assert 'raw_doppler_factor_path: ""' in text
            assert "enable_raw_doppler: false" in text
            assert "enable_source_aware: false" in text


def test_strong_runtime_contract_normalizes_equal_to_parity(tmp_path: Path) -> None:
    imu, gnss = tmp_path / "i", tmp_path / "g"
    parity = active_runtime_config(imu, gnss, tmp_path / "parity")
    formal = active_runtime_config(
        imu, gnss, tmp_path / "formal",
        method_id="strong_dual_yaw_EKF",
        run_id="03_strong_dual_yaw_EKF",
    )
    assert normalize_runtime_config(formal) == normalize_runtime_config(parity)


def test_parity_gate_is_fail_closed() -> None:
    passed = {
        "active_port_clean_final_v23_parity": True,
        "strong_equals_clean_final_v23": True,
        "terminal_status": "PASS_FINAL_V23_CLEAN_PARITY_ANCHOR",
        "trace_opened": False,
    }
    _assert_parity_gate(passed)
    for field in passed:
        broken = dict(passed)
        broken[field] = None
        with pytest.raises(Clean1R2R1FormalError):
            _assert_parity_gate(broken)


def test_four_method_source_binds_parity_commit_and_executable() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src/legsa_gins/paper_rebuild/clean1r2r1_formal.py"
    ).read_text(encoding="utf-8")
    assert 'parity.get("active_code_commit") != code_freeze_commit' in source
    assert 'parity.get("active_executable_sha256") != sha256_file(binary)' in source


def test_module_counters_close_yaw_actions_and_out_of_scope_counts() -> None:
    manifest = {
        "position_update_count": 10,
        "receiver_velocity_update_count": 10,
        "yaw_update_count": 10,
        "dual_yaw_update_count": 9,
        "yaw_NORMAL": 7,
        "yaw_DOWNWEIGHT": 2,
        "yaw_REJECT": 1,
        "raw_doppler_update_count": 3,
        "source_aware_evaluation_count": 4,
        "source_aware_weight_changed_count": 1,
        "go2_roll_pitch_update_count": 5,
        "go2_horizontal_velocity_update_count": 6,
        "selected_fgo_feedback_update_count": 0,
        "nine_factor_fgo_update_count": 0,
        "multi_state_qm_update_count": 0,
        "qa_fallback_count": 0,
        "contact_fk_update_count": 0,
    }
    counters = module_counters(manifest)
    assert counters["dual_yaw_accepted_count"] == 9
    assert counters["fgo_count"] == counters["qm_count"] == 0
    manifest["yaw_REJECT"] = 2
    with pytest.raises(Clean1R2R1FormalError, match="do not close"):
        module_counters(manifest)


def _sealed_runtime(root: Path) -> None:
    root.mkdir()
    rows = []
    for order, (method, directory) in enumerate(zip(METHOD_ORDER, RUN_DIRECTORIES), start=1):
        run = root / directory
        run.mkdir()
        for role, name in (
            ("nav", "KF_GINS_Navresult.nav"),
            ("std", "KF_GINS_STD.txt"),
            ("solver_manifest", "RUN_MANIFEST.json"),
            ("formal_manifest", "CLEAN1R2R1_FORMAL_RUN_MANIFEST.json"),
            ("runtime_config", "CLEAN1R2R1_RUNTIME_CONFIG.yaml"),
            ("update_trace", "PORT_GNSS_UPDATE_TRACE.csv"),
        ):
            path = run / name
            path.write_text(f"{method}:{role}\n", encoding="utf-8")
            rows.append({
                "method_order": order,
                "algorithm_id": method,
                "output_role": role,
                "relative_path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "frozen_before_any_evaluation": True,
            })
    with (root / "FOUR_METHOD_OUTPUT_HASHES.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    (root / "FOUR_METHOD_EXECUTION_REPORT.json").write_text(json.dumps({
        "all_outputs_sealed_before_evaluation": True,
        "trace_opened": False,
    }), encoding="utf-8")


def test_evaluation_gate_requires_all_outputs_sealed_and_unchanged(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    _sealed_runtime(runtime)
    assert len(validate_four_method_seal(runtime)) == 24
    changed = runtime / RUN_DIRECTORIES[2] / "KF_GINS_Navresult.nav"
    changed.write_text("mutated\n", encoding="utf-8")
    with pytest.raises(Clean1R2R1FormalError, match="changed before evaluation"):
        validate_four_method_seal(runtime)


def test_evaluation_gate_stops_before_any_trace_requirement(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "FOUR_METHOD_EXECUTION_REPORT.json").write_text(json.dumps({
        "all_outputs_sealed_before_evaluation": False,
        "trace_opened": False,
    }), encoding="utf-8")
    with pytest.raises(Clean1R2R1FormalError, match="not sealed"):
        validate_four_method_seal(runtime)
