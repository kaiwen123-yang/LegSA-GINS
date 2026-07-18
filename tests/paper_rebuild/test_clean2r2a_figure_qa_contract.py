import csv
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean2r2a_plots import (
    Clean2R2APlotError,
    record_visual_figure_review,
)
from legsa_gins.paper_rebuild.manifest import sha256_file


ROOT = Path(__file__).resolve().parents[2]


def test_source_aware_panel_never_draws_a_false_reject_and_requires_visual_review() -> None:
    source = (ROOT / "src/legsa_gins/paper_rebuild/clean2r2a_plots.py").read_text(encoding="utf-8")
    assert 'axes[1].text(0.5, 0.5, "0 rejects"' in source
    assert 'if rejected:' in source
    assert 'if rejected else [0.0]' not in source
    assert "CLEAN2R2A1_FIGURE_MACHINE_QA.json" in source
    assert "CLEAN2R2A1_FIGURE_VISUAL_REVIEW.json" in source
    assert "record_visual_figure_review" in source
    assert 'decision.get("relative_path")' in source
    assert 'any_overlap = any(row["legend_or_label_overlap"]' in source
    assert '"passed": visual_passed' in source


def _review_fixture(tmp_path: Path, *, overlap: bool) -> tuple[Path, Path]:
    stage = tmp_path / "CLEAN2R2A1_RAW_DOPPLER_CANONICAL_PARITY_AND_CLEAN_ABLATION_RESUME"
    figures = stage / "10_DIAGNOSTIC_FIGURES"
    figures.mkdir(parents=True)
    manifest_rows = []
    decisions = []
    for index in range(1, 16):
        figure_id = f"F{index:02d}"
        png = figures / f"{figure_id}.png"
        png.write_bytes((figure_id.encode("ascii") * 500)[:1200])
        relative = png.relative_to(stage).as_posix()
        digest = sha256_file(png)
        manifest_rows.append({"figure_id": figure_id, "format": "PNG",
                              "relative_path": relative, "sha256": digest})
        decisions.append({
            "figure_id": figure_id, "relative_path": relative, "sha256": digest,
            "opened": True, "legend_or_label_overlap": overlap and index == 1,
            "curves_obscured": False, "long_labels_clipped": False,
            "misleading_real_scenario_wording": False,
            "action_labels_overlap_data": False, "passed": not (overlap and index == 1),
        })
    with (figures / "CLEAN2R2A1_FIGURE_MANIFEST.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0])); writer.writeheader(); writer.writerows(manifest_rows)
    (figures / "CLEAN2R2A1_FIGURE_MACHINE_QA.json").write_text(
        json.dumps({"passed": True}), encoding="utf-8",
    )
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"reviewer": "read-only-reviewer", "reviewed_at": "2026-07-18T00:00:00+08:00",
                                  "figures": decisions}), encoding="utf-8")
    return stage, review


def test_visual_review_is_decision_backed_and_fails_on_overlap(tmp_path: Path) -> None:
    stage, review = _review_fixture(tmp_path, overlap=False)
    assert record_visual_figure_review(stage_root=stage, review_json=review)["passed"] is True

    failed_stage, failed_review = _review_fixture(tmp_path / "failed", overlap=True)
    with pytest.raises(Clean2R2APlotError, match="readability failure"):
        record_visual_figure_review(stage_root=failed_stage, review_json=failed_review)
    payload = json.loads(
        (failed_stage / "10_DIAGNOSTIC_FIGURES/CLEAN2R2A1_FIGURE_RENDER_QA.json").read_text(encoding="utf-8")
    )
    assert payload["passed"] is False
