import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "build" / "cpp" / "legsa_v23_port_core_demo"


def test_quality_state_toy_outputs_trace_schema(tmp_path):
    assert BIN.exists(), "build/cpp/legsa_v23_port_core_demo must be built before this test"
    out = tmp_path / "qm_toy"
    subprocess.run(
        [str(BIN), "--dry-run-quality-state-toy", "--output-dir", str(out)],
        cwd=ROOT,
        check=True,
    )
    trace_path = out / "QM_STATE_ACTION_TRACE.csv"
    manifest_path = out / "RUN_MANIFEST.json"
    assert trace_path.exists()
    assert manifest_path.exists()

    rows = list(csv.DictReader(trace_path.open(newline="", encoding="utf-8")))
    assert rows
    fields = set(rows[0].keys())
    for field in [
        "source_id",
        "previous_state",
        "state",
        "action",
        "action_alters_update",
        "r_scale_multiplier",
        "go2_readiness_metadata_available",
        "reason_codes",
        "trace_used_online",
        "final_v23_output_solver_input",
        "legsa_output_solver_input",
        "no_per_case_tuning",
    ]:
        assert field in fields

    states = {row["state"] for row in rows}
    actions = {row["action"] for row in rows}
    assert {"NORMAL", "DOWNWEIGHT", "REJECT", "HOLD", "RECOVERY", "FALLBACK"}.issubset(states)
    assert "fallback_partial_source_fusion" in actions
    assert "hold_source_finite_window" in actions
    assert any(row["go2_readiness_metadata_available"] == "1" for row in rows)
    assert all(row["trace_used_online"] == "0" for row in rows)
    assert all(row["final_v23_output_solver_input"] == "0" for row in rows)
    assert all(row["legsa_output_solver_input"] == "0" for row in rows)
    assert all(row["no_per_case_tuning"] == "1" for row in rows)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["multi_state_qm"] is True
    assert manifest["enable_multi_state_qm"] is True
    assert manifest["multi_state_qm_mode"] == "QM04_FULL"
    assert manifest["qm_trace_rows"] == len(rows)
    assert manifest["qm_trace_used_online"] is False
    assert manifest["qm_final_v23_output_solver_input"] is False
    assert manifest["qm_legsa_output_solver_input"] is False
