import json
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


def test_da01_manifests_do_not_use_trace_online(tmp_path):
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
    run_da01_matrix(runtime_root=tmp_path, status_series=_series(), trace_reference=trace, provider_capability=provider)
    for manifest_path in (tmp_path / "DA01_TEUNISSEN_CLAMBDA").glob("*/run_manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["trace_used_online"] is False
        assert manifest["final_v23_output_solver_input"] is False
        assert manifest["LegSA_output_solver_input"] is False
