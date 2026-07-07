import json

from legsa_gins.da_repro.full_backend_classic_runner import apply_full_backend_case_policy
from scripts.experiments.run_paper10_da3_da01r2_full_backend_18classic import _write_runtime_case


def _base_rows(count=20):
    return [
        {
            "timestamp": float(idx) * 0.2,
            "rcv_tow": float(idx) * 0.2,
            "baseline_east_m": 0.0,
            "baseline_north_m": 0.355,
            "baseline_up_m": 0.0,
            "baseline_length_m": 0.355,
            "baseline_heading_deg": 0.0,
            "body_yaw_deg": 90.0,
            "num_dd": 5,
            "design_rank": 3,
            "design_condition_number": 2.0,
        }
        for idx in range(count)
    ]


def test_downsample_policy_changes_provider_rows_not_trace():
    rows, policy = apply_full_backend_case_policy(_base_rows(30), "C02_downsample_2Hz", nominal_length_m=0.355)
    assert len(rows) < 30
    assert policy["trace_modified"] is False
    assert all(row["method_mode"] == "full_backend" for row in rows)
    assert all(row["status_diagnostic_used_as_full_backend"] is False for row in rows)


def test_runtime_manifest_full_backend_flags(tmp_path):
    rows, policy = apply_full_backend_case_policy(_base_rows(5), "C00_clean_normal", nominal_length_m=0.355)
    metrics = {"yaw_rmse_deg": 1.0, "aligned_count": 5, "trace_used_online": False}
    _write_runtime_case(
        runtime_root=tmp_path,
        case_id="C00_clean_normal",
        epoch_rows=rows,
        metrics=metrics,
        baseline_summary={"median_baseline_length_m": 0.355, "baseline_physical_gate_pass": True},
        provider_summary={"usable_dd_epochs": 5},
        policy_report=policy,
        terminal_status="COMPLETED_EVALUABLE_FULL_BACKEND",
    )
    manifest = json.loads((tmp_path / "DA01_TEUNISSEN_CLAMBDA" / "C00_clean_normal" / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["method_mode"] == "full_backend"
    assert manifest["provider_layer_used"] == "raw_carrier_dd_los"
    assert manifest["status_diagnostic_used_as_full_backend"] is False
    assert manifest["trace_used_online"] is False
    assert manifest["old_aggregate_imported"] is False
