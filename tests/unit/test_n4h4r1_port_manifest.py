"""中文说明：检查 N4H4R1 PORT_MANIFEST 的禁用项和 source commit。"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "cpp/legsa_v23_port_core/PORT_MANIFEST.json"


def test_port_manifest_flags_and_source_commit():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["source_commit"] == "5a4471efd4fcfcdc31e258a677af354c652ff16f"
    assert manifest["parity_attempted"] is False
    for flag in [
        "final_v23_is_proposed",
        "final_v23_output_solver_input",
        "trace_solver_input",
        "raw_doppler",
        "go2_prior",
        "lsim_oim",
        "fgo",
        "performance_claim",
    ]:
        assert manifest[flag] is False
    assert manifest["copied_or_refactored_files"]

