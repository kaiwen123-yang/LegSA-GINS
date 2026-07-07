import csv

from scripts.experiments.run_paper10_da3_da01r1_satpos_los_dd_repair import _write_runtime_case


def test_clean_full_backend_manifest_flags(tmp_path):
    epoch_rows = [
        {
            "timestamp": 1.0,
            "body_yaw_deg": 90.0,
            "baseline_length_m": 0.355,
            "method_mode": "full_backend",
            "provider_layer_used": "raw_carrier_dd_los",
        }
    ]
    metrics = {"yaw_rmse_deg": 0.0, "aligned_count": 1, "trace_used_online": False}
    _write_runtime_case(tmp_path, epoch_rows, metrics, {"physical_gate_pass": True, "median_baseline_length_m": 0.355})
    manifest = tmp_path / "DA01_TEUNISSEN_CLAMBDA" / "C00_clean_normal" / "run_manifest.json"
    text = manifest.read_text(encoding="utf-8")
    assert '"method_mode": "full_backend"' in text
    assert '"provider_layer_used": "raw_carrier_dd_los"' in text
    assert '"status_diagnostic_used_as_full_backend": false' in text
    assert '"trace_used_online": false' in text
