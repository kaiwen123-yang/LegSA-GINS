import csv

from legsa_gins.da_repro.method_runner import run_da01_matrix


def _trace(path):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "yaw"])
        writer.writeheader()
        for idx in range(30):
            writer.writerow({"time": f"{float(idx):.1f}", "yaw": "90.0"})


def _series():
    return [
        {
            "time": float(idx),
            "east_m": 0.0,
            "north_m": 0.4,
            "up_m": 0.0,
            "baseline_length_m": 0.4,
            "baseline_heading_deg": 0.0,
        }
        for idx in range(30)
    ]


def test_status_diagnostic_is_never_full_backend(tmp_path):
    trace = tmp_path / "trace.csv"
    _trace(trace)
    provider = {
        "raw_ubx_rebuild_pass": True,
        "rinex_conversion_pass": True,
        "common_epoch_satellite_pass": True,
        "los_provider_pass": False,
        "dd_design_matrix_pass": False,
        "ambiguity_provider_pass": True,
        "physical_baseline_pass": True,
    }
    result = run_da01_matrix(runtime_root=tmp_path, status_series=_series(), trace_reference=trace, provider_capability=provider)
    assert result["full_backend_ready"] is False
    for row in result["row_results"]:
        assert row["method_mode"] == "status_diagnostic"
        assert row["terminal_status"] != "COMPLETED_EVALUABLE_FULL_BACKEND"
