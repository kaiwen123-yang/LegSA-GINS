"""中文说明：运行 toy N4H4E visual validation，确认报告和 runtime 图像生成。"""

import json
import subprocess
from pathlib import Path

from scripts.audit_legsa_v23_port_visual_validation import _make_toy


ROOT = Path(__file__).resolve().parents[2]


def test_toy_visual_validation_runner_generates_reports_and_figures(tmp_path):
    r3, r3a, r3b, r3c, dual, trace = _make_toy()
    out = tmp_path / "out"
    figs = tmp_path / "figs"
    result = subprocess.run(
        [
            "python3",
            "scripts/experiments/run_legsa_v23_port_visual_validation.py",
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
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--trace-path",
            str(trace),
            "--allow-run",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((out / "VISUAL_VALIDATION_REPORT.json").read_text(encoding="utf-8"))
    manifest = json.loads((out / "FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
    assert report["paper_performance_claim"] is False
    assert report["no_outperform_final_v23_claim"] is True
    assert manifest["figure_count_total"] >= 30
    assert not [path for path in figs.rglob("*.png") if "pure" in path.name.lower() or "single" in path.name.lower()]
    assert (figs / "09_case_review" / "visual_case_review.md").exists()
