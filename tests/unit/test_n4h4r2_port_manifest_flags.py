"""中文说明：检查 R2 PORT_MANIFEST 禁用项和非 parity 状态。"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "cpp/legsa_v23_port_core/PORT_MANIFEST.json"


def test_n4h4r2_manifest_flags():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["phase"] == "N4H4R2"
    assert manifest["math_port_completed"] is True
    assert manifest["parity_attempted"] is False
    assert manifest["real_clean_replay_attempted"] is False
    for flag in [
        "final_v23_output_solver_input",
        "trace_solver_input",
        "output_only_correction",
        "bad_epoch_deletion_for_metric",
        "raw_doppler",
        "go2_prior",
        "lsim_oim",
        "fgo",
        "performance_claim",
    ]:
        assert manifest[flag] is False
