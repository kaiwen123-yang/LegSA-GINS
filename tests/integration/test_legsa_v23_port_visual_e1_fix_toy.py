"""中文说明：运行 toy N4H4E1 STD/plot semantics 修正并检查 runtime 输出。"""

import json
import subprocess
from pathlib import Path

from scripts.audit_legsa_v23_port_visual_e1_fix import _make_toy


ROOT = Path(__file__).resolve().parents[2]


def test_toy_visual_e1_fix_generates_reports_and_figures(tmp_path):
    r3, r3a, r3b, r3c, n4h4e, dual, trace = _make_toy()
    out = tmp_path / "reports"
    figs = tmp_path / "figs"
    result = subprocess.run(
        [
            "python3",
            "scripts/experiments/run_legsa_v23_port_visual_e1_fix.py",
            "--n4h4e-root",
            str(n4h4e),
            "--r3-root",
            str(r3),
            "--r3a-root",
            str(r3a),
            "--r3b-root",
            str(r3b),
            "--r3c-root",
            str(r3c),
            "--dual-root",
            str(dual),
            "--trace-path",
            str(trace),
            "--report-output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--allow-run",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    std = json.loads((out / "STD_UNIT_AUDIT_REPORT.json").read_text(encoding="utf-8"))
    plot = json.loads((out / "PLOT_SEMANTICS_FIX_REPORT.json").read_text(encoding="utf-8"))
    visual = json.loads((out / "VISUAL_VALIDATION_E1_REPORT.json").read_text(encoding="utf-8"))
    assert std["port_attitude_std_unit"] == "rad"
    assert plot["vector_xy_line_removed"] is True
    assert plot["required_corrected_figures_generated"] is True
    assert visual["paper_performance_claim"] is False
    assert not [path for path in figs.rglob("*.png") if "pure" in path.name.lower() or "single" in path.name.lower()]
    assert (figs / "09_case_review" / "visual_case_review_e1.md").exists()
