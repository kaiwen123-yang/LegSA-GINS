import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

# 中文说明：测试真实 trial blocker 边界审计。

def test_raw_doppler_real_trial_boundary_audit_on_toy_report(tmp_path: Path):
    report = tmp_path / "N5A_RAW_DOPPLER_FACTOR_TRIAL_REPORT.json"
    report.write_text(
        json.dumps(
            {
                "rawx_found": True,
                "ephemeris_available": True,
                "rtklib_found": True,
                "solver_enabled": False,
                "raw_doppler_update_count": 0,
                "blocking_issue": "provider_missing_sat_state_export",
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
                "paper_performance_claim": False,
            }
        ),
        encoding="utf-8",
    )
    path = ROOT / "scripts/audit_raw_doppler_real_trial_boundary.py"
    spec = importlib.util.spec_from_file_location("audit_raw_doppler_real_trial_boundary", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.audit_report(report)
    module.audit_static_boundaries()
